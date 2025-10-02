#!/usr/bin/env python3
from __future__ import annotations

import sys

sys.path.insert(0, "./src")

import argparse
import os
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from cfb_model.data.storage.local_storage import LocalStorage


def load_weeks_from_raw(data_root: str, year: int) -> List[int]:
    raw = LocalStorage(data_root=data_root, file_format="csv", data_type="raw")
    games_idx = raw.read_index("games", {"year": year})
    if not games_idx:
        return []
    df = pd.DataFrame.from_records(games_idx)
    return sorted(int(w) for w in df["week"].dropna().unique())


# Columns we might need across both bet types
essential_cols = [
    "season",
    "week",
    "game_id",
    "home_team",
    "away_team",
    # Spread
    "home_team_spread_line",
    "predicted_spread",
    "model_spread",
    # Totals
    "total_line",
    "predicted_total",
    "model_total",
    # Eligibility
    "home_games_played",
    "away_games_played",
]


def load_week_bets(report_dir: str, year: int, week: int) -> pd.DataFrame | None:
    path = os.path.join(report_dir, str(year), f"CFB_week{week}_bets.csv")
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    # Keep only essential columns if present
    keep = [c for c in essential_cols if c in df.columns]
    # Include identifiers if present
    if "id" in df.columns and "game_id" not in keep:
        keep = [*keep, "id"]
    # Include dates optionally
    if "game_date" in df.columns:
        keep.append("game_date")
    return df[keep].copy()


def merge_actuals(
    data_root: str, year: int, week: int, bets_df: pd.DataFrame
) -> pd.DataFrame:
    raw = LocalStorage(data_root=data_root, file_format="csv", data_type="raw")
    games_idx = raw.read_index("games", {"year": year})
    games = pd.DataFrame.from_records(games_idx)
    wk_games = games[games["week"] == week].copy()
    # Determine join key
    key = "game_id" if "game_id" in bets_df.columns else "id"
    merged = bets_df.merge(
        wk_games[["id", "home_points", "away_points"]],
        left_on=[key],
        right_on=["id"],
        how="left",
    )
    merged["actual_margin"] = merged["home_points"].astype(float) - merged[
        "away_points"
    ].astype(float)
    merged["actual_total"] = merged["home_points"].astype(float) + merged[
        "away_points"
    ].astype(float)
    return merged


# Spread scoring


def score_threshold_spread(
    df: pd.DataFrame, threshold: float, min_games: int = 4
) -> Dict[str, Any]:
    d = df.copy()
    # Eligibility
    eligible = (d.get("home_games_played", 0) >= min_games) & (
        d.get("away_games_played", 0) >= min_games
    )
    d = d[eligible].copy()
    # Compute expected home margin from spread (home favored -7 => +7 expected margin)
    d["expected_home_margin"] = -pd.to_numeric(
        d["home_team_spread_line"], errors="coerce"
    )
    # Column compatibility: weekly CSV may name it 'model_spread'
    if "predicted_spread" not in d.columns and "model_spread" in d.columns:
        d["predicted_spread"] = d["model_spread"]
    d["predicted_spread"] = pd.to_numeric(d["predicted_spread"], errors="coerce")
    d["edge"] = (d["predicted_spread"] - d["expected_home_margin"]).abs()
    # Decision
    take = d["edge"] >= threshold
    d = d[take].copy()
    if d.empty:
        return {"threshold": threshold, "picks": 0, "wins": 0, "hit_rate": np.nan}
    d["bet_side"] = np.where(
        d["predicted_spread"] > d["expected_home_margin"], "home", "away"
    )
    # Outcome
    # home bet wins if actual_margin > expected_home_margin; away bet wins if actual_margin < expected_home_margin; push -> 0
    d["win"] = 0
    d.loc[
        (d["bet_side"] == "home") & (d["actual_margin"] > d["expected_home_margin"]),
        "win",
    ] = 1
    d.loc[
        (d["bet_side"] == "away") & (d["actual_margin"] < d["expected_home_margin"]),
        "win",
    ] = 1
    picks = int(len(d))
    wins = int(d["win"].sum())
    hit = float(wins / picks) if picks > 0 else np.nan
    return {"threshold": threshold, "picks": picks, "wins": wins, "hit_rate": hit}


