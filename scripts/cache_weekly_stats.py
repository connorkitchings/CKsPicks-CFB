#!/usr/bin/env python3
"""Cache weekly season-to-date stats (running + adjusted) for a full season."""

import argparse
import sys
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd
from tqdm import tqdm

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import get_data_root
from src.features.core import aggregate_team_season, apply_iterative_opponent_adjustment
from src.utils.base import Partition
from src.utils.local_storage import LocalStorage


def cache_running_stats(year: int, data_root: str | None) -> list[int]:
    """Stage 1: cache non-adjusted running stats per week."""
    print(f"--- Starting weekly NON-ADJUSTED stats caching for year {year} ---")

    processed_reader = LocalStorage(
        data_root=data_root, file_format="csv", data_type="processed"
    )
    processed_writer = LocalStorage(
        data_root=data_root, file_format="csv", data_type="processed"
    )

    team_game_records = processed_reader.read_index("team_game", {"year": year})
    if not team_game_records:
        print(f"No team_game data found for season {year}; skipping running caches.")
        return []

    team_game_df = pd.DataFrame.from_records(team_game_records)
    if "week" not in team_game_df:
        print("team_game data missing 'week' column; cannot compute running caches.")
        return []

    weeks = sorted(int(w) for w in team_game_df["week"].dropna().unique())
    if not weeks:
        print("No weeks present in team_game data; nothing to cache.")
        return []

    target_weeks = list(range(2, max(weeks) + 2))
    print(f"Will generate NON-ADJUSTED caches for weeks {target_weeks}...")

    for week in tqdm(
        target_weeks, desc=f"Caching non-adjusted weekly stats for {year}"
    ):
        prior_games_df = team_game_df[team_game_df["week"] < week].copy()
        if prior_games_df.empty:
            continue
        team_season_pre_week = aggregate_team_season(prior_games_df)
        team_season_pre_week["before_week"] = week

        cols = team_season_pre_week.columns.tolist()
        if "before_week" in cols:
            cols.insert(1, cols.pop(cols.index("before_week")))
            team_season_pre_week = team_season_pre_week[cols]

        partition = Partition({"year": year, "week": week})
        processed_writer.write(
            "running_team_season",
            team_season_pre_week.to_dict(orient="records"),
            partition=partition,
        )

    print(f"--- Successfully cached non-adjusted weekly stats for year {year} ---")
    return target_weeks


def cache_adjusted_stats(
    year: int,
    data_root: str | None,
    weeks: list[int] | None = None,
    *,
    iteration_depths: Sequence[int] = (4,),
) -> None:
    """
    Reads non-adjusted weekly stats, applies opponent adjustment, and saves the result.
    """
    print(f"--- Starting weekly ADJUSTED stats caching for year {year} ---")

    processed_reader = LocalStorage(
        data_root=data_root, file_format="csv", data_type="processed"
    )
    processed_writer = LocalStorage(
        data_root=data_root, file_format="csv", data_type="processed"
    )

    # 1. Find the weeks that have non-adjusted cached data
    if weeks is None:
        try:
            base_path = (
                Path(processed_reader.root()) / "running_team_season" / f"year={year}"
            )
            if not base_path.exists():
                print(
                    f"No non-adjusted data found for year {year} at {base_path}. Run stage 'running' first."
                )
                return
            weeks = sorted(
                int(p.name.split("=")[1])
                for p in base_path.iterdir()
                if p.is_dir() and "week=" in p.name
            )
        except (FileNotFoundError, IndexError):
            print("Could not determine weekly subdirectories for adjusted cache.")
            return

    if not weeks:
        print("No weeks found for adjusted caching; nothing to do.")
        return

    normalized_iterations = sorted(
        {int(depth) for depth in iteration_depths if int(depth) >= 0}
    )
    if not normalized_iterations:
        print("No valid iteration counts supplied; skipping adjusted cache build.")
        return

    print(
        f"Will generate ADJUSTED caches for weeks {weeks} at iterations {normalized_iterations}..."
    )

    # Also load team_game data once for the adjustment function
    team_game_records = processed_reader.read_index("team_game", {"year": year})
    if not team_game_records:
        print(
            f"No team_game data found for year {year} for opponent adjustment. Exiting."
        )
        return
    team_game_df = pd.DataFrame.from_records(team_game_records)

    # 2. Loop through each week, load non-adjusted data, adjust, and save
    for week in tqdm(weeks, desc=f"Caching adjusted weekly stats for {year}"):
        non_adjusted_records = processed_reader.read_index(
            "running_team_season", {"year": year, "week": week}
        )
        if not non_adjusted_records:
            print(f"  Week {week}: No non-adjusted data found, skipping.")
            continue

        team_season_pre_week = pd.DataFrame.from_records(non_adjusted_records)
        prior_games_df = team_game_df[team_game_df["week"] < week].copy()

        for iteration_count in normalized_iterations:
            if iteration_count == 0:
                adjusted_df = team_season_pre_week.copy()
            else:
                adjusted_df = apply_iterative_opponent_adjustment(
                    team_season_pre_week,
                    prior_games_df,
                    iterations=iteration_count,
                )

            adjusted_df["before_week"] = week

            cols = adjusted_df.columns.tolist()
            if "before_week" in cols:
                cols.insert(1, cols.pop(cols.index("before_week")))
                adjusted_df = adjusted_df[cols]

            partition_values = {
                "iteration": iteration_count,
                "year": year,
                "week": week,
            }
            partition = Partition(partition_values)
            records_to_write = adjusted_df.to_dict(orient="records")
            processed_writer.write(
                "team_week_adj", records_to_write, partition=partition
            )

    print(f"--- Successfully cached weekly adjusted stats for year {year} ---")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Cache weekly season-to-date stats (running, adjusted, or both)."
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
    parser.add_argument(
        "--stage",
        type=str,
        choices=["running", "adjusted", "both"],
        default="both",
        help="Which stage to run (defaults to both).",
    )
    parser.add_argument(
        "--adjustment-iterations",
        type=str,
        default="4",
        help=(
            "Comma-separated list of opponent-adjustment iteration counts to persist "
            "(default: '4'). Include 0 to also snapshot unadjusted aggregates."
        ),
    )
    args = parser.parse_args()

    # Resolve data_root using the centralized config helper if not provided
    data_root = args.data_root or get_data_root()
    weeks: list[int] | None = None
    if args.stage in {"running", "both"}:
        weeks = cache_running_stats(args.year, data_root)
    if args.stage in {"adjusted", "both"}:
        cache_adjusted_stats(
            args.year,
            data_root,
            weeks,
            iteration_depths=_parse_iteration_depths(args.adjustment_iterations),
        )


def _parse_iteration_depths(raw: str | None) -> Iterable[int]:
    if not raw:
        return [4]
    values = []
    for chunk in (piece.strip() for piece in raw.split(",") if piece.strip()):
        try:
            values.append(int(chunk))
        except ValueError as exc:
            raise ValueError(
                f"Invalid adjustment iteration value '{chunk}'. Expected integers."
            ) from exc
    return values or [4]


if __name__ == "__main__":
    main()
