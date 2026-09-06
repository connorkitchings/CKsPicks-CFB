#!/usr/bin/env python3
"""Verify and seal Phase 2d automation admission from a GitHub workflow run."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from typing import Any

import psycopg
from dotenv import load_dotenv

from cks_picks_cfb.data.catalog import catalog_connection_url
from cks_picks_cfb.data.data_first_phase2d import (
    Phase2dError,
    automation_admission,
    canonical_bytes,
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
            raise FileExistsError(f"immutable automation admission collision: {uri}")
        return
    storage.write_bytes(payload, uri)


def _verify_capture_manifest(
    storage, manifest_uri: str, expected_code_sha: str
) -> dict[str, Any]:
    manifest = _json(storage, manifest_uri)
    if manifest.get("schema_version") != "data_first_phase2_capture_run_v2":
        raise Phase2dError("capture manifest has wrong schema version")
    if manifest.get("environment") != "preview":
        raise Phase2dError("capture manifest is not Preview")
    if manifest.get("code_sha") != expected_code_sha:
        raise Phase2dError("capture manifest code SHA mismatch")
    results = manifest.get("results") or []
    captured = [row for row in results if row.get("state") == "captured"]
    if len(captured) != 7:
        raise Phase2dError(f"expected 7 captures, got {len(captured)}")
    return manifest


def _verify_r2_objects(storage, manifest: dict[str, Any], manifest_uri: str) -> None:
    prefix = manifest_uri.rsplit("/", 1)[0]
    for result in manifest.get("results") or []:
        if result.get("state") != "captured":
            continue
        request_sha = result.get("request_sha")
        uri = f"{prefix}/requests/{request_sha}.json"
        if not storage.exists(uri):
            raise Phase2dError(f"capture result not found: {uri}")
        payload = storage.read_bytes(uri)
        stored = json.loads(payload)
        if stored.get("request_sha") != request_sha:
            raise Phase2dError(f"capture result SHA mismatch: {uri}")


def _verify_catalog_registration(conn_url: str, manifest: dict[str, Any]) -> None:
    with psycopg.connect(conn_url) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        for result in manifest.get("results") or []:
            if result.get("state") != "captured":
                continue
            capture_id = result.get("capture_id")
            row = conn.execute(
                "SELECT capture_id, state FROM catalog.source_captures WHERE capture_id = %s",
                (capture_id,),
            ).fetchone()
            if not row or row[1] != "registered":
                raise Phase2dError(f"capture not registered: {capture_id}")


def _verify_future_kickoff(conn_url: str) -> int:
    with psycopg.connect(conn_url) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        row = conn.execute(
            "SELECT COUNT(*) FROM silver.games "
            "WHERE season = 2026 AND kickoff > NOW() AND completed = false"
        ).fetchone()
        return int(row[0]) if row else 0


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--capture-manifest-uri", required=True)
    parser.add_argument("--github-run-url", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--as-of", required=True)
    args = parser.parse_args()

    if os.getenv("CFB_STORAGE_BACKEND", "").casefold() != "r2":
        raise Phase2dError("automation admission requires CFB_STORAGE_BACKEND=r2")
    if args.expected_code_sha != _git_sha():
        raise Phase2dError("--expected-code-sha must match committed HEAD")

    args.as_of = _utc(args.as_of)
    storage = get_storage(environment="preview")
    reader = ReadOnlyStorage(storage)
    conn_url = catalog_connection_url("preview")

    manifest = _verify_capture_manifest(
        reader, args.capture_manifest_uri, args.expected_code_sha
    )
    _verify_r2_objects(reader, manifest, args.capture_manifest_uri)
    _verify_catalog_registration(conn_url, manifest)
    future_kickoff_count = _verify_future_kickoff(conn_url)

    captures = [
        {
            "request_sha": row["request_sha"],
            "capture_id": row["capture_id"],
            "row_count": row["row_count"],
            "captured_at": row["captured_at"],
            "state": row["state"],
        }
        for row in manifest.get("results") or []
        if row.get("state") == "captured"
    ]

    admission = automation_admission(
        run_id=args.run_id,
        code_sha=args.expected_code_sha,
        capture_manifest_uri=args.capture_manifest_uri,
        capture_manifest_sha256=sha256(canonical_bytes(manifest)),
        github_run_url=args.github_run_url,
        quota=manifest.get("quota") or {},
        captures=captures,
        future_kickoff_count=future_kickoff_count,
    )

    prefix = f"{OUTPUT_ROOT}/{args.run_id}"
    _immutable(storage, f"{prefix}/automation-admission.json", admission)
    print(
        json.dumps(
            {"state": admission["state"], "prefix": prefix}, sort_keys=True, default=str
        )
    )


if __name__ == "__main__":
    main()
