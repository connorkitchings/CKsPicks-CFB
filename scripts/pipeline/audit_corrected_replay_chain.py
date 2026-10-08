#!/usr/bin/env python3
"""Read back and revalidate a corrected replay chain. Never writes cloud state."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ops.v5_intended_update_release import (
    validate_intended_update_release_record,
)
from cks_picks_cfb.ratings_lab.artifacts import canonical_json
from scripts.pipeline.authorize_v5_intended_update_preview import authorization_record
from scripts.pipeline.package_v5_intended_update_runs import package_week


class ReadOnlyEvidence:
    """Cache verified reads and expose no mutation method to the audit."""

    def __init__(self, storage):
        self.storage = storage
        self.raw: dict[str, bytes] = {}

    def read_bytes(self, uri):
        if uri not in self.raw:
            self.raw[uri] = self.storage.read_bytes(uri)
        return self.raw[uri]

    def exists(self, uri):
        return uri in self.raw or self.storage.exists(uri)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def audit(
    storage, *, lock_path, release_tag, bridge_uri, rating_uri, expected_bundle_sha
):
    source = ReadOnlyEvidence(storage)
    lock_raw = lock_path.read_bytes()
    lock = json.loads(lock_raw)
    if set(lock.get("market_sources", {})) != {str(w) for w in range(6)}:
        raise ValueError("c2 certification requires exactly Weeks 0–5")
    bridge_raw = source.read_bytes(bridge_uri)
    bridge = json.loads(bridge_raw)
    verify_signed_payload(bridge, label="corrected bridge")
    weeks = {}
    for key in sorted(lock["market_sources"], key=int):
        week = int(key)
        manifest, scored, predictions_raw, scored_raw = package_week(
            source,
            lock,
            sha(lock_raw),
            week,
            release_tag=release_tag,
            bridge_uri=bridge_uri,
            rating_uri=rating_uri,
        )
        if manifest["inference_bundle_sha256"] != expected_bundle_sha:
            raise ValueError("replay does not use the reviewed B2 bundle")
        for value, raw in ((manifest, predictions_raw), (scored, scored_raw)):
            uri = value["artifact_uri"]
            if source.read_bytes(uri) != raw:
                raise ValueError(f"packaged CSV differs from serving evidence: {uri}")
            manifest_uri = uri.rsplit("/", 1)[0] + "/manifest.json"
            if json.loads(source.read_bytes(manifest_uri)) != value:
                raise ValueError(f"packaged manifest differs: {manifest_uri}")
        record = authorization_record(
            manifest, decision_ref="audit-only-not-authorization"
        )
        validate_intended_update_release_record(
            record,
            manifest=manifest,
            storage=source,
            season=2026,
            week=week,
            environment="preview",
        )
        weeks[key] = {
            "run_id": manifest["run_id"],
            "games": manifest["row_count"],
            "bundle_sha256": manifest["inference_bundle_sha256"],
            "prediction_sha256": sha(predictions_raw),
            "scored_sha256": sha(scored_raw),
            "package_and_release_record_verified": True,
        }
    # Independently read all corrected foundation/replay root members, not only the
    # packaged CSVs. Root pins come from the reviewed lock.
    block = lock["corrected_lineage"]
    roots = {}
    for namespace, name in (("6a", "rebuild"), ("6b", "replay")):
        uri = f"rebuild/{namespace}/{block[name + '_run_id']}/root-manifest.json"
        raw = source.read_bytes(uri)
        if sha(raw) != block[name + "_root_raw_sha256"]:
            raise ValueError(f"root pin differs: {uri}")
        root = json.loads(raw)
        verify_signed_payload(root, label=uri)
        for child, digest in root["objects"].items():
            if sha(source.read_bytes(child)) != digest:
                raise ValueError(f"root child differs: {child}")
        roots[uri] = {"raw_sha256": sha(raw), "objects_verified": len(root["objects"])}
    return {
        "schema_version": "corrected_replay_readback_v1",
        "state": "verified",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "source_lock_sha256": sha(lock_raw),
        "release_tag": release_tag,
        "writes": 0,
        "weeks": weeks,
        "roots": roots,
        "objects": {uri: sha(raw) for uri, raw in sorted(source.raw.items())},
        "limits": [
            "Package/release validation and byte integrity; numerical serving recomputation is a separate receipt.",
            "No authorization, database application or Production activation.",
        ],
    }


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-lock", type=Path, required=True)
    parser.add_argument("--release-tag", required=True)
    parser.add_argument("--bridge-uri", required=True)
    parser.add_argument("--rating-uri", required=True)
    parser.add_argument("--expected-bundle-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if os.getenv("CFB_STORAGE_BACKEND") != "r2":
        raise SystemExit("audit requires explicit R2 backend")
    os.environ["CFB_ARTIFACT_ENV"] = "preview"
    result = audit(
        get_storage(environment="preview"),
        lock_path=args.source_lock,
        release_tag=args.release_tag,
        bridge_uri=args.bridge_uri,
        rating_uri=args.rating_uri,
        expected_bundle_sha=args.expected_bundle_sha,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical_json(result))
    print(
        json.dumps(
            {
                "state": result["state"],
                "objects": len(result["objects"]),
                "weeks": len(result["weeks"]),
                "writes": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
