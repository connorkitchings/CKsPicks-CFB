"""Prediction calibration utilities.

Provides helpers to compute and apply simple week-of-season bias corrections
for spread and total predictions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd


@dataclass
class BiasModel:
    target: Literal["spread", "total"]
    by_week: pd.DataFrame  # columns: week, bias


def compute_weekly_bias(
    df: pd.DataFrame,
    *,
    target_col: str,
    pred_col: str,
    week_col: str = "week",
) -> pd.DataFrame:
    """Compute mean residual (y - yhat) per week.

    Args:
        df: DataFrame with actuals and predictions
        target_col: column name for actual values (e.g., spread_target)
        pred_col: column name for predictions (e.g., predicted_spread)
        week_col: week-of-season column name

    Returns:
        DataFrame with columns [week, bias] where bias = mean(y - yhat)
    """
    tmp = df[[week_col, target_col, pred_col]].dropna().copy()
    tmp["residual"] = tmp[target_col].astype(float) - tmp[pred_col].astype(float)
    by_week = (
        tmp.groupby(week_col)["residual"]
        .mean()
        .reset_index()
        .rename(columns={"residual": "bias"})
    )
    by_week[week_col] = by_week[week_col].astype(int)
    return by_week


def apply_weekly_bias(
    df: pd.DataFrame,
    by_week: pd.DataFrame,
    *,
    pred_col: str,
    out_col: str,
    week_col: str = "week",
) -> pd.DataFrame:
    """Apply week-of-season bias: calibrated = pred + bias_week."""
    out = df.copy()
    out = out.merge(
        by_week.rename(columns={"bias": "_bias_tmp"}), on=week_col, how="left"
    )
    out[out_col] = out[pred_col] + out["_bias_tmp"].fillna(0.0)
    out = out.drop(columns=["_bias_tmp"])  # cleanup
    return out
