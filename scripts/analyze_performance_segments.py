#!/usr/bin/env python3
"""
Analyze model performance across different segments.

This script loads a season of scored bets and analyzes performance:
1.  For spread bets: Favorite vs. Underdog.
2.  For all bets: Performance by week.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Add src to path for local imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.loader import load_scored_season_data
from src.config import REPORTS_DIR


def analyze_favorites_vs_underdogs(df: pd.DataFrame) -> pd.DataFrame:
    """Analyzes hit rate for bets on favorites vs. underdogs."""
    spread_bets = df[df["Spread Bet"].isin(["home", "away"])].copy()
    if spread_bets.empty:
        return pd.DataFrame()

    # Determine if the bet was on the favorite or underdog
    # Home team is favorite if home_team_spread_line < 0
    spread_bets["bet_on_favorite"] = np.where(
        (
            (spread_bets["Spread Bet"] == "home")
            & (spread_bets["home_team_spread_line"] < 0)
        )
        | (
            (spread_bets["Spread Bet"] == "away")
            & (spread_bets["home_team_spread_line"] > 0)
        ),
        True,
        False,
    )

    # Handle pick'ems (spread == 0)
    spread_bets.loc[spread_bets["home_team_spread_line"] == 0, "bet_on_favorite"] = (
        False  # Neither is a favorite
    )

    # Convert result to numeric
    spread_bets["win"] = (spread_bets["Spread Bet Result"] == "Win").astype(int)

    # Group and aggregate
    summary = (
        spread_bets.groupby("bet_on_favorite")["win"]
        .agg(["sum", "count"])
        .rename(columns={"sum": "wins", "count": "bets"})
    )
    summary["hit_rate"] = summary["wins"] / summary["bets"]
    summary = summary.reset_index().rename(columns={"bet_on_favorite": "Betting On"})
    summary["Betting On"] = summary["Betting On"].map(
        {True: "Favorite", False: "Underdog"}
    )

    return summary


def analyze_performance_by_week(df: pd.DataFrame) -> pd.DataFrame:
    """Analyzes hit rate for spreads and totals on a weekly basis."""
    # Spreads
    spread_bets = df[df["Spread Bet"].isin(["home", "away"])].copy()
    spread_bets["win"] = (spread_bets["Spread Bet Result"] == "Win").astype(int)
    spread_weekly = (
        spread_bets.groupby("Week")["win"]
        .agg(["sum", "count"])
        .rename(columns={"sum": "spread_wins", "count": "spread_bets"})
    )

    # Totals
    total_bets = df[df["Total Bet"].isin(["over", "under"])].copy()
    total_bets["win"] = (total_bets["Total Bet Result"] == "Win").astype(int)
    total_weekly = (
        total_bets.groupby("Week")["win"]
        .agg(["sum", "count"])
        .rename(columns={"sum": "total_wins", "count": "total_bets"})
    )

    # Combine
    weekly_summary = pd.concat([spread_weekly, total_weekly], axis=1).fillna(0)
    weekly_summary = weekly_summary.astype(int)

    weekly_summary["spread_hit_rate"] = (
        weekly_summary["spread_wins"] / weekly_summary["spread_bets"]
    ).where(weekly_summary["spread_bets"] > 0)
    weekly_summary["total_hit_rate"] = (
        weekly_summary["total_wins"] / weekly_summary["total_bets"]
    ).where(weekly_summary["total_bets"] > 0)

    return weekly_summary.reset_index()


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Analyze model performance by segments."
    )
    parser.add_argument(
        "--year", type=int, required=True, help="The season year to analyze."
    )
    parser.add_argument(
        "--report-dir",
        default=str(REPORTS_DIR),
        help="Root directory where season reports are stored.",
    )
    args = parser.parse_args()

    # Load the scored data for the season
    season_df = load_scored_season_data(args.year, args.report_dir)
    if season_df is None or season_df.empty:
        print(f"No scored data found for year {args.year}. Exiting.")
        return

    print(f"--- Performance Analysis for {args.year} Season ---")

    # 1. Favorite vs. Underdog Analysis
    fav_underdog_summary = analyze_favorites_vs_underdogs(season_df)
    if not fav_underdog_summary.empty:
        print("\n--- Spread Bets: Favorite vs. Underdog ---")
        print(fav_underdog_summary.to_string(index=False))
    else:
        print("\nNo spread bets found to analyze for Favorite vs. Underdog.")

    # 2. Weekly Performance Analysis
    weekly_summary = analyze_performance_by_week(season_df)
    if not weekly_summary.empty:
        print("\n--- Performance by Week ---")
        print(
            weekly_summary.to_string(
                index=False,
                formatters={
                    "spread_hit_rate": "{:.1%}".format,
                    "total_hit_rate": "{:.1%}".format,
                },
            )
        )
    else:
        print("\nNo bets found to analyze weekly performance.")


if __name__ == "__main__":
    main()
