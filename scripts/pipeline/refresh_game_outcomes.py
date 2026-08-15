#!/usr/bin/env python3
"""Capture current CFBD results as immutable Bronze and Silver outcomes.

This deliberately refreshes only final-score truth. It does not overwrite the
historical schedule or compatibility projection, so a live provider correction
can be reviewed and used as an explicit parent of a rebuilt Gold dataset.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone

import cfbd
from dotenv import load_dotenv

from cks_picks_cfb.data.base import BaseIngester
from cks_picks_cfb.data.catalog import (
    register_dataset_version,
    register_existing_dataset_ref,
    register_source_capture,
)
from cks_picks_cfb.data.lake import capture_provider_records
from cks_picks_cfb.data.silver import build_silver_version
from cks_picks_cfb.data.storage import get_storage


def _code_sha() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return completed.stdout.strip() if completed.returncode == 0 else "unknown"


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", action="append", type=int, required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--output-ref-uri", required=True)
    parser.add_argument(
        "--environment", choices=["preview", "production"], required=True
    )
    args = parser.parse_args()
    if 2020 in args.year:
        raise SystemExit("2020 is excluded from the model data lineage")
    token = os.getenv("CFBD_API_KEY")
    if not token:
        raise SystemExit("CFBD_API_KEY is required")
    conn_url = (
        os.getenv("PREVIEW_DATABASE_URL") or os.getenv("DATABASE_URL")
        if args.environment == "preview"
        else os.getenv("DATABASE_URL")
    )
    if not conn_url:
        raise SystemExit("DATABASE_URL is required")
    storage = get_storage(environment=args.environment)
    if storage.exists(args.output_ref_uri):
        register_existing_dataset_ref(conn_url, storage, args.output_ref_uri)
        print(storage.read_bytes(args.output_ref_uri).decode())
        return

    api = cfbd.GamesApi(cfbd.ApiClient(cfbd.Configuration(access_token=token)))
    records: list[dict[str, object]] = []
    for year in sorted(set(args.year)):
        games = api.get_games(year=year, season_type="regular", classification="fbs")
        for game in games:
            records.append(BaseIngester.provider_value(game))
    captured_at = datetime.now(timezone.utc)
    cutoff = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    capture = capture_provider_records(
        storage,
        provider="cfbd",
        entity="game_outcomes",
        records=records,
        captured_at=captured_at,
        effective_at=cutoff,
        request={
            "endpoint": "GamesApi.get_games",
            "years": sorted(set(args.year)),
            "season_type": "regular",
            "classification": "fbs",
        },
        provider_api_version=getattr(cfbd, "__version__", None),
        response_metadata={"purpose": "historical_outcome_refresh"},
    )
    register_source_capture(conn_url, capture)
    outcome_records = [
        {
            "season": record["season"],
            "game_id": record["id"],
            "completed": record["completed"],
            "home_points": record.get("homePoints", record.get("home_points")),
            "away_points": record.get("awayPoints", record.get("away_points")),
        }
        for record in records
    ]
    ref, manifest = build_silver_version(
        storage,
        dataset="game_outcomes",
        records=outcome_records,
        source_captures=[capture],
        as_of=cutoff,
        code_sha=_code_sha(),
        config_sha=hashlib.sha256(b"cfbd_game_outcomes_refresh_v1").hexdigest(),
    )
    register_dataset_version(conn_url, ref, manifest)
    storage.write_bytes(
        json.dumps(asdict(ref), indent=2, sort_keys=True).encode(),
        args.output_ref_uri,
    )
    print(json.dumps(asdict(ref), sort_keys=True))


if __name__ == "__main__":
    main()
