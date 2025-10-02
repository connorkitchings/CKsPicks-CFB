#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from typing import Tuple

import numpy as np
import pandas as pd


def _to_bool(series: pd.Series) -> pd.Series:
    # Normalize various truthy representations to 1/0
    s = series.fillna(0)
    if s.dtype == bool:
        return s.astype(int)
    # Handle strings like '1', '1.0', 'True', 'true', 'YES'
    return (
        s.astype(str)
        .str.strip()
        .str.lower()
        .map(
            {
                "1": 1,
                "1.0": 1,
                "true": 1,
                "t": 1,
                "yes": 1,
                "y": 1,
                "0": 0,
                "0.0": 0,
                "false": 0,
                "f": 0,
                "no": 0,
                "n": 0,
                "": 0,
            }
        )
        .fillna(0)
        .astype(int)
    )


def summarize(df: pd.DataFrame, win_col: str) -> Tuple[pd.DataFrame, pd.Series]:
    d = df.copy()
    d[win_col] = _to_bool(d[win_col])
    # Weekly
    weekly = (
        d.groupby("week")[win_col]
        .agg([("wins", "sum"), ("bets", "count")])
        .assign(
            hit_rate=lambda x: np.where(x["bets"] > 0, x["wins"] / x["bets"], np.nan)
        )
        .reset_index()
        .sort_values("week")
    )
    # Overall
    overall = pd.Series(
        {
            "wins": int(d[win_col].sum()),
            "bets": int(len(d)),
            "hit_rate": float(d[win_col].sum() / len(d)) if len(d) > 0 else np.nan,
        }
    )
    return weekly, overall


def main() -> None:
    p = argparse.ArgumentParser(
        description="Separate spread and total bets and summarize performance by week and overall."
    )
    p.add_argument(
        "--input",
        required=True,
        help="Path to combined season scored CSV (e.g., reports/2024/CFB_season_2024_all_bets_scored.csv)",
    )
    p.add_argument(
        "--out-dir",
        required=True,
        help="Output directory for separated CSVs and summaries (e.g., reports/2024)",
    )
    args = p.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    df = pd.read_csv(args.input)

    # Filter placed bets
    spread_bets = df[
        df.get("bet_spread", "none").astype(str).str.lower() != "none"
    ].copy()
    total_bets = df[
        df.get("bet_total", "none").astype(str).str.lower() != "none"
    ].copy()

    # Save separated rows
    spread_path = os.path.join(args.out_dir, "CFB_season_2024_spread_bets_scored.csv")
    total_path = os.path.join(args.out_dir, "CFB_season_2024_total_bets_scored.csv")
    spread_bets.to_csv(spread_path, index=False)
    total_bets.to_csv(total_path, index=False)

    # Summaries
    spread_weekly, spread_overall = summarize(spread_bets, win_col="pick_win")
    total_weekly, total_overall = summarize(total_bets, win_col="total_pick_win")

    spread_weekly_path = os.path.join(
        args.out_dir, "CFB_season_2024_spread_weekly_summary.csv"
    )
    total_weekly_path = os.path.join(
        args.out_dir, "CFB_season_2024_total_weekly_summary.csv"
    )
    spread_weekly.to_csv(spread_weekly_path, index=False)
    total_weekly.to_csv(total_weekly_path, index=False)

    # Print compact summaries
    print("Spread weekly summary:")
    print(spread_weekly.to_string(index=False))
    print("\nSpread overall:")
    print(spread_overall.to_dict())

    print("\nTotal weekly summary:")
    print(total_weekly.to_string(index=False))
    print("\nTotal overall:")
    print(total_overall.to_dict())


if __name__ == "__main__":
    main()
