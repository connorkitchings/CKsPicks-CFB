#!/usr/bin/env python3
"""Upload a local trained model as an immutable, checksummed artifact."""

from __future__ import annotations

import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from cks_picks_cfb.artifacts import sha256_bytes, write_json_artifact
from cks_picks_cfb.data.storage import get_storage


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--artifact-uri", required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--feature-version", required=True)
    parser.add_argument("--schema-version", required=True)
    parser.add_argument("--training-years", required=True)
    parser.add_argument(
        "--promotion-report",
        required=True,
        help="Durable URI or repository path for the signed-off promotion report.",
    )
    args = parser.parse_args()

    if not args.model.is_file():
        raise SystemExit(f"Model file not found: {args.model}")
    store = get_storage()
    if store.exists(args.artifact_uri):
        raise SystemExit(
            f"Immutable model artifact already exists: {args.artifact_uri}"
        )
    payload = args.model.read_bytes()
    checksum = sha256_bytes(payload)
    try:
        code_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        code_sha = "unknown"
    store.write_bytes(payload, args.artifact_uri)
    manifest = {
        "schema_version": "model_artifact_v1",
        "model_id": args.model_id,
        "feature_version": args.feature_version,
        "feature_schema_version": args.schema_version,
        "training_years": args.training_years,
        "promotion_report": args.promotion_report,
        "code_sha": code_sha,
        "artifact_uri": args.artifact_uri,
        "sha256": checksum,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json_artifact(manifest, f"{args.artifact_uri}.manifest.json", store)
    print(f"Uploaded {args.artifact_uri}\nsha256={checksum}")
