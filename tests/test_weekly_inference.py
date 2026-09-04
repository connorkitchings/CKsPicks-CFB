from __future__ import annotations

import hashlib

import pandas as pd
import pytest

from cks_picks_cfb.inference.weekly import (
    InferenceModelContext,
    PreparedInferenceInputs,
    build_publication_manifest,
    calculate_edges_and_leans,
    execute_regime_routing,
    load_inference_model_context,
    prepare_inference_features,
)


def _features() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "season": 2026,
                "week": 1,
                "game_id": 1,
                "home_team": "Home",
                "away_team": "Away",
                "start_date": "2026-09-01T18:00:00Z",
                "prediction_regime": "game_1",
                "home_current_season_games": 0,
                "away_current_season_games": 0,
            }
        ]
    )


def test_prepare_inputs_merges_latest_market_and_enforces_schedule_coverage():
    market = pd.DataFrame(
        [
            {
                "game_id": 1,
                "spread": -2.5,
                "total": 49.0,
                "captured_at": "2026-08-01",
                "market_captured_at": "2026-08-01T18:00:00Z",
                "market_snapshot_id": "old",
                "source_quote_ids": '["q-old"]',
            },
            {
                "game_id": 1,
                "spread": -3.5,
                "total": 50.0,
                "captured_at": "2026-08-02",
                "market_snapshot_id": "new",
                "market_captured_at": "2026-08-02T18:00:00Z",
                "market_policy_version": "consensus_then_median_v1",
                "spread_selection_rule": "cfbd_consensus",
                "total_selection_rule": "cfbd_consensus",
                "spread_provider_count": 1,
                "total_provider_count": 1,
                "source_quote_ids": '["q1", "q2"]',
            },
        ]
    )
    schedule = pd.DataFrame([{"season": 2026, "week": 1, "game_id": 1}])
    prepared = prepare_inference_features(
        _features(),
        year=2026,
        week=1,
        market_snapshot=market,
        schedule_snapshot=schedule,
    )
    assert prepared.features.loc[0, "id"] == 1
    assert prepared.features.loc[0, "home_team_spread_line"] == -3.5
    assert prepared.features.loc[0, "total_line"] == 50.0
    assert prepared.features.loc[0, "market_snapshot_id"] == "new"
    # Full market lineage must survive the merge for downstream persistence.
    assert prepared.features.loc[0, "source_quote_ids"] == '["q1", "q2"]'
    assert prepared.features.loc[0, "market_captured_at"] == "2026-08-02T18:00:00Z"
    assert (
        prepared.features.loc[0, "market_policy_version"] == "consensus_then_median_v1"
    )
    assert prepared.features.loc[0, "spread_selection_rule"] == "cfbd_consensus"
    assert prepared.features.loc[0, "total_selection_rule"] == "cfbd_consensus"
    assert prepared.features.loc[0, "spread_provider_count"] == 1
    assert prepared.features.loc[0, "total_provider_count"] == 1
    with pytest.raises(RuntimeError, match="coverage mismatch"):
        prepare_inference_features(
            _features(),
            year=2026,
            week=1,
            schedule_snapshot=pd.DataFrame([{"season": 2026, "week": 1, "game_id": 2}]),
        )


def test_edge_calculation_preserves_spread_sign_thresholds_and_missing_lines():
    features = _features().rename(columns={"game_id": "id"})
    features["home_team_spread_line"] = [-3.0]
    features["total_line"] = [50.0]
    predictions = pd.DataFrame(
        [
            {
                "predicted_spread": 6.0,
                "predicted_total": 52.0,
                "spread_model_version": "s",
                "total_model_version": "t",
                "high_confidence_eligible": True,
            }
        ]
    )
    result = calculate_edges_and_leans(
        predictions,
        features,
        spread_threshold=3.0,
        spread_threshold_high=3.0,
        total_threshold=2.0,
        run_id="run",
    )
    assert result.loc[0, "Spread Bet"] == "Home"
    assert result.loc[0, "Spread Confidence"] == "High"
    assert result.loc[0, "Total Bet"] == "No Bet"
    features["home_team_spread_line"] = [None]
    result = calculate_edges_and_leans(
        predictions,
        features,
        spread_threshold=3.0,
        spread_threshold_high=5.0,
        total_threshold=1.0,
        run_id="run",
    )
    assert result.loc[0, "Spread Bet"] == "No Bet"


def test_routing_normalizes_v3_and_compatibility_predictions():
    prepared = PreparedInferenceInputs(
        features=_features().rename(columns={"game_id": "id"})
    )
    context = InferenceModelContext(
        bundle=object(), bundle_version="v3", model_bundle_sha256="bundle"
    )

    def bundle_predictor(_, frame):
        assert frame.loc[0, "prediction_regime"] == "game_1"
        return pd.DataFrame(
            {
                "predicted_spread": [1.0],
                "predicted_total": [2.0],
                "spread_model_version": ["s"],
                "total_model_version": ["t"],
                "spread_high_confidence_eligible": [True],
                "total_high_confidence_eligible": [False],
            }
        )

    routed = execute_regime_routing(
        context, prepared, bundle_predictor=bundle_predictor
    )
    assert routed.loc[0, "high_confidence_eligible"] == False  # noqa: E712
    legacy = execute_regime_routing(
        InferenceModelContext(
            bundle=None,
            bundle_version=None,
            model_bundle_sha256="legacy",
            spread_model_version="s",
            total_model_version="t",
        ),
        prepared,
        legacy_predictor=lambda _: ([3.0], [4.0]),
    )
    assert legacy[["predicted_spread", "predicted_total"]].iloc[0].tolist() == [
        3.0,
        4.0,
    ]


def test_model_context_rejects_ambiguous_bundle_version():
    with pytest.raises(ValueError, match="declare version"):
        load_inference_model_context(bundle=object(), bundle_version=None)
    context = load_inference_model_context(
        bundle=None,
        bundle_version=None,
        spread_model_version="spread-sha",
        total_model_version="total-sha",
    )
    assert (
        context.model_bundle_sha256
        == hashlib.sha256(b"spread-sha:total-sha").hexdigest()
    )


def test_publication_manifest_counts_hashes_and_refs():
    features = _features().rename(columns={"game_id": "id"})
    results = pd.DataFrame(
        [
            {
                "home_team_spread_line": -3.0,
                "total_line": 50.0,
                "Spread Prediction": 2.0,
                "Total Prediction": 51.0,
            }
        ]
    )
    manifest = build_publication_manifest(
        results,
        state="preview",
        data_as_of="2026-09-01T00:00:00Z",
        feature_snapshot_uri="features.csv",
        feature_snapshot_sha256="feature-sha",
        code_sha="code",
        config_bytes=b"config",
        model_context=InferenceModelContext(
            bundle=None, bundle_version=None, model_bundle_sha256="model-sha"
        ),
        prepared_inputs=PreparedInferenceInputs(
            features=features, dataset_refs=({"dataset": "gold"},)
        ),
        source_config="conf/test.yaml",
        system_name="CKsPicks",
        model_id="v4",
    )
    assert manifest["config_sha"] == hashlib.sha256(b"config").hexdigest()
    assert manifest["lined_games"] == manifest["predicted_games"] == 1
    assert manifest["input_dataset_refs"] == [{"dataset": "gold"}]
