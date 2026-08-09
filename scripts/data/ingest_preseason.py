#!/usr/bin/env python3
"""Capture immutable, provider-backed preseason inputs in configured storage."""

from __future__ import annotations

import argparse
import os
from datetime import date

import cfbd
from dotenv import load_dotenv

from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.preseason import (
    REQUIRED_SNAPSHOT_SOURCES,
    PreseasonSnapshotIngester,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument(
        "--as-of",
        required=True,
        help="Immutable ISO date identifying the provider snapshot (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--sources",
        default=",".join(REQUIRED_SNAPSHOT_SOURCES),
        help="Comma-separated subset of preseason sources.",
    )
    args = parser.parse_args()
    date.fromisoformat(args.as_of)

    load_dotenv()
    token = os.getenv("CFBD_API_KEY")
    if not token:
        raise ValueError("Missing required environment variable: CFBD_API_KEY")
    sources = tuple(
        source.strip() for source in args.sources.split(",") if source.strip()
    )
    unknown = sorted(set(sources) - set(REQUIRED_SNAPSHOT_SOURCES))
    if unknown:
        raise ValueError(f"Unknown preseason sources: {', '.join(unknown)}")

    ingester = PreseasonSnapshotIngester(
        args.year,
        args.as_of,
        get_storage(),
        cfbd.Configuration(access_token=token),
    )
    counts = ingester.run(sources)
    print(f"Captured preseason snapshot {args.year}/{args.as_of}: {counts}")


if __name__ == "__main__":
    main()
