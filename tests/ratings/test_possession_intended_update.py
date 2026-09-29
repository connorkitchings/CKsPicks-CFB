"""Focused safeguards for the versioned V5 intended-update successor."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from cks_picks_cfb.ratings.possession_intended_update import (
    IntendedUpdate,
    IntendedUpdateError,
    _four_pass_context,
)
from cks_picks_cfb.ratings_lab.adjusted_game import four_pass_graph


def _inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    games = [
        (0, 1, "2026-08-29T12:00:00Z", "A", "B"),
        (1, 2, "2026-09-05T12:00:00Z", "A", "C"),
        (1, 3, "2026-09-05T16:00:00Z", "B", "D"),
        (2, 4, "2026-09-12T12:00:00Z", "A", "D"),
    ]
    schedule = pd.DataFrame(
        [
            {
                "season": 2026,
                "week": week,
                "game_id": game_id,
                "kickoff_utc": kickoff,
                "home_team": home,
                "away_team": away,
            }
            for week, game_id, kickoff, home, away in games
        ]
    )
    observations = []
    for week, game_id, kickoff, home, away in games[:3]:
        for team, opponent in ((home, away), (away, home)):
            for role in ("offense", "defense"):
                value = 1.0 + game_id / 10 + (0.1 if team == home else -0.1)
                observations.append(
                    {
                        "season": 2026,
                        "week": week,
                        "game_id": game_id,
                        "kickoff_utc": kickoff,
                        "team": team,
                        "opponent": opponent,
                        "measurement_id": "ppp",
                        "unit_role": role,
                        "raw_value": value,
                        "numerator": value * 8,
                        "denominator": 8.0,
                        "coverage_status": "observed",
                    }
                )
    priors = pd.DataFrame(
        [
            {
                "season": 2026,
                "team": team,
                "unit_role": role,
                "prior_mean": 0.0,
                "prior_variance": 1.0,
            }
            for team in "ABCD"
            for role in ("offense", "defense")
        ]
    )
    terminal = pd.DataFrame(
        [
            {
                "season": 2025,
                "team": team,
                "measurement_id": "ppp",
                "unit_role": role,
                "adjusted_value": 1.0 + idx * 0.2,
                "primary_exposure": 8.0,
            }
            for idx, team in enumerate("ABCD")
            for role in ("offense", "defense")
        ]
    )
    return schedule, pd.DataFrame(observations), priors, terminal


def _engine() -> IntendedUpdate:
    schedule, observations, priors, terminal = _inputs()
    return IntendedUpdate(
        schedule=schedule,
        observations=observations,
        priors=priors,
        historical_terminal=terminal,
    )


def test_four_pass_context_matches_research_reference() -> None:
    engine = _engine()
    source = engine._evidence(week=2, cutoff=pd.Timestamp("2026-09-12T12:00:00Z"))
    values, centers = _four_pass_context(source)
    reference = four_pass_graph(list(source.itertuples(index=False)))
    assert set(values) == set(reference.opponent_values)
    for key, value in values.items():
        assert value == pytest.approx(reference.opponent_values[key], abs=1e-12)
    assert centers == pytest.approx(reference.opponent_centers, abs=1e-12)


def test_one_contribution_per_source_game_and_prior_share() -> None:
    states = _engine().pregame().rating_states
    a = states[
        states.game_id.eq(4) & states.team.eq("A") & states.unit_role.eq("offense")
    ].iloc[0]
    assert json.loads(a.source_game_ids) == [1, 2]
    assert a.usable_exposure == 16.0
    assert a.rating_variance == pytest.approx(1 / 3)
    explanation = json.loads(a.explanation)
    assert explanation["prior_weight"] == pytest.approx(1 / 3)
    assert len(explanation["evidence_contributions"]) == 2
    assert a.rating_mean == pytest.approx(
        explanation["prior_contribution"]
        + sum(row["contribution"] for row in explanation["evidence_contributions"])
    )


def test_same_week_and_future_results_cannot_change_earlier_state() -> None:
    schedule, observations, priors, terminal = _inputs()
    before = _engine().pregame().rating_states
    late = observations[observations.game_id.eq(3)].copy()
    late["raw_value"] += 100
    late["numerator"] = late.raw_value * late.denominator
    changed = observations[observations.game_id.ne(3)].copy()
    changed = pd.concat([changed, late], ignore_index=True)
    after = (
        IntendedUpdate(
            schedule=schedule,
            observations=changed,
            priors=priors,
            historical_terminal=terminal,
        )
        .pregame()
        .rating_states
    )
    keys = ["game_id", "team", "unit_role"]
    first = before[before.game_id.eq(2)].set_index(keys)
    second = after[after.game_id.eq(2)].set_index(keys)
    assert first.rating_mean.to_dict() == second.rating_mean.to_dict()
    assert first.source_game_ids.to_dict() == second.source_game_ids.to_dict()


def test_six_hour_delay_and_post_week_boundary() -> None:
    schedule, observations, priors, terminal = _inputs()
    schedule.loc[schedule.game_id.eq(2), "kickoff_utc"] = "2026-08-29T17:00:00Z"
    observations.loc[observations.game_id.eq(2), "kickoff_utc"] = "2026-08-29T17:00:00Z"
    result = IntendedUpdate(
        schedule=schedule,
        observations=observations,
        priors=priors,
        historical_terminal=terminal,
    )
    states = result.pregame().rating_states
    a = states[
        states.game_id.eq(2) & states.team.eq("A") & states.unit_role.eq("offense")
    ].iloc[0]
    assert json.loads(a.source_game_ids) == []


def test_current_generation_has_all_teams_and_rejects_early_cutoff() -> None:
    engine = _engine()
    with pytest.raises(IntendedUpdateError, match="six-hour"):
        engine.current(post_week=1, cutoff_utc="2026-09-05T17:00:00Z")
    rows = engine.current(post_week=1, cutoff_utc="2026-09-06T00:00:00Z")
    assert len(rows.team_states) == 4
    assert len(rows.rating_states) == 8
