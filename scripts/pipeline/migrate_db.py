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
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--migrations", type=Path, default=Path("contracts/migrations"))
    args = parser.parse_args()
    if not args.database_url:
        raise SystemExit("DATABASE_URL is not set")
    applied = apply_migrations(args.database_url, args.migrations)
    print("Applied migrations: " + (", ".join(applied) if applied else "none"))


if __name__ == "__main__":
    main()
