#!/usr/bin/env python3
"""
Ingest all data for a full season from the CFBD API into cloud/local storage.

Usage:
    PYTHONPATH=.:src uv run python scripts/data/ingest_season.py --year 2026
    PYTHONPATH=.:src uv run python scripts/data/ingest_season.py --year 2026 --entities games,teams,venues

Storage backend is auto-detected from CFB_STORAGE_BACKEND env var (r2/s3/local).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from cks_picks_cfb.data.betting_lines import BettingLinesIngester
from cks_picks_cfb.data.coaches import CoachesIngester
from cks_picks_cfb.data.games import GamesIngester
from cks_picks_cfb.data.plays import PlaysIngester
from cks_picks_cfb.data.rankings import RankingsIngester
from cks_picks_cfb.data.recruiting import RecruitingIngester
from cks_picks_cfb.data.rosters import RostersIngester
from cks_picks_cfb.data.teams import TeamsIngester
from cks_picks_cfb.data.venues import VenuesIngester

ENTITIES = {
    "teams": TeamsIngester,
    "venues": VenuesIngester,
    "games": GamesIngester,
    "rosters": RostersIngester,
    "coaches": CoachesIngester,
    "betting_lines": BettingLinesIngester,
    "plays": PlaysIngester,
    "rankings": RankingsIngester,
    "recruiting": RecruitingIngester,
    "external_ratings": None,  # handled specially
}

DEFAULT_ORDER = list(ENTITIES.keys())


def main():
    parser = argparse.ArgumentParser(description="Ingest a full season from CFBD API.")
    parser.add_argument("--year", type=int, required=True, help="Season year")
    parser.add_argument(
        "--entities",
        type=str,
        default="teams,venues,games",
        help=f"Comma-separated entities (order matters). Default: teams,venues,games. Available: {','.join(DEFAULT_ORDER)}",
    )
    parser.add_argument(
        "--season-type",
        type=str,
        default="regular",
        help="Season type for games/plays/betting_lines",
    )
    args = parser.parse_args()

    requested = [e.strip().lower() for e in args.entities.split(",")]
    unknown = [e for e in requested if e not in ENTITIES]
    if unknown:
        print(f"Unknown entities: {unknown}")
        sys.exit(1)

    for entity_key in requested:
        if entity_key == "external_ratings":
            print("⏭  Skipping external_ratings (requires offline CSVs)")
            continue

        cls = ENTITIES[entity_key]
        print(f"\n{'=' * 60}")
        print(f"  Ingesting {entity_key} for {args.year}...")
        print(f"{'=' * 60}")

        kwargs = {"year": args.year}
        if entity_key in ("games", "betting_lines", "plays"):
            kwargs["season_type"] = args.season_type

        try:
            ingester = cls(**kwargs)
            ingester.run()
            print(f"  ✅ {entity_key} done")
        except Exception as exc:
            print(f"  ❌ {entity_key} failed: {exc}")
            # Continue with next entity (non-fatal)
            continue

    print(f"\n✅ Full-season ingestion complete for {args.year}")


if __name__ == "__main__":
    main()
