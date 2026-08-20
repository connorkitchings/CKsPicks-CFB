import json

import pandas as pd
import pytest

from scripts.pipeline.extract_model_accuracy import (
    champion_selection_metrics,
    distill,
    locked_baseline_metrics_from_csv,
    locked_metrics,
)


def _selection_report() -> dict:
    return {
        "spread": {
            "game_1": {
                "blend": {
                    "metrics": {
                        "baseline_mae": 17.4,
                        "candidate_mae": 17.4,
                        "sample_count": 243,
                        "seasonal": [
                            {
                                "season": 2022,
                                "baseline_mae": 16.3,
                                "candidate_mae": 16.3,
                            },
                            {
                                "season": 2023,
                                "baseline_mae": 17.4,
                                "candidate_mae": 17.4,
                            },
                            {
                                "season": 2024,
                                "baseline_mae": 18.4,
                                "candidate_mae": 18.4,
                            },
                        ],
                    }
                },
                "direct_catboost": {
                    "metrics": {
                        "baseline_mae": 17.4,
                        "candidate_mae": 15.98,
                        "sample_count": 243,
                        "seasonal": [
                            {
                                "season": 2022,
                                "baseline_mae": 16.3,
                                "candidate_mae": 16.7,
                            },
                            {
                                "season": 2023,
                                "baseline_mae": 17.4,
                                "candidate_mae": 14.6,
                            },
                            {
                                "season": 2024,
                                "baseline_mae": 18.4,
                                "candidate_mae": 16.4,
                            },
                        ],
                    }
                },
            }
        },
        "total": {
            "game_1": {
                "direct_ridge": {
                    "metrics": {
                        "baseline_mae": 15.16,
                        "candidate_mae": 14.4,
                        "sample_count": 243,
                        "seasonal": [
                            {
                                "season": 2022,
                                "baseline_mae": 15.0,
                                "candidate_mae": 14.0,
                            },
                            {
                                "season": 2023,
                                "baseline_mae": 15.1,
                                "candidate_mae": 14.1,
                            },
                            {
                                "season": 2024,
                                "baseline_mae": 15.2,
                                "candidate_mae": 14.2,
                            },
                        ],
                    }
                }
            }
        },
    }


def _routing_report() -> dict:
    return {
        "routing": {
            "spread": {
                "game_1": "direct_catboost",
                "game_2": "baseline",
                "game_3": "baseline",
                "game_4": "baseline",
            },
            "total": {
                "game_1": "baseline",
                "game_2": "blend",
                "game_3": "blend",
                "game_4": "blend",
            },
        },
        "selection_report": {
            "selection_design_sha": "a" * 64,
            "reports": _selection_report(),
        },
        "locked_2025_reports": {
            "spread": {
                "game_1": {
                    "candidate": "direct_catboost",
                    "locked_test_pass": True,
                    "report": {
                        "metrics": {
                            "baseline_mae": 14.55,
                            "candidate_mae": 15.156,
                            "sample_count": 83,
                            "seasonal": [
                                {
                                    "season": 2025,
                                    "baseline_mae": 14.55,
                                    "candidate_mae": 15.156,
                                }
                            ],
                        }
                    },
                }
            },
            "total": {"game_1": {"candidate": "baseline", "locked_test_pass": True}},
        },
    }


def _locked_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "season": [2025] * 4,
            "game_id": [1, 1, 2, 3],
            "target": ["total", "spread", "total", "total"],
            "regime": ["game_1"] * 4,
            "candidate_stage": ["locked"] * 4,
            "baseline_prediction": [50.0, 3.0, 44.0, 55.0],
            "actual": [40.0, 7.0, 50.0, 53.0],
        }
    )


def _manifest() -> dict:
    return {
        "bundle_id": "test-bundle",
        "promotion_reports": {
            "game_ordinal_predictive_routing": "artifacts/preview/refs/test.json"
        },
    }


def test_champion_selection_metrics_for_candidate_champion():
    block = champion_selection_metrics(
        _selection_report(), "spread", "game_1", "direct_catboost"
    )
    assert block["mae"] == 15.98
    assert block["n"] == 243
    assert block["seasons"]["2023"] == 14.6


def test_champion_selection_metrics_for_baseline_champion_reads_baseline():
    block = champion_selection_metrics(
        _selection_report(), "total", "game_1", "baseline"
    )
    assert block["mae"] == 15.16
    assert block["n"] == 243
    assert block["seasons"]["2024"] == 15.2


def test_locked_metrics_prefers_report_block():
    block = locked_metrics(
        _routing_report()["locked_2025_reports"], "spread", "game_1", "direct_catboost"
    )
    assert block == {"mae": 15.16, "n": 83}


def test_locked_baseline_metrics_from_csv_dedups_and_computes_mae():
    block = locked_baseline_metrics_from_csv(_locked_frame(), "total", "game_1")
    # games 1..3 -> errors 10, 6, 2 -> mean 6.0
    assert block == {"mae": 6.0, "n": 3}


def test_locked_baseline_metrics_from_csv_rejects_inconsistent_predictions():
    frame = _locked_frame()
    frame.loc[3, "baseline_prediction"] = 99.0
    frame.loc[3, "game_id"] = 1
    with pytest.raises(ValueError, match="Inconsistent baseline"):
        locked_baseline_metrics_from_csv(frame, "total", "game_1")


def test_distill_builds_all_routes_with_provenance():
    payload = distill(
        _manifest(), _routing_report(), _locked_frame(), manifest_sha256="b" * 64
    )
    assert payload["schema_version"] == "model_accuracy_v1"
    assert payload["bundle_id"] == "test-bundle"
    assert payload["manifest_sha256"] == "b" * 64
    assert payload["selection_design_sha"] == "a" * 64
    assert sorted(payload["routes"]) == ["game_1", "game_2", "game_3", "game_4"]

    spread_g1 = payload["routes"]["game_1"]["spread"]
    assert spread_g1["champion"] == "direct_catboost"
    assert spread_g1["selection"]["mae"] == 15.98
    assert spread_g1["locked_2025"] == {"mae": 15.16, "n": 83}

    total_g1 = payload["routes"]["game_1"]["total"]
    assert total_g1["champion"] == "baseline"
    assert total_g1["selection"]["mae"] == 15.16
    assert total_g1["locked_2025"] == {"mae": 6.0, "n": 3}

    # Routes absent from the fixture reports yield null selection metrics.
    assert payload["routes"]["game_2"]["spread"]["selection"] is None
    assert json.dumps(payload)  # payload is JSON-serializable
