#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from typing import Dict, List

import pandas as pd

from cfb_model.data.storage.local_storage import LocalStorage


def list_weeks(data_root: str, year: int) -> List[int]:
    raw = LocalStorage(data_root=data_root, file_format="csv", data_type="raw")
    games_idx = raw.read_index("games", {"year": year})
    if not games_idx:
        return []
    return sorted(
        int(w) for w in pd.DataFrame.from_records(games_idx)["week"].dropna().unique()
    )


def evaluate_week(
    data_root: str, report_dir: str, year: int, week: int, threshold: float
) -> Dict:
    path = os.path.join(report_dir, str(year), f"CFB_week{week}_bets.csv")
    if not os.path.exists(path):
        return {"week": week, "picks": 0, "wins": 0, "hit_rate": None}
    bets = pd.read_csv(path)
    if "model_spread" in bets.columns and "predicted_spread" not in bets.columns:
        bets["predicted_spread"] = bets["model_spread"]

    # Merge actual outcomes
    raw = LocalStorage(data_root=data_root, file_format="csv", data_type="raw")
    games_idx = raw.read_index("games", {"year": year})
    gdf = pd.DataFrame.from_records([r for r in games_idx if r.get("week") == week])

    key = "game_id" if "game_id" in bets.columns else "id"
    m = bets.merge(
        gdf[["id", "home_points", "away_points"]],
        left_on=[key],
        right_on=["id"],
        how="left",
    )

    # Compute edges
    m["expected_home_margin"] = -pd.to_numeric(
        m["home_team_spread_line"], errors="coerce"
    )
    m["predicted_spread"] = pd.to_numeric(m["predicted_spread"], errors="coerce")
    m["edge"] = (m["predicted_spread"] - m["expected_home_margin"]).abs()

    # Eligibility and selection
    elig = (m.get("home_games_played", 0) >= 4) & (m.get("away_games_played", 0) >= 4)
    sel = (m["edge"] >= threshold) & elig
    mm = m.loc[sel].copy()
    if mm.empty:
        return {"week": week, "picks": 0, "wins": 0, "hit_rate": None}

    mm["bet_side"] = (mm["predicted_spread"] > mm["expected_home_margin"]).map(
        {True: "home", False: "away"}
    )
    actual_margin = mm["home_points"].astype(float) - mm["away_points"].astype(float)
    win_mask = (
        (mm["bet_side"] == "home") & (actual_margin > mm["expected_home_margin"])
    ) | ((mm["bet_side"] == "away") & (actual_margin < mm["expected_home_margin"]))

    picks = int(len(mm))
    wins = int(win_mask.sum())
    hit = round(wins / picks, 3) if picks else None
    return {"week": week, "picks": picks, "wins": wins, "hit_rate": hit}


def main() -> None:
    p = argparse.ArgumentParser(
        description="Weekly win rates at a given edge threshold"
    )
    p.add_argument("--data-root", required=True)
    p.add_argument("--report-dir", default="./reports")
    p.add_argument("--year", type=int, default=2024)
    p.add_argument("--threshold", type=float, default=5.0)
    args = p.parse_args()

    weeks = list_weeks(args.data_root, args.year)
    rows = [
        evaluate_week(args.data_root, args.report_dir, args.year, wk, args.threshold)
        for wk in weeks
    ]
    out = pd.DataFrame(rows).sort_values("week")
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
