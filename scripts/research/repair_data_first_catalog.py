#!/usr/bin/env python3
"""Verify and optionally register Phase 2 immutable dataset evidence."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import fields

from dotenv import load_dotenv

from cks_picks_cfb.data.catalog import catalog_connection_url, register_dataset_version
from cks_picks_cfb.data.lake import DatasetManifest, DatasetRef, read_dataset
from cks_picks_cfb.data.storage import ReadOnlyStorage, get_storage


def _git_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _manifest(value: dict) -> DatasetManifest:
    payload = {
        field.name: value[field.name]
        for field in fields(DatasetManifest)
        if field.name in value
    }
    payload["parent_versions"] = tuple(payload.get("parent_versions") or ())
    payload["source_capture_ids"] = tuple(payload.get("source_capture_ids") or ())
    payload.setdefault("identity_version", "v1")
    payload.setdefault("schema_sha", None)
    return DatasetManifest(**payload)


def _immutable_json(storage, uri: str, value: dict) -> None:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str
    ).encode()
    if storage.exists(uri):
        if storage.read_bytes(uri) != payload:
            raise FileExistsError(f"immutable catalog repair report collision: {uri}")
        return
    storage.write_bytes(payload, uri)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resolved-manifest-uri", required=True)
    parser.add_argument("--mode", choices=("dry-run", "apply"), required=True)
    parser.add_argument("--expected-code-sha")
    parser.add_argument("--output-uri")
    args = parser.parse_args()
    if os.getenv("CFB_STORAGE_BACKEND", "").casefold() != "r2":
        raise RuntimeError("catalog repair requires CFB_STORAGE_BACKEND=r2")
    if args.mode == "apply" and args.expected_code_sha != _git_sha():
        raise ValueError("apply requires --expected-code-sha equal to committed HEAD")
    storage = get_storage(environment="preview")
    reader = ReadOnlyStorage(storage)
    resolved = json.loads(reader.read_bytes(args.resolved_manifest_uri))
    datasets = {str(row["version_id"]): row for row in resolved["datasets"]}
    gaps = {str(row["version_id"]) for row in resolved.get("registration_gaps", [])}
    pending: dict[str, tuple[DatasetRef, DatasetManifest]] = {}
    results = []
    for version_id in sorted(gaps):
        row = datasets[version_id]
        ref = DatasetRef(
            str(row["dataset"]),
            version_id,
            str(row["schema_version"]),
            str(row["content_sha"]),
            str(row["uri"]),
        )
        manifest_uri = ref.uri.rsplit("/", 1)[0] + "/manifest.json"
        try:
            frame = read_dataset(reader, ref)
            raw = json.loads(reader.read_bytes(manifest_uri))
            manifest = _manifest(raw)
            if (
                manifest.dataset != ref.dataset
                or manifest.version_id != ref.version_id
                or manifest.content_sha != ref.content_sha
                or manifest.uri != ref.uri
                or manifest.row_count != len(frame)
            ):
                raise ValueError("ref, manifest, and object metadata do not agree")
            pending[version_id] = (ref, manifest)
            results.append(
                {
                    "version_id": version_id,
                    "state": "verified_complete_metadata",
                    "row_count": len(frame),
                    "manifest_uri": manifest_uri,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "version_id": version_id,
                    "state": "quarantined",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
    if args.mode == "apply":
        conn_url = catalog_connection_url("preview")
        completed: set[str] = set()
        while pending:
            progressed = False
            for version_id, (ref, manifest) in list(pending.items()):
                if any(
                    parent in pending and parent not in completed
                    for parent in manifest.parent_versions
                ):
                    continue
                register_dataset_version(conn_url, ref, manifest)
                completed.add(version_id)
                del pending[version_id]
                progressed = True
            if not progressed:
                raise RuntimeError(
                    f"cannot order catalog repair dependencies: {sorted(pending)}"
                )
        for row in results:
            if row["version_id"] in completed:
                row["state"] = "registered"
    report = {
        "schema_version": "data_first_phase2_catalog_repair_v1",
        "mode": args.mode,
        "resolved_manifest_uri": args.resolved_manifest_uri,
        "code_sha": args.expected_code_sha if args.mode == "apply" else _git_sha(),
        "results": results,
        "verified_count": sum(
            row["state"] in {"verified_complete_metadata", "registered"}
            for row in results
        ),
        "quarantined_count": sum(row["state"] == "quarantined" for row in results),
    }
    if args.mode == "apply":
        if not args.output_uri or not args.output_uri.startswith(
            "artifacts/research/data-first-football-v1/phase2/"
        ):
            raise ValueError("apply requires a Phase 2 research --output-uri")
        _immutable_json(storage, args.output_uri, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["quarantined_count"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
