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

from cfb_model.config import get_data_root
from cfb_model.data.aggregations.core import (
    apply_iterative_opponent_adjustment,
)
from cfb_model.data.storage.base import Partition
from cfb_model.data.storage.local_storage import LocalStorage


def cache_season_stats(year: int, data_root: str | None):
    """
    Reads non-adjusted weekly stats, applies opponent adjustment, and saves the result.

    This is the second stage of the weekly caching process.
    """
    print(f"--- Starting weekly ADJUSTED stats caching for year {year} ---")

    processed_reader = LocalStorage(
        data_root=data_root, file_format="csv", data_type="processed"
    )
    processed_writer = LocalStorage(
        data_root=data_root, file_format="csv", data_type="processed"
    )

    # 1. Find the weeks that have non-adjusted cached data
    try:
        base_path = (
            Path(processed_reader.root()) / "running_team_season" / f"year={year}"
        )
        if not base_path.exists():
            print(
                f"No non-adjusted data found for year {year} at {base_path}. Run cache_running_season_stats.py first."
            )
            return
        process_weeks = sorted(
            [int(p.name.split("=")[1]) for p in base_path.iterdir() if p.is_dir()]
        )
    except (FileNotFoundError, IndexError):
        print(f"Could not find any weekly subdirectories in {base_path}")
        return

    print(f"Will generate ADJUSTED caches for weeks {process_weeks}...")

    # Also load team_game data once for the adjustment function
    team_game_records = processed_reader.read_index("team_game", {"year": year})
    if not team_game_records:
        print(
            f"No team_game data found for year {year} for opponent adjustment. Exiting."
        )
        return
    team_game_df = pd.DataFrame.from_records(team_game_records)

    # 2. Loop through each week, load non-adjusted data, adjust, and save
    for week in tqdm(process_weeks, desc=f"Caching adjusted weekly stats for {year}"):
        non_adjusted_records = processed_reader.read_index(
            "running_team_season", {"year": year, "week": week}
        )
        if not non_adjusted_records:
            print(f"  Week {week}: No non-adjusted data found, skipping.")
            continue

        team_season_pre_week = pd.DataFrame.from_records(non_adjusted_records)
        prior_games_df = team_game_df[team_game_df["week"] < week].copy()

        # Perform opponent adjustment on the point-in-time data
        team_season_adj_pre_week = apply_iterative_opponent_adjustment(
            team_season_pre_week, prior_games_df
        )

        team_season_adj_pre_week["before_week"] = week

        cols = team_season_adj_pre_week.columns.tolist()
        if "before_week" in cols:
            cols.insert(1, cols.pop(cols.index("before_week")))
            team_season_adj_pre_week = team_season_adj_pre_week[cols]

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
        help="Absolute path to the root directory for data storage. Defaults to env var or ./data.",
    )
    args = parser.parse_args()

    # Resolve data_root using the centralized config helper if not provided
    data_root = args.data_root or get_data_root()
    cache_season_stats(args.year, data_root)


if __name__ == "__main__":
    main()
