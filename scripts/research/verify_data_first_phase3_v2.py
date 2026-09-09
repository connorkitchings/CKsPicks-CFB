#!/usr/bin/env python3
"""Independently reconstruct and verify a frozen Preview-only Phase 3 v2 run."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

try:  # Supports both `python script.py` and repository-module invocation.
    from scripts.research.run_data_first_phase3_v2 import compute_phase3_v2
except ModuleNotFoundError:  # pragma: no cover - direct script path only
    from run_data_first_phase3_v2 import compute_phase3_v2

from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload
from cks_picks_cfb.data.data_first_phase3_v2 import (
    PHASE3_V2_DATASETS,
    PHASE3_V2_RETAINED_CORE_SCHEMA,
    REQUIRED_REPAIR_CANONICAL_SHA256,
    REQUIRED_REPAIR_RAW_SHA256,
    Phase3V2Error,
    sha256,
    verify_repair_manifest,
)
from cks_picks_cfb.data.lake import DatasetRef, read_dataset
from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame
from cks_picks_cfb.data.storage import get_storage

REPO_ROOT = Path(__file__).resolve().parents[2]


def _ref(value: dict[str, Any]) -> DatasetRef:
    return DatasetRef(
        dataset=str(value["dataset"]),
        version_id=str(value["version_id"]),
        schema_version=str(value["schema_version"]),
        content_sha=str(value["content_sha"]),
        uri=str(value["uri"]),
    )


def _frame_digest(frame: Any) -> str:
    return sha256(frame.to_dict("records"))


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-uri", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--environment", choices=["preview"], required=True)
    args = parser.parse_args(argv)

    storage = get_storage(environment="preview")
    raw_manifest = storage.read_bytes(args.manifest_uri)
    manifest = json.loads(raw_manifest)
    if manifest.get("schema_version") != PHASE3_V2_RETAINED_CORE_SCHEMA:
        raise Phase3V2Error("unexpected Phase 3 v2 retained-core schema")
    verify_signed_payload(manifest, label="Phase 3 v2 retained core")
    if manifest.get("production_activation_authorized") is not False:
        raise Phase3V2Error("Phase 3 v2 retained core authorizes production")
    identity = manifest.get("identity") or {}
    if identity.get("environment") != "preview":
        raise Phase3V2Error("Phase 3 v2 retained core is not Preview evidence")
    if identity.get("code_sha") != args.expected_code_sha:
        raise Phase3V2Error("Phase 3 v2 code SHA does not match expectation")

    repair_uri = str(manifest.get("repair_manifest_uri") or "")
    raw_repair = storage.read_bytes(repair_uri)
    if hashlib.sha256(raw_repair).hexdigest() != REQUIRED_REPAIR_RAW_SHA256:
        raise Phase3V2Error("Phase 3 v2 Repair parent raw checksum mismatch")
    repair = verify_repair_manifest(json.loads(raw_repair))
    if repair.get("manifest_sha256") != REQUIRED_REPAIR_CANONICAL_SHA256:
        raise Phase3V2Error("Phase 3 v2 Repair parent canonical checksum mismatch")
    if identity.get("repair_manifest_raw_sha256") != REQUIRED_REPAIR_RAW_SHA256:
        raise Phase3V2Error("Phase 3 v2 identity has wrong Repair raw checksum")
    if (
        identity.get("repair_manifest_canonical_sha256")
        != REQUIRED_REPAIR_CANONICAL_SHA256
    ):
        raise Phase3V2Error("Phase 3 v2 identity has wrong Repair canonical checksum")

    frames = {}
    for name, ref_value in (manifest.get("output_refs") or {}).items():
        if name not in PHASE3_V2_DATASETS:
            raise Phase3V2Error(f"unexpected Phase 3 v2 output: {name}")
        dataset, schema = PHASE3_V2_DATASETS[name]
        ref = _ref(ref_value)
        if ref.dataset != dataset or ref.schema_version != schema:
            raise Phase3V2Error(f"Phase 3 v2 output schema mismatch: {name}")
        frame = read_dataset(storage, ref)
        validate_frame(frame, schema_for(dataset, schema))
        frames[name] = frame
    if set(frames) != set(PHASE3_V2_DATASETS):
        raise Phase3V2Error("Phase 3 v2 output set is incomplete")
    if int(len(frames["population"])) != 8936:
        raise Phase3V2Error("Phase 3 v2 population count mismatch")
    if int(frames["population"]["forecast_eligible"].sum()) != 8935:
        raise Phase3V2Error("Phase 3 v2 eligible population mismatch")
    if int(frames["population"]["measurement_usable"].sum()) != 8903:
        raise Phase3V2Error("Phase 3 v2 usable population mismatch")
    if int(len(frames["observations"])) != 303790:
        raise Phase3V2Error("Phase 3 v2 observation grid mismatch")
    if any(frame["season"].astype(int).eq(2020).any() for frame in frames.values()):
        raise Phase3V2Error("Phase 3 v2 outputs contain forbidden 2020")

    recomputed = compute_phase3_v2(
        storage=storage,
        repair=repair,
        identity=identity,
        as_of=pd_timestamp(identity["as_of"]),
    )
    for name, frame in recomputed["frames"].items():
        if _frame_digest(frame) != _frame_digest(frames[name]):
            raise Phase3V2Error(f"independent reconstruction mismatch: {name}")
    if recomputed["retained"]["selected_candidate"] != manifest.get(
        "selected_candidate"
    ):
        raise Phase3V2Error("independent selection differs from retained core")
    certification = json.loads(
        storage.read_bytes(args.manifest_uri.rsplit("/", 1)[0] + "/certification.json")
    )
    verify_signed_payload(certification, label="Phase 3 v2 certification")
    if certification.get("manifest_sha256") != manifest.get("certification_sha256"):
        raise Phase3V2Error("certification checksum mismatch")
    if not certification.get("all_checks_passed"):
        raise Phase3V2Error("Phase 3 v2 certification did not pass")
    print(
        json.dumps(
            {
                "status": "verified",
                "manifest_uri": args.manifest_uri,
                "manifest_raw_sha256": hashlib.sha256(raw_manifest).hexdigest(),
                "selected_candidate": manifest["selected_candidate"],
                "output_rows": {name: len(frame) for name, frame in frames.items()},
            },
            indent=2,
            sort_keys=True,
        )
    )


def pd_timestamp(value: str):
    import pandas as pd

    result = pd.Timestamp(value)
    if result.tzinfo is None:
        raise Phase3V2Error("identity as-of must be timezone-aware")
    return result.to_pydatetime()


if __name__ == "__main__":
    main()
