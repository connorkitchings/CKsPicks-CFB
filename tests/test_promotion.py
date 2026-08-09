import numpy as np
import pandas as pd

from cks_picks_cfb.models.promotion import (
    evaluate_promotion,
    locked_test_anti_regression,
    select_regime_candidate,
    select_simplest_passing_candidate,
)


def test_five_gate_report_and_simple_candidate_preference():
    actual = np.tile(np.arange(50, dtype=float), 3)
    frame = pd.DataFrame(
        {
            "season": np.repeat([2022, 2023, 2024], 50),
            "actual": actual,
            "candidate_prediction": actual,
            "baseline_prediction": actual + 3.0,
            "market_line": np.full(150, -50.0),
        }
    )
    report = evaluate_promotion(
        frame, target="spread", regime="two_games", n_bootstrap=200
    )
    assert report["gates"]["minimum_volume"] is True
    assert report["gates"]["bootstrap_95"] is True
    assert report["gates"]["temporal_stability"] is True
    assert select_simplest_passing_candidate(
        {"ridge": report, "catboost": {"promotion_pass": True}}
    ) == ("ridge" if report["promotion_pass"] else "catboost")


def test_underpowered_regime_stays_display_only():
    frame = pd.DataFrame(
        {
            "season": [2024] * 20,
            "actual": np.arange(20, dtype=float),
            "candidate_prediction": np.arange(20, dtype=float),
            "baseline_prediction": np.arange(20, dtype=float) + 1,
            "market_line": [0.0] * 20,
        }
    )
    report = evaluate_promotion(
        frame, target="total", regime="one_game", n_bootstrap=100
    )
    assert report["gates"]["minimum_volume"] is False
    assert report["promotion_pass"] is False
    assert select_simplest_passing_candidate({"ridge": report}) is None


def test_candidate_selection_uses_mae_then_simplicity_tie_break():
    reports = {
        "direct_ridge": {
            "promotion_pass": True,
            "metrics": {"candidate_mae": 10.05},
        },
        "blend": {"promotion_pass": True, "metrics": {"candidate_mae": 10.0}},
        "direct_catboost": {
            "promotion_pass": True,
            "metrics": {"candidate_mae": 9.0},
        },
    }
    assert select_regime_candidate(reports) == "direct_catboost"
    reports["direct_catboost"]["metrics"]["candidate_mae"] = 10.02
    assert select_regime_candidate(reports) == "direct_ridge"


def test_locked_test_does_not_require_one_hundred_single_year_bets():
    report = {
        "metrics": {
            "candidate_mae": 10.0,
            "baseline_mae": 10.0,
            "candidate_calibration": 0.5,
            "baseline_calibration": 0.5,
            "candidate_max_drawdown": 4.0,
            "baseline_max_drawdown": 4.0,
            "candidate_volume": 60,
            "baseline_volume": 60,
        }
    }
    assert locked_test_anti_regression(report)
