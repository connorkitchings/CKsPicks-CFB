#!/usr/bin/env python3
"""Runs the complete data ingestion pipeline for a given year."""

import argparse
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cfb_model.data.ingestion import (
    BettingLinesIngester,
    CoachesIngester,
    GamesIngester,
    PlaysIngester,
    RostersIngester,
    TeamsIngester,
    VenuesIngester,
)
from cfb_model.data.storage.local_storage import LocalStorage


def run_pipeline_for_year(year: int, data_root: str | None):
    """Executes the full ingestion pipeline for a single year."""
    print(f"--- Starting full data ingestion for year {year} ---")

    # 1. Initialize a single, shared storage backend
    storage = LocalStorage(data_root=data_root, file_format="csv", data_type="raw")
    print(f"Using data root: {storage.root()}")

    # 2. Define the ingestion sequence
    ingestion_sequence = [
        (TeamsIngester, {}),
        (VenuesIngester, {}),
        (GamesIngester, {"season_type": "regular"}),
        (RostersIngester, {}),
        (CoachesIngester, {}),
        (BettingLinesIngester, {"season_type": "regular"}),
        (PlaysIngester, {"season_type": "regular"}),
    ]

    # 3. Run each ingester in order
    for ingester_class, kwargs in ingestion_sequence:
        try:
            ingester = ingester_class(year=year, storage=storage, **kwargs)
            ingester.run()
            print(f"✅ Successfully completed {ingester_class.__name__}")
        except Exception as e:
            print(f"❌ Error during {ingester_class.__name__}: {e}")
            print(f"--- Halting ingestion pipeline for {year} due to error ---")
            sys.exit(1)

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
    args = parser.parse_args()

    run_pipeline_for_year(args.year, args.data_root)


if __name__ == "__main__":
    main()
