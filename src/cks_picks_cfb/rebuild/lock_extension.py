"""Extend the pinned 2026 rebuild source lock by one completed week (pure, I/O-free).

The 6A/6B rebuild stages read a few fields of the 2026 source lock: ``games`` (kickoff and
final points), ``post_week_cutoffs`` and ``research_2026_prediction_keys.completed_games``.
Adding a completed week means recording that week's finals and its post-week cutoff. Nothing
earlier may change: a different final score for an already-recorded game, a non-contiguous
week, or a cutoff before a final becomes available is an error, never a silent edit. The
base lock's own provenance fields stay untouched and are cited by hash.
"""

from __future__ import annotations

import copy
import hashlib
import math
from collections.abc import Collection, Mapping
from typing import Any

import pandas as pd

from cks_picks_cfb.ratings_lab.artifacts import canonical_json

AVAILABILITY_HOURS = 6
EXTENSION_KEY = "extends"


class LockExtensionError(ValueError):
    """The lock cannot be extended without changing something already recorded."""


def rows_sha256(rows: list[list[Any]]) -> str:
    """Hash of the lock's game rows in canonical JSON form (method recorded in the lock)."""
    return hashlib.sha256(canonical_json(rows)).hexdigest()


def extend_lock(
    base: Mapping[str, Any],
    *,
    base_sha256: str,
    finals: pd.DataFrame,
    new_cutoff: str,
    outcomes_ref: Mapping[str, Any],
    schedule: pd.DataFrame | None = None,
    schedule_ref: Mapping[str, Any] | None = None,
    accepted_kickoff_revisions: Collection[int] = (),
    append_week: int | None = None,
    expected_games: int | None = None,
) -> dict[str, Any]:
    """Return a new lock that adds the next post-week cutoff and the newly final games.

    When ``schedule`` (``game_id``, ``week``, ``kickoff_utc``) is given, every locked game
    must still agree with it. A kickoff that the provider revised is refused unless its
    game id is named in ``accepted_kickoff_revisions``; then the row takes the new kickoff
    and the old/new pair is recorded under ``extends.kickoff_revisions``. A changed week,
    or an acceptance for a game that did not change, is always an error.

    Explicit ``append_week`` mode instead adds a complete new schedule with an
    exact ``expected_games`` count. It supports chained extensions, preserves
    prior metadata and refuses all historical revisions, including waivers.
    """
    if append_week is not None:
        return _append_week(
            base,
            base_sha256=base_sha256,
            finals=finals,
            new_cutoff=new_cutoff,
            outcomes_ref=outcomes_ref,
            schedule=schedule,
            schedule_ref=schedule_ref,
            accepted_kickoff_revisions=accepted_kickoff_revisions,
            append_week=append_week,
            expected_games=expected_games,
        )
    if expected_games is not None:
        raise LockExtensionError("expected_games requires append_week")
    if EXTENSION_KEY in base:
        raise LockExtensionError("the base lock is already an extension")
    lock = copy.deepcopy(dict(base))
    columns = lock["games"]["columns"]
    position = {name: index for index, name in enumerate(columns)}
    needed = {"week", "game_id", "start_date", "home_points", "away_points"}
    if needed - set(position):
        raise LockExtensionError(
            f"lock games lack columns {sorted(needed - set(position))}"
        )
    if {"game_id", "home_points", "away_points"} - set(finals.columns):
        raise LockExtensionError("finals frame lacks game_id or points")
    final_points = {
        int(row.game_id): (int(row.home_points), int(row.away_points))
        for row in finals.itertuples(index=False)
        if pd.notna(row.home_points) and pd.notna(row.away_points)
    }

    limit = pd.Timestamp(new_cutoff)
    if limit.tzinfo is None:
        limit = limit.tz_localize("UTC")
    cutoffs = {int(w): str(c) for w, c in lock["post_week_cutoffs"].items()}
    last_week = max(cutoffs)
    if sorted(cutoffs) != list(range(last_week + 1)):
        raise LockExtensionError("base post-week cutoffs are not contiguous")
    next_week = last_week + 1
    if limit <= pd.Timestamp(cutoffs[last_week]):
        raise LockExtensionError(
            "the new cutoff must be after the last recorded cutoff"
        )

    rows = lock["games"]["rows"]
    revisions = _revise_kickoffs(
        rows, position, schedule, {int(g) for g in accepted_kickoff_revisions}
    )
    recorded_before = sum(1 for row in rows if row[position["home_points"]] is not None)
    newly_final: list[int] = []
    for row in rows:
        game_id = int(row[position["game_id"]])
        points = final_points.get(game_id)
        if points is None:
            continue
        current = (row[position["home_points"]], row[position["away_points"]])
        if current != (None, None):
            if (int(current[0]), int(current[1])) != points:
                raise LockExtensionError(
                    f"game {game_id}: recorded final {current} differs from {points}"
                )
            continue
        kickoff = pd.Timestamp(row[position["start_date"]])
        if kickoff.tzinfo is None:
            kickoff = kickoff.tz_localize("UTC")
        if kickoff + pd.Timedelta(hours=AVAILABILITY_HOURS) > limit:
            raise LockExtensionError(
                f"game {game_id} is final but not available at the new cutoff"
            )
        row[position["home_points"]], row[position["away_points"]] = points
        newly_final.append(game_id)
    if not newly_final:
        raise LockExtensionError("no newly final games: nothing to extend")
    completed = sum(1 for row in rows if row[position["home_points"]] is not None)

    cutoffs[next_week] = new_cutoff
    lock["post_week_cutoffs"] = {str(week): cutoffs[week] for week in sorted(cutoffs)}
    keys = dict(lock["research_2026_prediction_keys"])
    keys["completed_games"] = completed
    lock["research_2026_prediction_keys"] = keys
    lock[EXTENSION_KEY] = {
        "base_lock_sha256": base_sha256,
        "base_game_rows_sha256": base.get("game_rows_sha256"),
        "game_rows_sha256": rows_sha256(rows),
        "game_rows_sha256_method": "sha256(canonical_json(games.rows))",
        "added_post_week": next_week,
        "added_cutoff": new_cutoff,
        "completed_games_before": recorded_before,
        "completed_games_after": completed,
        "newly_final_game_ids": sorted(newly_final),
        "game_outcomes_ref": dict(outcomes_ref),
        "availability_hours": AVAILABILITY_HOURS,
    }
    if schedule is not None:
        lock[EXTENSION_KEY]["kickoff_revisions"] = revisions
        lock[EXTENSION_KEY]["schedule_ref"] = dict(schedule_ref or {})
    return lock


