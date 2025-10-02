#!/usr/bin/env python3
"""
Pre-calculates and caches weekly, point-in-time, opponent-adjusted stats for a full season.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd
from tqdm import tqdm

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cfb_model.data.aggregations.core import (
    aggregate_team_season,
    apply_iterative_opponent_adjustment,
)
from cfb_model.data.storage.base import Partition
from cfb_model.data.storage.local_storage import LocalStorage


def cache_season_stats(year: int, data_root: str | None):
    """
    Generates and caches point-in-time adjusted stats for each week of a season.

    For each week, it calculates team stats using all data from previous weeks,
    adjusts them for opponent strength, and saves the result to a dedicated
    partition in `processed/team_week_adj/`.
    """
    print(f"--- Starting weekly adjusted stats caching for year {year} ---")

    # Initialize storage readers and writers
    processed_reader = LocalStorage(
        data_root=data_root, file_format="csv", data_type="processed"
    )
    processed_writer = LocalStorage(
        data_root=data_root, file_format="csv", data_type="processed"
    )

    # 1. Load all team_game data for the entire season
    print(f"Loading all team_game data for {year}...")
    team_game_records = processed_reader.read_index("team_game", {"year": year})
    if not team_game_records:
        print(f"No team_game data found for year {year}. Exiting.")
        return

    team_game_df = pd.DataFrame.from_records(team_game_records)
    print(f"Loaded {len(team_game_df)} total team-game records.")

    # 2. Determine the weeks to process
    weeks = sorted(team_game_df["week"].unique())
    # Start from week 2, as week 1 has no prior data to adjust
    # Go one week past the max to calculate stats for the final week
    process_weeks = range(2, max(weeks) + 2)

    print(f"Will generate caches for weeks {list(process_weeks)}...")

    # 3. Loop through each week, calculate point-in-time stats, and save
    for week in tqdm(process_weeks, desc=f"Caching weekly stats for {year}"):
        # Filter data to include only games played *before* the current week
        prior_games_df = team_game_df[team_game_df["week"] < week].copy()

        if prior_games_df.empty:
            print(f"  Week {week}: No prior games found, skipping.")
            continue

        # Calculate season-to-date stats using only past data
        team_season_pre_week = aggregate_team_season(prior_games_df)

        # Perform opponent adjustment on the point-in-time data
        team_season_adj_pre_week = apply_iterative_opponent_adjustment(
            team_season_pre_week, prior_games_df
        )

        # Add the 'before_week' identifier
        team_season_adj_pre_week["before_week"] = week

        # Reorder for clarity
        cols = team_season_adj_pre_week.columns.tolist()
        if "before_week" in cols:
            cols.insert(1, cols.pop(cols.index("before_week")))
            team_season_adj_pre_week = team_season_adj_pre_week[cols]

        # Save the cached data to its weekly partition
        partition_values = {"year": year, "week": week}
        partition = Partition(partition_values)
        records_to_write = team_season_adj_pre_week.to_dict(orient="records")
        processed_writer.write("team_week_adj", records_to_write, partition=partition)

    print(f"--- Successfully cached weekly adjusted stats for year {year} ---")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Cache weekly opponent-adjusted stats for a full season."
    )
    parser.add_argument(
        "--year",
        type=int,
        required=True,
        help="The year to process.",
    )
    parser.add_argument(
        "--data-root",
        type=str,
        default=None,
        help="Absolute path to the root directory for data storage.",
    )
    args = parser.parse_args()

    cache_season_stats(args.year, args.data_root)


if __name__ == "__main__":
    main()
