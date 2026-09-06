#!/usr/bin/env python3
"""Build the Phase 2 eligibility handoff from one corrected sealed audit."""

from __future__ import annotations

import argparse
import io
import json
import os
import subprocess

import pandas as pd
from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_phase2 import (
    build_eligibility_manifest,
    coverage_gate,
)
from cks_picks_cfb.data.evidence_audit import canonical_json, sha256
from cks_picks_cfb.data.storage import ReadOnlyStorage, get_storage

OUTPUT_ROOT = "artifacts/research/data-first-football-v1/phase2/recertification/runs"


def _git_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _json(storage, uri: str) -> dict:
    return json.loads(storage.read_bytes(uri))


def _immutable(storage, uri: str, value: dict) -> None:
    payload = canonical_json(value)
    if storage.exists(uri):
        if storage.read_bytes(uri) != payload:
            raise FileExistsError(f"immutable eligibility artifact collision: {uri}")
        return
    storage.write_bytes(payload, uri)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-prefix", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    args = parser.parse_args()
    if os.getenv("CFB_STORAGE_BACKEND", "").casefold() != "r2":
        raise RuntimeError("eligibility build requires CFB_STORAGE_BACKEND=r2")
    if args.expected_code_sha != _git_sha():
        raise ValueError("--expected-code-sha must equal committed HEAD")
    storage = get_storage(environment="preview")
    reader = ReadOnlyStorage(storage)
    audit = args.audit_prefix.rstrip("/")
    summary = _json(reader, f"{audit}/summary.json")
    if summary.get("code_sha") != args.expected_code_sha:
        raise ValueError("audit and eligibility code SHAs differ")
    resolved = _json(reader, f"{audit}/resolved-evidence-manifest.json")
    issue_payload = _json(reader, f"{audit}/issue-register.json")
    inventory = pd.read_parquet(
        io.BytesIO(reader.read_bytes(f"{audit}/dataset-inventory.parquet"))
    )
    coverage = pd.read_parquet(
        io.BytesIO(reader.read_bytes(f"{audit}/game-stage-coverage.parquet"))
    )
    gated = coverage[
        coverage["completion_status"].eq("completed")
        & coverage["stage"].isin({"plays", "outcomes", "reconciled_team_game"})
    ].copy()
    gate = coverage_gate(gated)
    inventory_by_version = {
        str(row["version_id"]): row
        for row in inventory.to_dict("records")
        if row.get("version_id") and pd.notna(row.get("version_id"))
    }
    dataset_rows = []
    for row in resolved["datasets"]:
        version_id = str(row["version_id"])
        detail = inventory_by_version.get(version_id, {})
        dataset_rows.append(
            {
                **row,
                "timing_class": detail.get("timing_class", "unresolved"),
                "null_policy": "preserve_with_reason",
            }
        )
    manifest = build_eligibility_manifest(
        audit_summary=summary,
        dataset_rows=dataset_rows,
        issues=list(issue_payload.get("issues") or []),
        coverage_result=gate,
    )
    manifest.update(
        {
            "run_id": args.run_id,
            "code_sha": args.expected_code_sha,
            "audit_prefix": audit,
            "historical_result_dispositions_uri": f"{audit}/result-dispositions.json",
        }
    )
    manifest["manifest_sha256"] = sha256(canonical_json(manifest))
    prefix = f"{OUTPUT_ROOT}/{args.run_id}"
    _immutable(storage, f"{prefix}/eligibility-manifest.json", manifest)
    print(json.dumps({"state": manifest["state"], "prefix": prefix}, sort_keys=True))
    if manifest["state"] != "eligible":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