def _append_week(
    base: Mapping[str, Any],
    *,
    base_sha256: str,
    finals: pd.DataFrame,
    new_cutoff: str,
    outcomes_ref: Mapping[str, Any],
    schedule: pd.DataFrame | None,
    schedule_ref: Mapping[str, Any] | None,
    accepted_kickoff_revisions: Collection[int],
    append_week: int,
    expected_games: int | None,
) -> dict[str, Any]:
    """Append a complete new schedule without rewriting any historical row.

    This only constructs an in-memory lock. The operator must establish finals
    stability independently before using its output as an operational input.
    """
    if expected_games is None or expected_games <= 0:
        raise LockExtensionError("append_week requires positive expected_games")
    if schedule is None or not schedule_ref or not outcomes_ref:
        raise LockExtensionError("append_week requires schedule and input refs")
    if accepted_kickoff_revisions:
        raise LockExtensionError("append_week refuses historical kickoff revisions")
    columns = base["games"]["columns"]
    required = {
        "week",
        "game_id",
        "start_date",
        "home_team",
        "away_team",
        "home_points",
        "away_points",
    }
    if set(columns) != required or len(columns) != len(required):
        raise LockExtensionError("append_week requires the seven-column games schema")
    needed_schedule = {"game_id", "week", "kickoff_utc", "home_team", "away_team"}
    if needed_schedule - set(schedule.columns):
        raise LockExtensionError("append schedule lacks required columns")
    if {"game_id", "home_points", "away_points"} - set(finals.columns):
        raise LockExtensionError("append finals lack required columns")
    for name, frame in (("schedule", schedule), ("finals", finals)):
        if (
            frame["game_id"].isna().any()
            or frame["game_id"].astype(int).duplicated().any()
        ):
            raise LockExtensionError(f"duplicate or missing game_id in {name}")
        if "season" in frame and not frame["season"].eq(2026).all():
            raise LockExtensionError(f"append {name} must contain only season 2026")
    cutoffs = base["post_week_cutoffs"]
    weeks = sorted(int(w) for w in cutoffs)
    if not weeks or weeks != list(range(weeks[-1] + 1)):
        raise LockExtensionError("base post-week cutoffs are not contiguous")
    if append_week != weeks[-1] + 1:
        raise LockExtensionError("append_week must be the next contiguous week")
    limit = _append_timestamp(new_cutoff)
    if limit <= _append_timestamp(cutoffs[str(weeks[-1])]):
        raise LockExtensionError("new cutoff must be after the last recorded cutoff")

    rows = base["games"]["rows"]
    if any(len(row) != len(columns) for row in rows):
        raise LockExtensionError("historical row has an invalid column count")
    history = [dict(zip(columns, row)) for row in rows]
    old_ids = {int(row["game_id"]) for row in history}
    if len(old_ids) != len(history):
        raise LockExtensionError("duplicate historical game_id")
    if {int(row["week"]) for row in history} != set(weeks):
        raise LockExtensionError("historical rows do not match recorded weeks")
    if base["research_2026_prediction_keys"]["completed_games"] != len(history):
        raise LockExtensionError("historical completed count mismatch")
    previous = base.get(EXTENSION_KEY)
    if previous and previous.get("game_rows_sha256") != rows_sha256(rows):
        raise LockExtensionError("prior extension row checksum mismatch")
    schedule_by_id = schedule.set_index(schedule["game_id"].astype(int))
    finals_by_id = finals.set_index(finals["game_id"].astype(int))
    for row in history:
        game_id = int(row["game_id"])
        if game_id not in schedule_by_id.index or game_id not in finals_by_id.index:
            raise LockExtensionError(f"historical game {game_id} missing from inputs")
        game = schedule_by_id.loc[game_id]
        scores = finals_by_id.loc[game_id]
        if (
            int(row["week"]) != int(game["week"])
            or row["home_team"] != game["home_team"]
            or row["away_team"] != game["away_team"]
            or _append_timestamp(row["start_date"])
            != _append_timestamp(game["kickoff_utc"])
            or _append_points(row) != _append_points(scores)
        ):
            raise LockExtensionError(f"historical drift for game {game_id}")
    historical_source_ids = set(
        schedule.loc[schedule["week"].astype(int) < append_week, "game_id"].astype(int)
    )
    if historical_source_ids != old_ids:
        raise LockExtensionError("historical schedule population drift")
    additions = schedule.loc[schedule["week"].astype(int).eq(append_week)]
    if len(additions) != expected_games:
        raise LockExtensionError(
            f"append schedule count mismatch: {len(additions)} != {expected_games}"
        )
    new_rows = []
    for game in additions.sort_values("game_id").to_dict("records"):
        game_id = int(game["game_id"])
        if game_id in old_ids or game_id not in finals_by_id.index:
            raise LockExtensionError(f"new game {game_id} duplicate or missing final")
        kickoff = _append_timestamp(game["kickoff_utc"])
        if kickoff + pd.Timedelta(hours=AVAILABILITY_HOURS) > limit:
            raise LockExtensionError(f"game {game_id} final not available at cutoff")
        if pd.isna(game["home_team"]) or pd.isna(game["away_team"]):
            raise LockExtensionError(f"game {game_id} missing team identity")
        home, away = _append_points(finals_by_id.loc[game_id])
        new_row = {
            "week": append_week,
            "game_id": game_id,
            "start_date": kickoff.isoformat(),
            "home_team": game["home_team"],
            "away_team": game["away_team"],
            "home_points": home,
            "away_points": away,
        }
        new_rows.append([new_row[column] for column in columns])
    lock = copy.deepcopy(dict(base))
    lock["games"]["rows"].extend(new_rows)
    lock["post_week_cutoffs"][str(append_week)] = new_cutoff
    lock["research_2026_prediction_keys"]["completed_games"] = len(rows) + len(new_rows)
    lock[EXTENSION_KEY] = {
        "base_lock_sha256": base_sha256,
        "base_game_rows_sha256": rows_sha256(rows),
        "game_rows_sha256": rows_sha256(lock["games"]["rows"]),
        "game_rows_sha256_method": "sha256(canonical_json(games.rows))",
        "added_post_week": append_week,
        "added_cutoff": new_cutoff,
        "completed_games_before": len(rows),
        "completed_games_after": len(rows) + len(new_rows),
        "newly_final_game_ids": sorted(
            int(row["game_id"]) for row in additions.to_dict("records")
        ),
        "game_outcomes_ref": dict(outcomes_ref),
        "schedule_ref": dict(schedule_ref),
        "availability_hours": AVAILABILITY_HOURS,
        "kickoff_revisions": [],
    }
    if previous is not None:
        lock[EXTENSION_KEY]["previous_extension"] = copy.deepcopy(previous)
    return lock


