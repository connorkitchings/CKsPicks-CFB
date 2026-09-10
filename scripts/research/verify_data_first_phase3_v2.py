#!/usr/bin/env python3
"""Independently stream and verify a frozen Preview-only Phase 3 v2 run."""

from __future__ import annotations

import argparse
import hashlib
import json
from typing import Any

from dotenv import load_dotenv

try:
    from scripts.research.run_data_first_phase3_v2 import preflight_phase3_v2
except ModuleNotFoundError:  # pragma: no cover - direct script path only
    from run_data_first_phase3_v2 import preflight_phase3_v2

from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload
from cks_picks_cfb.data.data_first_phase3_v2 import (
    PHASE3_V2_DATASETS,
    PHASE3_V2_RETAINED_CORE_SCHEMA,
    REQUIRED_REPAIR_CANONICAL_SHA256,
    REQUIRED_REPAIR_RAW_SHA256,
    Phase3V2Error,
    verify_repair_manifest,
)
from cks_picks_cfb.data.lake import (
    PARTITIONED_DATASET_KIND,
    PartitionedDatasetRef,
    iter_partitioned_dataset,
)
from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame
from cks_picks_cfb.data.storage import get_storage


def _partitioned_ref(value: dict[str, Any]) -> PartitionedDatasetRef:
    return PartitionedDatasetRef(
        artifact_kind=str(value["artifact_kind"]),
        dataset=str(value["dataset"]),
        version_id=str(value["version_id"]),
        schema_version=str(value["schema_version"]),
        content_sha=str(value["content_sha"]),
        records_sha=str(value["records_sha"]),
        uri=str(value["uri"]),
        row_count=int(value["row_count"]),
        partition_keys=tuple(value["partition_keys"]),
    )


def _timestamp(value: str):
    import pandas as pd

    result = pd.Timestamp(value)
    if result.tzinfo is None:
        raise Phase3V2Error("identity as-of must be timezone-aware")
    return result.to_pydatetime()


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
    if (
        identity.get("environment") != "preview"
        or identity.get("code_sha") != args.expected_code_sha
    ):
        raise Phase3V2Error("Phase 3 v2 identity is not the expected Preview code")
    raw_repair = storage.read_bytes(str(manifest.get("repair_manifest_uri") or ""))
    if hashlib.sha256(raw_repair).hexdigest() != REQUIRED_REPAIR_RAW_SHA256:
        raise Phase3V2Error("Phase 3 v2 Repair parent raw checksum mismatch")
    repair = verify_repair_manifest(json.loads(raw_repair))
    if repair.get("manifest_sha256") != REQUIRED_REPAIR_CANONICAL_SHA256:
        raise Phase3V2Error("Phase 3 v2 Repair parent canonical checksum mismatch")

    output_rows: dict[str, int] = {}
    output_digests: dict[str, str] = {}
    for name, value in (manifest.get("output_refs") or {}).items():
        if name not in PHASE3_V2_DATASETS:
            raise Phase3V2Error(f"unexpected Phase 3 v2 output: {name}")
        ref = _partitioned_ref(value)
        dataset, schema_version = PHASE3_V2_DATASETS[name]
        if (
            ref.artifact_kind != PARTITIONED_DATASET_KIND
            or ref.dataset != dataset
            or ref.schema_version != schema_version
        ):
            raise Phase3V2Error(f"Phase 3 v2 partitioned output mismatch: {name}")
        schema = schema_for(dataset, schema_version)
        count = 0
        for frame in iter_partitioned_dataset(storage, ref):
            validate_frame(frame, schema)
            count += len(frame)
        if count != ref.row_count:
            raise Phase3V2Error(f"Phase 3 v2 partition count mismatch: {name}")
        output_rows[name] = count
        output_digests[name] = ref.records_sha
    if set(output_rows) != set(PHASE3_V2_DATASETS):
        raise Phase3V2Error("Phase 3 v2 output set is incomplete")
    if output_rows != manifest.get("output_rows") or output_digests != manifest.get(
        "output_records_sha256"
    ):
        raise Phase3V2Error("stored Phase 3 v2 output summaries differ from manifest")

    recomputed = preflight_phase3_v2(
        storage=storage,
        repair=repair,
        identity=identity,
        as_of=_timestamp(identity["as_of"]),
    )
    expected_rows = {name: plan.row_count for name, plan in recomputed.plans.items()}
    expected_digests = {
        name: plan.records_sha for name, plan in recomputed.plans.items()
    }
    if output_rows != expected_rows or output_digests != expected_digests:
        raise Phase3V2Error("independent partitioned reconstruction mismatch")
    if recomputed.retained["selected_candidate"] != manifest.get("selected_candidate"):
        raise Phase3V2Error("independent selection differs from retained core")
    compact_evidence = manifest.get("compact_tournament_evidence")
    if not isinstance(compact_evidence, dict):
        raise Phase3V2Error("retained core lacks compact tournament evidence")
    if compact_evidence != recomputed.compact_evidence:
        raise Phase3V2Error("independent compact tournament evidence differs")
    certification = json.loads(
        storage.read_bytes(args.manifest_uri.rsplit("/", 1)[0] + "/certification.json")
    )
    verify_signed_payload(certification, label="Phase 3 v2 certification")
    if certification.get("manifest_sha256") != manifest.get(
        "certification_sha256"
    ) or not certification.get("all_checks_passed"):
        raise Phase3V2Error("Phase 3 v2 certification mismatch")
    if certification.get("compact_tournament_evidence") != compact_evidence:
        raise Phase3V2Error("Phase 3 v2 compact certification mismatch")
    print(
        json.dumps(
            {
                "status": "verified",
                "manifest_uri": args.manifest_uri,
                "manifest_raw_sha256": hashlib.sha256(raw_manifest).hexdigest(),
                "selected_candidate": manifest["selected_candidate"],
                "output_rows": output_rows,
                "compact_tournament_evidence": compact_evidence,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
