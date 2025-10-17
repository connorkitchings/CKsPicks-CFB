"""
Sweep confidence (standard deviation) thresholds using scored season data.
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

from src.loader import load_scored_season_data
from src.config import REPORTS_DIR, METRICS_SUBDIR

BET_TYPES = {
    "spread": {
        "edge_col": "edge_spread",
        "std_dev_col": "predicted_spread_std_dev",
        "win_col": "Spread Bet Result",
    },
    "total": {
        "edge_col": "edge_total",
        "std_dev_col": "predicted_total_std_dev",
        "win_col": "Total Bet Result",
    },
}


def result_to_win_int(s: pd.Series) -> pd.Series:
    """Converts a result string ('Win', 'Loss', 'Push') to an integer (1, 0, 0)."""
    return s.str.lower().map({"win": 1, "loss": 0, "push": 0}).fillna(0).astype(int)


def sweep(
    df: pd.DataFrame,
    *,
    edge_col: str,
    std_dev_col: str,
    win_col: str,
    edge_threshold: float,
    std_dev_thresholds: List[float],
) -> pd.DataFrame:
    """Calculate hit rate at various standard deviation thresholds."""
    d = df.copy()
    d[edge_col] = pd.to_numeric(d[edge_col], errors="coerce")
    d[std_dev_col] = pd.to_numeric(d[std_dev_col], errors="coerce")
    d["win"] = result_to_win_int(d[win_col])
    d = d.dropna(subset=[edge_col, std_dev_col, win_col])

    # Pre-filter by the fixed edge threshold
    d = d[d[edge_col] >= edge_threshold]

    rows: List[Dict] = []
    for std_dev_thresh in std_dev_thresholds:
        mask = d[std_dev_col] <= std_dev_thresh
        picks = int(mask.sum())
        wins = int(d.loc[mask, "win"].sum())
        hit = float(wins / picks) if picks > 0 else np.nan
        rows.append(
            {
                "edge_threshold": edge_threshold,
                "std_dev_threshold": std_dev_thresh,
                "picks": picks,
                "wins": wins,
                "hit_rate": hit,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    p = argparse.ArgumentParser(
        description="Sweep confidence thresholds and evaluate hit rate."
    )
    p.add_argument(
        "--year", type=int, required=True, help="The season year to analyze."
    )
    p.add_argument(
        "--report-dir",
        default=str(REPORTS_DIR),
        help="Root directory where season reports are stored.",
    )
    p.add_argument("--min-week", type=int, default=5)
    p.add_argument("--max-week", type=int, default=16)
    p.add_argument("--edge-threshold", type=float, default=6.0)
    p.add_argument(
        "--std-dev-thresholds",
        type=str,
        default="1,1.5,2,2.5,3,3.5,4,4.5,5,5.5,6,6.5,7",
    )
    p.add_argument(
        "--bet-type", type=str, choices=["spread", "total"], default="spread"
    )
    p.add_argument("--out-dir", default=None, help="Optional output directory.")
    args = p.parse_args()

    out_dir = args.out_dir or os.path.join(
        args.report_dir, METRICS_SUBDIR, str(args.year)
    )
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
    std_dev_thresholds = [
        float(t.strip()) for t in args.std_dev_thresholds.split(",") if t.strip()
    ]

    # Perform the sweep using the simplified function
    out = sweep(
        df,
        edge_col=cfg["edge_col"],
        std_dev_col=cfg["std_dev_col"],
        win_col=cfg["win_col"],
        edge_threshold=args.edge_threshold,
        std_dev_thresholds=std_dev_thresholds,
    )

    out_path = os.path.join(out_dir, f"confidence_threshold_sweep_{args.bet_type}.csv")
    out.to_csv(out_path, index=False)

    print(f"Results for {args.bet_type} bets in {args.year}:")
    print(out.sort_values("std_dev_threshold").to_string(index=False))
    print(f"\nOutput saved to {out_path}")


if __name__ == "__main__":
    main()
