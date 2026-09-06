#!/usr/bin/env python3
"""Build the Phase 2d eligibility handoff from certified audit and automation admission."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_phase2d import (
    Phase2dError,
    canonical_bytes,
    eligibility_manifest,
    eligibility_role,
    sha256,
)
from cks_picks_cfb.data.storage import ReadOnlyStorage, get_storage

OUTPUT_ROOT = "artifacts/research/data-first-football-v1/phase2/recertification/runs"


def _git_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _utc(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise Phase2dError("--as-of must be an explicit UTC timestamp")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _json(storage, uri: str) -> dict[str, Any]:
    return json.loads(storage.read_bytes(uri))


def _immutable(storage, uri: str, value: dict[str, Any]) -> None:
    payload = canonical_bytes(value)
    if storage.exists(uri):
        if storage.read_bytes(uri) != payload:
            raise FileExistsError(f"immutable eligibility artifact collision: {uri}")
        return
    storage.write_bytes(payload, uri)


def _enrich_inputs(inputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = []
    for row in inputs:
        dataset = str(row.get("dataset"))
        role, permitted_uses = eligibility_role(dataset)
        enriched.append(
            {
                **row,
                "role": role,
                "permitted_uses": permitted_uses,
                "timing_class": "historically_reconstructed",
                "semantic_availability": "postgame",
                "null_policy": "preserve_with_reason",
                "eligible": dataset != "source_reconciliation",
            }
        )
    return enriched


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--audit-prefix", required=True, help="Phase 2d audit-v4 prefix"
    )
    parser.add_argument(
        "--automation-admission-uri",
        required=True,
        help="URI of the sealed automation-admission.json",
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    args = parser.parse_args()

    if os.getenv("CFB_STORAGE_BACKEND", "").casefold() != "r2":
        raise Phase2dError("Phase 2d eligibility requires CFB_STORAGE_BACKEND=r2")
    if args.expected_code_sha != _git_sha():
        raise Phase2dError("--expected-code-sha must match committed HEAD")

    args.as_of = _utc(args.as_of)
    storage = get_storage(environment="preview")
    reader = ReadOnlyStorage(storage)

    audit_prefix = args.audit_prefix.rstrip("/")
    audit = _json(reader, f"{audit_prefix}/audit-v4.json")
    audit_identity = audit.get("identity") or {}
    if audit_identity.get("schema_version") != "data_first_phase2d_run_identity_v1":
        raise Phase2dError("audit-v4 identity has wrong schema")
    if audit_identity.get("code_sha") != args.expected_code_sha:
        raise Phase2dError("audit and eligibility code SHAs differ")

    automation_admission = _json(reader, args.automation_admission_uri)
    if (
        automation_admission.get("schema_version")
        != "data_first_phase2d_automation_admission_v1"
    ):
        raise Phase2dError("automation admission has wrong schema")
    automation_sha = sha256(canonical_bytes(automation_admission))

    inputs = _enrich_inputs(audit.get("inputs") or [])
    coverage = audit.get("coverage_gate") or {}
    omissions = audit.get("omissions") or {}

    manifest = eligibility_manifest(
        identity=audit_identity,
        audit={
            "uri": f"{audit_prefix}/audit-v4.json",
            "sha256": audit.get("manifest_sha256"),
            **audit,
        },
        automation_admission={
            "uri": args.automation_admission_uri,
            "sha256": automation_sha,
            **automation_admission,
        },
        inputs=inputs,
        coverage=coverage,
        omissions=omissions,
    )

    manifest.update(
        {
            "run_id": args.run_id,
            "as_of": args.as_of,
            "code_sha": args.expected_code_sha,
        }
    )
    manifest["manifest_sha256"] = sha256(canonical_bytes(manifest))

    prefix = f"{OUTPUT_ROOT}/{args.run_id}"
    _immutable(storage, f"{prefix}/eligibility-manifest.json", manifest)
    print(
        json.dumps(
            {"state": manifest["state"], "prefix": prefix}, sort_keys=True, default=str
        )
    )
    if manifest["state"] != "eligible":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
