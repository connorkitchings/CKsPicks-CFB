#!/usr/bin/env python3
from __future__ import annotations

import os
import sys

import pandas as pd

from cfb_model.data.storage.local_storage import LocalStorage

DATA_ROOT = "/Volumes/CK SSD/Coding Projects/cfb_model"
REPORT_PATH = "./reports/2024/CFB_week5_bets.csv"


def main() -> int:
    if not os.path.exists(REPORT_PATH):
        print(f"Missing report at {REPORT_PATH}")
        return 1
    picks = pd.read_csv(REPORT_PATH)

    raw = LocalStorage(data_root=DATA_ROOT, file_format="csv", data_type="raw")
    records = raw.read_index("games", {"year": 2024})
    if not records:
        print("No raw games found in external data root for 2024")
        return 1
    games = pd.DataFrame.from_records(records)
    need = [
        "id",
        "season",
        "week",
        "home_team",
        "away_team",
        "home_points",
        "away_points",
    ]
    for c in need:
        if c not in games.columns:
            print(f"Missing required games column: {c}")
            return 1
    games = games[need]

    merged = picks.merge(
        games,
        left_on=["game_id", "season", "week"],
        right_on=["id", "season", "week"],
        how="left",
        suffixes=("", "_g"),
    )
    merged["actual_margin"] = merged["home_points"].astype(float) - merged[
        "away_points"
    ].astype(float)
    merged["actual_total"] = merged["home_points"].astype(float) + merged[
        "away_points"
    ].astype(float)

    # Spread summary
    sd = merged[
        (merged["bet_spread"].notna()) & (merged["bet_spread"] != "none")
    ].copy()
    win_home = (sd["bet_spread"] == "home") & (sd["actual_margin"] > sd["spread_line"])
    win_away = (sd["bet_spread"] == "away") & (sd["actual_margin"] < sd["spread_line"])
    sd["win"] = (win_home | win_away).astype(int)
    spread_bets = int(len(sd))
    spread_wins = int(sd["win"].sum())
    spread_hr = round(spread_wins / max(spread_bets, 1), 3)
    spread_edge = round(float(sd["edge_spread"].mean()) if spread_bets else 0.0, 2)

    # Totals summary
    td = merged[(merged["bet_total"].notna()) & (merged["bet_total"] != "none")].copy()
    win_over = (td["bet_total"] == "over") & (td["actual_total"] > td["total_line"])
    win_under = (td["bet_total"] == "under") & (td["actual_total"] < td["total_line"])
    td["win"] = (win_over | win_under).astype(int)
    total_bets = int(len(td))
    total_wins = int(td["win"].sum())
    total_hr = round(total_wins / max(total_bets, 1), 3)
    total_edge = round(float(td["edge_total"].mean()) if total_bets else 0.0, 2)

    summary = {
        "games_in_week": int(picks["game_id"].nunique()),
        "spread": {
            "bets": spread_bets,
            "wins": spread_wins,
            "hit_rate": spread_hr,
            "avg_edge": spread_edge,
        },
        "total": {
            "bets": total_bets,
            "wins": total_wins,
            "hit_rate": total_hr,
            "avg_edge": total_edge,
        },
    }

    print("SUMMARY")
    print(summary)

    # Top 5 edges
    sel_spread = [
        "game_id",
        "home_team",
        "away_team",
        "spread_line",
        "model_spread",
        "edge_spread",
        "bet_spread",
        "win",
    ]
    sel_total = [
        "game_id",
        "home_team",
        "away_team",
        "total_line",
        "model_total",
        "edge_total",
        "bet_total",
        "win",
    ]
    top_spread = sd.sort_values("edge_spread", ascending=False).head(5)[sel_spread]
    top_total = td.sort_values("edge_total", ascending=False).head(5)[sel_total]

    print("\nTOP SPREAD EDGES (top 5):")
    print(top_spread.to_string(index=False))
    print("\nTOP TOTAL EDGES (top 5):")
    print(top_total.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
