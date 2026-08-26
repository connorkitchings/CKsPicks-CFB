"""Contract, config-hashing, and market-field rejection tests (Task 1)."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from cks_picks_cfb.ratings.contracts import (
    BASELINE_MEASUREMENT_IDS,
    MeasurementContractError,
    load_measurement_config,
    market_field_conflicts,
    validate_observation_frame,
    verify_design_id,
)
from cks_picks_cfb.ratings.observations import build_measurement_observations

BASELINE_CONFIG_PATH = "conf/ratings/measurement_baseline_v1.yaml"


@pytest.fixture(scope="module")
def module_config():
    return load_measurement_config(BASELINE_CONFIG_PATH)


@pytest.fixture(scope="module")
def built_frames(module_config, league, as_of):
    return build_measurement_observations(
        byplay=league["byplay"],
        drives=league["drives"],
        games=league["games"],
        outcomes=league["outcomes"],
        reconciled_team_game=league["reconciled_team_game"],
        config=module_config,
        as_of=as_of,
        code_sha="codesha",
        config_sha="configsha",
        parent_ref_shas="aaa;bbb",
    )


def _write_config(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(payload))
    return path


def _baseline_raw(config) -> dict:
    return copy.deepcopy(dict(config.raw_config))


def test_baseline_config_loads_with_frozen_catalog(config):
    assert tuple(spec.measurement_id for spec in config.measurements) == (
        BASELINE_MEASUREMENT_IDS
    )
    adjusted = {spec.measurement_id for spec in config.measurements if spec.is_adjusted}
    assert adjusted == {
        "epa_per_play",
        "success_rate",
        "explosive_rate_20",
        "points_per_scoring_opportunity",
    }
    assert config.adjustment_iterations == 4
    assert config.retained_iterations == (0, 4)
    assert config.historical_development_seasons == (2021, 2022, 2023, 2024, 2025)
    assert config.protected_seasons == (2026,)
    assert config.temporal_status_for_season(2025) == "reconstructed"
    assert config.temporal_status_for_season(2026) == "authentic"


def test_true_ppso_v3_config_has_separate_artifact_contracts():
    config = load_measurement_config("conf/ratings/measurement_baseline_v3.yaml")
    assert config.uses_true_ppso is True
    assert config.observation_schema_version == "rating_measurement_observations_v3"
    assert config.snapshot_schema_version == "rating_adjusted_measurement_snapshots_v3"
    assert (
        config.terminal_snapshot_schema_version
        == "rating_adjusted_measurement_terminal_snapshots_v2"
    )


def test_design_id_is_deterministic_and_content_addressed(config, tmp_path):
    raw = _baseline_raw(config)
    raw["adjustment"]["iterations"] = 5
    raw["adjustment"]["retained_iterations"] = [0, 5]
    mutated = load_measurement_config(_write_config(tmp_path, raw))
    assert mutated.design_id != config.design_id
    assert load_measurement_config(BASELINE_CONFIG_PATH).design_id == config.design_id


def test_verify_design_id_rejects_mismatch(config):
    verify_design_id(config, config.design_id)
    with pytest.raises(MeasurementContractError, match="mismatch"):
        verify_design_id(config, "deadbeef")


def test_market_field_conflicts_flags_bookmaker_columns():
    assert market_field_conflicts(
        ["kickoff_utc", "spread_line", "total", "home_points", "implied_total"]
    ) == ["implied_total", "spread_line", "total"]
    assert market_field_conflicts(["season", "game_id", "raw_value"]) == []


def test_config_rejects_market_keys(config, tmp_path):
    raw = _baseline_raw(config)
    raw["market_quotes"] = []
    with pytest.raises(MeasurementContractError, match="market"):
        load_measurement_config(_write_config(tmp_path, raw))


def test_config_rejects_invalid_roles(config, tmp_path):
    raw = _baseline_raw(config)
    raw["measurements"][0]["roles"] = ["offense", "special"]
    with pytest.raises(MeasurementContractError, match="role"):
        load_measurement_config(_write_config(tmp_path, raw))


def test_config_rejects_invalid_exposure_unit(config, tmp_path):
    raw = _baseline_raw(config)
    raw["measurements"][0]["exposure_unit"] = "snaps"
    with pytest.raises(MeasurementContractError, match="exposure unit"):
        load_measurement_config(_write_config(tmp_path, raw))


def test_config_rejects_non_baseline_retained_iterations(config, tmp_path):
    raw = _baseline_raw(config)
    raw["adjustment"]["retained_iterations"] = [0, 2, 4]
    with pytest.raises(MeasurementContractError, match="retained"):
        load_measurement_config(_write_config(tmp_path, raw))


def test_config_rejects_temporal_policy_gaps(config, tmp_path):
    raw = _baseline_raw(config)
    raw["temporal_policy"]["authentic_seasons"] = [2027]
    with pytest.raises(MeasurementContractError, match="partition"):
        load_measurement_config(_write_config(tmp_path, raw))


def test_validate_observation_frame_accepts_builder_output(built_frames, module_config):
    validate_observation_frame(built_frames.frame, module_config)


def test_validate_observation_frame_rejects_negative_exposure(
    built_frames, module_config
):
    frame = built_frames.frame.copy()
    frame.loc[0, "denominator"] = -1.0
    with pytest.raises(MeasurementContractError, match="nonnegative"):
        validate_observation_frame(frame, module_config)


def test_validate_observation_frame_rejects_inconsistent_missing_reason(
    built_frames, module_config
):
    frame = built_frames.frame.copy()
    frame.loc[0, "coverage_status"] = "missing"
    with pytest.raises(MeasurementContractError, match="inconsistent"):
        validate_observation_frame(frame, module_config)


def test_validate_observation_frame_rejects_reconstructed_effective_time(
    built_frames, module_config
):
    frame = built_frames.frame.copy()
    frame.loc[0, "effective_at"] = "2025-09-06T18:00:00+00:00"
    with pytest.raises(MeasurementContractError, match="reconstructed"):
        validate_observation_frame(frame, module_config)


def test_validate_observation_frame_rejects_forbidden_season(
    built_frames, module_config
):
    frame = built_frames.frame.copy()
    frame["season"] = 2020
    with pytest.raises(MeasurementContractError, match="forbidden"):
        validate_observation_frame(frame, module_config)


def test_validate_observation_frame_rejects_unauthorized_role(
    built_frames, module_config
):
    frame = built_frames.frame.copy()
    offense_only = frame[
        (frame["measurement_id"] == "plays_per_drive")
        & (frame["unit_role"] == "offense")
    ]
    frame.loc[offense_only.index[0], "unit_role"] = "defense"
    with pytest.raises(MeasurementContractError, match="unauthorized role"):
        validate_observation_frame(frame, module_config)


def test_validate_observation_frame_rejects_market_column(built_frames, module_config):
    frame = built_frames.frame.copy()
    frame["spread_line"] = 3.5
    with pytest.raises(MeasurementContractError, match="market"):
        validate_observation_frame(frame, module_config)


def test_validate_observation_frame_rejects_wrong_ratio(built_frames, module_config):
    frame = built_frames.frame.copy()
    observed = frame["coverage_status"] == "observed"
    frame.loc[observed, "raw_value"] = frame.loc[observed, "raw_value"] + 5.0
    with pytest.raises(MeasurementContractError, match="exposure ratio"):
        validate_observation_frame(frame, module_config)
