"""Nested rolling-origin residual calibration for V5-04B forecasts."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from cks_picks_cfb.forecast.heads import (
    FEATURES,
    HeadError,
    _fit_one,
    _target,
    select_inner_alpha,
)
from cks_picks_cfb.forecast.horizons import fitting_seasons


class CalibrationError(ValueError):
    """Raised when calibration evidence cannot support a variance estimate."""


@dataclass(frozen=True)
class CalibrationResult:
    records: pd.DataFrame
    variances: dict[str, dict[int, float]]


def calibrate_uncertainty(
    features: pd.DataFrame,
    *,
    horizon: str,
    development_seasons: tuple[int, ...],
    outer_seasons: tuple[int, ...],
    alpha_grid: tuple[float, ...],
    floor: float,
    residual_floor: float = 1e-6,
) -> CalibrationResult:
    """Compute per-target, per-season calibration variance from nested residuals.

    For each outer season S, generate earlier nested rolling-origin prediction
    residuals using the identical structural design, offset rule, and inner-alpha
    procedure. Require at least one eligible prior residual season; the first
    eligible residual season is 2017 (after 2015, 2016 fitting seasons). No
    current-validation residual or in-sample training error may substitute.

    Target variance is the mean squared prior prediction error, floor residual_floor.
    No extra bias correction or second calibration of the same residuals.
    """
    required = {
        "season",
        "actual_margin",
        "actual_total",
        "offset_margin",
        "offset_total",
        *FEATURES,
    }
    if missing := sorted(required - set(features)):
        raise CalibrationError(f"calibration frame lacks columns: {missing}")
    clean = (
        features.replace([np.inf, -np.inf], np.nan).dropna(subset=list(required)).copy()
    )
    records: list[dict[str, object]] = []
    variances: dict[str, dict[int, float]] = {"margin": {}, "total": {}}
    for target in ("margin", "total"):
        for season in outer_seasons:
            fit_seasons = fitting_seasons(season, development_seasons, horizon)
            residual_seasons = tuple(s for s in fit_seasons if s >= 2017)
            if len(residual_seasons) < 1:
                records.append(
                    {
                        "target": target,
                        "season": int(season),
                        "residual_count": 0,
                        "variance": float(residual_floor),
                        "fallback_reason": "no_prior_residuals",
                    }
                )
                variances[target][season] = float(residual_floor)
                continue
            all_residuals: list[float] = []
            for residual_season in residual_seasons:
                train_seasons = tuple(s for s in fit_seasons if s < residual_season)
                if len(train_seasons) < 2:
                    continue
                train = clean[clean["season"].isin(train_seasons)].copy()
                test = clean[clean["season"].eq(residual_season)].copy()
                if train.empty or test.empty:
                    continue
                selected_alpha, _ = select_inner_alpha(
                    train,
                    target=target,
                    seasons=train_seasons,
                    alpha_grid=alpha_grid,
                    floor=floor,
                )
                try:
                    predicted, _ = _fit_one(
                        train, test, target=target, alpha=selected_alpha, floor=floor
                    )
                except (HeadError, ValueError):
                    continue
                actual = _target(test, target).to_numpy(float)
                residuals = actual - predicted
                all_residuals.extend(residuals.tolist())
            if not all_residuals:
                records.append(
                    {
                        "target": target,
                        "season": int(season),
                        "residual_count": 0,
                        "variance": float(residual_floor),
                        "fallback_reason": "no_valid_residuals",
                    }
                )
                variances[target][season] = float(residual_floor)
            else:
                variance = max(
                    float(residual_floor), float(np.mean(np.square(all_residuals)))
                )
                records.append(
                    {
                        "target": target,
                        "season": int(season),
                        "residual_count": len(all_residuals),
                        "variance": variance,
                        "fallback_reason": "",
                    }
                )
                variances[target][season] = variance
    return CalibrationResult(
        records=pd.DataFrame.from_records(records),
        variances=variances,
    )
