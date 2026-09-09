"""Focused contracts for Phase 3 repaired-population v2."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest
import yaml

from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.data.data_first_phase3 import CORE_CANDIDATES
from cks_picks_cfb.data.data_first_phase3_v2 import (
    ATTRIBUTION_COLUMNS_V2,
    BOOTSTRAP_REPLICATES,
    MEASUREMENT_ROLE_GRID,
    Phase3V2Error,
    build_population,
    common_bootstrap_plan,
    complete_observation_grid,
    phase3_v2_identity,
    select_retained_core,
    source_is_available,
    validate_phase3_v2_config,
    verify_repair_manifest,
)
from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame
from cks_picks_cfb.ratings.phase3_v2 import (
    _adjustment_trace,
    build_replayable_measurements,
)

ROOT = Path(__file__).resolve().parents[1]


def _repair_population() -> pd.DataFrame:
    rows = []
    for game_id in range(1, 8937):
        eligible = game_id != 8936
        usable = game_id <= 8903
        rows.append(
            {
                "season": 2015,
                "week": 1 if game_id < 4000 else 2,
                "game_id": game_id,
                "kickoff_utc": "2015-09-01T12:00:00Z",
                "home_team": f"H{game_id}",
                "away_team": f"A{game_id}",
                "home_points": 21 if eligible else None,
                "away_points": 14 if eligible else None,
                "forecast_eligible": eligible,
                "measurement_usable": usable,
                "missing_reason": None if usable else "provider_omission",
                "timing_class": "historically_reconstructed",
            }
        )
    return pd.DataFrame(rows)


def _observed_rows() -> pd.DataFrame:
    rows = []
    for team, opponent, side in (("Home", "Away", "home"), ("Away", "Home", "away")):
        for measurement, role in MEASUREMENT_ROLE_GRID:
            rows.append(
                {
                    "season": 2025,
                    "week": 1,
                    "game_id": 1,
                    "kickoff_utc": "2025-09-01T12:00:00Z",
                    "team": team,
                    "opponent": opponent,
                    "side": side,
                    "measurement_id": measurement,
                    "unit_role": role,
                    "numerator": 1.0,
                    "denominator": 2.0,
                    "raw_value": 0.5,
                    "coverage_status": "observed",
                    "missing_reason": None,
                }
            )
    return pd.DataFrame(rows)


def _small_population() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "season": 2025,
                "week": 1,
                "game_id": 1,
                "kickoff_utc": "2025-09-01T12:00:00Z",
                "home_team": "Home",
                "away_team": "Away",
                "forecast_eligible": True,
                "missing_reason": None,
            },
            {
                "season": 2025,
                "week": 2,
                "game_id": 2,
                "kickoff_utc": "2025-09-08T12:00:00Z",
                "home_team": "OtherHome",
                "away_team": "OtherAway",
                "forecast_eligible": True,
                "missing_reason": "provider_omission",
            },
        ]
    )


def _prediction_fixture() -> pd.DataFrame:
    rows = []
    for candidate in CORE_CANDIDATES:
        for mode in ("primary", "half_life_4_games"):
            for target in ("margin", "total"):
                for game_id in (1, 2):
                    error = 10.0
                    if candidate == "quality_core_equal":
                        error = 8.0
                    rows.append(
                        {
                            "candidate": candidate,
                            "recency_mode": mode,
                            "target": target,
                            "season": 2024,
                            "week": game_id,
                            "game_id": game_id,
                            "absolute_error": error,
                        }
                    )
    return pd.DataFrame(rows)


def test_config_is_sealed_and_rejects_availability_drift():
    payload = yaml.safe_load(
        (
            ROOT
            / "conf/research/data_first_football_v1/phase3_measurement_core_v2.yaml"
        ).read_text()
    )
    validate_phase3_v2_config(payload)
    payload["availability_policy"]["source_kickoff_buffer_hours"] = 5
    with pytest.raises(Phase3V2Error, match="availability"):
        validate_phase3_v2_config(payload)


def test_repaired_population_remains_complete_and_rejects_duplicates():
    population = build_population(_repair_population())
    assert len(population) == 8936
    assert int(population["forecast_eligible"].sum()) == 8935
    assert int(population["measurement_usable"].sum()) == 8903
    duplicate = _repair_population()
    duplicate.loc[8935, "game_id"] = 1
    with pytest.raises(Phase3V2Error, match="duplicate"):
        build_population(duplicate)


def test_completed_games_without_measurements_receive_explicit_grid_rows():
    observations = complete_observation_grid(
        population=_small_population(), observed=_observed_rows()
    )
    assert len(observations) == 68
    missing = observations[observations["game_id"].eq(2)]
    assert len(missing) == 34
    assert missing["raw_value"].isna().all()
    assert (missing["denominator"] == 0).all()
    assert missing["missing_reason"].eq("provider_omission").all()


def test_six_hour_cutoff_is_prior_week_only_and_inclusive_at_boundary():
    cutoff = "2025-09-08T18:00:00Z"
    assert source_is_available(
        source_week=1,
        source_kickoff_utc="2025-09-08T12:00:00Z",
        target_week=2,
        target_week_cutoff_utc=cutoff,
    )
    assert not source_is_available(
        source_week=1,
        source_kickoff_utc="2025-09-08T12:00:01Z",
        target_week=2,
        target_week_cutoff_utc=cutoff,
    )
    assert not source_is_available(
        source_week=2,
        source_kickoff_utc="2025-09-01T00:00:00Z",
        target_week=2,
        target_week_cutoff_utc=cutoff,
    )


def test_iteration_three_opponent_values_drive_the_fourth_pass_correction():
    rows = pd.DataFrame(
        [
            {
                "game_id": 1,
                "team": "A",
                "opponent": "B",
                "unit_role": "offense",
                "numerator": 2.0,
                "denominator": 2.0,
            },
            {
                "game_id": 1,
                "team": "B",
                "opponent": "A",
                "unit_role": "defense",
                "numerator": 2.0,
                "denominator": 2.0,
            },
            {
                "game_id": 2,
                "team": "B",
                "opponent": "A",
                "unit_role": "offense",
                "numerator": 0.0,
                "denominator": 2.0,
            },
            {
                "game_id": 2,
                "team": "A",
                "opponent": "B",
                "unit_role": "defense",
                "numerator": 0.0,
                "denominator": 2.0,
            },
        ]
    )
    final, iteration_three, centers = _adjustment_trace(rows)
    assert set(final) == {"offense", "defense"}
    assert set(iteration_three["defense"]) == {"A", "B"}
    assert centers["defense"] == pytest.approx(0.5)


def test_replay_history_is_cutoff_safe_and_records_source_correction():
    population = _small_population()
    observations = _observed_rows()
    snapshots, history, terminal = build_replayable_measurements(
        population=population, observations=observations
    )
    assert len(snapshots) == 272
    assert not terminal.empty
    assert set(history["source_week"]) == {1}
    assert set(history["week"]) == {2}
    assert history["source_available_utc"].le(history["target_week_cutoff_utc"]).all()
    assert history["iteration_three_opponent_value"].notna().all()


def test_common_bootstrap_is_deterministic_and_shared_for_selection():
    predictions = _prediction_fixture()
    plan = common_bootstrap_plan(predictions[predictions["recency_mode"].eq("primary")])
    assert len(plan) == BOOTSTRAP_REPLICATES
    assert plan == common_bootstrap_plan(
        predictions[predictions["recency_mode"].eq("primary")]
    )
    attribution, retained = select_retained_core(predictions)
    assert tuple(attribution.columns) == ATTRIBUTION_COLUMNS_V2
    assert (
        attribution.loc[
            attribution["candidate"].eq("quality_core_equal"), "bootstrap_90_lower"
        ].iloc[0]
        > 0
    )
    assert retained["selected_candidate"] == "quality_core_equal"


def test_repair_manifest_and_identity_fail_closed():
    payload = signed_payload(
        {
            "schema_version": "data_first_repair_manifest_v2",
            "state": "repaired_reconstructed_only",
            "identity": {"environment": "preview"},
            "population": {
                "scheduled_games": 8936,
                "forecast_eligible_games": 8935,
                "measurement_usable_games": 8903,
                "measurement_missing_games": 33,
            },
            "output_refs": {
                "population": {
                    "dataset": "repair_population",
                    "schema_version": "data_first_repair_population_v2",
                }
            },
            "timing_class": "historically_reconstructed",
            "production_activation_authorized": False,
        }
    )
    assert verify_repair_manifest(payload)["state"] == "repaired_reconstructed_only"
    drifted = deepcopy(payload)
    drifted["production_activation_authorized"] = True
    drifted = signed_payload(drifted)
    with pytest.raises(Phase3V2Error, match="authorizes production"):
        verify_repair_manifest(drifted)
    first = phase3_v2_identity(
        run_id="one",
        environment="preview",
        as_of="2026-09-09T00:00:00Z",
        code_sha="code",
        config_sha="config",
        repair_manifest_uri="repair.json",
        repair_manifest_raw_sha256="raw",
        repair_manifest_canonical_sha256="canonical",
    )
    second = phase3_v2_identity(
        run_id="two",
        environment="preview",
        as_of="2026-09-09T00:00:00Z",
        code_sha="code",
        config_sha="config",
        repair_manifest_uri="repair.json",
        repair_manifest_raw_sha256="raw",
        repair_manifest_canonical_sha256="canonical",
    )
    assert first["identity_sha256"] != second["identity_sha256"]


def test_population_schema_enforces_unique_keys():
    frame = build_population(_repair_population())
    schema = schema_for("phase3_population", "data_first_phase3_population_v2")
    assert validate_frame(frame, schema)["schema_valid"]
