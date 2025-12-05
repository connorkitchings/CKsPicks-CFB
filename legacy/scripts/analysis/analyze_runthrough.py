import argparse
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())
# noqa: E402
import numpy as np
import pandas as pd


def analyze_thresholds(df, target_type="spread"):
    # Ensure required columns exist
    # For stacked bets output:
    # Spread: "Spread Prediction", "home_team_spread_line", "Spread Bet"
    # Total: "Total Prediction", "total_line", "Total Bet"
    # Actuals: We need to merge with actual scores.

    # The stacked bets file has "home_score" and "away_score" if the game is completed?
    # Let's check if generate_stacked_bets includes actual scores.
    # It loads raw_df which usually has scores if the game is past.
    # But for backfill, we are running as if it's that week.
    # However, load_point_in_time_data loads data available AT THAT TIME.
    # So actual scores might NOT be in the file if we simulated "before the game".

    # We need to load actual scores separately.
    pass


def load_actual_scores(year, data_root):
    # Load games.csv or similar from data_root
    # Or use the internal data loader for the END of the season
    from src.utils.local_storage import LocalStorage

    storage = LocalStorage(data_root=data_root, file_format="csv", data_type="raw")
    games = storage.read_index("games", {"year": year})
    if not games:
        return pd.DataFrame()
    return pd.DataFrame.from_records(games)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True, help="Year to analyze")
    args = parser.parse_args()

    year = args.year
    reports_dir = Path(f"artifacts/reports/{year}/predictions")

    print(f"Loading predictions from {reports_dir}...")
    dfs = []
    for file_path in reports_dir.glob("CFB_week*_stacked_bets.csv"):
        try:
            df = pd.read_csv(file_path)
            dfs.append(df)
        except Exception as e:
            print(f"Error reading {file_path}: {e}")

    if not dfs:
        print("No prediction files found.")
        return

    preds_df = pd.concat(dfs, ignore_index=True)
    print(f"Loaded {len(preds_df)} bets.")

    # Load Actual Scores
    # We need to know the result to calculate ROI.
    # We can use the 'games' data from the data directory.
    data_root = "/Volumes/CK SSD/Coding Projects/cfb_model/"  # Hardcoded as per generate_stacked_bets.py
    actuals_df = load_actual_scores(year, data_root)

    if actuals_df.empty:
        print("Error: Could not load actual scores.")
        return

    # Merge Actuals
    # preds_df has 'game_id'
    # actuals_df has 'id' (which is game_id), 'home_points', 'away_points'
    actuals_df = actuals_df[["id", "home_points", "away_points"]].rename(
        columns={
            "id": "game_id",
            "home_points": "actual_home_points",
            "away_points": "actual_away_points",
        }
    )

    merged_df = preds_df.merge(actuals_df, on="game_id", how="inner")

    # Filter completed games
    merged_df = merged_df.dropna(subset=["actual_home_points", "actual_away_points"])
    print(f"Analyzable Games (Completed): {len(merged_df)}")

    # --- SPREAD ANALYSIS ---
    print("\n=== SPREAD ANALYSIS (Points-For) ===")
    # Edge = Pred - (-Line)
    # But generate_stacked_bets already calculates 'edge_spread'
    if "edge_spread" not in merged_df.columns:
        print("edge_spread column missing.")
    else:
        # Calculate Result
        # Home Cover Margin = (Actual Home - Actual Away) + Line
        # Line is usually negative for favorite (e.g. -3.5).
        # So (H - A) - 3.5 > 0 means Home Covered.
        # Wait, 'home_team_spread_line' in stacked bets.
        merged_df["actual_margin"] = (
            merged_df["actual_home_points"] - merged_df["actual_away_points"]
        )
        merged_df["cover_margin"] = (
            merged_df["actual_margin"] + merged_df["home_team_spread_line"]
        )

        # Bet Result
        # Bet Home if edge > 0
        # Bet Away if edge < 0
        # Win if (Bet Home AND cover_margin > 0) OR (Bet Away AND cover_margin < 0)

        conditions = [
            (merged_df["edge_spread"] > 0)
            & (merged_df["cover_margin"] > 0),  # Bet Home, Home Covers
            (merged_df["edge_spread"] < 0)
            & (merged_df["cover_margin"] < 0),  # Bet Away, Away Covers
            (merged_df["cover_margin"] == 0),  # Push
        ]
        choices = ["Win", "Win", "Push"]
        merged_df["spread_result"] = np.select(conditions, choices, default="Loss")

        # Threshold Loop
        thresholds = [0.0, 2.5, 5.0, 7.5, 10.0]
        print(
            f"{'Threshold':>10} {'Bets':>6} {'Wins':>6} {'Losses':>6} {'Win Rate':>8} {'ROI':>8}"
        )

        for t in thresholds:
            subset = merged_df[merged_df["edge_spread"].abs() >= t]
            decided = subset[subset["spread_result"] != "Push"]
            wins = len(decided[decided["spread_result"] == "Win"])
            losses = len(decided[decided["spread_result"] == "Loss"])
            total = len(subset)

            if wins + losses > 0:
                rate = wins / (wins + losses)
                roi = (wins * 0.909 - losses) / ((wins + losses) * 1.1)
                print(
                    f"{t:10.1f} {total:6d} {wins:6d} {losses:6d} {rate:8.1%} {roi:8.1%}"
                )
            else:
                print(f"{t:10.1f} {total:6d} {0:6d} {0:6d} {'N/A':>8} {'N/A':>8}")

    # --- TOTAL ANALYSIS ---
    print("\n=== TOTAL ANALYSIS ===")
    if "edge_total" in merged_df.columns:
        # Edge = Pred - Line
        # Bet Over if Edge > 0
        # Bet Under if Edge < 0

        merged_df["actual_total"] = (
            merged_df["actual_home_points"] + merged_df["actual_away_points"]
        )

        # Win conditions
        # Bet Over (Edge > 0) AND Actual > Line
        # Bet Under (Edge < 0) AND Actual < Line

        conditions = [
            (merged_df["edge_total"] > 0)
            & (merged_df["actual_total"] > merged_df["total_line"]),
            (merged_df["edge_total"] < 0)
            & (merged_df["actual_total"] < merged_df["total_line"]),
            (merged_df["actual_total"] == merged_df["total_line"]),
        ]
        choices = ["Win", "Win", "Push"]
        merged_df["total_result"] = np.select(conditions, choices, default="Loss")

        thresholds = [0.0, 2.5, 3.5, 5.0, 7.5]
        print(
            f"{'Threshold':>10} {'Bets':>6} {'Wins':>6} {'Losses':>6} {'Win Rate':>8} {'ROI':>8}"
        )

        for t in thresholds:
            subset = merged_df[merged_df["edge_total"].abs() >= t]
            decided = subset[subset["total_result"] != "Push"]
            wins = len(decided[decided["total_result"] == "Win"])
            losses = len(decided[decided["total_result"] == "Loss"])
            total = len(subset)

            if wins + losses > 0:
                rate = wins / (wins + losses)
                roi = (wins * 0.909 - losses) / ((wins + losses) * 1.1)
                print(
                    f"{t:10.1f} {total:6d} {wins:6d} {losses:6d} {rate:8.1%} {roi:8.1%}"
                )
            else:
                print(f"{t:10.1f} {total:6d} {0:6d} {0:6d} {'N/A':>8} {'N/A':>8}")


if __name__ == "__main__":
    main()
