"""Script to ingest betting lines for multiple years (2019, 2021-2025)."""

import logging
import sys
from pathlib import Path
from typing import List

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))
# noqa: E402
from src.data.betting_lines import BettingLinesIngester  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def ingest_betting_lines(years: List[int]) -> None:
    """Ingest betting lines for the specified years.

    Args:
        years: List of years to ingest data for.
    """
    for year in years:
        logging.info(f"Starting betting lines ingestion for {year}...")
        try:
            ingester = BettingLinesIngester(year=year)
            ingester.run()
            logging.info(f"Successfully ingested betting lines for {year}.")
        except Exception as e:
            logging.error(f"Failed to ingest betting lines for {year}: {e}")


def main() -> None:
    """Main execution function."""
    # Years to ingest: 2019, 2021-2025 (skipping 2020 as per project convention)
    target_years = [2019, 2021, 2022, 2023, 2024, 2025]

    logging.info(f"Targeting years: {target_years}")
    ingest_betting_lines(target_years)
    logging.info("Betting lines ingestion process completed.")


if __name__ == "__main__":
    main()
