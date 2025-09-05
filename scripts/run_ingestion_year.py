#!/usr/bin/env python3
"""Runs the complete data ingestion pipeline for a given year."""

import argparse
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cfb_model.data.ingestion import (  # isort: skip
    BettingLinesIngester,
    CoachesIngester,
    GameStatsIngester,
    GamesIngester,
    PlaysIngester,
    RostersIngester,
    TeamsIngester,
    VenuesIngester,
)
from cfb_model.data.storage.local_storage import LocalStorage  # isort: skip


def run_pipeline_for_year(year: int, data_root: str | None, limit_games: int | None = None, season_type: str = "regular"):
    """Executes the full data ingestion pipeline for a single year.

    limit_games: if provided, passes a limit to ingesters that support it (plays, betting_lines, game_stats).
    season_type: regular or postseason.
    """
    print(f"--- Starting full data ingestion for year {year} ---")

    # 1. Initialize a single, shared storage backend
    storage = LocalStorage(data_root=data_root, file_format="csv", data_type="raw")
    print(f"Using data root: {storage.root()}")

    # 2. Define the ingestion sequence
    ingestion_sequence = [
        (TeamsIngester, {}),
        (VenuesIngester, {}),
        (GamesIngester, {"season_type": season_type}),
        (RostersIngester, {}),
        (CoachesIngester, {}),
        (BettingLinesIngester, {"season_type": season_type, "limit_games": limit_games}),
        (PlaysIngester, {"season_type": season_type, "limit_games": limit_games}),
        # Advanced box scores for validation purposes
        (GameStatsIngester, {"limit_games": limit_games, "season_type": season_type}),
    ]

    # 3. Run each ingester in order
    failures: list[str] = []
    for ingester_class, kwargs in ingestion_sequence:
        try:
            ingester = ingester_class(year=year, storage=storage, **kwargs)
            if limit_games is not None and hasattr(ingester, "limit_games"):
                setattr(ingester, "limit_games", limit_games)
            ingester.run()
            print(f"✅ Successfully completed {ingester_class.__name__}")
        except Exception as e:
            msg = f"❌ Error during {ingester_class.__name__}: {e}"
            print(msg)
            failures.append(msg)
            # Continue with remaining ingestion steps so subsequent stages can be tested

    if failures:
        print(f"--- Completed ingestion for {year} with {len(failures)} failure(s) ---")
        for f in failures:
            print(f)
    else:
        print(f"--- Successfully completed full data ingestion for year {year} ---")

    print(f"--- Successfully completed full data ingestion for year {year} ---")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run the full data ingestion pipeline for a specific year."
    )
    parser.add_argument(
        "--year",
        type=int,
        required=True,
        help="The year to ingest data for.",
    )
    parser.add_argument(
        "--data-root",
        type=str,
        default=None,
        help="Absolute path to the root directory for data storage.",
    )
    parser.add_argument(
        "--limit-games",
        type=int,
        default=None,
        help="Limit number of games for testing (applies to plays, betting_lines, game_stats)",
    )
    parser.add_argument(
        "--season-type",
        type=str,
        default="regular",
        choices=["regular", "postseason"],
        help="Season type to ingest",
    )
    args = parser.parse_args()

    run_pipeline_for_year(args.year, args.data_root, limit_games=args.limit_games, season_type=args.season_type)


if __name__ == "__main__":
    main()
