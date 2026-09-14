#!/usr/bin/env python3
"""Independently reconstruct and verify a Preview V5 possession run.

This verifier intentionally does not import the producer runner or its preflight
function.  It rereads the Repair sources and recomputes ledgers/replay evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from typing import Any

import pandas as pd
from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_phase3 import verify_core_eligibility
from cks_picks_cfb.data.data_first_phase3_v2 import verify_repair_manifest
from cks_picks_cfb.data.data_first_possession_v1 import (
    POSSESSION_DATASETS,
    POSSESSION_MANIFEST_SCHEMA,
    REQUIRED_REPAIR_CANONICAL_SHA256,
    REQUIRED_REPAIR_RAW_SHA256,
    build_population,
)
from cks_picks_cfb.data.lake import (
    PARTITIONED_DATASET_KIND,
    DatasetRef,
    PartitionedDatasetRef,
    canonical_frame_digest,
    iter_partitioned_dataset,
    read_dataset,
)
from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ratings.possession_measurements import (
    build_measurements,
    build_replay,
)


class PossessionVerificationError(ValueError):
    pass


def _partitioned(value: dict[str, Any]) -> PartitionedDatasetRef:
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


def _ref(value: dict[str, Any]) -> DatasetRef:
    return DatasetRef(
        **{
            key: value[key]
            for key in ("dataset", "version_id", "schema_version", "content_sha", "uri")
        }
    )


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-uri", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--environment", choices=["preview"], required=True)
    args = parser.parse_args(argv)
    storage = get_storage(environment="preview")
    raw = storage.read_bytes(args.manifest_uri)
    manifest = json.loads(raw)
    if manifest.get("schema_version") != POSSESSION_MANIFEST_SCHEMA:
        raise PossessionVerificationError("unexpected possession manifest schema")
    from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload

    verify_signed_payload(manifest, label="possession measurement manifest")
    identity = manifest.get("identity") or {}
    if (
        identity.get("environment") != "preview"
        or identity.get("code_sha") != args.expected_code_sha
    ):
        raise PossessionVerificationError(
            "manifest is not the expected committed Preview code"
        )
    if manifest.get("production_activation_authorized") is not False:
        raise PossessionVerificationError("manifest authorizes production")
    raw_repair = storage.read_bytes(str(manifest.get("repair_manifest_uri") or ""))
    if hashlib.sha256(raw_repair).hexdigest() != REQUIRED_REPAIR_RAW_SHA256:
        raise PossessionVerificationError("Repair raw checksum mismatch")
    repair = verify_repair_manifest(json.loads(raw_repair))
    if repair.get("manifest_sha256") != REQUIRED_REPAIR_CANONICAL_SHA256:
        raise PossessionVerificationError("Repair canonical checksum mismatch")

    stored: dict[str, pd.DataFrame] = {}
    row_counts: dict[str, int] = {}
    digests: dict[str, str] = {}
    for name, value in (manifest.get("output_refs") or {}).items():
        if name not in POSSESSION_DATASETS:
            raise PossessionVerificationError(f"unexpected output {name}")
        ref = _partitioned(value)
        expected_dataset, expected_schema = POSSESSION_DATASETS[name]
        if (
            ref.artifact_kind != PARTITIONED_DATASET_KIND
            or ref.dataset != expected_dataset
            or ref.schema_version != expected_schema
        ):
            raise PossessionVerificationError(f"output identity mismatch: {name}")
        frames = list(iter_partitioned_dataset(storage, ref))
        frame = (
            pd.concat(frames, ignore_index=True)
            if frames
            else pd.DataFrame(
                columns=schema_for(expected_dataset, expected_schema).required
            )
        )
        validate_frame(frame, schema_for(expected_dataset, expected_schema))
        stored[name] = frame
        row_counts[name] = len(frame)
        digests[name] = ref.records_sha
    if (
        set(stored) != set(POSSESSION_DATASETS)
        or row_counts != manifest.get("output_rows")
        or digests != manifest.get("output_records_sha256")
    ):
        raise PossessionVerificationError("stored output summary differs from manifest")

    population_ref = _ref(repair["output_refs"]["population"])
    population = build_population(read_dataset(storage, population_ref))
    eligibility_uri = ((repair.get("parents") or {}).get("core_eligibility") or {}).get(
        "uri"
    )
    if not eligibility_uri:
        raise PossessionVerificationError("Repair lacks core eligibility URI")
    source_refs: dict[int, dict[str, DatasetRef]] = {}
    for value in verify_core_eligibility(
        json.loads(storage.read_bytes(str(eligibility_uri)))
    ):
        source_refs.setdefault(int(value["season"]), {})[str(value["dataset"])] = _ref(
            value
        )
    if any({"byplay", "game_outcomes"} - set(refs) for refs in source_refs.values()):
        raise PossessionVerificationError(
            "certified sources lack byplay or outcome evidence"
        )
    byplay = pd.concat(
        [
            read_dataset(storage, source_refs[season]["byplay"])
            for season in sorted(source_refs)
        ],
        ignore_index=True,
    )
    outcomes = pd.concat(
        [
            read_dataset(storage, source_refs[season]["game_outcomes"])
            for season in sorted(source_refs)
        ],
        ignore_index=True,
    )
    rebuilt = build_measurements(
        byplay=byplay, outcomes=outcomes, population=population
    )
    snapshots, history, terminal, _ = build_replay(
        population=population, observations=rebuilt.observations
    )
    expected = {
        "population": population,
        "possessions": rebuilt.possessions,
        "scoring_events": rebuilt.scoring_events,
        "observations": rebuilt.observations,
        "snapshots": snapshots,
        "adjusted_history": history,
        "terminal": terminal,
        "coverage": rebuilt.coverage,
    }
    for name, frame in expected.items():
        dataset, schema_version = POSSESSION_DATASETS[name]
        schema = schema_for(dataset, schema_version)
        validate_frame(frame, schema)
        actual_digest = canonical_frame_digest(
            stored[name]
            .sort_values(list(schema.keys), kind="mergesort")
            .reset_index(drop=True),
            columns=schema.required,
        )
        expected_digest = canonical_frame_digest(
            frame.sort_values(list(schema.keys), kind="mergesort").reset_index(
                drop=True
            ),
            columns=schema.required,
        )
        if actual_digest != expected_digest:
            raise PossessionVerificationError(
                f"independent reconstruction mismatch: {name}"
            )
    certification = json.loads(
        storage.read_bytes(args.manifest_uri.rsplit("/", 1)[0] + "/certification.json")
    )
    verify_signed_payload(certification, label="possession certification")
    if certification.get("manifest_sha256") != manifest.get(
        "certification_sha256"
    ) or not certification.get("all_checks_passed"):
        raise PossessionVerificationError("certification is missing or failed")
    print(
        json.dumps(
            {
                "status": "verified",
                "manifest_uri": args.manifest_uri,
                "manifest_raw_sha256": hashlib.sha256(raw).hexdigest(),
                "output_rows": row_counts,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
