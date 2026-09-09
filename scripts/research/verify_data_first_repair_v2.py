#!/usr/bin/env python3
"""Independently reconstruct and verify a frozen Repair v2 Preview artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
from types import SimpleNamespace

from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload
from cks_picks_cfb.data.data_first_repair_v2 import (
    REPAIR_MANIFEST_SCHEMA,
    RepairV2Error,
    sha256,
)
from cks_picks_cfb.data.lake import read_dataset
from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame
from cks_picks_cfb.data.storage import get_storage
from scripts.research.run_data_first_repair_v2 import (
    _ref,
    _validate_parents,
    compute_repair,
)


def _frame_digest(frame):
    """Hash records after normalizing equivalent nullable object values."""
    normalized = frame.copy()
    for column in normalized.select_dtypes(include=["object"]).columns:
        normalized[column] = normalized[column].where(normalized[column].notna(), None)
    return sha256(normalized.to_dict("records"))


def _capture_plan_extra_captures(storage, frame):
    """Read only capture IDs recorded by the repaired artifact itself."""
    from cks_picks_cfb.data.catalog import catalog_connection_url, source_capture_by_id

    conn_url = catalog_connection_url("preview")
    return [
        source_capture_by_id(conn_url, str(capture_id))
        for capture_id in frame["capture_id"].dropna().unique()
    ]


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
    try:
        verify_signed_payload(manifest, label="Repair v2 manifest")
    except ValueError as exc:
        raise RepairV2Error(str(exc)) from exc
    if (
        manifest.get("schema_version") != REPAIR_MANIFEST_SCHEMA
        or manifest.get("state") != "repaired_reconstructed_only"
    ):
        raise RepairV2Error(
            "Repair v2 manifest is not a repaired reconstructed artifact"
        )
    identity = dict(manifest.get("identity") or {})
    if identity.get("code_sha") != args.expected_code_sha:
        raise RepairV2Error("Repair v2 code SHA does not match expectation")
    if manifest.get("production_activation_authorized") is not False:
        raise RepairV2Error("Repair v2 manifest improperly permits production")
    output_frames = {}
    for name, value in dict(manifest.get("output_refs") or {}).items():
        ref = _ref(value)
        frame = read_dataset(storage, ref)
        validate_frame(frame, schema_for(ref.dataset, ref.schema_version))
        output_frames[name] = frame
    required = {"population", "auxiliary", "coverage", "issues", "capture_plan"}
    if set(output_frames) != required:
        raise RepairV2Error("Repair v2 output refs are incomplete")
    for name, frame in output_frames.items():
        if int(manifest["output_rows"].get(name, -1)) != len(frame):
            raise RepairV2Error(f"Repair v2 output row count mismatch: {name}")
        if "season" in frame and frame["season"].astype(int).eq(2020).any():
            raise RepairV2Error(f"Repair v2 output contains forbidden 2020: {name}")
    parent = dict(manifest.get("parents") or {})
    core_uri = parent.get("core_eligibility", {}).get("uri")
    auxiliary_uri = parent.get("auxiliary_eligibility", {}).get("uri")
    phase3_uri = parent.get("phase3_retained_diagnostic_only", {}).get("uri")
    if not all((core_uri, auxiliary_uri, phase3_uri)):
        raise RepairV2Error("Repair v2 manifest lacks exact parents")
    core, auxiliary, phase3, _ = _validate_parents(
        storage,
        SimpleNamespace(
            core_eligibility_uri=core_uri,
            auxiliary_eligibility_uri=auxiliary_uri,
            phase3_retained_uri=phase3_uri,
        ),
    )
    extra = _capture_plan_extra_captures(storage, output_frames["capture_plan"])
    recomputed, admissions, _ = compute_repair(
        storage,
        core=core,
        auxiliary_uri=auxiliary_uri,
        auxiliary=auxiliary,
        phase3=phase3,
        extra_captures=extra,
    )
    for name in ("population", "auxiliary", "coverage", "issues"):
        expected = _frame_digest(recomputed[name])
        actual = _frame_digest(output_frames[name])
        if actual != expected:
            raise RepairV2Error(
                f"Repair v2 independent reconstruction mismatch: {name}"
            )
    population = output_frames["population"]
    summary = dict(manifest.get("population") or {})
    if (
        summary.get("scheduled_games") != len(population)
        or summary.get("forecast_eligible_games")
        != int(population["forecast_eligible"].sum())
        or summary.get("measurement_usable_games")
        != int(population["measurement_usable"].sum())
    ):
        raise RepairV2Error("Repair v2 population summary does not reconcile")
    if admissions != manifest.get("family_admission"):
        raise RepairV2Error("Repair v2 family admission does not reconstruct")
    print(
        json.dumps(
            {
                "status": "verified",
                "manifest_uri": args.manifest_uri,
                "manifest_raw_sha256": hashlib.sha256(raw_manifest).hexdigest(),
                "population": summary,
                "output_rows": {
                    name: len(frame) for name, frame in output_frames.items()
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
