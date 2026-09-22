from __future__ import annotations

import pandas as pd
import pytest

from cks_picks_cfb.forecast.live_sources import (
    LiveSourceError,
    _validate_schedule_matches_population,
    _week4_gate,
)


def _week4_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    schedule = pd.DataFrame(
        [
            {
                "season": 2026,
                "week": 4,
                "game_id": 401,
                "kickoff_utc": "2026-09-24T16:00:00Z",
                "home_team": "Home A",
                "away_team": "Away A",
            },
            {
                "season": 2026,
                "week": 4,
                "game_id": 402,
                "kickoff_utc": "2026-09-25T16:00:00Z",
                "home_team": "Home B",
                "away_team": "Away B",
            },
        ]
    )
    population = schedule.assign(schedule_completed=True, outcome_valid=True)
    return schedule, population


def test_week4_gate_requires_complete_reconciled_finals() -> None:
    schedule, population = _week4_inputs()
    _week4_gate(
        schedule=schedule,
        population=population,
        measurement_as_of="2026-09-26T20:00:00Z",
        as_of="2026-09-27T00:00:00Z",
    )
    with pytest.raises(LiveSourceError, match="not final"):
        _week4_gate(
            schedule=schedule,
            population=population.assign(outcome_valid=[True, False]),
            measurement_as_of="2026-09-26T20:00:00Z",
            as_of="2026-09-27T00:00:00Z",
        )


def test_week4_gate_rejects_measurement_before_last_kickoff() -> None:
    schedule, population = _week4_inputs()
    with pytest.raises(LiveSourceError, match="predates the final Week 4 kickoff"):
        _week4_gate(
            schedule=schedule,
            population=population,
            measurement_as_of="2026-09-25T15:00:00Z",
            as_of="2026-09-27T00:00:00Z",
        )


def test_schedule_parent_must_match_every_certified_2026_schedule_fact() -> None:
    schedule, population = _week4_inputs()
    _validate_schedule_matches_population(schedule=schedule, population=population)

    for column, value in (
        ("week", 5),
        ("kickoff_utc", "2026-09-26T16:00:00Z"),
        ("home_team", "Unrelated Team"),
    ):
        mismatched = schedule.copy()
        mismatched.loc[mismatched["game_id"].eq(401), column] = value
        with pytest.raises(LiveSourceError, match="schedule_source_mismatch"):
            _validate_schedule_matches_population(
                schedule=mismatched, population=population
            )
