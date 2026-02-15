#!/usr/bin/env python3
"""
Pre-calculates and caches weekly, point-in-time, NON-ADJUSTED stats for a full season.

This is the first stage of the weekly caching process.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cks_picks_cfb.config import get_data_root
from cks_picks_cfb.features.core import aggregate_team_season
from cks_picks_cfb.utils.base import Partition
from cks_picks_cfb.utils.local_storage import LocalStorage


def cache_running_stats(year: int, data_root: str | None):
    """
    Generates and caches point-in-time non-adjusted stats for each week of a season.
    """
    print(f"--- Starting weekly NON-ADJUSTED stats caching for year {year} ---")

    processed_reader = LocalStorage(
        data_root=data_root, file_format="csv", data_type="processed"
    )
    processed_writer = LocalStorage(
        data_root=data_root, file_format="csv", data_type="processed"
    )

    print(f"Loading all team_game data for {year}...")
    team_game_records = processed_reader.read_index("team_game", {"year": year})
    if not team_game_records:
        print(f"No team_game data found for year {year}. Exiting.")
        return

    team_game_df = pd.DataFrame.from_records(team_game_records)
    print(f"Loaded {len(team_game_df)} total team-game records.")

    weeks = sorted(team_game_df["week"].unique())
    process_weeks = range(2, max(weeks) + 2)

    print(f"Will generate non-adjusted caches for weeks {list(process_weeks)}...")

    for week in tqdm(
        process_weeks, desc=f"Caching non-adjusted weekly stats for {year}"
    ):
        prior_games_df = team_game_df[team_game_df["week"] < week].copy()

        if prior_games_df.empty:
            print(f"  Week {week}: No prior games found, skipping.")
            continue

        team_season_pre_week = aggregate_team_season(prior_games_df)
        team_season_pre_week["before_week"] = week

        cols = team_season_pre_week.columns.tolist()
        if "before_week" in cols:
            cols.insert(1, cols.pop(cols.index("before_week")))
            team_season_pre_week = team_season_pre_week[cols]

        partition_values = {"year": year, "week": week}
        partition = Partition(partition_values)
        records_to_write = team_season_pre_week.to_dict(orient="records")
        processed_writer.write(
            "running_team_season", records_to_write, partition=partition
        )

    print(f"--- Successfully cached non-adjusted weekly stats for year {year} ---")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Cache weekly non-adjusted stats for a full season."
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

    data_root = args.data_root or get_data_root()
    cache_running_stats(args.year, data_root)


if __name__ == "__main__":
    main()
