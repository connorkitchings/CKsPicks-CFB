#!/usr/bin/env python3
"""Apply the append-only SQL migration history to a configured Neon branch."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

from cks_picks_cfb.db.migrations import apply_migrations


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument(
        "--database-url", help="Explicit URL for the reviewed Neon branch"
    )
    target.add_argument(
        "--database-env",
        choices=("DATABASE_URL", "PREVIEW_DATABASE_URL"),
        help="Explicit environment variable containing the reviewed Neon branch URL",
    )
    parser.add_argument("--migrations", type=Path, default=Path("contracts/migrations"))
    args = parser.parse_args()
    database_url = args.database_url or os.getenv(args.database_env)
    if not database_url:
        raise SystemExit("Selected database URL is not set")
    applied = apply_migrations(database_url, args.migrations)
    print("Applied migrations: " + (", ".join(applied) if applied else "none"))


if __name__ == "__main__":
    main()
