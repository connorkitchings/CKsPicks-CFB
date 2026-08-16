"""Five-gate, target/regime model promotion evaluation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from cks_picks_cfb.models.market_grading import american_profit_per_unit


def _bet_returns(
    actual: np.ndarray,
    prediction: np.ndarray,
    line: np.ndarray,
    *,
    target: str,
    edge_threshold: float,
    prices: np.ndarray | None = None,
) -> np.ndarray:
    market = -line if target == "spread" else line
    edge = prediction - market
    outcome = actual - market
    eligible = np.isfinite(line) & (np.abs(edge) >= edge_threshold)
    returns = np.zeros(int(eligible.sum()), dtype=float)
    settled_outcome = outcome[eligible]
    wins = np.sign(edge[eligible]) == np.sign(settled_outcome)
    prices = prices[eligible] if prices is not None else np.full(len(returns), np.nan)
    returns[wins] = [american_profit_per_unit(price) for price in prices[wins]]
    returns[(~wins) & (settled_outcome != 0)] = -1.0
    return returns


def select_nested_temporal_thresholds(
    frame: pd.DataFrame,
    *,
    edge_column: str = "edge",
    return_column: str = "return",
    threshold_grid: tuple[float, ...] = tuple(np.arange(0.0, 10.5, 0.5)),
    min_tuning_bets: int = 30,
    years: tuple[int, ...] = (2022, 2023, 2024),
) -> pd.DataFrame:
    """Cross-fit edge thresholds without using a season's own outcomes.

    The first selection season remains ungraded because no preceding OOF
    history exists.  Each later season uses all prior selection seasons to
    choose the threshold by net units, then volume, then lower threshold.
    """
    required = {"season", edge_column, return_column}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Threshold frame is missing columns: {missing}")
    result = frame.copy()
    result["selected_edge_threshold"] = np.nan
    result["threshold_eligible"] = False
    for year in years:
        history = result[result["season"].astype(int).isin([item for item in years if item < year])]
        current = result[result["season"].astype(int) == year]
        if history.empty or current.empty:
            continue
        candidates: list[tuple[float, float, int]] = []
        for threshold in threshold_grid:
            rows = history[history[edge_column].abs() >= threshold]
            if len(rows) < min_tuning_bets:
                continue
            candidates.append((float(rows[return_column].sum()), float(threshold), len(rows)))
        if not candidates:
            continue
        # Net units desc, volume desc, threshold asc.
        _, threshold, _ = sorted(candidates, key=lambda item: (-item[0], -item[2], item[1]))[0]
        mask = result["season"].astype(int) == year
        result.loc[mask, "selected_edge_threshold"] = threshold
        result.loc[mask, "threshold_eligible"] = result.loc[mask, edge_column].abs() >= threshold
    return result


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
    candidate_prices = pd.to_numeric(
        rows.get("candidate_price", pd.Series(np.nan, index=rows.index)), errors="coerce"
    ).to_numpy(dtype=float)
    baseline_prices = pd.to_numeric(
        rows.get("baseline_price", pd.Series(np.nan, index=rows.index)), errors="coerce"
    ).to_numpy(dtype=float)

    candidate_error = np.abs(candidate - actual)
    baseline_error = np.abs(baseline - actual)
    candidate_returns = _bet_returns(
        actual,
        candidate,
        lines,
        target=target,
        edge_threshold=edge_threshold,
        prices=candidate_prices,
    )
    baseline_returns = _bet_returns(
        actual,
        baseline,
        lines,
        target=target,
        edge_threshold=edge_threshold,
        prices=baseline_prices,
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
    candidate_roi_lower_95 = 0.0
    if candidate_returns.size:
        roi_samples = np.array(
            [
                candidate_returns[rng.integers(0, candidate_returns.size, candidate_returns.size)].mean()
                for _ in range(n_bootstrap)
            ]
        )
        candidate_roi_lower_95 = float(np.quantile(roi_samples, 0.025))

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
        "roi_bootstrap_95": candidate_roi_lower_95 > 0.0,
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
            "candidate_roi_lower_95": candidate_roi_lower_95,
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
    for name in (
        "direct_ridge",
        "points_ridge",
        "blend",
        "direct_catboost",
        "points_catboost",
    ):
        if name in tied:
            return name
    return min(tied)
