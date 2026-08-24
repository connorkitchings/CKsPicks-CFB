"""Phase 2 empirical-Bayes state tests."""

from __future__ import annotations

import pytest
from helpers import AS_OF, simple_league

from cks_picks_cfb.ratings.contracts import load_measurement_config
from cks_picks_cfb.ratings.observations import build_measurement_observations
from cks_picks_cfb.ratings.snapshots import (
    build_pregame_snapshots,
    build_season_terminal_snapshots,
)
from cks_picks_cfb.ratings.state_contracts import load_team_state_config
from cks_picks_cfb.ratings.states import build_team_states


def _states():
    league = simple_league()
    measurement_config = load_measurement_config(
        "conf/ratings/measurement_baseline_v1.yaml"
    )
    observation = build_measurement_observations(
        byplay=league["byplay"],
        drives=league["drives"],
        games=league["games"],
        outcomes=league["outcomes"],
        reconciled_team_game=league["reconciled_team_game"],
        config=measurement_config,
        as_of=AS_OF,
        code_sha="code",
        config_sha="config",
        parent_ref_shas="parent",
    ).frame
    snapshots = build_pregame_snapshots(
        observations=observation,
        games=league["games"],
        config=measurement_config,
        code_sha="code",
        config_sha="config",
        parent_observation_version_id="obs",
        parent_ref_shas="parent",
    ).frame
    terminal = build_season_terminal_snapshots(
        observations=observation,
        games=league["games"],
        config=measurement_config,
        code_sha="code",
        config_sha="config",
        parent_observation_version_id="obs",
        parent_ref_shas="parent",
    ).frame
    return build_team_states(
        pregame_snapshots=snapshots,
        terminal_snapshots=terminal,
        config=load_team_state_config("conf/ratings/team_state_baseline_v1.yaml"),
        code_sha="code",
        config_sha="config",
        parent_measurement_refs="parent",
    )


def test_first_season_uses_neutral_nonnull_prior_and_exact_components():
    components, teams, _ = _states()
    first = components[
        (components["state_id"] == "game:2025:1") & (components["team"] == "Alpha")
    ]
    assert len(first) == 8
    assert (first["prior_mean"] == 0).all()
    assert (first["prior_variance"] == 1).all()
    assert (first["posterior_sd"] > 0).all()
    team = teams[
        (teams["state_id"] == "game:2025:1") & (teams["team"] == "Alpha")
    ].iloc[0]
    assert team["component_count"] == 8
    assert team["overall_mean"] == pytest.approx(
        (team["offense_mean"] + team["defense_mean"]) / 2
    )


def test_exposure_increases_current_weight_and_contracts_uncertainty():
    components, _, _ = _states()
    rows = components[
        (components["team"] == "Alpha")
        & (components["measurement_id"] == "epa_per_play")
        & (components["unit_role"] == "offense")
        & (components["state_kind"] == "pregame")
    ].sort_values("as_of_utc")
    assert rows["observed_weight"].iloc[-1] >= rows["observed_weight"].iloc[0]
    assert rows["posterior_sd"].iloc[-1] <= rows["posterior_sd"].iloc[0]


def test_defensive_direction_reverses_standardized_observation():
    components, _, _ = _states()
    row = components[
        (components["state_id"] == "game:2025:3")
        & (components["team"] == "Alpha")
        & (components["measurement_id"] == "epa_per_play")
        & (components["unit_role"] == "defense")
    ].iloc[0]
    if row["native_adjusted_value"] is not None:
        assert row["observed_z"] == pytest.approx(
            -(row["native_adjusted_value"] - row["standardization_center"])
            / row["standardization_scale"]
        )


def test_terminal_state_becomes_next_season_prior():
    components, _, _ = _states()
    terminal = components[
        (components["state_kind"] == "season_terminal")
        & (components["season"] == 2025)
        & (components["team"] == "Alpha")
        & (components["measurement_id"] == "epa_per_play")
        & (components["unit_role"] == "offense")
    ].iloc[0]
    next_state = components[
        (components["state_id"] == "game:2026:5")
        & (components["team"] == "Alpha")
        & (components["measurement_id"] == "epa_per_play")
        & (components["unit_role"] == "offense")
    ].iloc[0]
    assert next_state["prior_source_season"] == 2025
    assert next_state["prior_mean"] == pytest.approx(0.6 * terminal["posterior_mean"])
