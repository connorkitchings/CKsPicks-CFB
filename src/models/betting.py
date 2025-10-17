"""Utilities for betting policy and bet sizing."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm


def _american_to_b(odds: float | int) -> float:
    odds = float(odds)
    if odds > 0:
        return odds / 100.0
    if odds < 0:
        return 100.0 / abs(odds)
    return 0.0


def _calculate_kelly_fraction(
    win_prob: float, american_odds: int, kelly_fraction: float, kelly_cap: float
) -> float:
    b = _american_to_b(american_odds)
    p = win_prob
    q = 1 - p
    # c = kelly cap
    # f = fractional kelly
    # Full kelly is (b*p - q) / b
    full_kelly = (b * p - q) / b
    capped_kelly = min(full_kelly, kelly_cap)
    return max(0.0, capped_kelly * kelly_fraction)


def apply_betting_policy(
    predictions_df: pd.DataFrame,
    *,
    spread_edge_threshold: float = 5.0,
    total_edge_threshold: float = 5.5,
    spread_std_dev_threshold: float | None = None,
    total_std_dev_threshold: float | None = None,
    min_games_played: int = 2,
    fractional_kelly: float = 0.25,
    kelly_cap: float = 0.25,
    base_unit_fraction: float = 0.02,
    default_american_price: int = -110,
    single_bet_cap: float = 0.05,
) -> pd.DataFrame:
    df = predictions_df.copy()
    df["expected_home_margin"] = -df["home_team_spread_line"]
    df["edge_spread"] = (df["predicted_spread"] - df["expected_home_margin"]).abs()
    df["edge_total"] = (df["predicted_total"] - df["total_line"]).abs()
    df["spread_bet_reason"] = "Bet Placed"
    df["total_bet_reason"] = "Bet Placed"
    home_count = (
        df.get("home_fbs_games_played")
        if "home_fbs_games_played" in df.columns
        else df.get("home_games_played", 0)
    )
    away_count = (
        df.get("away_fbs_games_played")
        if "away_fbs_games_played" in df.columns
        else df.get("away_games_played", 0)
    )
    ineligible_games = (home_count < min_games_played) | (away_count < min_games_played)
    df.loc[ineligible_games, ["spread_bet_reason", "total_bet_reason"]] = (
        "No Bet - Min Games"
    )
    eligible_mask = ~ineligible_games
    if spread_std_dev_threshold is not None:
        low_conf_spread = df["predicted_spread_std_dev"] > spread_std_dev_threshold
        df.loc[eligible_mask & low_conf_spread, "spread_bet_reason"] = (
            "No Bet - Low Confidence"
        )
    if total_std_dev_threshold is not None:
        low_conf_total = df["predicted_total_std_dev"] > total_std_dev_threshold
        df.loc[eligible_mask & low_conf_total, "total_bet_reason"] = (
            "No Bet - Low Confidence"
        )
    small_edge_spread = df["edge_spread"] < spread_edge_threshold
    df.loc[eligible_mask & small_edge_spread, "spread_bet_reason"] = (
        "No Bet - Small Edge"
    )
    small_edge_total = df["edge_total"] < total_edge_threshold
    df.loc[eligible_mask & small_edge_total, "total_bet_reason"] = "No Bet - Small Edge"
    df["bet_spread"] = "none"
    spread_bet_mask = df["spread_bet_reason"] == "Bet Placed"
    df.loc[spread_bet_mask, "bet_spread"] = np.where(
        df.loc[spread_bet_mask, "predicted_spread"]
        > df.loc[spread_bet_mask, "expected_home_margin"],
        "home",
        "away",
    )
    df["bet_total"] = "none"
    total_bet_mask = df["total_bet_reason"] == "Bet Placed"
    df.loc[total_bet_mask, "bet_total"] = np.where(
        df.loc[total_bet_mask, "predicted_total"]
        > df.loc[total_bet_mask, "total_line"],
        "over",
        "under",
    )

    # Kelly Criterion Calculations
    # Spread
    win_prob_spread = pd.Series(
        norm.cdf(
            df["predicted_spread"],
            loc=df["expected_home_margin"],
            scale=df["predicted_spread_std_dev"],
        ),
        index=df.index,
    )
    df["kelly_fraction_spread"] = win_prob_spread.combine(
        df["bet_spread"],
        lambda p, b: _calculate_kelly_fraction(
            p if b == "home" else 1 - p,
            default_american_price,
            fractional_kelly,
            kelly_cap,
        ),
    )
    df.loc[df["bet_spread"] == "none", "kelly_fraction_spread"] = 0.0

    # Total
    win_prob_total = pd.Series(
        norm.cdf(
            df["predicted_total"],
            loc=df["total_line"],
            scale=df["predicted_total_std_dev"],
        ),
        index=df.index,
    )
    df["kelly_fraction_total"] = win_prob_total.combine(
        df["bet_total"],
        lambda p, b: _calculate_kelly_fraction(
            p if b == "over" else 1 - p,
            default_american_price,
            fractional_kelly,
            kelly_cap,
        ),
    )
    df.loc[df["bet_total"] == "none", "kelly_fraction_total"] = 0.0

    # Bet Units
    df["bet_units_spread"] = (df["kelly_fraction_spread"] / base_unit_fraction).round(2)
    df["bet_units_total"] = (df["kelly_fraction_total"] / base_unit_fraction).round(2)
    df["bet_units"] = df["bet_units_spread"] + df["bet_units_total"]

    return df
