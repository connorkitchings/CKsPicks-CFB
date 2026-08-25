"""Outcome-only historical evaluation for the frozen Phase 3 baseline."""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd

from cks_picks_cfb.ratings.contracts import MeasurementContractError


def _metrics(rows: pd.DataFrame) -> dict[str, float]:
    error = rows["prediction_mean"].to_numpy(float) - rows["actual"].to_numpy(float)
    sd = rows["prediction_sd"].to_numpy(float)
    standardized = error / sd
    return {
        "count": int(len(rows)),
        "mae": float(np.abs(error).mean()),
        "rmse": float(np.sqrt(np.mean(error**2))),
        "bias": float(error.mean()),
        "abs_standardized_residual_mean": float(abs(standardized.mean())),
        "standardized_residual_sd": float(standardized.std(ddof=1)),
        "interval_80_coverage": float(
            (
                (rows.actual >= rows.interval_80_lower)
                & (rows.actual <= rows.interval_80_upper)
            ).mean()
        ),
        "interval_95_coverage": float(
            (
                (rows.actual >= rows.interval_95_lower)
                & (rows.actual <= rows.interval_95_upper)
            ).mean()
        ),
        "normal_log_score": float(
            np.mean(0.5 * np.log(2 * np.pi * sd**2) + 0.5 * standardized**2)
        ),
    }


def evaluate_predictions(
    *, predictions: pd.DataFrame, v4: pd.DataFrame, gates: Mapping[str, Any]
) -> dict[str, Any]:
    required = {
        "season",
        "game_id",
        "target",
        "actual",
        "prediction_mean",
        "prediction_sd",
    }
    if missing := sorted(required - set(predictions.columns)):
        raise MeasurementContractError(
            f"Prediction evaluation missing columns: {missing}"
        )
    candidate = predictions.dropna(subset=["actual"]).copy()
    if len(candidate) != len(predictions):
        raise MeasurementContractError(
            "Historical prediction evaluation contains missing completed outcomes"
        )
    candidate["v4_target"] = candidate["target"].replace({"margin": "spread"})
    paired = candidate.merge(
        v4[["season", "game_id", "target", "v4_prediction", "source_kind"]],
        left_on=["season", "game_id", "v4_target"],
        right_on=["season", "game_id", "target"],
        how="inner",
        suffixes=("", "_v4"),
        validate="one_to_one",
    )
    report: dict[str, Any] = {
        "report_schema_version": "rating_prediction_evaluation_v1",
        "coverage": {
            "candidate_rows": int(len(candidate)),
            "paired_v4_rows": int(len(paired)),
            "unpaired_candidate_rows": int(len(candidate) - len(paired)),
        },
        "targets": {},
    }
    rng = np.random.default_rng(int(gates["bootstrap_seed"]))
    for target in ("margin", "total"):
        rows = paired[paired["target"] == target].copy()
        if rows.empty:
            raise MeasurementContractError(f"No paired V4 rows for {target}")
        metric = _metrics(rows)
        v4_error = rows["v4_prediction"].to_numpy(float) - rows["actual"].to_numpy(
            float
        )
        v4_metric = {
            "mae": float(np.abs(v4_error).mean()),
            "rmse": float(np.sqrt(np.mean(v4_error**2))),
            "bias": float(v4_error.mean()),
        }
        lift = np.abs(v4_error) - np.abs(
            rows["prediction_mean"].to_numpy(float) - rows["actual"].to_numpy(float)
        )
        samples = np.array(
            [
                lift[rng.integers(0, len(lift), len(lift))].mean()
                for _ in range(int(gates["bootstrap_samples"]))
            ]
        )
        seasons = {
            str(int(season)): _metrics(values)
            for season, values in rows.groupby("season", observed=True)
        }
        seasonal_pass = all(
            value["mae"]
            <= float(gates["seasonal_mae_ratio"])
            * float(np.abs(v4_error[rows["season"].to_numpy() == int(season)]).mean())
            for season, value in seasons.items()
        )
        checks = {
            "paired_v4_coverage": len(rows)
            == len(candidate[candidate["target"] == target]),
            "pooled_mae": metric["mae"]
            <= float(gates["pooled_error_ratio"]) * v4_metric["mae"],
            "pooled_rmse": metric["rmse"]
            <= float(gates["pooled_error_ratio"]) * v4_metric["rmse"],
            "seasonal_mae": seasonal_pass,
            "bias": abs(metric["bias"]) <= float(gates["max_absolute_bias"])
            and abs(metric["bias"])
            <= abs(v4_metric["bias"]) + float(gates["max_bias_excess"]),
            "standardized_mean": metric["abs_standardized_residual_mean"]
            <= float(gates["max_abs_standardized_residual_mean"]),
            "standardized_sd": float(gates["standardized_residual_sd_min"])
            <= metric["standardized_residual_sd"]
            <= float(gates["standardized_residual_sd_max"]),
            "coverage_80": float(gates["interval_80_min"])
            <= metric["interval_80_coverage"]
            <= float(gates["interval_80_max"]),
            "coverage_95": float(gates["interval_95_min"])
            <= metric["interval_95_coverage"]
            <= float(gates["interval_95_max"]),
        }
        report["targets"][target] = {
            "candidate": metric,
            "v4": v4_metric,
            "seasonal": seasons,
            "paired_mae_lift_bootstrap_95": [
                float(np.quantile(samples, 0.025)),
                float(np.quantile(samples, 0.975)),
            ],
            "v4_source_kind_counts": {
                str(k): int(v) for k, v in rows["source_kind"].value_counts().items()
            },
            "checks": checks,
            "all_checks_passed": all(checks.values()),
        }
    report["all_checks_passed"] = all(
        value["all_checks_passed"] for value in report["targets"].values()
    )
    return report
