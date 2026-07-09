#!/usr/bin/env python3
"""Preflight checks for the 2026 weekly operating path."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

from cks_picks_cfb.artifacts import (
    local_prediction_path,
    local_scored_path,
    prediction_artifact_path,
    scored_artifact_path,
)
from cks_picks_cfb.data.storage import get_storage

REQUIRED_R2_VARS = [
    "CFB_R2_BUCKET",
    "CFB_R2_ACCOUNT_ID",
    "CFB_R2_ACCESS_KEY",
    "CFB_R2_SECRET_KEY",
]

REQUIRED_DB_TABLES = ["games", "game_results", "system_stats", "current_week"]


def _ok(message: str) -> None:
    print(f"OK  {message}")


def _fail(message: str, failures: list[str]) -> None:
    print(f"ERR {message}")
    failures.append(message)


def _warn(message: str) -> None:
    print(f"WARN {message}")


def check_storage(*, allow_local: bool, failures: list[str]) -> None:
    if not os.getenv("CFBD_API_KEY"):
        _fail("CFBD_API_KEY is not set; weekly ingestion will fail.", failures)

    backend = os.getenv("CFB_STORAGE_BACKEND", "local").lower()
    if backend != "r2" and not allow_local:
        _fail(
            "CFB_STORAGE_BACKEND must be 'r2' for the 2026 MVP weekly path "
            "(use --allow-local for local-only development).",
            failures,
        )
        return

    if backend == "r2":
        missing = [name for name in REQUIRED_R2_VARS if not os.getenv(name)]
        if missing:
            _fail(f"Missing R2 environment variables: {', '.join(missing)}", failures)
            return

    try:
        storage = get_storage()
    except Exception as exc:
        _fail(f"Storage backend failed to initialize: {exc}", failures)
        return

    _ok(f"Storage backend initialized: {storage.describe()}")


def check_database(*, skip_db: bool, failures: list[str]) -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        _fail("DATABASE_URL is not set.", failures)
        return

    if skip_db:
        _warn("Skipping live database schema check (--skip-db).")
        return

    try:
        import psycopg

        with psycopg.connect(database_url) as conn:
            with conn.cursor() as cur:
                for table in REQUIRED_DB_TABLES:
                    cur.execute("SELECT to_regclass(%s)", (table,))
                    exists = cur.fetchone()[0] is not None
                    if not exists:
                        _fail(f"Neon table is missing: {table}", failures)
                cur.execute("SELECT season, week FROM current_week WHERE id = 1")
                row = cur.fetchone()
                if row:
                    _ok(f"Neon current_week row exists: season={row[0]} week={row[1]}")
                else:
                    _fail("Neon current_week singleton row is missing.", failures)
    except Exception as exc:
        _fail(f"Database schema check failed: {exc}", failures)


def check_deploy_config(failures: list[str]) -> None:
    if Path("vercel.json").exists():
        _fail(
            "Root vercel.json exists; Vercel should use Root Directory = web/.",
            failures,
        )
    else:
        _ok("No root vercel.json; Vercel Root Directory should be web/.")

    if not Path("web/package.json").exists():
        _fail("web/package.json is missing.", failures)
    else:
        _ok("web/package.json found.")


def report_artifact_paths(year: int, week: int) -> None:
    print("\nArtifact paths")
    print(f"  local predictions: {local_prediction_path(year, week)}")
    print(f"  durable predictions: {prediction_artifact_path(year, week)}")
    print(f"  local scored: {local_scored_path(year, week)}")
    print(f"  durable scored: {scored_artifact_path(year, week)}")


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Weekly pipeline preflight checks.")
    parser.add_argument("--year", type=int, required=True, help="Season year")
    parser.add_argument("--week", type=int, required=True, help="Week number")
    parser.add_argument(
        "--allow-local",
        action="store_true",
        help="Allow CFB_STORAGE_BACKEND=local for development checks.",
    )
    parser.add_argument(
        "--skip-db",
        action="store_true",
        help="Skip live Neon connection/schema checks.",
    )
    args = parser.parse_args()

    failures: list[str] = []
    print(f"Preflight for {args.year} week {args.week}")
    check_storage(allow_local=args.allow_local, failures=failures)
    check_database(skip_db=args.skip_db, failures=failures)
    check_deploy_config(failures)
    report_artifact_paths(args.year, args.week)

    if failures:
        print("\nPreflight failed.")
        raise SystemExit(1)

    print("\nPreflight passed.")


if __name__ == "__main__":
    main()
