"""Pure contracts for the Preview-only data-first Phase 3 path."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest

from cks_picks_cfb.data.data_first_phase2 import DEVELOPMENT_SEASONS
from cks_picks_cfb.data.data_first_phase2d import PHASE3_DATASETS, signed_payload
from cks_picks_cfb.data.data_first_phase3 import (
    CANDIDATE_COMPONENTS,
    CORE_CANDIDATES,
    PHASE3_ADJUSTED_DATASET,
    PHASE3_ADJUSTED_SCHEMA,
    PHASE3_ATTRIBUTION_DATASET,
    PHASE3_ATTRIBUTION_SCHEMA,
    PHASE3_OBSERVATION_DATASET,
    PHASE3_OBSERVATION_SCHEMA,
    PHASE3_PREDICTION_DATASET,
    PHASE3_PREDICTION_SCHEMA,
    REQUIRED_CORE_ELIGIBILITY_SHA256,
    Phase3Error,
    phase3_identity,
    retained_core,
    validate_phase3_config,
    verify_core_eligibility,
    verify_retained_core_manifest,
)
from cks_picks_cfb.ratings.contracts import load_measurement_config
from cks_picks_cfb.ratings.phase3 import (
    ADJUSTED_COMPONENTS,
    build_adjusted_measurements,
    build_component_states,
    build_pass_rush_observations,
    hierarchical_bootstrap_interval,
    independent_definition_audit,
    run_candidate_tournament,
)

ROOT = Path(__file__).resolve().parents[1]


def _manifest() -> dict:
    refs = []
    for season in DEVELOPMENT_SEASONS:
        for dataset in sorted(PHASE3_DATASETS):
            refs.append(
                {
                    "season": season,
                    "dataset": dataset,
                    "version_id": f"{season}-{dataset}",
                    "schema_version": "v1",
                    "content_sha": f"sha-{season}-{dataset}",
                    "uri": f"lake/{season}/{dataset}",
                    "eligible": True,
                    "permitted_uses": ["phase3_measurement_validation"],
                }
            )
    return signed_payload(
        {
            "schema_version": "data_first_phase2_eligibility_v3",
            "state": "eligible",
            "development_seasons": list(DEVELOPMENT_SEASONS),
            "forbidden_seasons": [2020],
            "production_activation_authorized": False,
            "phase3_input_refs": refs,
        }
    )


def _losses() -> pd.DataFrame:
    rows = []
    for candidate in CORE_CANDIDATES:
        error = 10.0 if candidate == "epa_only" else 9.8
        for target in ("margin", "total"):
            for game_id in (1, 2):
                rows.append(
                    {
                        "candidate": candidate,
                        "target": target,
                        "season": 2024,
                        "week": game_id,
                        "game_id": game_id,
                        "absolute_error": error,
                        "bootstrap_excludes_zero": True,
                        "coverage_equal": True,
                        "seasonal_gate_passed": True,
                    }
                )
    return pd.DataFrame(rows)


def test_core_eligibility_requires_the_exact_seventy_refs():
    assert len(verify_core_eligibility(_manifest())) == 70
    broken = deepcopy(_manifest())
    broken["phase3_input_refs"].pop()
    broken = signed_payload(broken)
    with pytest.raises(Phase3Error, match="exactly 70"):
        verify_core_eligibility(broken)


def test_core_eligibility_rejects_signature_drift():
    broken = _manifest()
    broken["state"] = "ineligible"
    with pytest.raises(Phase3Error):
        verify_core_eligibility(broken)


def test_retained_core_uses_simplicity_when_candidates_are_within_half_percent():
    result = retained_core(_losses())
    assert result["selected_candidate"] == "epa_pass_rush"


def test_retained_core_falls_back_to_epa_only_without_required_lift():
    losses = _losses()
    losses.loc[losses["candidate"] != "epa_only", "absolute_error"] = 9.99
    assert retained_core(losses)["selected_candidate"] == "epa_only"


def test_phase3_config_is_the_complete_ten_season_measurement_contract():
    config = load_measurement_config(
        ROOT / "conf/research/data_first_football_v1/phase3_measurement_core_v1.yaml"
    )
    assert config.historical_development_seasons == DEVELOPMENT_SEASONS
    assert config.forbidden_seasons == (2020,)
    assert config.research_prefix == "artifacts/research/data-first-football-v1/phase3"
    validate_phase3_config(config.raw_config)
    drifted = deepcopy(config.raw_config)
    drifted["selection"]["ridge_alpha"] = 11
    with pytest.raises(Phase3Error, match="selection scaffold"):
        validate_phase3_config(drifted)


def test_phase3_identity_binds_the_as_of_cutoff():
    first = phase3_identity(
        run_id="run",
        environment="preview",
        as_of="2026-03-01T00:00:00+00:00",
        code_sha="abc",
        config_sha="def",
        core_eligibility_uri="parent.json",
        core_eligibility_sha256="123",
    )
    second = phase3_identity(
        run_id="run",
        environment="preview",
        as_of="2026-03-02T00:00:00+00:00",
        code_sha="abc",
        config_sha="def",
        core_eligibility_uri="parent.json",
        core_eligibility_sha256="123",
    )
    assert first["identity_sha256"] != second["identity_sha256"]


def test_retained_core_manifest_is_the_only_phase4a_handoff():
    identity = phase3_identity(
        run_id="run",
        environment="preview",
        as_of="2026-03-01T00:00:00+00:00",
        code_sha="abc",
        config_sha="def",
        core_eligibility_uri="parent.json",
        core_eligibility_sha256=REQUIRED_CORE_ELIGIBILITY_SHA256,
    )
    outputs = {
        "observations": (PHASE3_OBSERVATION_DATASET, PHASE3_OBSERVATION_SCHEMA),
        "adjusted_measurements": (PHASE3_ADJUSTED_DATASET, PHASE3_ADJUSTED_SCHEMA),
        "fold_predictions": (PHASE3_PREDICTION_DATASET, PHASE3_PREDICTION_SCHEMA),
        "attribution_coverage": (
            PHASE3_ATTRIBUTION_DATASET,
            PHASE3_ATTRIBUTION_SCHEMA,
        ),
    }
    payload = signed_payload(
        {
            "schema_version": "data_first_phase3_retained_core_v1",
            "state": "frozen",
            "selected_candidate": "epa_only",
            "selected_components": ["epa_per_play"],
            "auxiliary_context_consumed": False,
            "production_activation_authorized": False,
            "identity": identity,
            "output_refs": {
                name: {
                    "dataset": dataset,
                    "version_id": f"{name}-v1",
                    "schema_version": schema,
                    "content_sha": f"sha-{name}",
                    "uri": f"lake/{name}",
                }
                for name, (dataset, schema) in outputs.items()
            },
        }
    )
    assert verify_retained_core_manifest(payload)["selected_candidate"] == "epa_only"
    broken = dict(payload)
    broken["auxiliary_context_consumed"] = True
    broken = signed_payload(broken)
    with pytest.raises(Phase3Error, match="auxiliary context"):
        verify_retained_core_manifest(broken)


def _base_observation_rows() -> pd.DataFrame:
    rows = []
    for team, opponent, side in (("A", "B", "home"), ("B", "A", "away")):
        for role in ("offense", "defense"):
            rows.append(
                {
                    "season": 2025,
                    "week": 1,
                    "game_id": 1,
                    "kickoff_utc": "2025-09-01T00:00:00+00:00",
                    "team": team,
                    "opponent": opponent,
                    "side": side,
                    "measurement_id": "epa_per_play",
                    "unit_role": role,
                    "numerator": 0.0,
                    "denominator": 1.0,
                    "raw_value": 0.0,
                    "exposure_unit": "plays",
                    "effective_at": None,
                    "temporal_status": "reconstructed",
                    "eligible_after": None,
                    "coverage_status": "observed",
                    "missing_reason": None,
                    "quality_flags": None,
                    "measurement_schema_version": "v1",
                    "measurement_design_id": "design",
                    "parent_ref_shas": "parent",
                    "code_sha": "code",
                    "config_sha": "config",
                }
            )
    return pd.DataFrame(rows)


def test_pass_rush_classification_is_mutually_exclusive_and_explained():
    byplay = pd.DataFrame(
        [
            {
                "season": 2025,
                "game_id": 1,
                "offense": "A",
                "defense": "B",
                "play_type": "Pass",
                "st": 0,
                "penalty": 0,
                "twopoint": 0,
                "garbage": 0,
                "ppa": 0.4,
                "dropback": 1,
                "rush_attempt": 0,
            },
            {
                "season": 2025,
                "game_id": 1,
                "offense": "B",
                "defense": "A",
                "play_type": "Rush",
                "st": 0,
                "penalty": 0,
                "twopoint": 0,
                "garbage": 0,
                "ppa": -0.2,
                "dropback": 0,
                "rush_attempt": 1,
            },
            {
                "season": 2025,
                "game_id": 1,
                "offense": "A",
                "defense": "B",
                "play_type": "Other",
                "st": 0,
                "penalty": 0,
                "twopoint": 0,
                "garbage": 0,
                "ppa": 0.1,
                "dropback": 0,
                "rush_attempt": 0,
            },
            {
                "season": 2025,
                "game_id": 1,
                "offense": "A",
                "defense": "B",
                "play_type": "Pass",
                "st": 0,
                "penalty": 0,
                "twopoint": 0,
                "garbage": 1,
                "ppa": 0.2,
                "dropback": 1,
                "rush_attempt": 0,
            },
        ]
    )
    frame, audit = build_pass_rush_observations(
        byplay=byplay, base_observations=_base_observation_rows()
    )
    assert audit["classified_or_explained"] is True
    assert audit["eligible_pass_rows"] == 1
    assert audit["eligible_rush_rows"] == 1
    assert audit["excluded_ambiguous_classification"] == 1
    assert audit["excluded_garbage_or_missing_flag"] == 1
    pass_a = frame[
        (frame["team"] == "A")
        & (frame["unit_role"] == "offense")
        & (frame["measurement_id"] == "epa_pass")
    ].iloc[0]
    assert pass_a["numerator"] == pytest.approx(0.4)
    assert pass_a["denominator"] == 1


def test_independent_definition_audit_recomputes_raw_play_and_drive_totals():
    plays = pd.DataFrame(
        [
            {
                "season": 2025,
                "game_id": 1,
                "drive_number": 1,
                "offense": "A",
                "defense": "B",
                "play_type": "Pass",
                "st": 0,
                "penalty": 0,
                "twopoint": 0,
                "garbage": 0,
                "ppa": 0.4,
                "success": 1,
                "yards_gained": 25,
                "turnover": 0,
            },
            {
                "season": 2025,
                "game_id": 1,
                "drive_number": 2,
                "offense": "B",
                "defense": "A",
                "play_type": "Rush",
                "st": 0,
                "penalty": 0,
                "twopoint": 0,
                "garbage": 0,
                "ppa": -0.2,
                "success": 0,
                "yards_gained": 5,
                "turnover": 1,
            },
        ]
    )
    drives = pd.DataFrame(
        [
            {
                "season": 2025,
                "game_id": 1,
                "drive_number": 1,
                "offense": "A",
                "defense": "B",
                "start_yards_to_goal": 60,
            },
            {
                "season": 2025,
                "game_id": 1,
                "drive_number": 2,
                "offense": "B",
                "defense": "A",
                "start_yards_to_goal": 70,
            },
        ]
    )
    expected = {
        ("A", "offense"): {
            "epa_per_play": (0.4, 1),
            "success_rate": (1, 1),
            "explosive_rate_20": (1, 1),
            "turnover_rate": (0, 1),
            "average_start_field_position": (40, 1),
            "plays_per_drive": (1, 1),
        },
        ("B", "defense"): {
            "epa_per_play": (0.4, 1),
            "success_rate": (1, 1),
            "explosive_rate_20": (1, 1),
            "turnover_rate": (0, 1),
            "average_start_field_position": (40, 1),
        },
        ("B", "offense"): {
            "epa_per_play": (-0.2, 1),
            "success_rate": (0, 1),
            "explosive_rate_20": (0, 1),
            "turnover_rate": (1, 1),
            "average_start_field_position": (30, 1),
            "plays_per_drive": (1, 1),
        },
        ("A", "defense"): {
            "epa_per_play": (-0.2, 1),
            "success_rate": (0, 1),
            "explosive_rate_20": (0, 1),
            "turnover_rate": (1, 1),
            "average_start_field_position": (30, 1),
        },
    }
    rows = []
    for (team, role), measurements in expected.items():
        for measurement_id, (numerator, denominator) in measurements.items():
            rows.append(
                {
                    "season": 2025,
                    "game_id": 1,
                    "team": team,
                    "unit_role": role,
                    "measurement_id": measurement_id,
                    "numerator": numerator,
                    "denominator": denominator,
                }
            )
    observations = pd.DataFrame(rows)
    audit = independent_definition_audit(
        byplay=plays, drives=drives, observations=observations
    )
    assert audit["all_rows_exact"] is True
    assert audit["mismatch_rows"] == 0
    drifted = observations.copy()
    drifted.loc[0, "numerator"] += 1
    assert not independent_definition_audit(
        byplay=plays, drives=drives, observations=drifted
    )["all_rows_exact"]


def _tournament_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    state_rows = []
    game_rows = []
    outcome_rows = []
    for index, season in enumerate(DEVELOPMENT_SEASONS):
        game_id = season * 10
        kickoff = f"{season}-09-01T00:00:00+00:00"
        game_rows.append(
            {
                "season": season,
                "week": 1,
                "game_id": game_id,
                "kickoff_utc": kickoff,
                "home_team": "A",
                "away_team": "B",
                # The real fbs_involved_games parent also carries scores; the
                # tournament must source targets only from game_outcomes.
                "home_points": 999,
                "away_points": 999,
            }
        )
        outcome_rows.append(
            {
                "season": season,
                "game_id": game_id,
                "home_points": 21 + index,
                "away_points": 14,
            }
        )
        for team_sign, team in ((1.0, "A"), (-1.0, "B")):
            for role_sign, role in ((1.0, "offense"), (0.8, "defense")):
                for component_index, component in enumerate(
                    sorted(
                        {
                            value
                            for values in CANDIDATE_COMPONENTS.values()
                            for value in values
                        }
                    )
                ):
                    state_rows.append(
                        {
                            "season": season,
                            "week": 1,
                            "game_id": game_id,
                            "kickoff_utc": kickoff,
                            "team": team,
                            "measurement_id": component,
                            "unit_role": role,
                            "state_value": team_sign
                            * role_sign
                            * (index + component_index / 10),
                            "state_uncertainty": 0.5,
                            "evidence_available": True,
                        }
                    )
    states = pd.DataFrame(state_rows)
    return states, pd.DataFrame(game_rows), pd.DataFrame(outcome_rows)


def test_candidate_tournament_is_fold_local_and_population_complete():
    states, games, outcomes = _tournament_inputs()
    predictions = run_candidate_tournament(
        primary_states=states,
        sensitivity_states=states,
        games=games,
        outcomes=outcomes,
        ridge_alpha=10,
    )
    assert len(predictions) == 2 * len(CORE_CANDIDATES) * 7 * 2
    fold_2018 = predictions[predictions["season"] == 2018]
    assert set(fold_2018["training_seasons"]) == {"[2015,2016,2017]"}
    fold_2021 = predictions[predictions["season"] == 2021]
    assert set(fold_2021["training_seasons"]) == {"[2015,2016,2017,2018,2019]"}
    assert not predictions["season"].eq(2020).any()


def test_hierarchical_bootstrap_is_deterministic_and_paired():
    rows = []
    for season in (2023, 2024):
        for week in (1, 2):
            for target in ("margin", "total"):
                rows.extend(
                    [
                        {
                            "candidate": "epa_only",
                            "season": season,
                            "week": week,
                            "game_id": season * 10 + week,
                            "target": target,
                            "absolute_error": 10.0,
                        },
                        {
                            "candidate": "quality_core_equal",
                            "season": season,
                            "week": week,
                            "game_id": season * 10 + week,
                            "target": target,
                            "absolute_error": 9.0,
                        },
                    ]
                )
    losses = pd.DataFrame(rows)
    first = hierarchical_bootstrap_interval(
        losses,
        "quality_core_equal",
        replicates=100,
        confidence=0.90,
        seed=7,
    )
    second = hierarchical_bootstrap_interval(
        losses,
        "quality_core_equal",
        replicates=100,
        confidence=0.90,
        seed=7,
    )
    assert first == second
    assert first == pytest.approx((1.0, 1.0, 1.0))


def _quality_observations() -> tuple[pd.DataFrame, pd.DataFrame]:
    template = _base_observation_rows().iloc[0].to_dict()
    rows = []
    games = []
    for season in (2019, 2021):
        for week in (1, 2):
            game_id = season * 10 + week
            kickoff = f"{season}-09-{week:02d}T00:00:00+00:00"
            games.append(
                {
                    "season": season,
                    "week": week,
                    "game_id": game_id,
                    "kickoff_utc": kickoff,
                    "home_team": "A",
                    "away_team": "B",
                }
            )
            for component in ADJUSTED_COMPONENTS:
                for team, opponent, side, offense_value in (
                    ("A", "B", "home", 1.0),
                    ("B", "A", "away", 2.0),
                ):
                    for role in ("offense", "defense"):
                        value = (
                            offense_value if role == "offense" else 3.0 - offense_value
                        )
                        row = dict(template)
                        row.update(
                            {
                                "season": season,
                                "week": week,
                                "game_id": game_id,
                                "kickoff_utc": kickoff,
                                "team": team,
                                "opponent": opponent,
                                "side": side,
                                "measurement_id": component,
                                "unit_role": role,
                                "numerator": value * 10,
                                "denominator": 10.0,
                                "raw_value": value,
                            }
                        )
                        rows.append(row)
    return pd.DataFrame(rows), pd.DataFrame(games)


def test_adjustment_is_week_open_and_retains_iterations_zero_and_four():
    observations, games = _quality_observations()
    config = load_measurement_config(
        ROOT / "conf/research/data_first_football_v1/phase3_measurement_core_v1.yaml"
    )
    adjusted, _ = build_adjusted_measurements(
        observations=observations,
        games=games,
        config=config,
        identity_sha="identity",
        code_sha="code",
        config_sha="config",
        recency_mode="primary",
    )
    assert set(adjusted["adjustment_iteration"]) == {0, 4}
    assert (adjusted[adjusted["week"] == 1]["coverage_status"] == "missing").all()
    week_two = adjusted[
        (adjusted["season"] == 2019)
        & (adjusted["week"] == 2)
        & (adjusted["measurement_id"] == "epa_per_play")
        & (adjusted["unit_role"] == "offense")
        & (adjusted["team"] == "A")
    ]
    assert set(week_two["games_exposure"]) == {1}
    assert set(week_two["denominator"]) == {10.0}


def test_component_state_uses_two_decay_steps_across_the_2020_gap():
    observations, games = _quality_observations()
    config = load_measurement_config(
        ROOT / "conf/research/data_first_football_v1/phase3_measurement_core_v1.yaml"
    )
    adjusted, terminal = build_adjusted_measurements(
        observations=observations,
        games=games,
        config=config,
        identity_sha="identity",
        code_sha="code",
        config_sha="config",
        recency_mode="primary",
    )
    states = build_component_states(
        adjusted=adjusted, terminal=terminal, recency_mode="primary"
    )
    first_2021 = states[
        (states["season"] == 2021)
        & (states["week"] == 1)
        & (states["team"] == "A")
        & (states["measurement_id"] == "epa_per_play")
        & (states["unit_role"] == "offense")
    ].iloc[0]
    assert first_2021["prior_source_season"] == 2019
    assert first_2021["annual_decay_steps"] == 2
    assert first_2021["state_value"] is not None
