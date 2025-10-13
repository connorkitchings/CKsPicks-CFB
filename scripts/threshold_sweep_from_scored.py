"""
Sweep edge thresholds using scored season data loaded by the analysis loader.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

# Add src to path for local imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cfb_model.analysis.loader import load_scored_season_data

BET_TYPES = {
    "spread": {
        "edge_col": "edge_spread",
        "win_col": "Spread Bet Result",
        "bet_col": "Spread Bet",
        "valid_bets": ["home", "away"],
    },
    "total": {
        "edge_col": "edge_total",
        "win_col": "Total Bet Result",
        "bet_col": "Total Bet",
        "valid_bets": ["over", "under"],
    },
}


def result_to_win_int(s: pd.Series) -> pd.Series:
    """Converts a result string ('Win', 'Loss', 'Push') to an integer (1, 0, 0)."""
    return s.str.lower().map({"win": 1, "loss": 0, "push": 0}).fillna(0).astype(int)


def sweep(
    df: pd.DataFrame,
    *,
    edge_col: str,
    win_col: str,
    bet_col: str,
    valid_bets: List[str],
    thresholds: List[float],
) -> pd.DataFrame:
    """Calculate hit rate at various edge thresholds for actual bets."""
    d = df.copy()

    # First, filter to only include rows where a bet was actually placed.
    d = d[d[bet_col].isin(valid_bets)].copy()

    d[edge_col] = pd.to_numeric(d[edge_col], errors="coerce")
    d["win"] = result_to_win_int(d[win_col])
    d = d.dropna(subset=[edge_col, "win"])

    rows: List[Dict] = []
    for t in thresholds:
        mask = d[edge_col] >= t
        subset = d[mask]
        picks = len(subset)
        wins = int(subset["win"].sum())
        hit = float(wins / picks) if picks > 0 else np.nan
        rows.append({"threshold": t, "picks": picks, "wins": wins, "hit_rate": hit})
    return pd.DataFrame(rows)


def main() -> None:
    p = argparse.ArgumentParser(
        description="Sweep edge thresholds using scored season data."
    )
    p.add_argument(
        "--year", type=int, required=True, help="The season year to analyze."
    )
    p.add_argument(
        "--report-dir",
        default="./reports",
        help="Root directory where season reports are stored.",
    )
    p.add_argument("--bet-type", choices=["spread", "total"], default="spread")
    p.add_argument("--thresholds", type=str, default="3,3.5,4,4.5,5,5.5,6,6.5,7")
    p.add_argument("--min-week", type=int, default=5)
    p.add_argument("--max-week", type=int, default=16)
    p.add_argument("--out-dir", default=None, help="Optional output directory.")
    args = p.parse_args()

    out_dir = args.out_dir or os.path.join(args.report_dir, str(args.year))
    os.makedirs(out_dir, exist_ok=True)

    # Use the new centralized loader
    df = load_scored_season_data(args.year, args.report_dir)
    if df is None or df.empty:
        print(f"No scored data found for year {args.year}. Exiting.")
        return

    # Restrict to requested weeks
    if "Week" in df.columns:
        df = df[(df["Week"] >= args.min_week) & (df["Week"] <= args.max_week)].copy()

    cfg = BET_TYPES[args.bet_type]
    thresholds = [float(t.strip()) for t in args.thresholds.split(",") if t.strip()]

    # The win column names have changed in the refactored scoring script
    out = sweep(
        df,
        edge_col=cfg["edge_col"],
        win_col=cfg["win_col"],
        bet_col=cfg["bet_col"],
        valid_bets=cfg["valid_bets"],
        thresholds=thresholds,
    )

    out_path = os.path.join(
        out_dir, f"edge_threshold_sweep_{args.bet_type}_from_scored.csv"
    )
    out.to_csv(out_path, index=False)

    print(f"Results for {args.bet_type} bets in {args.year}:")
    print(out.sort_values("threshold").to_string(index=False))
    print(f"\nOutput saved to {out_path}")


if __name__ == "__main__":
    main()
