"""
Utilities for scoring and settling bets against actual outcomes.
"""

from __future__ import annotations

import pandas as pd


def settle_spread_bets(df: pd.DataFrame) -> pd.DataFrame:
    """
    Scores spread bets against actual game outcomes.

    Expects a DataFrame with the following columns:
    - home_points, away_points: The final score.
    - home_team_spread_line: The spread line from the home team's perspective.
    - bet_spread: The side bet on ('home' or 'away').

    Returns:
        The DataFrame with a new 'spread_bet_result' column containing
        'Win', 'Loss', 'Push', or 'No Bet'.
    """
    df = df.copy()

    def score_row(row):
        if row.get("bet_spread") not in ("home", "away"):
            return "No Bet"
        if pd.isna(row.get("home_points")) or pd.isna(row.get("away_points")):
            return "Pending"

        actual_margin = float(row["home_points"]) - float(row["away_points"])
        expected_margin = -float(row["home_team_spread_line"])

        if row["bet_spread"] == "home":
            if actual_margin > expected_margin:
                return "Win"
            if actual_margin < expected_margin:
                return "Loss"
            return "Push"
        if row["bet_spread"] == "away":
            if actual_margin < expected_margin:
                return "Win"
            if actual_margin > expected_margin:
                return "Loss"
            return "Push"
        return "No Bet"

    df["spread_bet_result"] = df.apply(score_row, axis=1)
    return df


def settle_total_bets(df: pd.DataFrame) -> pd.DataFrame:
    """
    Scores total bets against actual game outcomes.

    Expects a DataFrame with the following columns:
    - home_points, away_points: The final score.
    - total_line: The over/under line.
    - bet_total: The side bet on ('over' or 'under').

    Returns:
        The DataFrame with a new 'total_bet_result' column containing
        'Win', 'Loss', 'Push', or 'No Bet'.
    """
    df = df.copy()

    def score_row(row):
        if row.get("bet_total") not in ("over", "under"):
            return "No Bet"
        if pd.isna(row.get("home_points")) or pd.isna(row.get("away_points")):
            return "Pending"

        actual_total = float(row["home_points"]) + float(row["away_points"])
        total_line = float(row["total_line"])

        if row["bet_total"] == "over":
            if actual_total > total_line:
                return "Win"
            if actual_total < total_line:
                return "Loss"
            return "Push"
        if row["bet_total"] == "under":
            if actual_total < total_line:
                return "Win"
            if actual_total > total_line:
                return "Loss"
            return "Push"
        return "No Bet"

    df["total_bet_result"] = df.apply(score_row, axis=1)
    return df
