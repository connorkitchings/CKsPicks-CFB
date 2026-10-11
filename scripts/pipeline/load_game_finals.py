#!/usr/bin/env python3
"""Load certified Silver finals into game_results (scores only, no grades).

Use this for a week whose run is display-only or otherwise never scored, so the
grades-only backfill (backfill_v5_unconstrained_grades.py) has finals to read.
It inserts missing rows, leaves matching rows alone and aborts on any stored
score that differs from the certified final. It does not touch grades,
prediction runs or system_stats.

Dry run is the default:
    zsh scripts/ops/with_preview_env.sh env DATABASE_URL="$PREVIEW_DATABASE_URL" \\
        PYTHONPATH=src:. uv run python scripts/pipeline/load_game_finals.py \\
        --year 2026 --week 6 --outcomes-ref-uri <game_outcomes_ref.json URI> \\
        --environment preview
Add --apply to write. Production also needs --confirm-production.
"""

from __future__ import annotations

import argparse
import json
import os

import psycopg
from dotenv import load_dotenv

from cks_picks_cfb.data.lake import DatasetRef, read_dataset
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ops.game_finals import (
    apply_finals,
    fetch_existing,
    plan_finals,
)


def _resolve_db_url(environment: str, confirm_production: bool, apply: bool) -> str:
    if environment == "production":
        if apply and not confirm_production:
            raise SystemExit("Production writes require --confirm-production")
        url = os.getenv("DATABASE_URL")
        if not url:
            raise SystemExit("DATABASE_URL is not set")
        return url
    url = os.getenv("PREVIEW_DATABASE_URL")
    if not url:
        raise SystemExit("PREVIEW_DATABASE_URL must identify an isolated Neon branch")
    if url == os.getenv("DATABASE_URL"):
        raise SystemExit("PREVIEW_DATABASE_URL must not equal DATABASE_URL")
    return url


def _load_outcomes(storage, ref_uri: str):
    ref = json.loads(storage.read_bytes(ref_uri))
    if ref.get("dataset") != "game_outcomes":
        raise SystemExit("--outcomes-ref-uri is not a Silver game_outcomes DatasetRef")
    dataset_ref = DatasetRef(
        **{
            key: ref[key]
            for key in ("dataset", "version_id", "schema_version", "content_sha", "uri")
        }
    )
    return read_dataset(storage, dataset_ref), dataset_ref


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--outcomes-ref-uri", required=True)
    parser.add_argument(
        "--environment", choices=("preview", "production"), default="preview"
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-production", action="store_true")
    args = parser.parse_args()

    conn_url = _resolve_db_url(args.environment, args.confirm_production, args.apply)
    storage = get_storage(environment=args.environment)
    outcomes, dataset_ref = _load_outcomes(storage, args.outcomes_ref_uri)

    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        existing = fetch_existing(cur, season=args.year, week=args.week)
        plan = plan_finals(outcomes, existing, season=args.year, week=args.week)
        print(
            json.dumps(
                {
                    "environment": args.environment,
                    "game_outcomes_version": dataset_ref.version_id,
                    "mode": "apply" if args.apply else "dry-run",
                    **plan.summary(),
                },
                indent=2,
            )
        )
        if plan.conflicts:
            print(json.dumps(plan.conflicts, indent=2))
            raise SystemExit(
                "Stored scores differ from certified finals; nothing written"
            )
        if not args.apply:
            return 0
        written = apply_finals(cur, plan)
        conn.commit()
        print(f"inserted {written} game_results rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
