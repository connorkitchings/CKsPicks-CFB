"""Focused contracts for Phase 4 isolated shadow operations."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from cks_picks_cfb.ratings.contracts import MeasurementContractError
from cks_picks_cfb.ratings.score_models import (
    ScoreModel,
    load_score_model,
    model_record,
    predict_score_model,
)
from cks_picks_cfb.ratings.shadow import (
    ORACLE_TOLERANCE,
    canonical_manifest_uri,
    compare_oracle,
    existing_or_collision,
    load_shadow_config,
    normal_coverage,
    normalize_v4_prediction_run,
    score_freeze,
    validate_freeze_predictions,
    validate_freeze_timing,
    week_cutoff,
)


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "season": [2026],
            "week": [1],
            "game_id": [1],
            "kickoff_utc": ["2026-09-05T19:00:00Z"],
            "home_state_id": ["game:2026:1"],
            "away_state_id": ["game:2026:1"],
            "home_completed_games": [0],
            "away_completed_games": [0],
            "home_pace_source": ["terminal_fallback"],
            "away_pace_source": ["terminal_fallback"],
            "home_field": [1.0],
            "home_offense_mean": [0.1],
            "away_offense_mean": [-0.1],
            "home_defense_mean": [0.1],
            "away_defense_mean": [-0.1],
            "pace_z": [0.0],
            "actual_margin": [np.nan],
            "actual_total": [np.nan],
            "actual_home_points": [np.nan],
            "actual_away_points": [np.nan],
        }
    )


def _model() -> ScoreModel:
    return ScoreModel(
        "negative_binomial_scores",
        np.array([3.3, 0.1, 0.2, -0.2, 0.0]),
        np.array([[10.0, 1.0], [1.0, 10.0]]),
        0.1,
        (2021, 2022, 2023, 2024),
        True,
    )


def _predictions() -> pd.DataFrame:
    return predict_score_model(_model(), _frame(), fold_id="locked_2025")


def test_loader_accepts_real_parquet_style_sequences():
    record = model_record(_model())
    record["feature_names"] = str(record["feature_names"])
    record["training_seasons"] = str(record["training_seasons"])
    restored = load_score_model(record)
    np.testing.assert_allclose(restored.coefficients, _model().coefficients)
    assert restored.training_seasons == (2021, 2022, 2023, 2024)


def test_loader_rejects_invalid_covariance_and_unsuccessful_fit():
    record = model_record(_model())
    record["residual_covariance"] = json.dumps([[1.0, 4.0], [4.0, 1.0]])
    with pytest.raises(MeasurementContractError):
        load_score_model(record)
    record = model_record(_model())
    record["optimizer_success"] = False
    with pytest.raises(MeasurementContractError):
        load_score_model(record)


def test_freeze_requires_exact_coverage_null_actuals_and_ordered_intervals():
    predictions = _predictions()
    validate_freeze_predictions(predictions, slate=_frame(), prospective=True)
    incomplete = predictions[predictions.target.eq("margin")]
    with pytest.raises(MeasurementContractError):
        validate_freeze_predictions(incomplete, slate=_frame(), prospective=True)
    wrong = predictions.copy()
    wrong.loc[0, "interval_80_lower"] = wrong.loc[0, "interval_80_upper"]
    with pytest.raises(MeasurementContractError):
        validate_freeze_predictions(wrong, slate=_frame(), prospective=True)


def test_timing_and_normal_coverage_rules():
    cutoff, earliest, latest = week_cutoff(_frame())
    assert cutoff < earliest < latest + pd.Timedelta(seconds=1)
    validate_freeze_timing(as_of=cutoff, slate=_frame())
    with pytest.raises(MeasurementContractError):
        validate_freeze_timing(as_of=earliest, slate=_frame())
    assert normal_coverage(
        40, {"normal_coverage_min_games": 40, "ineligible_weeks": [0]}, week=1
    )
    assert not normal_coverage(
        50, {"normal_coverage_min_games": 40, "ineligible_weeks": [0]}, week=0
    )


def test_production_v4_csv_adapter_checks_checksum_and_normalizes_targets():
    csv_bytes = b"game_id,Spread Prediction,Total Prediction\n1,3.5,48.5\n"
    manifest = {
        "schema_version": "prediction_run_v1",
        "season": 2026,
        "week": 1,
        "artifact_sha256": __import__("hashlib").sha256(csv_bytes).hexdigest(),
        "model_bundle_sha256": "v4",
        "data_as_of": "2026-09-05T18:00:00Z",
    }
    rows = normalize_v4_prediction_run(
        manifest=manifest, csv_bytes=csv_bytes, season=2026, week=1
    )
    assert set(rows.target) == {"margin", "total"}
    assert set(rows.source_kind) == {"production_v4_frozen_run"}
    with pytest.raises(MeasurementContractError):
        normalize_v4_prediction_run(
            manifest={**manifest, "week": 2}, csv_bytes=csv_bytes, season=2026, week=1
        )


def test_score_requires_complete_outcomes_and_v4_pairing_with_row_lineage():
    predictions = _predictions()
    outcomes = pd.DataFrame(
        {
            "season": [2026],
            "game_id": [1],
            "completed": [True],
            "home_points": [30],
            "away_points": [20],
        }
    )
    v4 = pd.DataFrame(
        {
            "season": [2026, 2026],
            "game_id": [1, 1],
            "target": ["margin", "total"],
            "v4_prediction": [4.0, 49.0],
            "source_kind": ["production_v4_frozen_run"] * 2,
        }
    )
    evidence, report = score_freeze(
        freeze_predictions=predictions,
        outcomes=outcomes,
        v4=v4,
        lineage={
            "freeze_manifest_sha256": "abc",
            "outcome_refs": "[]",
            "scored_at": "now",
        },
    )
    assert report["complete"] is True
    assert set(evidence.freeze_manifest_sha256) == {"abc"}
    v4 = v4.iloc[:1]
    evidence, report = score_freeze(
        freeze_predictions=predictions, outcomes=outcomes, v4=v4, lineage={}
    )
    assert evidence.empty and report["complete"] is False


def test_oracle_and_canonical_collision_contracts(tmp_path):
    predictions = _predictions()
    result = compare_oracle(predictions, predictions, fold_prefix="locked_2025")
    assert result["max_absolute_delta"] <= ORACLE_TOLERANCE
    from cks_picks_cfb.data.storage import LocalStorage

    storage = LocalStorage(str(tmp_path))
    uri = "freeze.json"
    storage.write_bytes(
        json.dumps(
            {
                "shadow_design_id": "x",
                "season": 2026,
                "week": 1,
                "as_of": "t",
                "input_identity": {"a": 1},
            }
        ).encode(),
        uri,
    )
    assert existing_or_collision(
        storage,
        uri,
        {
            "shadow_design_id": "x",
            "season": 2026,
            "week": 1,
            "as_of": "t",
            "input_identity": {"a": 1},
        },
    )
    with pytest.raises(FileExistsError):
        existing_or_collision(
            storage,
            uri,
            {
                "shadow_design_id": "x",
                "season": 2026,
                "week": 1,
                "as_of": "later",
                "input_identity": {"a": 1},
            },
        )
    shadow = load_shadow_config("conf/ratings/shadow_operations_v1.yaml")
    assert canonical_manifest_uri(shadow, season=2026, week=1, kind="freeze").endswith(
        "season=2026/week=01/freeze-manifest.json"
    )
