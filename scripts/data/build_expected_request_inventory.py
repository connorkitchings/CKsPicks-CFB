#!/usr/bin/env python3
"""Derive an immutable-input CFBD request inventory without consulting attempts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv

from cks_picks_cfb.data.lake import DatasetRef
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.data.week_policy import load_week_policy_spec
from cks_picks_cfb.quality.request_inventory import (
    build_expected_request_inventory,
    read_pinned_schedule,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--schedule-ref", type=Path)
    source.add_argument("--raw-schedule-uri", type=str)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--canonical-week", type=int, required=True)
    parser.add_argument(
        "--environment", choices=("preview", "production"), required=True
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load_dotenv()
    if os.getenv("CFB_STORAGE_BACKEND") != "r2":
        raise SystemExit("request inventory requires explicit R2 storage")
    storage = get_storage(environment=args.environment)
    if args.schedule_ref:
        ref = asdict(DatasetRef(**json.loads(args.schedule_ref.read_text())))
    else:
        if args.raw_schedule_uri != f"raw/games/year={args.season}/part-0.parquet":
            raise ValueError("Raw schedule URI must match the requested season")
        digest = hashlib.sha256(storage.read_bytes(args.raw_schedule_uri)).hexdigest()
        ref = {
            "dataset": "games",
            "schema_version": "raw_games_snapshot_v1",
            "version_id": digest[:24],
            "content_sha": digest,
            "uri": args.raw_schedule_uri,
        }
    schedule = read_pinned_schedule(storage, ref, season=args.season)
    inventory = build_expected_request_inventory(
        schedule,
        schedule_ref=ref,
        policy=load_week_policy_spec(args.policy),
        season=args.season,
        canonical_week=args.canonical_week,
    )
    inventory["week_policy_path"] = str(args.policy)
    raw = json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(raw)
    print(
        json.dumps({"requests": len(inventory["requests"]), "output": str(args.output)})
    )


if __name__ == "__main__":
    main()
