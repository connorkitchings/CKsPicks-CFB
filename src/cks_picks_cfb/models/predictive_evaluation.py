"""Result-only model selection for canonical early-season routes.

This module deliberately has no market-line, price, or return inputs.  It is
the selection contract for a football prediction model; market evaluation is a
separate optional research concern in :mod:`cks_picks_cfb.models.promotion`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

PREDICTIVE_TIE_MAE = 0.10
PREDICTIVE_CANDIDATE_ORDER = (
    "baseline",
    "established",
    "blend",
    "direct_ridge",
    "points_ridge",
    "direct_catboost",
    "points_catboost",
)


def evaluate_predictive_candidate(
    frame: pd.DataFrame,
    *,
    target: str,
    regime: str,
    min_games: int = 150,
    min_mae_lift: float = 0.10,
    n_bootstrap: int = 2_000,
    random_seed: int = 42,
) -> dict[str, Any]:
    """Evaluate a candidate against a frozen baseline using game results only."""
    required = {"season", "actual", "candidate_prediction", "baseline_prediction"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Predictive evaluation frame is missing columns: {missing}")
    rows = frame.dropna(subset=sorted(required)).copy()
    if rows.empty:
        raise ValueError("Predictive evaluation frame has no complete rows")
    actual = rows["actual"].to_numpy(dtype=float)
    candidate = rows["candidate_prediction"].to_numpy(dtype=float)
    baseline = rows["baseline_prediction"].to_numpy(dtype=float)
    candidate_error = np.abs(candidate - actual)
    baseline_error = np.abs(baseline - actual)
    mae_lift = baseline_error - candidate_error
    candidate_mae = float(candidate_error.mean())
    baseline_mae = float(baseline_error.mean())
    candidate_rmse = float(np.sqrt(np.mean((candidate - actual) ** 2)))
    baseline_rmse = float(np.sqrt(np.mean((baseline - actual) ** 2)))
    candidate_bias = float(np.mean(candidate - actual))
    baseline_bias = float(np.mean(baseline - actual))

    rng = np.random.default_rng(random_seed)
    samples = np.empty(n_bootstrap, dtype=float)
    for index in range(n_bootstrap):
        sample = rng.integers(0, len(rows), len(rows))
        samples[index] = float(mae_lift[sample].mean())
    lift_lower_95, lift_upper_95 = np.quantile(samples, (0.025, 0.975))

    seasonal = (
        rows.assign(candidate_error=candidate_error, baseline_error=baseline_error)
        .groupby("season", observed=True)[["candidate_error", "baseline_error"]]
        .mean()
    )
    better_seasons = int(
        (seasonal["candidate_error"] < seasonal["baseline_error"]).sum()
    )
    gates = {
        "minimum_volume": len(rows) >= min_games,
        "meaningful_mae_lift": baseline_mae - candidate_mae >= min_mae_lift,
        "paired_bootstrap_lower_95": float(lift_lower_95) > 0.0,
        "rmse_within_guard": candidate_rmse <= baseline_rmse * 1.10,
        "bias_within_guard": abs(candidate_bias) <= abs(baseline_bias) * 1.10,
        "temporal_stability": better_seasons >= 2,
    }
    return {
        "target": target,
        "regime": regime,
        "metrics": {
            "candidate_mae": candidate_mae,
            "baseline_mae": baseline_mae,
            "mae_lift": baseline_mae - candidate_mae,
            "candidate_rmse": candidate_rmse,
            "baseline_rmse": baseline_rmse,
            "candidate_bias": candidate_bias,
            "baseline_bias": baseline_bias,
            "sample_count": int(len(rows)),
            "better_seasons": better_seasons,
            "season_count": int(len(seasonal)),
            "paired_mae_lift_lower_95": float(lift_lower_95),
            "paired_mae_lift_upper_95": float(lift_upper_95),
            "seasonal": [
                {
                    "season": int(season),
                    "candidate_mae": float(values["candidate_error"]),
                    "baseline_mae": float(values["baseline_error"]),
                }
                for season, values in seasonal.iterrows()
            ],
        },
        "gates": gates,
        "promotion_pass": all(gates.values()),
    }


def locked_predictive_anti_regression(
    report: Mapping[str, Any], *, max_degradation: float = 0.10
) -> bool:
    """Apply the preregistered result-only 2025 anti-regression guard."""
    metrics = report["metrics"]
    return all(
        (
            metrics["candidate_mae"]
            <= metrics["baseline_mae"] * (1.0 + max_degradation),
            metrics["candidate_rmse"]
            <= metrics["baseline_rmse"] * (1.0 + max_degradation),
            abs(metrics["candidate_bias"])
            <= abs(metrics["baseline_bias"]) * (1.0 + max_degradation),
        )
    )


def select_predictive_candidate(
    reports: Mapping[str, Mapping[str, Any]],
    *,
    tie_mae: float = PREDICTIVE_TIE_MAE,
) -> str | None:
    """Choose a passing result-only challenger with an explicit simplicity tie."""
    passing = {
        name: report
        for name, report in reports.items()
        if name != "baseline" and report.get("promotion_pass") is True
    }
    if not passing:
        return None
    best_mae = min(
        float(report["metrics"]["candidate_mae"]) for report in passing.values()
    )
    tied = {
        name: report
        for name, report in passing.items()
        if float(report["metrics"]["candidate_mae"]) <= best_mae + tie_mae
    }
    order = {name: index for index, name in enumerate(PREDICTIVE_CANDIDATE_ORDER)}
    return min(
        tied,
        key=lambda name: (
            order.get(name, len(order)),
            float(tied[name]["metrics"]["candidate_mae"]),
            name,
        ),
    )


def select_predictive_route(
    reports: Mapping[str, Mapping[str, Any]], *, tie_mae: float = PREDICTIVE_TIE_MAE
) -> str:
    """Choose a challenger or the baseline using the declared simplicity tie.

    A challenger must qualify first.  The baseline itself is always available
    and wins whenever it is within the declared MAE tie band of the best
    qualifying candidate.
    """
    champion = select_predictive_candidate(reports, tie_mae=tie_mae)
    if champion is None:
        return "baseline"
    challenger_mae = float(reports[champion]["metrics"]["candidate_mae"])
    baseline_mae = float(reports[champion]["metrics"]["baseline_mae"])
    return "baseline" if baseline_mae <= challenger_mae + tie_mae else champion
