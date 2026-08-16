import numpy as np
import pandas as pd

from cks_picks_cfb.models.predictive_evaluation import (
    evaluate_predictive_candidate,
    locked_predictive_anti_regression,
    select_predictive_candidate,
    select_predictive_route,
)


def _frame(candidate_offset: float = 0.0) -> pd.DataFrame:
    actual = np.tile(np.arange(60, dtype=float), 3)
    return pd.DataFrame(
        {
            "season": np.repeat([2022, 2023, 2024], 60),
            "actual": actual,
            "candidate_prediction": actual + candidate_offset,
            "baseline_prediction": actual + 2.0,
        }
    )


def test_predictive_evaluation_needs_no_market_line_and_reports_all_gates():
    report = evaluate_predictive_candidate(
        _frame(), target="spread", regime="game_1", n_bootstrap=200
    )
    assert report["promotion_pass"] is True
    assert report["metrics"]["sample_count"] == 180
    assert report["metrics"]["paired_mae_lift_lower_95"] > 0
    assert report["metrics"]["better_seasons"] == 3


def test_predictive_selection_prefers_simpler_candidate_inside_mae_tie():
    reports = {
        "direct_ridge": {"promotion_pass": True, "metrics": {"candidate_mae": 10.05}},
        "points_catboost": {"promotion_pass": True, "metrics": {"candidate_mae": 10.0}},
    }
    assert select_predictive_candidate(reports) == "direct_ridge"


def test_route_selection_keeps_baseline_inside_declared_tie_band():
    reports = {
        "direct_ridge": {
            "promotion_pass": True,
            "metrics": {"candidate_mae": 9.9, "baseline_mae": 10.0},
        }
    }
    assert select_predictive_route(reports) == "baseline"


def test_locked_guard_reverts_only_for_material_regression():
    report = {
        "metrics": {
            "candidate_mae": 11.0,
            "baseline_mae": 10.0,
            "candidate_rmse": 12.0,
            "baseline_rmse": 11.0,
            "candidate_bias": 0.5,
            "baseline_bias": 0.5,
        }
    }
    assert locked_predictive_anti_regression(report)
    report["metrics"]["candidate_mae"] = 11.01
    assert not locked_predictive_anti_regression(report)
