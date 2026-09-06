#!/usr/bin/env python3
"""Build and register one canonical Silver dataset from explicit Bronze captures."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone

from dotenv import load_dotenv

from cks_picks_cfb.data.catalog import (
    register_dataset_version,
    source_capture_by_id,
)
from cks_picks_cfb.data.lake import DatasetRef, read_dataset, read_source_capture
from cks_picks_cfb.data.runtime import resolve_runtime_target
from cks_picks_cfb.data.silver import SILVER_CONTRACTS, build_silver_version
from cks_picks_cfb.data.storage import get_storage


def _code_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _ref(storage, uri: str) -> DatasetRef:
    raw = json.loads(storage.read_bytes(uri).decode())
    return DatasetRef(**raw)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=sorted(SILVER_CONTRACTS), required=True)
    parser.add_argument("--capture-id", action="append", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--games-ref-uri")
    parser.add_argument("--week-policy-ref-uri")
    parser.add_argument("--output-ref-uri", required=True)
    parser.add_argument(
        "--environment", choices=("preview", "production"), required=True
    )
    args = parser.parse_args()
    target = resolve_runtime_target(args.environment)
    conn_url = target.database_url
    storage = get_storage(environment=args.environment)
    captures = [source_capture_by_id(conn_url, value) for value in args.capture_id]
    records = []
    for capture in captures:
        capture_records = read_source_capture(storage, capture).to_dict("records")
        source_uri = capture.request.get("source_uri") if capture.request else None
        source_sha = None
        if capture.response_metadata:
            source_sha = capture.response_metadata.get("source_sha256")
        for record in capture_records:
            record.setdefault("__capture_id", capture.capture_id)
            record.setdefault("__captured_at", capture.captured_at.isoformat())
            record.setdefault("__capture_provider", capture.provider)
            if source_uri:
                record.setdefault("__source_uri", source_uri)
            if source_sha:
                record.setdefault("__source_sha256", source_sha)
        records.extend(capture_records)
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
    config_sha = hashlib.sha256(
        json.dumps(
            {
                "dataset": args.dataset,
                "schema": SILVER_CONTRACTS[args.dataset].schema_version,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    ref, manifest = build_silver_version(
        storage,
        dataset=args.dataset,
        records=records,
        source_captures=captures,
        as_of=cutoff,
        code_sha=_code_sha(),
        config_sha=config_sha,
        context=context,
    )
    register_dataset_version(conn_url, ref, manifest)
    payload = json.dumps(asdict(ref), indent=2, sort_keys=True).encode()
    if storage.exists(args.output_ref_uri):
        if storage.read_bytes(args.output_ref_uri) != payload:
            raise FileExistsError(f"Immutable ref exists: {args.output_ref_uri}")
    else:
        storage.write_bytes(payload, args.output_ref_uri)
    print(json.dumps(asdict(ref), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
