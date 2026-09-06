#!/usr/bin/env python3
"""Verify and seal Phase 2d automation admission from a GitHub workflow run."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from typing import Any

import psycopg
from dotenv import load_dotenv

from cks_picks_cfb.data.catalog import catalog_connection_url, source_capture_by_id
from cks_picks_cfb.data.data_first_phase2 import CaptureRequest
from cks_picks_cfb.data.data_first_phase2d import (
    Phase2dError,
    automation_admission,
    canonical_bytes,
    sha256,
)
from cks_picks_cfb.data.lake import read_source_capture
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


def _json(storage, uri: str) -> dict[str, Any]:
    return json.loads(storage.read_bytes(uri))


def _immutable(storage, uri: str, value: dict[str, Any]) -> None:
    payload = canonical_bytes(value)
    if storage.exists(uri):
        if storage.read_bytes(uri) != payload:
            raise FileExistsError(f"immutable automation admission collision: {uri}")
        return
    storage.write_bytes(payload, uri)


def _verify_capture_manifest(storage, manifest_uri: str) -> dict[str, Any]:
    manifest = _json(storage, manifest_uri)
    if manifest.get("schema_version") != "data_first_phase2_capture_run_v2":
        raise Phase2dError("capture manifest has wrong schema version")
    if manifest.get("environment") != "preview":
        raise Phase2dError("capture manifest is not Preview")
    if not manifest.get("code_sha"):
        raise Phase2dError("capture manifest missing code_sha")
    results = manifest.get("results") or []
    captured = [row for row in results if row.get("state") == "captured"]
    requests = manifest.get("requests") or []
    if (
        manifest.get("state") != "complete"
        or int(manifest.get("request_count", -1)) != 7
        or int(manifest.get("failed_or_empty_count", -1)) != 0
        or len(requests) != 7
        or len(captured) != 7
    ):
        raise Phase2dError(f"expected 7 captures, got {len(captured)}")
    planned: set[str] = set()
    for row in requests:
        request = CaptureRequest(
            provider=str(row.get("provider")),
            entity=str(row.get("entity")),
            endpoint=str(row.get("endpoint")),
            parameters=dict(row.get("parameters") or {}),
        )
        if row.get("request_sha") != request.request_sha:
            raise Phase2dError("capture plan request checksum mismatch")
        if request.request_sha in planned:
            raise Phase2dError("capture plan repeats a request")
        planned.add(request.request_sha)
    actual = {str(row.get("request_sha")) for row in captured}
    if actual != planned or len(actual) != 7:
        raise Phase2dError("capture results do not match the request plan")
    return manifest


def _verify_capture_evidence(
    storage, conn_url: str, manifest: dict[str, Any], manifest_uri: str
) -> list[dict[str, Any]]:
    prefix = manifest_uri.rsplit("/", 1)[0]
    captures = []
    for result in manifest.get("results") or []:
        if result.get("state") != "captured":
            continue
        request_sha = result.get("request_sha")
        uri = f"{prefix}/requests/{request_sha}.json"
        if not storage.exists(uri):
            raise Phase2dError(f"capture result not found: {uri}")
        payload = storage.read_bytes(uri)
        stored = json.loads(payload)
        if (
            payload != canonical_bytes(result)
            or stored.get("request_sha") != request_sha
        ):
            raise Phase2dError(f"capture result SHA mismatch: {uri}")
        capture = source_capture_by_id(conn_url, str(result.get("capture_id")))
        if capture.state != "registered":
            raise Phase2dError(f"capture not registered: {capture.capture_id}")
        frame = read_source_capture(storage, capture)
        if len(frame) != int(result.get("row_count", -1)) or len(frame) <= 0:
            raise Phase2dError(f"capture row-count mismatch: {capture.capture_id}")
        if capture.row_count != len(frame):
            raise Phase2dError(f"catalog row-count mismatch: {capture.capture_id}")
        if capture.captured_at.isoformat() != str(result.get("captured_at")):
            raise Phase2dError(f"capture timestamp mismatch: {capture.capture_id}")
        if capture.effective_at != capture.captured_at:
            raise Phase2dError(
                f"capture is not authentic pregame: {capture.capture_id}"
            )
        if capture.response_metadata.get("timing_class") != "authentic_pregame":
            raise Phase2dError(f"capture timing class mismatch: {capture.capture_id}")
        request = dict(capture.request)
        request_identity = CaptureRequest(
            provider=str(request.get("provider")),
            entity=str(request.get("entity")),
            endpoint=str(request.get("endpoint")),
            parameters=dict(request.get("parameters") or {}),
        ).request_sha
        if request_identity != request_sha:
            raise Phase2dError(f"catalog request mismatch: {capture.capture_id}")
        captures.append(
            {
                "request_sha": request_sha,
                "capture_id": capture.capture_id,
                "row_count": capture.row_count,
                "captured_at": capture.captured_at.isoformat(),
                "state": "captured",
                "content_sha": capture.content_sha,
                "object_sha": capture.object_sha,
                "uri": capture.uri,
                "effective_at": capture.effective_at.isoformat(),
                "timing_class": "authentic_pregame",
            }
        )
    return captures


def _github_run(github_run_url: str) -> dict[str, Any]:
    match = re.fullmatch(
        r"https://github\.com/[^/]+/[^/]+/actions/runs/(\d+)", github_run_url
    )
    if not match:
        raise Phase2dError("invalid GitHub run URL")
    result = subprocess.run(
        [
            "gh",
            "run",
            "view",
            match.group(1),
            "--json",
            "status,conclusion,headSha,event,url,workflowName",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise Phase2dError(f"GitHub run could not be verified: {result.stderr[-500:]}")
    return dict(json.loads(result.stdout))


def _verify_future_kickoff(conn_url: str) -> int:
    with psycopg.connect(conn_url) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        row = conn.execute(
            "SELECT COUNT(*) FROM public.games "
            "WHERE season = 2026 AND start_date > NOW()"
        ).fetchone()
        return int(row[0]) if row else 0


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--capture-manifest-uri", required=True)
    parser.add_argument("--github-run-url", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--mode", choices=("dry-run", "apply"), required=True)
    parser.add_argument("--expected-code-sha", required=True)
    args = parser.parse_args()

    if os.getenv("CFB_STORAGE_BACKEND", "").casefold() != "r2":
        raise Phase2dError("automation admission requires CFB_STORAGE_BACKEND=r2")

    args.as_of = _utc(args.as_of)
    if args.expected_code_sha != _git_sha():
        raise Phase2dError("--expected-code-sha must match HEAD")
    if args.mode == "apply" and not _tracked_worktree_clean():
        raise Phase2dError("apply requires a clean tracked worktree")
    storage = get_storage(environment="preview")
    reader = ReadOnlyStorage(storage)
    conn_url = catalog_connection_url("preview")

    manifest = _verify_capture_manifest(reader, args.capture_manifest_uri)
    captures = _verify_capture_evidence(
        reader, conn_url, manifest, args.capture_manifest_uri
    )
    future_kickoff_count = _verify_future_kickoff(conn_url)
    github_run = _github_run(args.github_run_url)

    code_sha = manifest.get("code_sha")
    if not code_sha:
        raise Phase2dError("capture manifest missing code_sha")

    admission = automation_admission(
        run_id=args.run_id,
        code_sha=code_sha,
        capture_manifest_uri=args.capture_manifest_uri,
        capture_manifest_sha256=sha256(canonical_bytes(manifest)),
        github_run_url=args.github_run_url,
        quota=manifest.get("quota") or {},
        captures=captures,
        future_kickoff_count=future_kickoff_count,
        github_run=github_run,
        verifier_code_sha=args.expected_code_sha,
    )

    prefix = f"{OUTPUT_ROOT}/{args.run_id}"
    if args.mode == "apply":
        _immutable(storage, f"{prefix}/automation-admission.json", admission)
    print(
        json.dumps(
            {"state": admission["state"], "prefix": prefix}, sort_keys=True, default=str
        )
    )


if __name__ == "__main__":
    main()
