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
    signed_payload,
    verify_signed_payload,
)
from cks_picks_cfb.data.storage import ReadOnlyStorage, get_storage

OUTPUT_ROOT = "artifacts/research/data-first-football-v1/phase2/recertification/runs"


def _git_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _tracked_worktree_clean() -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and not result.stdout.strip()


def _utc(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise Phase2dError("--as-of must be an explicit UTC timestamp")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _signed_json(storage, uri: str, *, label: str) -> tuple[dict[str, Any], str]:
    raw = storage.read_bytes(uri)
    value = json.loads(raw)
    verify_signed_payload(value, label=label)
    return value, sha256(raw)


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
    parser.add_argument("--mode", choices=("dry-run", "apply"), required=True)
    parser.add_argument("--expected-code-sha", required=True)
    args = parser.parse_args()

    if os.getenv("CFB_STORAGE_BACKEND", "").casefold() != "r2":
        raise Phase2dError("Phase 2d eligibility requires CFB_STORAGE_BACKEND=r2")

    args.as_of = _utc(args.as_of)
    if args.expected_code_sha != _git_sha():
        raise Phase2dError("--expected-code-sha must match HEAD")
    if args.mode == "apply" and not _tracked_worktree_clean():
        raise Phase2dError("apply requires a clean tracked worktree")
    storage = get_storage(environment="preview")
    reader = ReadOnlyStorage(storage)

    audit_prefix = args.audit_prefix.rstrip("/")
    audit_uri = f"{audit_prefix}/audit-v5.json"
    audit, audit_raw_sha256 = _signed_json(reader, audit_uri, label="audit-v5")
    audit_identity = audit.get("identity") or {}
    if audit_identity.get("schema_version") != "data_first_phase2d_run_identity_v2":
        raise Phase2dError("audit-v5 identity has wrong schema")
    if not audit_identity.get("code_sha"):
        raise Phase2dError("audit-v5 identity missing code_sha")
    if audit_identity["code_sha"] != args.expected_code_sha:
        raise Phase2dError("audit-v5 is not bound to the expected code SHA")

    automation_admission, automation_raw_sha256 = _signed_json(
        reader, args.automation_admission_uri, label="automation admission"
    )
    if automation_admission.get("schema_version") != (
        "data_first_phase2d_automation_admission_v2"
    ):
        raise Phase2dError("automation admission has wrong schema")
    inputs = _enrich_inputs(audit.get("inputs") or [])
    coverage = audit.get("coverage_gate") or {}
    omissions = audit.get("omissions") or {}

    manifest = eligibility_manifest(
        identity=audit_identity,
        audit={
            **audit,
            "uri": audit_uri,
            "sha256": audit_raw_sha256,
            "declared_manifest_sha256": audit.get("manifest_sha256"),
        },
        automation_admission={
            **automation_admission,
            "uri": args.automation_admission_uri,
            "sha256": automation_raw_sha256,
            "declared_manifest_sha256": automation_admission.get("manifest_sha256"),
        },
        inputs=inputs,
        coverage=coverage,
        omissions=omissions,
    )

    manifest.update(
        {
            "run_id": args.run_id,
            "as_of": args.as_of,
            "code_sha": audit_identity["code_sha"],
        }
    )
    manifest = signed_payload(manifest)

    prefix = f"{OUTPUT_ROOT}/{args.run_id}"
    if args.mode == "apply":
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
