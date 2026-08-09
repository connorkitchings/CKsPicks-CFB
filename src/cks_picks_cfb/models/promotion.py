"""Five-gate, target/regime model promotion evaluation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd


def _bet_returns(
    actual: np.ndarray,
    prediction: np.ndarray,
    line: np.ndarray,
    *,
    target: str,
    edge_threshold: float,
) -> np.ndarray:
    market = -line if target == "spread" else line
    edge = prediction - market
    outcome = actual - market
    eligible = np.isfinite(line) & (np.abs(edge) >= edge_threshold) & (outcome != 0)
    wins = np.sign(edge[eligible]) == np.sign(outcome[eligible])
    return np.where(wins, 1.0 / 1.1, -1.0)


def _max_drawdown(returns: np.ndarray) -> float:
    if returns.size == 0:
        return 0.0
    equity = np.cumsum(returns)
    peaks = np.maximum.accumulate(np.insert(equity, 0, 0.0))[1:]
    return float(np.max(peaks - equity))


def evaluate_promotion(
    frame: pd.DataFrame,
    *,
    target: str,
    regime: str,
    edge_threshold: float = 0.0,
    n_bootstrap: int = 1000,
    random_seed: int = 42,
) -> dict[str, Any]:
    """Evaluate one target/regime candidate against a frozen baseline.

    Required columns are ``season``, ``actual``, ``candidate_prediction``,
    ``baseline_prediction``, and ``market_line``. Callers must supply only
    genuine out-of-fold or locked-holdout rows.
    """
    if target not in {"spread", "total"}:
        raise ValueError("target must be spread or total")
    required = {
        "season",
        "actual",
        "candidate_prediction",
        "baseline_prediction",
        "market_line",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Promotion frame is missing columns: {missing}")
    rows = frame.dropna(
        subset=["season", "actual", "candidate_prediction", "baseline_prediction"]
    ).copy()
    if rows.empty:
        raise ValueError("Promotion frame has no graded prediction rows")
    actual = rows["actual"].to_numpy(dtype=float)
    candidate = rows["candidate_prediction"].to_numpy(dtype=float)
    baseline = rows["baseline_prediction"].to_numpy(dtype=float)
    lines = pd.to_numeric(rows["market_line"], errors="coerce").to_numpy(dtype=float)

    candidate_error = np.abs(candidate - actual)
    baseline_error = np.abs(baseline - actual)
    candidate_returns = _bet_returns(
        actual, candidate, lines, target=target, edge_threshold=edge_threshold
    )
    baseline_returns = _bet_returns(
        actual, baseline, lines, target=target, edge_threshold=edge_threshold
    )
    candidate_mae = float(candidate_error.mean())
    baseline_mae = float(baseline_error.mean())
    candidate_rmse = float(np.sqrt(np.mean((candidate - actual) ** 2)))
    baseline_rmse = float(np.sqrt(np.mean((baseline - actual) ** 2)))
    candidate_roi = float(candidate_returns.mean()) if candidate_returns.size else 0.0
    baseline_roi = float(baseline_returns.mean()) if baseline_returns.size else 0.0
    candidate_hit = (
        float((candidate_returns > 0).mean()) if candidate_returns.size else 0.0
    )
    baseline_hit = (
        float((baseline_returns > 0).mean()) if baseline_returns.size else 0.0
    )

    rng = np.random.default_rng(random_seed)
    bootstrap_lifts = np.empty(n_bootstrap)
    for index in range(n_bootstrap):
        sample = rng.integers(0, len(rows), len(rows))
        bootstrap_lifts[index] = (
            baseline_error[sample].mean() - candidate_error[sample].mean()
        )
    bootstrap_confidence = float((bootstrap_lifts > 0).mean())

    seasonal = (
        rows.assign(candidate_error=candidate_error, baseline_error=baseline_error)
        .groupby("season")[["candidate_error", "baseline_error"]]
        .mean()
    )
    stable_seasons = int(
        (seasonal["candidate_error"] <= seasonal["baseline_error"]).sum()
    )
    temporal_stability = stable_seasons >= max(1, int(np.ceil(len(seasonal) * 0.75)))

    candidate_calibration = abs(float(np.mean(candidate - actual)))
    baseline_calibration = abs(float(np.mean(baseline - actual)))
    candidate_drawdown = _max_drawdown(candidate_returns)
    baseline_drawdown = _max_drawdown(baseline_returns)
    no_degradation = all(
        (
            candidate_mae <= baseline_mae * 1.10,
            candidate_calibration <= max(baseline_calibration, 0.1) * 1.10,
            candidate_returns.size >= baseline_returns.size * 0.90,
            candidate_drawdown <= max(baseline_drawdown, 1.0) * 1.10,
        )
    )
    gates = {
        "meaningful_lift": (
            baseline_mae - candidate_mae >= 0.10
            or candidate_roi - baseline_roi >= 0.015
            or candidate_hit - baseline_hit >= 0.02
        ),
        "minimum_volume": candidate_returns.size >= 100,
        "bootstrap_95": bootstrap_confidence >= 0.95,
        "temporal_stability": temporal_stability,
        "no_degradation": no_degradation,
    }
    return {
        "target": target,
        "regime": regime,
        "metrics": {
            "candidate_mae": candidate_mae,
            "baseline_mae": baseline_mae,
            "candidate_rmse": candidate_rmse,
            "baseline_rmse": baseline_rmse,
            "candidate_roi": candidate_roi,
            "baseline_roi": baseline_roi,
            "candidate_hit_rate": candidate_hit,
            "baseline_hit_rate": baseline_hit,
            "candidate_volume": int(candidate_returns.size),
            "baseline_volume": int(baseline_returns.size),
            "candidate_calibration": candidate_calibration,
            "baseline_calibration": baseline_calibration,
            "candidate_max_drawdown": candidate_drawdown,
            "baseline_max_drawdown": baseline_drawdown,
            "bootstrap_confidence": bootstrap_confidence,
            "stable_seasons": stable_seasons,
            "season_count": int(len(seasonal)),
        },
        "gates": gates,
        "promotion_pass": all(gates.values()),
    }


def select_simplest_passing_candidate(
    reports: Mapping[str, Mapping[str, Any]],
) -> str | None:
    """Prefer Ridge when it passes, otherwise CatBoost, else display fallback."""
    for candidate in ("ridge", "catboost"):
        if reports.get(candidate, {}).get("promotion_pass") is True:
            return candidate
    return None


def locked_test_anti_regression(
    report: Mapping[str, Any], *, max_degradation: float = 0.10
) -> bool:
    """Apply the locked-year guard without imposing a yearly volume gate."""
    metrics = report["metrics"]
    return all(
        (
            metrics["candidate_mae"]
            <= metrics["baseline_mae"] * (1.0 + max_degradation),
            metrics["candidate_calibration"]
            <= max(metrics["baseline_calibration"], 0.1) * (1.0 + max_degradation),
            metrics["candidate_max_drawdown"]
            <= max(metrics["baseline_max_drawdown"], 1.0) * (1.0 + max_degradation),
            metrics["candidate_volume"] >= metrics["baseline_volume"] * 0.90,
        )
    )


def select_regime_candidate(
    reports: Mapping[str, Mapping[str, Any]], *, mae_tolerance: float = 0.10
) -> str | None:
    """Choose by OOF MAE, preferring operational simplicity inside a tie band."""
    passing = {
        name: report
        for name, report in reports.items()
        if report.get("promotion_pass") is True
    }
    if not passing:
        return None
    best_mae = min(
        float(report["metrics"]["candidate_mae"]) for report in passing.values()
    )
    tied = {
        name
        for name, report in passing.items()
        if float(report["metrics"]["candidate_mae"]) <= best_mae + mae_tolerance
    }
    for name in ("direct_ridge", "blend", "direct_catboost"):
        if name in tied:
            return name
    return min(tied)
