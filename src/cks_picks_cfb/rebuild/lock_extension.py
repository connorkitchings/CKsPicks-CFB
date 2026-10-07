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
from collections.abc import Mapping
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
) -> dict[str, Any]:
    """Return a new lock that adds the next post-week cutoff and the newly final games."""
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
    return lock
