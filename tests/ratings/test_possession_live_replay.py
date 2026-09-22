"""Contract tests for the isolated 2026 single-candidate rating replay."""

from __future__ import annotations

import copy

import pandas as pd
import pytest

from cks_picks_cfb.ratings.possession_live_replay import (
    FROZEN_CANDIDATE,
    LiveReplayError,
    LiveReplayInputs,
    build_live_replay,
)


def _inputs() -> LiveReplayInputs:
    population: list[dict] = []
    observations: list[dict] = []
    snapshots: list[dict] = []
    for week, game_id in enumerate((100, 101, 102)):
        kickoff = f"2026-09-{week + 1:02d}T18:00:00Z"
        population.append(
            {
                "season": 2026,
                "week": week,
                "game_id": game_id,
                "kickoff_utc": kickoff,
                "home_team": "Alpha",
                "away_team": "Beta",
                "forecast_eligible": True,
                "schedule_completed": True,
                "outcome_valid": True,
                "timing_class": "live",
            }
        )
        for team, opponent in (("Alpha", "Beta"), ("Beta", "Alpha")):
            for role in ("offense", "defense"):
                observations.append(
                    {
                        "season": 2026,
                        "game_id": game_id,
                        "kickoff_utc": kickoff,
                        "team": team,
                        "measurement_id": "ppp",
                        "unit_role": role,
                        "denominator": 10.0,
                        "coverage_status": "observed",
                        "timing_class": "live",
                    }
                )
                snapshots.append(
                    {
                        "season": 2026,
                        "as_of_game_id": game_id,
                        "team": team,
                        "measurement_id": "ppp",
                        "unit_role": role,
                        "adjustment_iteration": 4,
                        "adjusted_value": 2.0 + week + (0.5 if team == "Alpha" else -0.5),
                        "timing_class": "live",
                    }
                )
    terminal: list[dict] = []
    for team, value in (("Alpha", 3.0), ("Beta", 1.0)):
        for role in ("offense", "defense"):
            terminal.append(
                {
                    "season": 2025,
                    "team": team,
                    "measurement_id": "ppp",
                    "unit_role": role,
                    "adjusted_value": value,
                    "primary_exposure": 20.0,
                }
            )
    return LiveReplayInputs(
        population=pd.DataFrame(population),
        observations=pd.DataFrame(observations),
        snapshots=pd.DataFrame(snapshots),
        historical_terminal=pd.DataFrame(terminal),
    )


def test_replay_keeps_frozen_candidate_and_continuous_week_history() -> None:
    result = build_live_replay(_inputs())

    assert set(result.priors["candidate_id"]) == {FROZEN_CANDIDATE}
    assert result.diagnostics["weeks"] == [0, 1, 2]
    assert len(result.priors) == 4
    assert len(result.rating_states) == 12
    assert len(result.team_states) == 6
    assert result.diagnostics["source_observations"] == 8
    week_zero = result.rating_states[result.rating_states["week"].eq(0)]
    assert week_zero["completed_games"].eq(0).all()
    week_one = result.rating_states[result.rating_states["week"].eq(1)]
    assert week_one["completed_games"].eq(1).all()
    assert week_one["evidence_weight"].gt(0).all()


def test_future_snapshot_cannot_change_an_earlier_state() -> None:
    baseline = build_live_replay(_inputs())
    original = copy.deepcopy(_inputs())
    snapshots = original.snapshots.copy()
    snapshots.loc[
        snapshots["as_of_game_id"].eq(102), "adjusted_value"
    ] += 100.0
    altered = LiveReplayInputs(
        population=original.population,
        observations=original.observations,
        snapshots=snapshots,
        historical_terminal=original.historical_terminal,
    )

    replayed = build_live_replay(altered)
    before = baseline.rating_states[baseline.rating_states["week"].lt(2)]
    after = replayed.rating_states[replayed.rating_states["week"].lt(2)]
    pd.testing.assert_frame_equal(before.reset_index(drop=True), after.reset_index(drop=True))


def test_replay_rejects_a_gap_in_week_history() -> None:
    original = _inputs()
    inputs = LiveReplayInputs(
        population=original.population[~original.population["week"].eq(1)].copy(),
        observations=original.observations,
        snapshots=original.snapshots,
        historical_terminal=original.historical_terminal,
    )

    with pytest.raises(LiveReplayError, match="continuous"):
        build_live_replay(inputs)
