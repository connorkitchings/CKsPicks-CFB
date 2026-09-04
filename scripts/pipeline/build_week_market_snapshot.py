#!/usr/bin/env python3
"""Build immutable weekly market quotes and snapshot from the publish capture."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone

import pandas as pd
import psycopg
from dotenv import load_dotenv

from cks_picks_cfb.data.catalog import (
    register_dataset_version,
    register_existing_dataset_ref,
    source_capture_by_id,
)
from cks_picks_cfb.data.lake import read_source_capture
from cks_picks_cfb.data.silver import build_silver_version
from cks_picks_cfb.data.storage import get_storage


def _code_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _write_ref(storage, uri: str, ref) -> None:
    payload = json.dumps(asdict(ref), indent=2, sort_keys=True).encode()
    if storage.exists(uri):
        if storage.read_bytes(uri) != payload:
            raise FileExistsError(f"Immutable ref exists: {uri}")
    else:
        storage.write_bytes(payload, uri)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--pipeline-run-id", required=True)
    parser.add_argument("--output-ref-uri", required=True)
    args = parser.parse_args()

    conn_url = os.getenv("DATABASE_URL")
    if not conn_url:
        raise SystemExit("DATABASE_URL is required")
    storage = get_storage()
    if storage.exists(args.output_ref_uri):
        register_existing_dataset_ref(conn_url, storage, args.output_ref_uri)
        print(storage.read_bytes(args.output_ref_uri).decode())
        return

    ingestion_run_ids = {
        "cfbd": f"{args.pipeline_run_id}:betting_lines",
        "the_odds_api": f"{args.pipeline_run_id}:market_quotes",
    }
    with psycopg.connect(conn_url) as conn:
        rows = conn.execute(
            "SELECT capture_id FROM catalog.source_captures "
            "WHERE ((ingestion_run_id = %s AND entity = 'betting_lines' "
            "AND provider = 'cfbd') "
            "OR (ingestion_run_id = %s AND entity = 'market_quotes' "
            "AND provider = 'the_odds_api')) "
            "AND state = 'registered' "
            "ORDER BY captured_at, capture_id",
            (
                ingestion_run_ids["cfbd"],
                ingestion_run_ids["the_odds_api"],
            ),
        ).fetchall()
    if not rows:
        raise LookupError(
            f"No registered market capture for {sorted(ingestion_run_ids.values())}"
        )

    captures = [source_capture_by_id(conn_url, str(row[0])) for row in rows]
    cutoff = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    late = [capture.capture_id for capture in captures if capture.captured_at > cutoff]
    if late:
        raise ValueError(
            "Market capture occurred after the requested as-of cutoff; rerun with "
            f"an honest later cutoff. Late captures: {late}"
        )

    records: list[dict] = []
    game_ids: set[int] = set()
    for capture in captures:
        for raw in read_source_capture(storage, capture).to_dict("records"):
            row = dict(raw)
            row.setdefault("__capture_id", capture.capture_id)
            row.setdefault("__captured_at", capture.captured_at.isoformat())
            row.setdefault("__capture_provider", capture.provider)
            records.append(row)
            if row.get("game_id") is not None:
                game_ids.add(int(row["game_id"]))
            elif row.get("id") is not None:
                game_ids.add(int(row["id"]))
    games = pd.DataFrame.from_records(
        [
            {"game_id": game_id, "season": args.year, "week": args.week}
            for game_id in sorted(game_ids)
        ]
    )
    if games.empty:
        raise ValueError("Market capture did not contain any game IDs")

    config_sha = hashlib.sha256(
        f"weekly-market:{args.year}:{args.week}:consensus_then_median_v1".encode()
    ).hexdigest()
    run_prefix = args.output_ref_uri.rsplit("/", 1)[0]
    for dataset, output_uri in (
        ("market_quotes", f"{run_prefix}/market_quotes_ref.json"),
        ("market_snapshots", args.output_ref_uri),
    ):
        ref, manifest = build_silver_version(
            storage,
            dataset=dataset,
            records=records,
            source_captures=captures,
            as_of=cutoff,
            code_sha=_code_sha(),
            config_sha=config_sha,
            context={"games": games},
        )
        register_dataset_version(conn_url, ref, manifest)
        _write_ref(storage, output_uri, ref)
        if dataset == "market_snapshots":
            print(json.dumps(asdict(ref), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
