#!/usr/bin/env python3
"""
Ingest a single week's worth of data from the CFBD API into cloud/local storage.

Usage:
    PYTHONPATH=.:src uv run python scripts/data/ingest_week.py --year 2026 --week 1
    PYTHONPATH=.:src uv run python scripts/data/ingest_week.py --year 2026 --week 1 --entities plays,betting_lines

Storage backend is auto-detected from CFB_STORAGE_BACKEND env var (r2/s3/local).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from cks_picks_cfb.data.betting_lines import BettingLinesIngester
from cks_picks_cfb.data.game_stats import GameStatsIngester
from cks_picks_cfb.data.plays import PlaysIngester

ENTITIES = {
    "plays": PlaysIngester,
    "betting_lines": BettingLinesIngester,
    "game_stats": GameStatsIngester,
}

WEEK_KWARGS = {
    "plays": "only_week",
    "betting_lines": "week",
    "game_stats": "week",
}


def main():
    parser = argparse.ArgumentParser(description="Ingest a single week from CFBD API.")
    parser.add_argument("--year", type=int, required=True, help="Season year")
    parser.add_argument("--week", type=int, required=True, help="Week number")
    parser.add_argument(
        "--entities",
        type=str,
        default="plays,betting_lines",
        help="Comma-separated entities. Default: plays,betting_lines",
    )
    parser.add_argument(
        "--season-type",
        type=str,
        default="regular",
        help="Season type (regular/postseason/both)",
    )
    args = parser.parse_args()

    requested = [e.strip().lower() for e in args.entities.split(",")]
    unknown = [e for e in requested if e not in ENTITIES]
    if unknown:
        print(f"Unknown entities: {unknown}")
        sys.exit(1)

    for entity_key in requested:
        cls = ENTITIES[entity_key]
        kwarg_name = WEEK_KWARGS[entity_key]

        print(f"\n{'=' * 60}")
        print(f"  Ingesting {entity_key} for {args.year} week {args.week}...")
        print(f"{'=' * 60}")

        kwargs = {"year": args.year, "season_type": args.season_type}
        kwargs[kwarg_name] = args.week

        try:
            ingester = cls(**kwargs)
            ingester.run()
            print(f"  ✅ {entity_key} done")
        except Exception as exc:
            print(f"  ❌ {entity_key} failed: {exc}")
            sys.exit(1)

    print(f"\n✅ Week {args.week} ingestion complete")


if __name__ == "__main__":
    main()
