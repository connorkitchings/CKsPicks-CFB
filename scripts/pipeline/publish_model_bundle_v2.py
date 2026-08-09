#!/usr/bin/env python3
"""Publish and validate a complete ten-cell model_bundle_v2 routing manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.model_bundle import load_model_bundle_v2


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--environment", choices=("preview", "production"), required=True
    )
    args = parser.parse_args()
    raw = json.loads(args.manifest.read_text(encoding="utf-8"))
    raw["schema_version"] = "model_bundle_v2"
    bundle_id = str(raw["bundle_id"])
    payload = json.dumps(raw, indent=2, sort_keys=True).encode("utf-8")
    sha256 = hashlib.sha256(payload).hexdigest()
    uri = f"artifacts/{args.environment}/models/{bundle_id}/manifest.json"
    storage = get_storage()
    if storage.exists(uri):
        if storage.read_bytes(uri) != payload:
            raise FileExistsError(f"Immutable bundle ID already exists: {bundle_id}")
    else:
        storage.write_bytes(payload, uri)
    bundle = load_model_bundle_v2(
        {"artifact_uri": uri, "sha256": sha256}, storage=storage
    )
    print(
        json.dumps(
            {
                "artifact_uri": uri,
                "sha256": sha256,
                "bundle_id": bundle.bundle_id,
                "route_count": len(bundle.routes),
                "environment": args.environment,
                "code_sha": bundle.code_sha,
                "caller_environment": os.getenv("CFB_ARTIFACT_ENV"),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
