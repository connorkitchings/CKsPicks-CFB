"""Estimate The Odds API historical NCAAF backfill cost without network access.

Example:
    PYTHONPATH=src uv run python scripts/data/estimate_historical_odds_backfill.py \
        --schedule /path/to/games.csv
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from cks_picks_cfb.data.the_odds_api import (
    HISTORICAL_CREDITS_PER_SNAPSHOT,
    estimate_historical_snapshot_requests,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--schedule",
        required=True,
        type=Path,
        help="CSV containing the historical schedule and its start_date column.",
    )
    parser.add_argument(
        "--credits-per-snapshot",
        type=int,
        default=HISTORICAL_CREDITS_PER_SNAPSHOT,
        help="Provider credit cost per historical snapshot (default: %(default)s).",
    )
    args = parser.parse_args()

    if args.credits_per_snapshot < 1:
        raise ValueError("--credits-per-snapshot must be positive")
    if not args.schedule.is_file():
        raise FileNotFoundError(f"Schedule CSV not found: {args.schedule}")

    estimate = estimate_historical_snapshot_requests(
        pd.read_csv(args.schedule),
        credits_per_snapshot=args.credits_per_snapshot,
    )
    print(
        json.dumps(
            {
                "schedule": str(args.schedule),
                "provider": "the_odds_api",
                "network_requests_made": 0,
                **estimate,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
