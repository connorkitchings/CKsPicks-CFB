"""Build a market-only revision manifest from a certified source manifest.

Mid-week line refresh: reuses every certified football input, completed-week
cutoff and score exception, and replaces only the cumulative market quotes, the
target-week pre-week cutoff and the revision identity. Never queries a provider;
it reads captures already stored in the database.

Usage: python -m scripts.pipeline.build_market_revision --from-manifest <src> \
    --to-manifest <dst> --revision-id <id> --cutoff <ISO-8601 UTC> --target-week <N> \
    [--schedule-ref <games ref key>]

``--target-week`` must be the upcoming (highest) week in the source manifest.

``--schedule-ref`` (Monday kickoff-time refresh) names a freshly built ``games``
Silver ref. It replaces the ``schedule`` and ``venue_games`` pins together, and
only when the game set is unchanged: the same game IDs, weeks and teams, with
kickoff times moving only for the target week and later. Any added, cancelled or
moved game stops the build with the game list.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from cks_picks_cfb.data.catalog import register_dataset_version
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.season.inputs import frame
from cks_picks_cfb.season.manifest import validate_revision
from scripts.pipeline.build_season_revision import (
    build_market_quotes,
    season_market_capture_ids,
)
from scripts.pipeline.build_week_market_snapshot import market_captures

SEASON = 2026


def parse_cutoff(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("--cutoff must include a timezone, e.g. 2026-10-20T16:00:00Z")
    return parsed


def check_target(old: dict[str, Any], target_week: str, cutoff: str) -> None:
    """Refuse a target week that is not the upcoming one or a cutoff moved back."""
    cutoffs = old["pre_week_cutoffs"]
    if target_week not in cutoffs:
        raise ValueError(f"Week {target_week} is not in the source pre_week_cutoffs")
    upcoming = max(cutoffs, key=int)
    if target_week != upcoming:
        raise ValueError(
            f"--target-week {target_week} is not the source manifest's upcoming "
            f"week {upcoming}; a refresh may only move the upcoming week's cutoff"
        )
    if parse_cutoff(cutoff) < parse_cutoff(cutoffs[target_week]):
        raise ValueError(
            f"Week {target_week} cutoff {cutoff} is earlier than the source "
            f"manifest's {cutoffs[target_week]}; a refresh never moves it back"
        )


def _kickoff_column(games: pd.DataFrame) -> str:
    return "start_date" if "start_date" in games.columns else "kickoff_utc"


def _differs(left: pd.Series, right: pd.Series) -> pd.Series:
    """Element-wise inequality that treats two missing values as equal."""
    return left.ne(right) & ~(left.isna() & right.isna())


def check_game_set_unchanged(
    old: pd.DataFrame, new: pd.DataFrame, *, target_week: int
) -> list[Any]:
    """Refuse a refreshed schedule that adds, cancels or moves a game.

    Model-relevant fields stop the run: the game set, and each shared game's week,
    teams and ``neutral_site`` (when both frames carry it). Kickoff time and the
    display-only columns (venue, venue id, attendance, kickoff-time flag, notes and
    similar) may differ in any week. Returns the sorted IDs of games before
    ``target_week`` whose kickoff changed, for reporting and the re-check in
    ``kickoff_outcome_moves``. Raises ``ValueError`` naming game IDs only.
    """
    old_ids, new_ids = set(old["game_id"]), set(new["game_id"])
    problems = []
    if added := sorted(new_ids - old_ids, key=str):
        problems.append(f"added games {added}")
    if cancelled := sorted(old_ids - new_ids, key=str):
        problems.append(f"cancelled games {cancelled}")
    shared = old[old["game_id"].isin(new_ids)].set_index("game_id")
    fresh = new[new["game_id"].isin(old_ids)].set_index("game_id").loc[shared.index]
    model_columns = ["week", "home_team", "away_team"] + [
        c for c in ("neutral_site",) if c in shared and c in fresh
    ]
    moved = pd.concat(
        [_differs(shared[c], fresh[c]) for c in model_columns], axis=1
    ).any(axis=1)
    if moved.any():
        problems.append(
            "moved games (week, teams or neutral_site) "
            f"{sorted(shared.index[moved], key=str)}"
        )
    if problems:
        raise ValueError(
            "the refreshed schedule changes more than kickoff time and display "
            "fields: " + "; ".join(problems)
        )
    retimed = pd.to_datetime(shared[_kickoff_column(old)], utc=True).ne(
        pd.to_datetime(fresh[_kickoff_column(new)], utc=True)
    )
    return sorted(
        shared.index[retimed & (shared["week"].astype(int) < target_week)], key=str
    )


def kickoff_outcome_moves(
    old: pd.DataFrame,
    new: pd.DataFrame,
    *,
    quotes: pd.DataFrame,
    cutoffs: dict[str, str],
    target_week: int,
) -> list[Any]:
    """IDs of games whose corrected kickoff would move a grade or cutoff outcome.

    Re-runs, on the old and the new schedule, the three kickoff-dependent rules
    and returns the games whose outcome differs:

    * grading eligibility: a retained quote counts for a game of a week before
      ``target_week`` only if captured strictly before kickoff
      (``season/grading.py``); a game moves when a quote's side of kickoff flips;
    * a week's pre-week cutoff must precede that week's first kickoff;
    * a week's cutoff must be at least six hours after every earlier kickoff
      (``season/prepare.py``).

    ``quotes`` needs ``game_id`` and ``captured_at``; ``cutoffs`` maps week to the
    manifest's cutoff, with ``target_week`` already holding the refreshed value.
    """
    column = _kickoff_column(old)
    kick_old = pd.to_datetime(old.set_index("game_id")[column], utc=True)
    kick_new = pd.to_datetime(new.set_index("game_id")[_kickoff_column(new)], utc=True)
    weeks = new.set_index("game_id")["week"].astype(int)
    moved: set[Any] = set()

    captured = pd.to_datetime(quotes["captured_at"], utc=True)
    for game_id, stamp in zip(quotes["game_id"], captured, strict=True):
        if game_id in weeks.index and weeks[game_id] < target_week:
            if (stamp < kick_old[game_id]) != (stamp < kick_new[game_id]):
                moved.add(game_id)

    margin = pd.Timedelta(hours=6)
    for week_text, cutoff_text in cutoffs.items():
        week, cutoff = int(week_text), pd.Timestamp(cutoff_text).tz_convert("UTC")
        ids = weeks.index

        def offenders(kick: pd.Series, week: int = week, cutoff: pd.Timestamp = cutoff):
            late = {g for g in ids[weeks == week] if kick[g] <= cutoff}
            unsettled = {g for g in ids[weeks < week] if kick[g] + margin > cutoff}
            return late | unsettled

        moved |= offenders(kick_old) ^ offenders(kick_new)
    return sorted(moved, key=str)


def derive_manifest(
    old: dict[str, Any],
    *,
    revision_id: str,
    captured_at: str,
    target_week: str,
    cutoff: str,
    quotes_input: dict[str, str] | None = None,
    historical_lines: dict[str, str] | None = None,
    schedule_input: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Return ``old`` with only market identity changed; assert nothing else moved.

    ``quotes_input`` replaces the cumulative quotes; ``historical_lines`` pins the
    explicit retrospective CFBD fallback input; ``schedule_input`` replaces the
    ``schedule`` and ``venue_games`` pins together (both must name the same Silver
    ``games`` version in the source). Each is optional.
    """
    check_target(old, target_week, cutoff)
    new = copy.deepcopy(old)
    new["revision_id"] = revision_id
    market_inputs = {}
    if quotes_input is not None:
        market_inputs["market_quotes"] = quotes_input
    if historical_lines is not None:
        market_inputs["historical_lines"] = historical_lines
    if schedule_input is not None:
        if old["inputs"]["schedule"] != old["inputs"]["venue_games"]:
            raise ValueError("schedule and venue_games pins differ in the source")
        market_inputs["schedule"] = schedule_input
        market_inputs["venue_games"] = schedule_input
    new["inputs"].update(market_inputs)
    new["captured_at"] = captured_at
    new["pre_week_cutoffs"][target_week] = cutoff

    def without(mapping: dict[str, Any], key: str) -> dict[str, Any]:
        return {k: v for k, v in mapping.items() if k != key}

    def football(inputs: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in inputs.items() if k not in market_inputs}

    if football(new["inputs"]) != football(old["inputs"]):
        raise ValueError("football inputs differ from the source manifest")
    if new["post_week_cutoffs"] != old["post_week_cutoffs"]:
        raise ValueError("post-week cutoffs differ from the source manifest")
    if new["score_reconciliation_exceptions"] != old["score_reconciliation_exceptions"]:
        raise ValueError("score exceptions differ from the source manifest")
    if without(new["pre_week_cutoffs"], target_week) != without(
        old["pre_week_cutoffs"], target_week
    ):
        raise ValueError(
            "earlier-week pre-week cutoffs differ from the source manifest"
        )
    validate_revision(new)
    return new


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-manifest", type=Path, required=True)
    parser.add_argument("--to-manifest", type=Path, required=True)
    parser.add_argument("--revision-id", required=True)
    parser.add_argument(
        "--cutoff", required=True, help="ISO-8601 UTC, last capture + ~5 min"
    )
    parser.add_argument(
        "--target-week",
        type=int,
        required=True,
        help="Upcoming week being refreshed; must be the highest week in the source",
    )
    parser.add_argument("--environment", default="preview")
    parser.add_argument(
        "--schedule-ref",
        help="Storage key of a freshly built games Silver ref (kickoff-time refresh)",
    )
    args = parser.parse_args(argv)

    if args.to_manifest.exists():
        raise SystemExit(f"Refusing to overwrite {args.to_manifest}")
    cutoff = parse_cutoff(args.cutoff)
    database_url = os.environ["DATABASE_URL"]
    old = json.loads(args.from_manifest.read_text())
    try:
        check_target(old, str(args.target_week), args.cutoff)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    store = get_storage(environment=args.environment)
    games = frame(store, old["inputs"]["schedule"])
    target_week = args.target_week
    schedule_input = None
    if args.schedule_ref:
        fresh_ref = json.loads(store.read_bytes(args.schedule_ref).decode())
        schedule_input = {"uri": fresh_ref["uri"], "sha256": fresh_ref["content_sha"]}
        fresh = frame(store, schedule_input)
        try:
            retimed = check_game_set_unchanged(games, fresh, target_week=target_week)
            if retimed:
                print(
                    f"Kickoff changed for {len(retimed)} completed-week games: {retimed}"
                )
            cutoffs = {**old["pre_week_cutoffs"], str(target_week): args.cutoff}
            if shifted := kickoff_outcome_moves(
                games,
                fresh,
                quotes=frame(store, old["inputs"]["market_quotes"]),
                cutoffs=cutoffs,
                target_week=target_week,
            ):
                raise ValueError(
                    "a corrected kickoff would move a grading-eligibility or "
                    f"pre-week-cutoff outcome for games {shifted}"
                )
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        games = fresh
    if games.loc[(games.season == SEASON) & (games.week == target_week)].empty:
        raise SystemExit(f"Week {target_week} has no games in the schedule")

    captures = market_captures(
        database_url, season_market_capture_ids(database_url, SEASON, cutoff)
    )
    last_capture = max(x.captured_at for x in captures)
    if last_capture > cutoff:
        raise SystemExit("A capture is later than --cutoff")
    code_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    ref, quotes_manifest = build_market_quotes(
        store, store, captures=captures, games=games, code_sha=code_sha
    )
    new = derive_manifest(
        old,
        revision_id=args.revision_id,
        quotes_input={"uri": ref.uri, "sha256": ref.content_sha},
        captured_at=last_capture.isoformat().replace("+00:00", "Z"),
        target_week=str(target_week),
        cutoff=cutoff.isoformat().replace("+00:00", "Z"),
        schedule_input=schedule_input,
    )
    register_dataset_version(database_url, ref, quotes_manifest)
    args.to_manifest.write_text(json.dumps(new, indent=2) + "\n")
    print(
        f"Wrote {args.to_manifest}: only quotes, Week {target_week} cutoff and revision "
        "identity changed. No provider calls."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
