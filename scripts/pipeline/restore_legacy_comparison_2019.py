#!/usr/bin/env python3
"""Restore exact 2019 archive evidence as Preview-only comparison refs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict
from typing import Any, Mapping

from dotenv import load_dotenv

from cks_picks_cfb.data.catalog import source_capture_by_id
from cks_picks_cfb.data.history import (
    import_historical_object,
    inventory_historical_source,
)
from cks_picks_cfb.data.lake import DatasetRef
from cks_picks_cfb.data.legacy_comparison import (
    LEGACY_COMPARISON_2019_CONTRACT,
    find_and_verify_legacy_archives,
    load_legacy_comparison_restore_config,
)
from cks_picks_cfb.data.runtime import resolve_runtime_target
from cks_picks_cfb.data.storage import get_source_storage, get_storage

RUN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,127}$")
RESTORE_COMMIT_PATHS = (
    "conf/ratings/legacy_comparison_2019_restore.yaml",
    "scripts/pipeline/build_history_silver.py",
    "scripts/pipeline/restore_legacy_comparison_2019.py",
    "src/cks_picks_cfb/data/history.py",
    "src/cks_picks_cfb/data/legacy_comparison.py",
)


def _canonical(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def _immutable_write(storage, uri: str, payload: bytes) -> None:
    if storage.exists(uri):
        if storage.read_bytes(uri) != payload:
            raise FileExistsError(f"Immutable legacy comparison collision: {uri}")
        return
    storage.write_bytes(payload, uri)


def _committed_code_sha() -> str:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()
    if not head:
        raise RuntimeError("Legacy comparison restoration requires a committed Git HEAD")
    for path in RESTORE_COMMIT_PATHS:
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", path],
            capture_output=True,
            text=True,
            check=False,
        )
        if tracked.returncode:
            raise RuntimeError(f"Legacy comparison implementation is not committed: {path}")
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all", "--", *RESTORE_COMMIT_PATHS],
        capture_output=True,
        text=True,
        check=False,
    )
    if dirty.stdout:
        raise RuntimeError("Legacy comparison implementation paths must be clean")
    return head


def _source_set_payload(
    *,
    run_id: str,
    as_of: str,
    code_sha: str,
    config_sha256: str,
    captures: list[dict[str, Any]],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "contract_version": LEGACY_COMPARISON_2019_CONTRACT,
        "state": "complete",
        "run_id": run_id,
        "season": 2019,
        "as_of": as_of,
        "code_sha": code_sha,
        "configuration_sha256": config_sha256,
        "entries": sorted(captures, key=lambda item: str(item["entity"])),
    }
    payload["manifest_sha256"] = hashlib.sha256(_canonical(payload)).hexdigest()
    return payload


def _ref(storage, uri: str, dataset: str) -> dict[str, Any]:
    raw = json.loads(storage.read_bytes(uri).decode())
    ref = DatasetRef(**raw)
    if ref.dataset != dataset or ref.uri.startswith("artifacts/research/rating-successor-v2/"):
        raise ValueError(f"Invalid restored {dataset} comparison ref")
    manifest_uri = ref.uri.rsplit("/", 1)[0] + "/manifest.json"
    manifest = json.loads(storage.read_bytes(manifest_uri).decode())
    if manifest.get("state") != "validated" or int(
        manifest.get("partitions", {}).get("season", -1)
    ) != 2019:
        raise ValueError(f"Restored {dataset} ref is not a validated 2019 dataset")
    return asdict(ref)


def _run_silver(
    *,
    source_set_uri: str,
    output_ref_uri: str,
    dataset: str,
    as_of: str,
) -> None:
    subprocess.run(
        [
            sys.executable,
            "scripts/pipeline/build_history_silver.py",
            "--dataset",
            dataset,
            "--season",
            "2019",
            "--as-of",
            as_of,
            "--legacy-comparison-source-set-uri",
            source_set_uri,
            "--output-ref-uri",
            output_ref_uri,
            "--identity-label",
            "legacy_comparison_2019_restore_v1",
            "--environment",
            "preview",
        ],
        check=True,
    )


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--environment", choices=("preview", "production"), required=True)
    args = parser.parse_args(argv)
    if args.environment != "preview":
        raise ValueError("Legacy comparison restoration is Preview-only")
    if not RUN_ID_RE.fullmatch(args.run_id):
        raise ValueError("Legacy comparison restoration run ID is invalid")
    if not args.as_of.endswith("Z"):
        raise ValueError("Legacy comparison restoration --as-of must be UTC Z time")
    if os.environ.get("CFB_STORAGE_BACKEND", "").lower() != "r2":
        raise RuntimeError("Legacy comparison restoration requires CFB_STORAGE_BACKEND=r2")
    target = resolve_runtime_target("preview")
    if not target.database_url:
        raise RuntimeError("Legacy comparison restoration requires PREVIEW_DATABASE_URL")
    code_sha = _committed_code_sha()
    source = get_source_storage()
    storage = get_storage(environment="preview")
    config = load_legacy_comparison_restore_config()
    base = f"{config.output_prefix}/{args.run_id}"
    source_set_uri = f"{base}/source-set.json"

    verified = find_and_verify_legacy_archives(
        source, config, inventory_historical_source(source)
    )
    entries: list[dict[str, Any]] = []
    for archive, item, _ in verified:
        capture = import_historical_object(
            source=source,
            destination=storage,
            conn_url=target.database_url,
            item=item,
            expected_source_sha256=archive.sha256,
        )
        capture = source_capture_by_id(target.database_url, capture.capture_id)
        if (
            capture.entity != archive.entity
            or capture.request.get("source_uri") != archive.uri
            or capture.response_metadata.get("source_sha256") != archive.sha256
            or capture.state != "registered"
        ):
            raise ValueError(f"Restored capture identity mismatch for {archive.uri}")
        entries.append(
            {
                "entity": archive.entity,
                "source_uri": archive.uri,
                "source_sha256": archive.sha256,
                "capture_ids": [capture.capture_id],
                "capture_uri": capture.uri,
                "content_sha": capture.content_sha,
                "object_sha": capture.object_sha,
                "row_count": capture.row_count,
            }
        )
    source_set = _source_set_payload(
        run_id=args.run_id,
        as_of=args.as_of,
        code_sha=code_sha,
        config_sha256=config.sha256,
        captures=entries,
    )
    _immutable_write(storage, source_set_uri, _canonical(source_set))

    refs: list[dict[str, Any]] = []
    for dataset in ("games", "game_outcomes", "teams"):
        output_ref_uri = f"{base}/refs/{dataset}.json"
        _run_silver(
            source_set_uri=source_set_uri,
            output_ref_uri=output_ref_uri,
            dataset=dataset,
            as_of=args.as_of,
        )
        refs.append({"dataset": dataset, **_ref(storage, output_ref_uri, dataset)})
    manifest: dict[str, Any] = {
        "contract_version": "legacy-comparison-2019-restoration-v1",
        "state": "complete",
        "run_id": args.run_id,
        "season": 2019,
        "as_of": args.as_of,
        "code_sha": code_sha,
        "configuration_sha256": config.sha256,
        "source_set_uri": source_set_uri,
        "source_set_sha256": source_set["manifest_sha256"],
        "refs": refs,
    }
    manifest["manifest_sha256"] = hashlib.sha256(_canonical(manifest)).hexdigest()
    manifest_uri = f"{base}/manifest.json"
    _immutable_write(storage, manifest_uri, _canonical(manifest))
    print(json.dumps({"manifest_uri": manifest_uri, **manifest}, sort_keys=True))


if __name__ == "__main__":
    main()
