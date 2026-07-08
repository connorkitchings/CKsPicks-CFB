import os
import sys
from pathlib import Path

import pandas as pd

# Add project root to path
sys.path.append(os.getcwd())

from cks_picks_cfb.config import get_data_root
from cks_picks_cfb.utils.local_storage import LocalStorage


def load_lines_for_year(year):
    data_root = get_data_root()
    storage = LocalStorage(data_root=data_root, file_format="csv", data_type="raw")
    records = storage.read_index("betting_lines", {"year": year})
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame.from_records(records)

    # Dedupe logic from features.py
    if "provider" in df.columns:
        provider_priority = {
            "Consensus": 0,
            "consensus": 0,
            "Bovada": 1,
            "DraftKings": 2,
            "FanDuel": 3,
            "BetMGM": 4,
            "Caesars": 5,
        }
        df["provider_rank"] = df["provider"].map(provider_priority).fillna(99)
        df = df.sort_values(["game_id", "provider_rank"])
        df = df.drop_duplicates(subset=["game_id"], keep="first")
        df = df.drop(columns=["provider_rank"])

    return df[["game_id", "spread"]]


def main():
    root = Path("artifacts/backtest/ppr")
    files = sorted(list(root.glob("backtest_*.csv")))

    if not files:
        print("No PPR backtest files found.")
        return

    print(f"Found {len(files)} backtest files.")

    results = []

    for f in files:
        year = int(f.stem.split("_")[1])
        print(f"Processing {year}...")

        # Load Predictions
        preds = pd.read_csv(f)

        # Load Lines
        lines = load_lines_for_year(year)

        if lines.empty:
            print(f"  No betting lines found for {year}. Skipping ATS.")
            continue

        # Merge
        # PPR backtest doesn't have game_id, but has home/away/week
        # We need to map game_id first.
        # Actually, let's load games to map home/away/week -> game_id

        data_root = get_data_root()
        storage = LocalStorage(data_root=data_root, file_format="csv", data_type="raw")
        games_records = storage.read_index("games", {"year": year})
        games_df = pd.DataFrame.from_records(games_records)

        # Merge preds with games to get ID
        # Preds has: year, week, home_team, away_team
        merged = preds.merge(
            games_df[["id", "week", "home_team", "away_team"]],
            on=["week", "home_team", "away_team"],
            how="left",
        )

        # Merge with lines
        merged = merged.merge(lines, left_on="id", right_on="game_id", how="left")

        # Calculate ATS
        # PPR Pred Diff = Home - Away
        # Line = Home Spread (e.g. -7)

        # Edge = Pred Diff + Line
        # If Edge > 0 => Pick Home
        # If Edge < 0 => Pick Away

        # Actual Margin = actual_diff (Home - Away)
        # Cover Margin = Actual Margin + Line

        valid = merged.dropna(subset=["spread"]).copy()

        valid["model_edge"] = valid["pred_diff"] + valid["spread"]
        valid["cover_margin"] = valid["actual_diff"] + valid["spread"]

        # Exclude Pushes
        no_push = valid[valid["cover_margin"] != 0].copy()

        no_push["correct"] = (no_push["model_edge"] > 0) == (
            no_push["cover_margin"] > 0
        )

        ats_acc = no_push["correct"].mean()
        count = len(no_push)

        print(f"  ATS Accuracy: {ats_acc:.4%} ({count} games)")

        results.append({"Year": year, "ATS Accuracy": ats_acc, "Games": count})

    if results:
        df_res = pd.DataFrame(results)
        print("\n--- PPR ATS Results ---")
        print(df_res.to_markdown(index=False))
        df_res.to_csv("artifacts/validation/ppr_ats_summary.csv", index=False)


if __name__ == "__main__":
    main()
