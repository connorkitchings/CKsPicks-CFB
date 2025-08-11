#!/usr/bin/env python3
"""CLI entry points for data ingestion modules.

This script provides command-line access to all ingestion modules
while maintaining backward compatibility with existing workflows.
"""

import argparse
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cfb_model.data.ingestion import (
    BettingLinesIngester,
    CoachesIngester,
    GamesIngester,
    PlaysIngester,
    RostersIngester,
    TeamsIngester,
    VenuesIngester,
)


def main():
    """Main CLI entry point for ingestion commands."""
    parser = argparse.ArgumentParser(
        description="CFBD Data Ingestion CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python scripts/ingest_cli.py teams --year 2024
  python scripts/ingest_cli.py games --year 2024 --season-type regular
  python scripts/ingest_cli.py plays --year 2024 --limit-games 5
""",
    )

    parser.add_argument(
        "entity",
        choices=[
            "teams",
            "venues",
            "games",
            "betting_lines",
            "rosters",
            "coaches",
            "plays",
        ],
        help="Entity type to ingest",
    )

    parser.add_argument(
        "--year",
        type=int,
        default=2024,
        help="Year to ingest data for (default: 2024)",
    )

    parser.add_argument(
        "--classification",
        default="fbs",
        help="Team classification filter (default: fbs)",
    )

    parser.add_argument(
        "--season-type",
        default="regular",
        help="Season type for games/plays (default: regular)",
    )

    parser.add_argument(
        "--limit-games",
        type=int,
        help="Limit number of games for testing (betting_lines, plays)",
    )

    parser.add_argument(
        "--limit-teams",
        type=int,
        help="Limit number of teams for testing (rosters, coaches)",
    )

    parser.add_argument(
        "--min-year",
        type=int,
        help="Minimum year for coach history",
    )

    parser.add_argument(
        "--max-year",
        type=int,
        help="Maximum year for coach history",
    )

    parser.add_argument(
        "--data-root",
        type=str,
        default=None,
        help="Absolute path to the root directory for data storage.",
    )

    args = parser.parse_args()

    # Create appropriate ingester based on entity type
    if args.entity == "teams":
        ingester = TeamsIngester(
            year=args.year, classification=args.classification, data_root=args.data_root
        )
    elif args.entity == "venues":
        ingester = VenuesIngester(
            year=args.year, classification=args.classification, data_root=args.data_root
        )
    elif args.entity == "games":
        ingester = GamesIngester(
            year=args.year,
            classification=args.classification,
            season_type=args.season_type,
            data_root=args.data_root,
        )
    elif args.entity == "betting_lines":
        ingester = BettingLinesIngester(
            year=args.year,
            classification=args.classification,
            season_type=args.season_type,
            limit_games=args.limit_games,
            data_root=args.data_root,
        )
    elif args.entity == "rosters":
        ingester = RostersIngester(
            year=args.year,
            classification=args.classification,
            limit_teams=args.limit_teams,
            data_root=args.data_root,
        )
    elif args.entity == "coaches":
        ingester = CoachesIngester(
            year=args.year,
            classification=args.classification,
            min_year=args.min_year,
            max_year=args.max_year,
            limit_teams=args.limit_teams,
            data_root=args.data_root,
        )
    elif args.entity == "plays":
        ingester = PlaysIngester(
            year=args.year,
            classification=args.classification,
            season_type=args.season_type,
            limit_games=args.limit_games,
            data_root=args.data_root,
        )

    # Run the ingestion
    try:
        ingester.run()
        print(f"\n✅ Successfully completed {args.entity} ingestion!")
    except Exception as e:
        print(f"\n❌ Error during {args.entity} ingestion: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
