#!/usr/bin/env python3
"""Combine explicit season-scoped dataset refs into one immutable training ref."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone

import pandas as pd
from dotenv import load_dotenv

from cks_picks_cfb.data.catalog import register_dataset_version
from cks_picks_cfb.data.lake import (
    BuildRequest,
    DatasetRef,
    build_dataset_version,
    read_dataset,
)
from cks_picks_cfb.data.silver import SILVER_CONTRACTS, validate_contract
from cks_picks_cfb.data.storage import get_storage


def _ref(storage, uri: str) -> DatasetRef:
    return DatasetRef(**json.loads(storage.read_bytes(uri).decode()))


def _code_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=sorted(SILVER_CONTRACTS), required=True)
    parser.add_argument("--season", action="append", type=int, required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--output-ref-uri", required=True)
    parser.add_argument("--allow-2026", action="store_true")
    args = parser.parse_args()
    seasons = sorted(set(args.season))
    allowed = set(range(2021, 2027 if args.allow_2026 else 2026))
    if 2020 in seasons or any(year not in allowed for year in seasons):
        raise SystemExit(f"Combined refs support only {sorted(allowed)}")
    storage = get_storage()
    refs = [
        _ref(storage, f"artifacts/preview/refs/history/{args.dataset}-{year}.json")
        for year in seasons
    ]
    frame = pd.concat([read_dataset(storage, ref) for ref in refs], ignore_index=True)
    validation = validate_contract(args.dataset, frame)
    cutoff = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    ref, manifest = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset=args.dataset,
            parent_refs=tuple(refs),
            code_sha=_code_sha(),
            config_sha=hashlib.sha256(
                f"combined:{args.dataset}:{seasons}:v1".encode()
            ).hexdigest(),
            as_of=cutoff,
            schema_version=SILVER_CONTRACTS[args.dataset].schema_version,
            tier="silver",
        ),
        records=frame.to_dict("records"),
        partitions={"seasons": seasons},
        validation=validation,
    )
    register_dataset_version(os.environ["DATABASE_URL"], ref, manifest)
    payload = json.dumps(asdict(ref), indent=2, sort_keys=True).encode()
    if storage.exists(args.output_ref_uri):
        if storage.read_bytes(args.output_ref_uri) != payload:
            raise FileExistsError(
                f"Immutable combined ref exists: {args.output_ref_uri}"
            )
    else:
        storage.write_bytes(payload, args.output_ref_uri)
    print(json.dumps(asdict(ref), sort_keys=True))


if __name__ == "__main__":
    main()
