#!/usr/bin/env python3
"""Refresh the score-reconciliation exceptions after a week's finals, only when verified.

Prepare requires every team-game's scoring events to sum to its final score unless the
team-game is declared in the pinned exceptions file. This script finds the completed
week's mismatches and declares each one **only** when the final score equals the sum of
that side's certified quarter line scores (the final is then proven correct and the
play-by-play stream is the incomplete party). It then re-pins the exceptions file's
SHA-256 in the revision manifest. It fails closed, writing nothing, when:

* any mismatch in the completed week fails the line-score check;
* an exception for an earlier week changed or is no longer needed;
* a mismatch appears in an earlier week that has no exception.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "src"))

from cks_picks_cfb.preseason_features import canonical_team  # noqa: E402
from cks_picks_cfb.ratings.drive_corroboration import _line_scores  # noqa: E402
from cks_picks_cfb.season.inputs import (  # noqa: E402
    frame,
    score_reconciliation_problems,
)

Key = tuple[int, str]
_DIFFERS = re.compile(r"score reconciliation differs: game (\d+), team (.+)")


class RefreshError(ValueError):
    """Carries every blocking problem so the report names all of them."""

    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def find_mismatches(
    completed: pd.DataFrame,
    finals: pd.DataFrame,
    events: pd.DataFrame,
) -> dict[Key, dict[str, Any]]:
    """Every team-game whose scoring events differ from its final, with its evidence.

    ``completed`` carries canonical ``home_team``/``away_team``, ``week`` and the
    optional ``home_line_scores``/``away_line_scores``; ``events`` carries canonical
    ``team``. Reuses prepare's own reconciliation so both agree on what a mismatch is.
    """
    problems = score_reconciliation_problems(completed, finals, events, {})
    keys = [
        (int(m.group(1)), m.group(2))
        for m in map(_DIFFERS.fullmatch, problems)
        if m is not None
    ]
    sums = (
        events.assign(score_increment=pd.to_numeric(events.score_increment))
        .groupby(["game_id", "team"])
        .score_increment.sum()
    )
    scores = finals.set_index("game_id")
    games = completed.set_index("game_id")
    out: dict[Key, dict[str, Any]] = {}
    for game_id, team in keys:
        game = games.loc[game_id]
        home = team == game.home_team
        lines = _line_scores(
            game.get("home_line_scores" if home else "away_line_scores")
        )
        flags = (
            sorted(
                set(
                    events.loc[
                        events.game_id.eq(game_id)
                        & events.team.eq(team)
                        & events.quality_reason.notna(),
                        "quality_reason",
                    ].astype(str)
                )
            )
            if "quality_reason" in events
            else []
        )
        out[(game_id, team)] = {
            "week": int(game.week),
            "final": float(
                scores.loc[game_id, "home_points" if home else "away_points"]
            ),
            "events_sum": float(sums.get((game_id, team), 0.0)),
            "line_scores": lines,
            "stream_flags": flags,
        }
    return out


def _points(value: float) -> str:
    return str(int(value))


def plan_refresh(
    mismatches: dict[Key, dict[str, Any]],
    existing: dict[Key, str],
    game_weeks: dict[int, int],
    completed_week: int,
) -> tuple[list[dict[str, Any]], dict[Key, str]]:
    """Return ``(added, entries)``; raise ``RefreshError`` naming every blocker.

    ``entries`` is the full new exceptions mapping: the unchanged earlier-week
    exceptions plus one verified, templated entry per completed-week mismatch (an
    existing completed-week entry keeps its reason so a rerun changes nothing).
    """
    problems: list[str] = []
    earlier_existing = {}
    for key, reason in existing.items():
        week = game_weeks.get(key[0])
        if week is None:
            problems.append(f"existing exception for unknown game {key[0]}, {key[1]}")
        elif week < completed_week:
            earlier_existing[key] = reason
        elif week > completed_week:
            problems.append(
                f"existing exception beyond completed week: game {key[0]}, team {key[1]}"
            )
    earlier = {k for k, v in mismatches.items() if v["week"] < completed_week}
    problems += [
        f"new mismatch outside completed week {completed_week}: game {g}, team {t}"
        for g, t in sorted(earlier - set(earlier_existing))
    ] + [
        f"earlier-week exception no longer needed: game {g}, team {t}"
        for g, t in sorted(set(earlier_existing) - earlier)
    ]
    added: list[dict[str, Any]] = []
    entries = dict(earlier_existing)
    for key in sorted(k for k, v in mismatches.items() if v["week"] == completed_week):
        info = mismatches[key]
        lines = info["line_scores"]
        if not lines or sum(lines) != info["final"]:
            problems.append(
                f"unverified mismatch (final {_points(info['final'])} vs line scores "
                f"{[_points(x) for x in lines] or 'missing'}): game {key[0]}, team {key[1]}"
            )
            continue
        flag = ", ".join(info["stream_flags"]) or "no stream flag recorded"
        reason = existing.get(key) or (
            f"Week {completed_week} scoring events sum to {_points(info['events_sum'])}, "
            f"final is {_points(info['final'])} (equals the quarter line scores); "
            f"play-by-play score stream flagged {flag}"
        )
        entries[key] = reason
        added.append(
            {
                "game_id": key[0],
                "team": key[1],
                "reason": reason,
                "final": info["final"],
                "line_scores": lines,
                "line_score_sum": sum(lines),
                "events_sum": info["events_sum"],
                "stream_flags": info["stream_flags"],
            }
        )
    if problems:
        raise RefreshError(problems)
    return added, entries


def render_exceptions(entries: dict[Key, str]) -> bytes:
    rows = [
        {"game_id": g, "team": t, "reason": r} for (g, t), r in sorted(entries.items())
    ]
    return (json.dumps(rows, indent=2) + "\n").encode()


def pin_manifest(manifest: dict, uri: str, exceptions_raw: bytes) -> dict:
    return {
        **manifest,
        "score_reconciliation_exceptions": {
            "uri": uri,
            "sha256": hashlib.sha256(exceptions_raw).hexdigest(),
        },
    }


def read_existing(path: Path) -> dict[Key, str]:
    """Parse the exceptions file with the same schema checks prepare applies."""
    if not path.exists():
        return {}
    entries = json.loads(path.read_bytes())
    out: dict[Key, str] = {}
    for entry in entries if isinstance(entries, list) else [None]:
        if (
            not isinstance(entry, dict)
            or set(entry) != {"game_id", "team", "reason"}
            or not isinstance(entry["game_id"], int)
        ):
            raise RefreshError(["exceptions file entry requires game_id, team, reason"])
        key = (entry["game_id"], canonical_team(entry["team"]))
        if key in out:
            raise RefreshError([f"duplicate exception: game {key[0]}, team {key[1]}"])
        out[key] = entry["reason"]
    return out


def load_completed(reader, revision: dict, completed_week: int):
    """Completed schedule, finals and scoring events, built as prepare builds them."""
    from cks_picks_cfb.ratings.possession_measurements import build_measurements

    r = revision["inputs"]
    schedule = frame(reader, r["schedule"])
    if "cancelled" in schedule:
        schedule = schedule[~schedule.cancelled.astype(bool)]
    completed = schedule[schedule.week.le(completed_week)].copy()
    for name in ("home_team", "away_team"):
        completed[name] = completed[name].map(canonical_team)
    ids = set(completed.game_id.astype(int))
    finals = frame(reader, r["finals"])
    finals = finals[finals.season.eq(2026) & finals.game_id.isin(ids)].copy()
    if set(finals.game_id.astype(int)) != ids:
        raise RefreshError(["every completed game requires a final score"])
    if "scoring_events" in r:
        events = frame(reader, r["scoring_events"])
    else:
        byplay = frame(reader, r["byplay"])
        byplay = byplay[byplay.season.eq(2026) & byplay.game_id.isin(ids)].copy()
        for name in ("offense", "defense"):
            if name in byplay:
                byplay[name] = byplay[name].map(canonical_team)
        population = completed.assign(
            forecast_eligible=True,
            schedule_completed=True,
            outcome_valid=True,
            measurement_usable=True,
        )
        events = build_measurements(
            byplay=byplay,
            population=population,
            outcomes=finals,
            scope="season_2026",
            play_identity=revision.get("play_identity", "byplay_v1"),
        ).scoring_events
    events = events[events.season.eq(2026) & events.game_id.isin(ids)].copy()
    events["team"] = events.team.map(canonical_team)
    return completed, finals, events


def refresh(
    *,
    reader,
    revision_path: Path,
    exceptions_path: Path,
    completed_week: int,
    dry_run: bool,
) -> dict[str, Any]:
    revision = json.loads(revision_path.read_bytes())
    completed, finals, events = load_completed(reader, revision, completed_week)
    mismatches = find_mismatches(completed, finals, events)
    game_weeks = dict(zip(completed.game_id.astype(int), completed.week.astype(int)))
    added, entries = plan_refresh(
        mismatches, read_existing(exceptions_path), game_weeks, completed_week
    )
    raw = render_exceptions(entries)
    changed = not exceptions_path.exists() or exceptions_path.read_bytes() != raw
    try:
        uri = str(exceptions_path.resolve().relative_to(REPOSITORY))
    except ValueError:
        uri = str(exceptions_path)
    if not dry_run:
        if changed:
            exceptions_path.write_bytes(raw)
        pinned = pin_manifest(revision, uri, raw)
        if pinned != revision:
            revision_path.write_text(json.dumps(pinned, indent=2) + "\n")
    return {
        "status": "ok",
        "completed_week": completed_week,
        "dry_run": dry_run,
        "exceptions_changed": changed,
        "exceptions_total": len(entries),
        "exceptions_sha256": hashlib.sha256(raw).hexdigest(),
        "added": added,
        "errors": [],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument(
        "--environment", choices=("preview", "production"), required=True
    )
    parser.add_argument("--revision-manifest", type=Path, required=True)
    parser.add_argument("--exceptions", type=Path, required=True)
    parser.add_argument("--completed-week", type=int, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.season != 2026:
        parser.error("only season 2026 is supported")
    from cks_picks_cfb.data.storage import get_storage

    try:
        report = refresh(
            reader=get_storage(environment=args.environment),
            revision_path=args.revision_manifest,
            exceptions_path=args.exceptions,
            completed_week=args.completed_week,
            dry_run=args.dry_run,
        )
        code = 0
    except RefreshError as error:
        report = {
            "status": "failed",
            "completed_week": args.completed_week,
            "dry_run": args.dry_run,
            "added": [],
            "errors": error.problems,
        }
        code = 1
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    summary = f"{report['status']}: {len(report['added'])} added"
    print(summary + "".join(f"\n  {p}" for p in report["errors"]))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
