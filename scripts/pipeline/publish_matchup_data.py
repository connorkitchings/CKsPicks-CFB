#!/usr/bin/env python3
"""Publish the matchup data layer (V5 measurements, adjusted values, game log,
rating decomposition) to Neon, bound to the rating manifest the site serves.

Reads the verified V5 rating artifacts from R2 (explicit URIs; Preview and
production share one bucket), builds the four data tables, reconciles them with
hard gates, and writes one transaction. Dry run is the default and also prints
the payload hash; production passes ``--expect-payload-sha`` with Preview's.

    PYTHONPATH=src:. uv run python scripts/pipeline/publish_matchup_data.py \\
        --season 2026 --environment preview \\
        --rating-manifest-uri <rating-manifest.json> \\
        --measurement-manifest-uri <measurement-manifest.json>

Add ``--apply`` to write. Production writes go through
``scripts/ops/with_production_pipeline_env.sh``.
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
from cks_picks_cfb.ops.lease import assert_active_pipeline_lease
from cks_picks_cfb.ops.v5_release import assert_v5_database_environment
from contracts.teams import TEAM_LOGO_MAP

URL_ENV = {"preview": "PREVIEW_DATABASE_URL", "production": "DATABASE_URL"}


def print_gates(gates: list[mp.GateResult]) -> bool:
    ok = True
    for gate in gates:
        print(
            f"  [{'ok' if gate.ok else 'FAIL'}] {gate.name}"
            + (f" - {gate.detail}" if gate.detail and not gate.ok else "")
        )
        ok &= gate.ok
    return ok


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument(
        "--lineage", choices=("intended_update",), default="intended_update"
    )
    parser.add_argument("--rating-manifest-uri", required=True)
    parser.add_argument("--measurement-manifest-uri", default=None)
    parser.add_argument("--six-a-run-id", default=None)
    parser.add_argument("--six-a-root-sha256", default=None)
    parser.add_argument("--environment", choices=sorted(URL_ENV), required=True)
    parser.add_argument("--weeks", help="As-of weeks, e.g. 0-5 or 5 (default: all)")
    parser.add_argument("--apply", action="store_true", help="Write (default: dry run)")
    parser.add_argument(
        "--expect-payload-sha", help="Abort unless the payload hash matches"
    )
    args = parser.parse_args()

    url = os.getenv(URL_ENV[args.environment])
    if not url:
        print(f"Set {URL_ENV[args.environment]}", file=sys.stderr)
        return 2
    bridged = args.six_a_run_id is not None or args.six_a_root_sha256 is not None
    if bridged and (not args.six_a_run_id or not args.six_a_root_sha256):
        print("6A run id and root sha256 are required together.", file=sys.stderr)
        return 2
    if not bridged and not args.measurement_manifest_uri:
        print("A measurement manifest URI is required.", file=sys.stderr)
        return 2
    storage = get_storage(environment="preview")  # artifacts live in the shared bucket
    try:
        weeks = mp.parse_weeks(args.weeks)
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                artifacts, built, game_names, payload_sha = mp.prepare_run(
                    storage,
                    cur,
                    season=args.season,
                    lineage=args.lineage,
                    rating_manifest_uri=args.rating_manifest_uri,
                    measurement_manifest_uri=args.measurement_manifest_uri,
                    weeks=weeks,
                    alias_map=TEAM_LOGO_MAP,
                    six_a_run_id=args.six_a_run_id,
                    six_a_root_sha256=args.six_a_root_sha256,
                )
                print(f"rating manifest   {artifacts.rating_sha256}")
                print(f"measurement parent {artifacts.measurement_sha256}")
                print(f"observations      {artifacts.observations_version_id}")
                print(f"as-of weeks       {built.weeks}")
                print(f"row counts        {json.dumps(built.payload.row_counts())}")
                print(
                    f"rating scale      {json.dumps(built.payload.rating_scale, sort_keys=True)}"
                )
                print(f"payload sha256    {payload_sha}")
                print("gates:")
                gates = mp.run_static_gates(built, game_names) + mp.run_db_gates(
                    cur, built, artifacts, args.season
                )
                if not print_gates(gates):
                    print("Gate failure: nothing written.", file=sys.stderr)
                    return 3
                if args.expect_payload_sha and args.expect_payload_sha != payload_sha:
                    print(
                        f"Payload hash {payload_sha} != expected {args.expect_payload_sha}",
                        file=sys.stderr,
                    )
                    return 4
                if bridged:
                    # A signed bridge verifier must attest this exact rating
                    # root, 6A root and rebuilt payload before any write.
                    try:
                        mp.assert_bridge_verifier(
                            storage,
                            mp.bridge_verifier_uri(args.rating_manifest_uri),
                            artifacts.rating_sha256,
                            artifacts.measurement_sha256,
                            payload_sha,
                        )
                    except mp.PublishError as exc:
                        print(f"Bridge verifier: {exc}", file=sys.stderr)
                        return 3
                    print("bridge verifier attests this build.")
                unmigrated = mp.missing_tables(cur)
                if unmigrated:
                    print(f"tables not migrated (0021): {unmigrated}")
                    if args.apply:
                        print("Apply migration 0021 first.", file=sys.stderr)
                        return 7
                    print("Dry run: nothing written.")
                    return 0
                stale = mp.stale_keys(cur, built, args.season)
                if stale:
                    for table, keys in stale.items():
                        print(
                            f"stale in {table}: {len(keys)} e.g. {keys[:2]}",
                            file=sys.stderr,
                        )
                    print(
                        "Stale rows would remain (the pipeline role cannot DELETE).",
                        file=sys.stderr,
                    )
                    return 5
                conflicts = mp.check_component_conflicts(
                    cur, built.payload.frames["team_rating_components"]
                )
                if conflicts:
                    print(f"component conflicts: {conflicts[:3]}", file=sys.stderr)
                    return 6
                if not args.apply:
                    print("Dry run: nothing written.")
                    return 0
                assert_v5_database_environment(cur, args.environment)
                assert_active_pipeline_lease(cur)
                log_game_ids = None
                if bridged:
                    # Gates evaluated the full payload; restrict the per-game
                    # log write to this publication's weeks so earlier
                    # lineages' provenance is never restamped (table keys are
                    # lineage-unaware). Other tables are new keys already.
                    cur.execute(
                        "SELECT game_id FROM games WHERE season = %s AND week = ANY(%s)",
                        (args.season, sorted(built.as_of_cutoffs)),
                    )
                    log_game_ids = {int(r[0]) for r in cur.fetchall()}
                    if not log_game_ids:
                        print(
                            "Bridge mode: no games in scope; nothing written.",
                            file=sys.stderr,
                        )
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
                counts = mp.write_payload(
                    cur,
                    built,
                    artifacts,
                    season=args.season,
                    environment=args.environment,
                    code_sha=code_sha,
                    payload_sha=payload_sha,
                    log_game_ids=log_game_ids,
                )
            conn.commit()
        print(f"Published {json.dumps(counts)} ({args.environment}).")
        return 0
    except mp.PublishError as exc:
        print(f"Cannot publish: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
