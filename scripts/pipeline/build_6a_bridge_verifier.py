#!/usr/bin/env python3
"""Build the signed gate-receipt verifier for a 6A-bridged matchup payload.

Loads the frozen rating manifest plus the pinned published 6A run through the
bridge loader, rebuilds every table, re-runs the static and database gates,
and writes the signed ``bridge-verifier-manifest.json`` beside the rating
manifest. The publisher asserts this verifier before any bridged write.

    PYTHONPATH=.:src zsh scripts/ops/with_preview_env.sh uv run python \\
        scripts/pipeline/build_6a_bridge_verifier.py \\
        --rating-manifest-uri <rating-manifest.json> \\
        --six-a-run-id <run-id> --six-a-root-sha256 <sha> \\
        --season 2026 --weeks 6 --environment preview

Dry run (default) prints the manifest and writes nothing. ``--apply`` writes
it write-once: an identical object is a no-op, a differing one refuses.
Database gates are read-only. No Neon writes, ever.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
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
    parser.add_argument("--rating-manifest-uri", required=True)
    parser.add_argument("--six-a-run-id", required=True)
    parser.add_argument("--six-a-root-sha256", required=True)
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--weeks", default=None)
    parser.add_argument("--environment", choices=sorted(URL_ENV), required=True)
    parser.add_argument("--out-uri", default=None)
    parser.add_argument("--apply", action="store_true", help="Write (default: dry run)")
    args = parser.parse_args()

    url = os.getenv(URL_ENV[args.environment])
    if not url:
        print(f"Set {URL_ENV[args.environment]}", file=sys.stderr)
        return 2
    storage = get_storage(environment="preview")  # artifacts live in the shared bucket
    out_uri = args.out_uri or mp.bridge_verifier_uri(args.rating_manifest_uri)
    try:
        weeks = mp.parse_weeks(args.weeks)
        with psycopg.connect(url) as conn, conn.cursor() as cur:
            artifacts, built, game_names, payload_sha = mp.prepare_run(
                storage,
                cur,
                season=args.season,
                lineage="intended_update",
                rating_manifest_uri=args.rating_manifest_uri,
                measurement_manifest_uri=None,
                weeks=weeks,
                alias_map=TEAM_LOGO_MAP,
                six_a_run_id=args.six_a_run_id,
                six_a_root_sha256=args.six_a_root_sha256,
            )
            static_gates = mp.run_static_gates(built, game_names)
            db_gates = mp.run_db_gates(cur, built, artifacts, args.season)
            ok = True
            for gate in static_gates + db_gates:
                print(
                    f"  [{'ok' if gate.ok else 'FAIL'}] {gate.name}"
                    + (f" - {gate.detail}" if gate.detail and not gate.ok else "")
                )
                ok &= gate.ok
            if not ok:
                print("Gate failure: no verifier written.", file=sys.stderr)
                return 3
            try:
                code_sha = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip()
            except Exception:  # noqa: BLE001
                code_sha = None
            manifest = mp.build_bridge_verifier_manifest(
                artifacts, built, payload_sha, static_gates, db_gates, code_sha
            )
            raw = json.dumps(manifest, indent=1, sort_keys=True).encode()
            print(f"payload sha256 {payload_sha}")
            print(f"verifier uri   {out_uri}")
            if not args.apply:
                print("Dry run: nothing written.")
                return 0
            try:
                existing = storage.read_bytes(out_uri)
            except Exception:  # noqa: BLE001
                existing = None
            if existing is not None:
                if existing == raw:
                    print("Verifier already published byte-identical; no write.")
                    return 0
                print(
                    f"Refusing: {out_uri} already holds different bytes.",
                    file=sys.stderr,
                )
                return 4
            storage.write_bytes(raw, out_uri)
        print(f"Wrote bridge verifier ({len(raw)} bytes).")
        return 0
    except mp.PublishError as exc:
        print(f"Cannot verify: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
