#!/usr/bin/env python3
"""Build one season-scoped Silver version from imported historical captures."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone

import psycopg
from dotenv import load_dotenv

from cks_picks_cfb.data.catalog import (
    register_dataset_version,
    register_existing_dataset_ref,
    source_capture_by_id,
)
from cks_picks_cfb.data.lake import DatasetRef, read_dataset, read_source_capture
from cks_picks_cfb.data.silver import (
    DATASET_PROVIDERS,
    build_silver_version,
)
from cks_picks_cfb.data.storage import get_storage

SOURCE_ENTITIES = {
    "teams": "teams",
    "team_aliases": "teams",
    "venues": "venues",
    "games": "games",
    "schedule_revisions": "games",
    "game_outcomes": "games",
    "plays": "plays",
    "team_game_stats": "game_stats",
    "market_quotes": "betting_lines",
    "market_snapshots": "betting_lines",
    "legacy_market_references": "betting_lines",
    "weather_observations": "weather_observations",
    "preseason_team_inputs": "team_season",
}


def _code_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _ref(storage, uri: str) -> DatasetRef:
    return DatasetRef(**json.loads(storage.read_bytes(uri).decode()))


def _capture_ids(conn_url: str, entity: str, season: int, dataset: str) -> list[str]:
    providers = DATASET_PROVIDERS.get(dataset, ("cfbd", "legacy_cfbd_export"))
    placeholders = ",".join(["%s"] * len(providers))
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT capture_id FROM catalog.source_captures "
                f"WHERE entity = %s AND provider IN ({placeholders}) "
                "AND state = 'registered' "
                "AND (request->'years' @> %s::jsonb "
                "OR request->'source_partitions'->>'year' = %s "
                "OR request->'source_partitions'->>'season' = %s "
                "OR (%s IN ('teams', 'venues') AND request->'years' = '[]'::jsonb)) "
                "ORDER BY captured_at, capture_id",
                (
                    entity,
                    *providers,
                    json.dumps([season]),
                    str(season),
                    str(season),
                    entity,
                ),
            )
            return [str(row[0]) for row in cur.fetchall()]


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=sorted(SOURCE_ENTITIES), required=True)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--games-ref-uri")
    parser.add_argument("--week-policy-ref-uri")
    parser.add_argument("--output-ref-uri", required=True)
    parser.add_argument("--optional", action="store_true")
    parser.add_argument(
        "--environment",
        choices=["production", "preview"],
        default=os.getenv("CFB_ARTIFACT_ENV", "production"),
    )
    args = parser.parse_args()
    if args.season == 2020:
        raise SystemExit("2020 is excluded from historical Silver builds")
    if args.season == 2019 and args.dataset != "preseason_team_inputs":
        raise SystemExit("2019 may only build preseason_team_inputs")
    if args.environment == "preview":
        conn_url = os.getenv("PREVIEW_DATABASE_URL") or os.getenv("DATABASE_URL")
    else:
        conn_url = os.getenv("DATABASE_URL")
    if not conn_url:
        raise SystemExit("DATABASE_URL is required")
    storage = get_storage(environment=args.environment)
    if storage.exists(args.output_ref_uri):
        register_existing_dataset_ref(conn_url, storage, args.output_ref_uri)
        print(storage.read_bytes(args.output_ref_uri).decode())
        return
    source_entity = SOURCE_ENTITIES[args.dataset]
    ids = _capture_ids(conn_url, source_entity, args.season, args.dataset)
    if not ids:
        if args.optional:
            print(
                json.dumps(
                    {
                        "state": "unavailable",
                        "dataset": args.dataset,
                        "season": args.season,
                    },
                    sort_keys=True,
                )
            )
            return
        raise LookupError(
            f"No imported {source_entity} captures found for season {args.season}"
        )
    captures = [source_capture_by_id(conn_url, capture_id) for capture_id in ids]
    records = []
    for capture in captures:
        rows = read_source_capture(storage, capture).to_dict("records")
        source_uri = capture.request.get("source_uri") if capture.request else None
        source_sha = None
        if capture.response_metadata:
            source_sha = capture.response_metadata.get("source_sha256")
        for row in rows:
            row.setdefault("__capture_id", capture.capture_id)
            row.setdefault("__captured_at", capture.captured_at.isoformat())
            row.setdefault("__capture_provider", capture.provider)
            if source_uri:
                row.setdefault("__source_uri", source_uri)
            if source_sha:
                row.setdefault("__source_sha256", source_sha)
        records.extend(rows)
    context = {}
    if args.games_ref_uri:
        context["games"] = read_dataset(storage, _ref(storage, args.games_ref_uri))
    if args.week_policy_ref_uri:
        context["week_policy"] = read_dataset(
            storage, _ref(storage, args.week_policy_ref_uri)
        )
    cutoff = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    try:
        ref, manifest = build_silver_version(
            storage,
            dataset=args.dataset,
            records=records,
            source_captures=captures,
            as_of=cutoff,
            code_sha=_code_sha(),
            config_sha=hashlib.sha256(
                f"history:{args.dataset}:{args.season}:v1".encode()
            ).hexdigest(),
            context=context,
        )
        if manifest.state != "validated":
            raise RuntimeError(
                f"Historical Silver validation failed: {manifest.validation}"
            )
    except Exception as exc:
        if args.optional:
            print(
                json.dumps(
                    {
                        "state": "unavailable",
                        "dataset": args.dataset,
                        "season": args.season,
                        "reason": str(exc)[:200],
                    },
                    sort_keys=True,
                )
            )
            return
        raise
    register_dataset_version(conn_url, ref, manifest)
    storage.write_bytes(
        json.dumps(asdict(ref), indent=2, sort_keys=True).encode(),
        args.output_ref_uri,
    )
    print(json.dumps(asdict(ref), sort_keys=True))


if __name__ == "__main__":
    main()
