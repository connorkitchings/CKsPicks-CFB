#!/usr/bin/env python3
"""Seed the reviewed legacy play fixes as immutable Bronze and Silver data."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone

from dotenv import load_dotenv

from cks_picks_cfb.data.catalog import (
    register_dataset_version,
    register_source_capture,
)
from cks_picks_cfb.data.lake import capture_provider_records
from cks_picks_cfb.data.silver import build_silver_version
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.features.byplay import legacy_data_correction_records

EFFECTIVE_AT = datetime(2026, 8, 9, tzinfo=timezone.utc)


def _code_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def main() -> None:
    load_dotenv()
    conn_url = os.getenv("DATABASE_URL")
    if not conn_url:
        raise SystemExit("DATABASE_URL is required")
    if os.getenv("CFB_ARTIFACT_ENV") != "preview":
        raise SystemExit("Correction seeding is allowed only in preview")
    storage = get_storage()
    records = legacy_data_correction_records()
    capture = capture_provider_records(
        storage,
        provider="cks_internal",
        entity="data_corrections",
        records=records,
        captured_at=EFFECTIVE_AT,
        effective_at=EFFECTIVE_AT,
        request={"policy": "legacy_data_corrections_v1"},
        response_metadata={"approval": "repository_legacy_policy"},
        capture_id=hashlib.sha256(b"legacy_data_corrections_v1").hexdigest()[:32],
    )
    register_source_capture(conn_url, capture)
    ref, manifest = build_silver_version(
        storage,
        dataset="data_corrections",
        records=records,
        source_captures=[capture],
        as_of=EFFECTIVE_AT,
        code_sha=_code_sha(),
        config_sha=hashlib.sha256(b"legacy_data_corrections_v1").hexdigest(),
    )
    register_dataset_version(conn_url, ref, manifest)
    output_uri = "artifacts/preview/refs/data-corrections-v1.json"
    payload = json.dumps(asdict(ref), indent=2, sort_keys=True).encode()
    if storage.exists(output_uri):
        if storage.read_bytes(output_uri) != payload:
            raise FileExistsError(f"Immutable correction ref exists: {output_uri}")
    else:
        storage.write_bytes(payload, output_uri)
    print(json.dumps(asdict(ref), sort_keys=True))


if __name__ == "__main__":
    main()
