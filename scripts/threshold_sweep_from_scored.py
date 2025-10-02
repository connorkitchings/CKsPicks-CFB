#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from typing import Dict, List

import numpy as np
import pandas as pd

BET_TYPES = {
    "spread": {"edge_col": "edge_spread", "win_col": "pick_win"},
    "total": {"edge_col": "edge_total", "win_col": "total_pick_win"},
}


def to_bool_int(s: pd.Series) -> pd.Series:
    s = s.fillna(0)
    if s.dtype == bool:
        return s.astype(int)
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


def sweep(
    df: pd.DataFrame, edge_col: str, win_col: str, thresholds: List[float]
) -> pd.DataFrame:
    d = df.copy()
    d[edge_col] = pd.to_numeric(d[edge_col], errors="coerce")
    d[win_col] = to_bool_int(d[win_col])
    d = d.dropna(subset=[edge_col])

    rows: List[Dict] = []
    for t in thresholds:
        mask = d[edge_col] >= t
        picks = int(mask.sum())
        wins = int(d.loc[mask, win_col].sum())
        hit = float(wins / picks) if picks > 0 else np.nan
        rows.append({"threshold": t, "picks": picks, "wins": wins, "hit_rate": hit})
    return pd.DataFrame(rows)


def main() -> None:
    p = argparse.ArgumentParser(
        description="Sweep edge thresholds using a combined scored CSV (no raw data required)."
    )
    p.add_argument(
        "--input",
        required=True,
        help="Path to combined season scored CSV, e.g. reports/2024/CFB_season_2024_all_bets_scored.csv",
    )
    p.add_argument("--bet-type", choices=["spread", "total"], default="spread")
    p.add_argument("--thresholds", type=str, default="3,3.5,4,4.5,5,5.5,6,6.5,7")
    p.add_argument("--min-week", type=int, default=5)
    p.add_argument("--max-week", type=int, default=16)
    p.add_argument("--out-dir", default="./reports/2024")
    args = p.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    df = pd.read_csv(args.input)
    # Restrict to requested weeks
    if "week" in df.columns:
        df = df[(df["week"] >= args.min_week) & (df["week"] <= args.max_week)].copy()

    cfg = BET_TYPES[args.bet_type]
    thresholds = [float(t.strip()) for t in args.thresholds.split(",") if t.strip()]

    out = sweep(
        df, edge_col=cfg["edge_col"], win_col=cfg["win_col"], thresholds=thresholds
    )
    out_path = os.path.join(
        args.out_dir, f"edge_threshold_sweep_{args.bet_type}_from_scored.csv"
    )
    out.to_csv(out_path, index=False)

    # Print compact
    print(out.sort_values("threshold").to_string(index=False))


if __name__ == "__main__":
    main()
