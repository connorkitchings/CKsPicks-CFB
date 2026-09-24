#!/usr/bin/env python3
"""Select an exact reviewed weekly run; supports same-slate fallback."""

from __future__ import annotations

import argparse
import os

import psycopg
from dotenv import load_dotenv

from cks_picks_cfb.ops.lease import assert_active_pipeline_lease
from cks_picks_cfb.ops.public_selection import select_week_run


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument(
        "--environment", choices=("preview", "production"), required=True
    )
    parser.add_argument("--allow-v4-fallback", action="store_true")
    args = parser.parse_args()
    url_var = (
        "PREVIEW_DATABASE_URL" if args.environment == "preview" else "DATABASE_URL"
    )
    conn_url = os.getenv(url_var)
    if not conn_url:
        raise SystemExit(f"{url_var} is required")
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            assert_active_pipeline_lease(cur)
            previous = select_week_run(
                cur,
                season=args.year,
                week=args.week,
                run_id=args.run_id,
                reason=args.reason,
                allow_v4_fallback=args.allow_v4_fallback,
            )
    print(
        f"Selected {args.run_id} for {args.year} week {args.week}; previous={previous}"
    )


if __name__ == "__main__":
    main()
