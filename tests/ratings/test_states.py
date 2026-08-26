"""Phase 2 empirical-Bayes state tests."""

from __future__ import annotations

import pandas as pd
import pytest
from helpers import AS_OF, simple_league

from cks_picks_cfb.ratings.contracts import load_measurement_config
from cks_picks_cfb.ratings.observations import build_measurement_observations
from cks_picks_cfb.ratings.snapshots import (
    build_pregame_snapshots,
    build_season_terminal_snapshots,
)
from cks_picks_cfb.ratings.state_audit import _location_stability
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


def test_v2_config_versions_schemas_and_pins_the_true_ppso_handoff():
    config = load_team_state_config("conf/ratings/team_state_baseline_v2.yaml")
    assert config.is_v2 is True
    assert config.measurement_state_schema_version == "rating_measurement_states_v2"
    assert config.team_state_schema_version == "rating_team_states_v2"
    assert config.raw_config["phase1"]["observations"]["schema_version"] == (
        "rating_measurement_observations_v3"
    )


def test_v2_location_gate_excludes_small_postseason_population_but_gates_terminal():
    config = load_team_state_config("conf/ratings/team_state_baseline_v2.yaml")
    rows = []
    for team in range(100):
        rows.append(
            {
                "state_kind": "season_terminal",
                "season": 2025,
                "team": f"T{team}",
                "completed_games": 12,
                "offense_mean": 0.1,
                "defense_mean": -0.1,
            }
        )
    for team in range(90):
        rows.append(
            {
                "state_kind": "pregame",
                "season": 2025,
                "team": f"T{team}",
                "completed_games": 10,
                "offense_mean": 0.2,
                "defense_mean": -0.2,
            }
        )
    for team in range(30):
        rows.append(
            {
                "state_kind": "pregame",
                "season": 2025,
                "team": f"T{team}",
                "completed_games": 11,
                "offense_mean": 0.6,
                "defense_mean": 0.6,
            }
        )
    passed, evidence = _location_stability(pd.DataFrame(rows), config)
    by_ordinal = {
        row["completed_games"]: row
        for row in evidence["groups"]
        if row["state_kind"] == "pregame"
    }
    assert passed is True
    assert by_ordinal[10]["qualifies"] is True
    assert by_ordinal[11]["qualifies"] is False
