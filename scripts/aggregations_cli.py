#!/usr/bin/env python3
"""CLI entry points for data aggregation modules (pre-aggregations).

This CLI reads the data root from the environment variable `CFB_MODEL_DATA_ROOT` (via .env)
and does not accept a data-root flag. It runs pre-aggregation jobs that read raw CSV and
write processed CSV partitions.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Ensure src is importable when run directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def get_data_root() -> str | None:
    value = os.getenv("CFB_MODEL_DATA_ROOT")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CFB Model Aggregations CLI (pre-aggregations). Uses CFB_MODEL_DATA_ROOT from env.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  # Ensure CFB_MODEL_DATA_ROOT is set in your .env or shell, then:
  python scripts/aggregations_cli.py preagg --year 2024
  python scripts/aggregations_cli.py byplay --year 2024
""",
    )

    parser.add_argument(
        "command",
        choices=["preagg", "byplay"],
        help="Aggregation command to run",
    )
    parser.add_argument("--year", type=int, required=True, help="Season year")

    args = parser.parse_args()

    data_root = get_data_root()
    if not data_root:
        print(
            "⚠️  CFB_MODEL_DATA_ROOT is not set; defaulting to current working directory's data folder."
        )
        print(
            "   Set it in your .env (CFB_MODEL_DATA_ROOT=/absolute/path) to use an external drive."
        )
        data_root = None

    if args.command == "preagg":
        from cfb_model.data.aggregations.persist import persist_preaggregations

        try:
            print(
                f"Running preagg for year {args.year} using data_root={data_root or '(cwd)'} ..."
            )
            totals = persist_preaggregations(year=args.year, data_root=data_root)
            print(
                f"\n✅ Pre-aggregations complete: byplay={totals['byplay']}, drives={totals['drives']}, "
                f"team_game={totals['team_game']}, team_season={totals['team_season']}, "
                f"team_season_adj={totals['team_season_adj']}"
            )
        except Exception as e:
            print(f"\n❌ Error during pre-aggregation: {e}")
            sys.exit(1)
    elif args.command == "byplay":
        from cfb_model.data.aggregations.persist import persist_byplay_only

        try:
            print(
                f"Running byplay-only for year {args.year} using data_root={data_root or '(cwd)'} ..."
            )
            count = persist_byplay_only(year=args.year, data_root=data_root)
            print(f"\n✅ Byplay-only complete: rows={count}")
        except Exception as e:
            print(f"\n❌ Error during byplay-only: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
