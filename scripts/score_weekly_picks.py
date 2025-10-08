"""
Scores the formatted weekly betting report against historical game data.

This script merges the weekly bets CSV with the actual game results and uses
the centralized scoring utilities to determine the outcome of each bet.
"""

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

# Add src to path for local imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cfb_model.analysis.scoring import settle_spread_bets, settle_total_bets
from cfb_model.config import get_data_root
from cfb_model.data.storage.local_storage import LocalStorage


def main() -> None:
    """Load bets, merge with game results, score, and save the output."""
    parser = argparse.ArgumentParser(
        description="Scores the formatted weekly betting report against historical data."
    )
    parser.add_argument("--year", type=int, required=True, help="The season year.")
    parser.add_argument("--week", type=int, required=True, help="The week to score.")
    parser.add_argument(
        "--data-root",
        type=str,
        default=None,
        help="Absolute path to the data root directory. Defaults to env var or ./data.",
    )
    parser.add_argument(
        "--report-dir",
        type=str,
        default="./reports",
        help="Directory where weekly reports are located.",
    )
    args = parser.parse_args()

    # Resolve data root using the centralized config helper
    data_root = args.data_root or get_data_root()

    # --- Load Input Files ---
    # Try the file with game IDs first, then fallback to regular file
    bets_file_with_ids = os.path.join(
        args.report_dir, str(args.year), f"CFB_week{args.week}_bets_with_ids.csv"
    )
    bets_file = os.path.join(
        args.report_dir, str(args.year), f"CFB_week{args.week}_bets.csv"
    )

    if os.path.exists(bets_file_with_ids):
        bets_file = bets_file_with_ids
        print(f"Using file with game IDs: {bets_file}")
    elif os.path.exists(bets_file):
        print(f"Using regular bets file: {bets_file}")
    else:
        print(f"Error: No bets file found at {bets_file} or {bets_file_with_ids}")
        return

    bets_df = pd.read_csv(bets_file)
    # Rename columns to match the internal logic expected by scoring functions
    bets_df = bets_df.rename(
        columns={"Spread Bet": "bet_spread", "Total Bet": "bet_total"}
    )

    try:
        storage = LocalStorage(data_root=data_root, file_format="csv", data_type="raw")
        game_records = storage.read_index("games", {"year": args.year})
        if not game_records:
            print(f"Error: No game data found for year {args.year} in {data_root}")
            return
        games_df = pd.DataFrame.from_records(game_records)
    except FileNotFoundError:
        print(f"Error: Could not find games data for year {args.year} in {data_root}")
        return

    # --- Merge and Score ---
    week_games_df = games_df[games_df["week"] == args.week].copy()
    # Remove duplicate games to prevent merge duplicates (preserves legitimate spread+total combinations)
    week_games_df = week_games_df.drop_duplicates(subset=["id"])

    # Merge using the reliable game_id
    merged_df = pd.merge(
        bets_df,
        week_games_df[["id", "home_points", "away_points"]],
        left_on="game_id",
        right_on="id",
        how="left",
    )

    # Apply centralized scoring logic
    scored_df = settle_spread_bets(merged_df)
    scored_df = settle_total_bets(scored_df)

    # --- Format for Output ---
    # Rename columns back to the report format
    final_df = scored_df.rename(
        columns={
            "bet_spread": "Spread Bet",
            "bet_total": "Total Bet",
            "spread_bet_result": "Spread Bet Result",
            "total_bet_result": "Total Bet Result",
        }
    )
    # Add legacy result columns for compatibility if needed
    final_df["Spread Result"] = final_df["home_points"] - final_df["away_points"]
    final_df["Total Result"] = final_df["home_points"] + final_df["away_points"]

    # --- Save and Summarize ---
    output_path = os.path.join(
        args.report_dir, str(args.year), f"CFB_week{args.week}_bets_scored.csv"
    )
    final_df.to_csv(output_path, index=False)
    print(f"Scored results saved to {output_path}")

    print("\n--- Scoring Summary ---")
    spread_summary = final_df["Spread Bet Result"].value_counts()
    total_summary = final_df["Total Bet Result"].value_counts()
    print("Spread Bets:")
    print(spread_summary)
    print("\nTotal Bets:")
    print(total_summary)


if __name__ == "__main__":
    main()
