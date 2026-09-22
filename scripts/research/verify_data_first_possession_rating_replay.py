#!/usr/bin/env python3
"""Independently reconstruct and verify a Contract 08 rating replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Mapping

import pandas as pd
from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload
from cks_picks_cfb.data.data_first_possession_v1 import (
    POSSESSION_DATASETS,
    POSSESSION_MANIFEST_SCHEMA,
)
from cks_picks_cfb.data.lake import PartitionedDatasetRef, iter_partitioned_dataset
from cks_picks_cfb.data.schema_contracts import schema_for
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ratings.possession_live_replay_verification import (
    FROZEN_CANDIDATE,
    IndependentReplayError,
    VerifierInputs,
    verify_replay_artifact,
)

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_SCHEMA = "data_first_possession_rating_replay_manifest_v1"


class ReplayVerificationError(ValueError):
    """Raised when the live replay cannot be independently certified."""


def _git_sha() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def _part_ref(value: Mapping[str, Any]) -> PartitionedDatasetRef:
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


def _read(storage: Any, value: Mapping[str, Any]) -> pd.DataFrame:
    ref = _part_ref(value)
    frames = [
        frame for frame in iter_partitioned_dataset(storage, ref) if not frame.empty
    ]
    schema = schema_for(ref.dataset, ref.schema_version)
    if not frames:
        return pd.DataFrame(columns=list(schema.required))
    unstable = {
        column
        for column in schema.required
        if len({str(frame[column].dtype) for frame in frames}) > 1
        and any(frame[column].isna().all() for frame in frames)
    }
    normalized = [
        frame.astype({column: "object" for column in unstable}) for frame in frames
    ]
    return pd.concat(normalized, ignore_index=True, sort=False).loc[
        :, list(schema.required)
    ]


def _raw_parent(
    storage: Any, uri: str, expected_sha: str, label: str
) -> dict[str, Any]:
    raw = storage.read_bytes(uri)
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ReplayVerificationError(f"{label} raw checksum differs")
    payload = json.loads(raw)
    verify_signed_payload(payload, label=label)
    return payload


def _inputs(storage: Any, manifest: Mapping[str, Any]) -> VerifierInputs:
    parents = manifest.get("parents") or {}
    measurement = _raw_parent(
        storage,
        str(parents.get("measurement_manifest_uri")),
        str(parents.get("measurement_manifest_raw_sha256")),
        "Contract 07 measurement manifest",
    )
    identity = measurement.get("identity") or {}
    if (
        measurement.get("schema_version") != POSSESSION_MANIFEST_SCHEMA
        or identity.get("environment") != "preview"
        or tuple(identity.get("development_seasons") or ()) != (2026,)
        or identity.get("run_id") != "possession-v1-measurements-20260922-2026c"
        or set(measurement.get("output_refs") or {}) != set(POSSESSION_DATASETS)
        or measurement.get("production_activation_authorized") is not False
    ):
        raise ReplayVerificationError("live measurement parent is ineligible")
    rating = _raw_parent(
        storage,
        str(parents.get("historical_rating_manifest_uri")),
        str(parents.get("historical_rating_manifest_raw_sha256")),
        "11B retained rating manifest",
    )
    if (
        rating.get("state") != "frozen"
        or rating.get("selected_candidate") != FROZEN_CANDIDATE
        or (rating.get("identity") or {}).get("run_id")
        != "possession-v1-ratings-20260921-11d59ee-r9cert"
    ):
        raise ReplayVerificationError("historical rating parent is ineligible")
    historical_uri = str((rating.get("parents") or {}).get("measurement_manifest_uri"))
    historical_sha = str(
        (rating.get("parents") or {}).get("measurement_manifest_raw_sha256")
    )
    historical = _raw_parent(
        storage, historical_uri, historical_sha, "r9 historical measurement manifest"
    )
    if hashlib.sha256(storage.read_bytes(historical_uri)).hexdigest() != parents.get(
        "historical_measurement_manifest_raw_sha256"
    ):
        raise ReplayVerificationError("historical measurement lineage differs")
    preseason_inputs = parents.get("preseason_inputs") or {}
    if set(preseason_inputs) != {"recruiting", "returning_production", "coaches"}:
        raise ReplayVerificationError("preseason parent set differs")
    for name, value in preseason_inputs.items():
        raw = storage.read_bytes(str(value.get("uri")))
        if hashlib.sha256(raw).hexdigest() != value.get("raw_sha256"):
            raise ReplayVerificationError(f"{name} preseason checksum differs")
        payload = json.loads(raw)
        if (
            payload.get("schema_version") != "cloud_v1"
            or int(payload.get("rows", 0)) <= 0
        ):
            raise ReplayVerificationError(f"{name} preseason manifest is malformed")
    live = measurement["output_refs"]
    historical_outputs = historical.get("output_refs") or {}
    return VerifierInputs(
        population=_read(storage, live["population"]),
        observations=_read(storage, live["observations"]),
        snapshots=_read(storage, live["snapshots"]),
        historical_terminal=_read(storage, historical_outputs["terminal"]),
    )


def verify_manifest(payload: Mapping[str, Any], *, expected_code_sha: str) -> None:
    verify_signed_payload(payload, label="retained rating replay manifest")
    identity = payload.get("identity") or {}
    if (
        payload.get("schema_version") != MANIFEST_SCHEMA
        or payload.get("state") != "frozen"
        or payload.get("selected_candidate") != FROZEN_CANDIDATE
        or payload.get("production_activation_authorized") is not False
        or identity.get("environment") != "preview"
        or identity.get("code_sha") != expected_code_sha
    ):
        raise ReplayVerificationError("retained rating replay envelope is invalid")


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-uri", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--environment", choices=("preview",), required=True)
    args = parser.parse_args(argv)
    storage = get_storage(environment="preview")
    raw = storage.read_bytes(args.manifest_uri)
    manifest = json.loads(raw)
    verify_manifest(manifest, expected_code_sha=args.expected_code_sha)
    try:
        report = verify_replay_artifact(
            storage=storage,
            manifest=manifest,
            manifest_uri=args.manifest_uri,
            inputs=_inputs(storage, manifest),
            verifier_code_sha=_git_sha(),
        )
    except IndependentReplayError as exc:
        raise ReplayVerificationError(
            f"independent replay verification failed: {exc}"
        ) from exc
    report["manifest_raw_sha256"] = hashlib.sha256(raw).hexdigest()
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
