"""Forward (live) feature rows for the week after the last replayed week.

Mirrors what the 6B reconstruction does for a replayed week, with the real time as the
forecast cutoff: earlier-only offsets from the admitted historical ledger and the 2026
scoring events, the team states at the last post-week cutoff, and only games that have not
kicked off at ``as_of``. Games already played are never given a feature row and never get
an earlier timestamp; they are listed so a display-only run can say so.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from cks_picks_cfb.rebuild.errors import GateError
from cks_picks_cfb.rebuild.successor_sources import (
    lock_schedule,
    rebuild_run,
    replay_run,
)


@dataclass(frozen=True)
class LiveWeek:
    features: pd.DataFrame
    state_refs: dict[int, str]
    omitted_kicked_off_game_ids: list[int]
    as_of: str
    evidence_games: int


def kicked_off_game_ids(schedule: pd.DataFrame, week: int, as_of: str) -> list[int]:
    """Games of ``week`` whose kickoff is at or before ``as_of`` (they cannot be forecast)."""
    cutoff = _utc(as_of)
    slate = schedule[schedule["week"].astype(int).eq(week)]
    kickoff = pd.to_datetime(slate["kickoff_utc"], utc=True)
    return sorted(int(g) for g in slate.loc[kickoff.le(cutoff), "game_id"])


def _utc(value: str) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        raise GateError("the live forecast as_of must be timezone-aware")
    return stamp.tz_convert("UTC")


def live_week_features(
    storage: Any,
    lock: dict[str, Any],
    *,
    as_of: str,
    current_teams: pd.DataFrame,
) -> LiveWeek:
    """Feature rows for the lock's active week, for games that kick off after ``as_of``."""
    from cks_picks_cfb.data.data_first_possession_v1 import build_population
    from cks_picks_cfb.forecast.live import (
        DEVELOPMENT_SEASONS,
        build_live_application_frame,
    )
    from cks_picks_cfb.forecast.offsets import build_offsets

    week = int(lock["active_week"]["week"])
    if "live_week" not in lock.get("corrected_lineage", {}):
        raise GateError("the lock names no live week")
    cutoff = _utc(as_of)
    if cutoff > pd.Timestamp.now(tz="UTC"):
        raise GateError("the live forecast as_of is in the future")
    schedule = lock_schedule(storage, lock)
    run_6a, run_6b = rebuild_run(storage, lock), replay_run(storage, lock)
    population = build_population(
        run_6a.frame("eligibility/population_raw.parquet"), scope="historical"
    )
    events = pd.concat(
        [
            run_6a.frame("comparison/admitted_events.parquet"),
            run_6b.frame("scoring_events_2026/events.parquet"),
        ],
        ignore_index=True,
    )
    kickoff = pd.to_datetime(schedule["kickoff_utc"], utc=True)
    earlier = schedule[schedule["week"].lt(week) & kickoff.lt(cutoff)].assign(
        forecast_eligible=True,
        schedule_completed=True,
        outcome_valid=True,
        measurement_usable=True,
    )
    target = schedule[schedule["week"].eq(week)].assign(
        forecast_eligible=True,
        schedule_completed=False,
        outcome_valid=False,
        measurement_usable=False,
    )
    computation = build_offsets(
        pd.concat([population, earlier, target], ignore_index=True, sort=False),
        events,
        development_seasons=DEVELOPMENT_SEASONS + (2026,),
        equivalent_games=4,
    )
    usable = computation.team_games[
        computation.team_games.season.eq(2026) & computation.team_games.usable
    ]
    if pd.to_datetime(usable["kickoff_utc"], utc=True).ge(cutoff).any():
        raise GateError("usable offset evidence kicked off at or after as_of")
    offsets = computation.offsets[
        computation.offsets["season"].eq(2026) & computation.offsets["week"].eq(week)
    ].copy()
    completed = schedule[
        schedule["week"].lt(week)
        & kickoff.lt(cutoff)
        & schedule["home_points"].notna()
        & schedule["away_points"].notna()
    ].assign(schedule_completed=True, outcome_valid=True)
    states = current_teams.copy()
    states["game_id"] = 0
    features, refs = build_live_application_frame(
        schedule, completed, states, offsets, as_of=as_of, target_week=week
    )
    omitted = kicked_off_game_ids(schedule, week, as_of)
    in_week = int(schedule["week"].eq(week).sum())
    if len(features) + len(omitted) != in_week:
        raise GateError(
            f"live week {week}: {len(features)} forecast + {len(omitted)} kicked off != {in_week}"
        )
    if set(features["game_id"].astype(int)) & set(omitted):
        raise GateError("a kicked-off game received a live feature row")
    return LiveWeek(
        features,
        refs,
        omitted,
        str(cutoff.isoformat()),
        int(usable["game_id"].nunique()),
    )