# Totals scoring


def score_threshold_total(
    df: pd.DataFrame, threshold: float, min_games: int = 4
) -> Dict[str, Any]:
    d = df.copy()
    # Eligibility
    eligible = (d.get("home_games_played", 0) >= min_games) & (
        d.get("away_games_played", 0) >= min_games
    )
    d = d[eligible].copy()
    # Expected total is the posted total line
    d["expected_total"] = pd.to_numeric(d["total_line"], errors="coerce")
    # Column compatibility: weekly CSV may name it 'model_total'
    if "predicted_total" not in d.columns and "model_total" in d.columns:
        d["predicted_total"] = d["model_total"]
    d["predicted_total"] = pd.to_numeric(d["predicted_total"], errors="coerce")
    d["edge"] = (d["predicted_total"] - d["expected_total"]).abs()
    # Decision
    take = d["edge"] >= threshold
    d = d[take].copy()
    if d.empty:
        return {"threshold": threshold, "picks": 0, "wins": 0, "hit_rate": np.nan}
    d["bet_side"] = np.where(
        d["predicted_total"] > d["expected_total"], "over", "under"
    )
    # Outcome: over wins if actual_total > expected_total, under wins if actual_total < expected_total; push -> 0
    d["win"] = 0
    d.loc[
        (d["bet_side"] == "over") & (d["actual_total"] > d["expected_total"]), "win"
    ] = 1
    d.loc[
        (d["bet_side"] == "under") & (d["actual_total"] < d["expected_total"]), "win"
    ] = 1
    picks = int(len(d))
    wins = int(d["win"].sum())
    hit = float(wins / picks) if picks > 0 else np.nan
    return {"threshold": threshold, "picks": picks, "wins": wins, "hit_rate": hit}


def main() -> None:
    p = argparse.ArgumentParser(
        description="Sweep edge thresholds and evaluate hit rate."
    )
    p.add_argument("--data-root", required=True)
    p.add_argument("--report-dir", default="./reports")
    p.add_argument("--year", type=int, default=2024)
    p.add_argument("--min-week", type=int, default=5)
    p.add_argument("--max-week", type=int, default=16)
    p.add_argument(
        "--thresholds", type=str, default="1,1.5,2,2.5,3,3.5,4,4.5,5,5.5,6,6.5,7"
    )
    p.add_argument(
        "--bet-type", type=str, choices=["spread", "total"], default="spread"
    )
    args = p.parse_args()

    weeks_avail = load_weeks_from_raw(args.data_root, args.year)
    weeks = [w for w in weeks_avail if args.min_week <= w <= args.max_week]
    if not weeks:
        print({"error": "no_weeks_in_range", "weeks_avail": weeks_avail})
        return

    # Load all weekly bets and attach outcomes
    weekly_frames: List[pd.DataFrame] = []
    for wk in weeks:
        bets = load_week_bets(args.report_dir, args.year, wk)
        if bets is None:
            # Skip missing weeks silently
            continue
        merged = merge_actuals(args.data_root, args.year, wk, bets)
        weekly_frames.append(merged)

    if not weekly_frames:
        print({"error": "no_weekly_reports_found"})
        return

    season_df = pd.concat(weekly_frames, ignore_index=True)

    # Sweep thresholds
    thresholds = [float(t.strip()) for t in args.thresholds.split(",") if t.strip()]
    if args.bet_type == "spread":
        results = [score_threshold_spread(season_df, t) for t in thresholds]
    else:
        results = [score_threshold_total(season_df, t) for t in thresholds]
    out = pd.DataFrame(results)
    out_path = os.path.join(
        args.report_dir, str(args.year), f"edge_threshold_sweep_{args.bet_type}.csv"
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    out.to_csv(out_path, index=False)
    # Print compact summary
    print(out.sort_values("threshold").to_string(index=False))


if __name__ == "__main__":
    main()
