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
) -> dict[str, Any]:
    """Return a new lock that adds the next post-week cutoff and the newly final games.

    When ``schedule`` (``game_id``, ``week``, ``kickoff_utc``) is given, every locked game
    must still agree with it. A kickoff that the provider revised is refused unless its
    game id is named in ``accepted_kickoff_revisions``; then the row takes the new kickoff
    and the old/new pair is recorded under ``extends.kickoff_revisions``. A changed week,
    or an acceptance for a game that did not change, is always an error.
    """
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
