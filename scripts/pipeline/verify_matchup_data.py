#!/usr/bin/env python3
"""Read-only verification of published matchup data against the V5 artifacts.

Rebuilds every table from the verified rating and measurement artifacts, runs
the reconciliation gates, and checks that each rebuilt row exists in Neon with
equal values. Exit 0 only when every gate passes and nothing differs.

    PYTHONPATH=src:. uv run python scripts/pipeline/verify_matchup_data.py \\
        --season 2026 --environment preview \\
        --rating-manifest-uri <rating-manifest.json> \\
        --measurement-manifest-uri <measurement-manifest.json>
"""

from __future__ import annotations

import argparse
import os
import sys

import psycopg
from dotenv import load_dotenv

from cks_picks_cfb.data import matchup_publish as mp
from cks_picks_cfb.data.storage import get_storage
from contracts.teams import TEAM_LOGO_MAP

URL_ENV = {"preview": "PREVIEW_DATABASE_URL", "production": "DATABASE_URL"}


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--rating-manifest-uri", required=True)
    parser.add_argument("--measurement-manifest-uri", required=True)
    parser.add_argument("--environment", choices=sorted(URL_ENV), required=True)
    parser.add_argument("--weeks")
    args = parser.parse_args()
    url = os.getenv(URL_ENV[args.environment])
    if not url:
        print(f"Set {URL_ENV[args.environment]}", file=sys.stderr)
        return 2
    storage = get_storage(environment="preview")
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        artifacts, built, game_names, payload_sha = mp.prepare_run(
            storage,
            cur,
            season=args.season,
            lineage="intended_update",
            rating_manifest_uri=args.rating_manifest_uri,
            measurement_manifest_uri=args.measurement_manifest_uri,
            weeks=mp.parse_weeks(args.weeks),
            alias_map=TEAM_LOGO_MAP,
        )
        print(f"payload sha256 {payload_sha}")
        gates = mp.run_static_gates(built, game_names) + mp.run_db_gates(
            cur, built, artifacts, args.season
        )
        ok = True
        for gate in gates:
            print(
                f"  [{'ok' if gate.ok else 'FAIL'}] {gate.name}"
                + (f" - {gate.detail}" if gate.detail and not gate.ok else "")
            )
            ok &= gate.ok
        mismatches = mp.compare_db_to_payload(cur, built, args.season)
        print(f"database rows differing from the artifacts: {len(mismatches)}")
        for line in mismatches[:10]:
            print(f"  {line}")
        ok &= not mismatches
    print("VERIFIED" if ok else "VERIFICATION FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
