#!/usr/bin/env python3
"""Build a versioned canonical-week policy Silver dataset for one season."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone

import psycopg
from dotenv import load_dotenv

from cks_picks_cfb.data.catalog import (
    register_dataset_version,
    source_capture_by_id,
)
from cks_picks_cfb.data.lake import read_source_capture
from cks_picks_cfb.data.silver import build_silver_version, normalize_games
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.data.week_policy import (
    build_policy_rows,
    load_week_policy_spec,
    policy_config_sha,
)


def _code_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _games_capture_ids(conn_url: str, season: int) -> list[str]:
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT capture_id FROM catalog.source_captures "
                "WHERE entity = 'games' "
                "AND provider IN ('cfbd', 'legacy_cfbd_export') "
                "AND state = 'registered' "
                "AND (request->'years' @> %s::jsonb "
                "OR request->'source_partitions'->>'year' = %s "
                "OR request->'source_partitions'->>'season' = %s) "
                "ORDER BY captured_at, capture_id",
                (json.dumps([season]), str(season), str(season)),
            )
            return [str(row[0]) for row in cur.fetchall()]


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--assignments", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--capture-id", action="append")
    parser.add_argument("--output-ref-uri", required=True)
    args = parser.parse_args()
    conn_url = os.getenv("DATABASE_URL")
    if not conn_url:
        raise SystemExit("DATABASE_URL is required")
    storage = get_storage()
    spec = load_week_policy_spec(args.assignments)
    if spec.season != args.season:
        raise SystemExit(
            f"Policy {spec.policy_version} targets season {spec.season}, "
            f"not {args.season}"
        )
    capture_ids = args.capture_id or _games_capture_ids(conn_url, args.season)
    if not capture_ids:
        raise LookupError(
            f"No registered games captures found for season {args.season}"
        )
    captures = [
        source_capture_by_id(conn_url, capture_id) for capture_id in capture_ids
    ]
    records = []
    for capture in captures:
        records.extend(read_source_capture(storage, capture).to_dict("records"))
    games = normalize_games(records)
    games = games[games["season"].astype(int) == args.season]
    policy_rows = build_policy_rows(games, spec, season=args.season)
    cutoff = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    ref, manifest = build_silver_version(
        storage,
        dataset="schedule_week_policy",
        records=policy_rows.to_dict("records"),
        source_captures=captures,
        as_of=cutoff,
        code_sha=_code_sha(),
        config_sha=policy_config_sha(spec, season=args.season),
        context={"games": games},
    )
    if manifest.state != "validated":
        raise RuntimeError(
            f"Schedule week policy validation failed: {manifest.validation}"
        )
    register_dataset_version(conn_url, ref, manifest)
    payload = json.dumps(asdict(ref), indent=2, sort_keys=True).encode()
    if storage.exists(args.output_ref_uri):
        if storage.read_bytes(args.output_ref_uri) != payload:
            raise FileExistsError(
                f"Immutable schedule week policy ref exists: {args.output_ref_uri}"
            )
    else:
        storage.write_bytes(payload, args.output_ref_uri)
    print(json.dumps(asdict(ref), sort_keys=True))


if __name__ == "__main__":
    main()