def _append_timestamp(value: Any) -> pd.Timestamp:
    try:
        stamp = pd.Timestamp(value)
    except (TypeError, ValueError):
        raise LockExtensionError(
            "append timestamps must be valid and timezone-aware"
        ) from None
    if pd.isna(stamp) or stamp.tzinfo is None:
        raise LockExtensionError("append timestamps must be valid and timezone-aware")
    return stamp.tz_convert("UTC")


def _append_points(row: Mapping[str, Any] | pd.Series) -> tuple[int, int]:
    if "completed" in row:
        completed = row["completed"]
        if pd.isna(completed) or completed != True:  # noqa: E712
            raise LockExtensionError("game is not completed")
    points = []
    for name in ("home_points", "away_points"):
        try:
            value = float(row[name])
        except (TypeError, ValueError):
            raise LockExtensionError("missing or invalid final score") from None
        if not math.isfinite(value) or value < 0 or not value.is_integer():
            raise LockExtensionError("missing or invalid final score")
        points.append(int(value))
    return points[0], points[1]


def _utc(value: Any) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    return stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")


def _revise_kickoffs(
    rows: list[list[Any]],
    position: Mapping[str, int],
    schedule: pd.DataFrame | None,
    accepted: set[int],
) -> list[dict[str, Any]]:
    """Apply accepted kickoff revisions in place; refuse any other disagreement."""
    if schedule is None:
        if accepted:
            raise LockExtensionError("kickoff revisions need the schedule to check")
        return []
    if {"game_id", "week", "kickoff_utc"} - set(schedule.columns):
        raise LockExtensionError("schedule frame lacks game_id, week or kickoff_utc")
    current = schedule.set_index(schedule["game_id"].astype(int))
    revisions: list[dict[str, Any]] = []
    for row in rows:
        game_id = int(row[position["game_id"]])
        if game_id not in current.index:
            raise LockExtensionError(
                f"locked game {game_id} is missing from the schedule"
            )
        game = current.loc[game_id]
        if int(game["week"]) != int(row[position["week"]]):
            raise LockExtensionError(f"game {game_id}: the provider changed the week")
        old = _utc(row[position["start_date"]])
        new = _utc(game["kickoff_utc"])
        if old == new:
            continue
        if game_id not in accepted:
            raise LockExtensionError(
                f"game {game_id}: kickoff {old.isoformat()} was revised to "
                f"{new.isoformat()} and the revision is not accepted"
            )
        row[position["start_date"]] = new.strftime("%Y-%m-%dT%H:%M:%SZ")
        revisions.append(
            {
                "game_id": game_id,
                "old_start_date": old.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "new_start_date": row[position["start_date"]],
            }
        )
    stale = accepted - {r["game_id"] for r in revisions}
    if stale:
        raise LockExtensionError(
            f"accepted revisions without a change: {sorted(stale)}"
        )
    return revisions
