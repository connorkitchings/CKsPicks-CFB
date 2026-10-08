"""Deterministic quality receipts, written immutably.

A receipt is evidence: identical inputs produce identical bytes, a different
receipt never overwrites an existing one, and nothing here reads the clock.
Callers pass ``as_of`` explicitly when they want a time recorded.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from cks_picks_cfb.quality.checks import QualityRun

SCHEMA_VERSION = "data_quality_receipt_v1"
RECEIPT_PREFIX = "quality/receipts"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def build_receipt(
    run: QualityRun,
    *,
    identity: Mapping[str, Any],
    code_sha: str,
    inputs: Mapping[str, Any] | None = None,
    as_of: str | None = None,
) -> dict[str, Any]:
    """Build the receipt for ``run``. ``receipt_id`` is the hash of its content."""
    records = sorted(
        (r.to_record() for r in run.results),
        key=lambda r: (r["check_id"], canonical_bytes(r["scope"]).decode()),
    )
    by_severity: dict[str, dict[str, int]] = {}
    for record in records:
        bucket = by_severity.setdefault(
            record["severity"], {"passed": 0, "failed": 0, "skipped": 0}
        )
        bucket[
            "skipped"
            if record["skipped"]
            else "passed"
            if record["passed"]
            else "failed"
        ] += 1
    content = {
        "schema_version": SCHEMA_VERSION,
        "stage": run.stage,
        "identity": dict(identity),
        "code_sha": code_sha,
        "inputs": dict(inputs or {}),
        "as_of": as_of,
        "blocked": run.blocked,
        "summary": {
            "checks": len(records),
            "failed": sum(1 for r in records if not r["passed"] and not r["skipped"]),
            "skipped": sum(1 for r in records if r["skipped"]),
            "by_severity": by_severity,
        },
        "checks": records,
    }
    receipt_id = hashlib.sha256(canonical_bytes(content)).hexdigest()
    return {**content, "receipt_id": receipt_id}


def receipt_relative_path(receipt: Mapping[str, Any]) -> str:
    return f"{RECEIPT_PREFIX}/{receipt['stage']}/{receipt['receipt_id']}.json"


def write_receipt_local(receipt: Mapping[str, Any], root: Path) -> Path:
    """Write ``receipt`` under ``root``; refuse to overwrite different bytes."""
    path = root / receipt_relative_path(receipt)
    payload = canonical_bytes(receipt)
    if path.exists():
        if path.read_bytes() != payload:
            raise FileExistsError(f"immutable receipt collision: {path}")
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def write_receipt_storage(receipt: Mapping[str, Any], storage: Any) -> str:
    """Write ``receipt`` through a storage backend with the same immutability rule."""
    uri = receipt_relative_path(receipt)
    payload = canonical_bytes(receipt)
    if storage.exists(uri):
        if storage.read_bytes(uri) != payload:
            raise FileExistsError(f"immutable receipt collision: {uri}")
        return uri
    storage.write_bytes(payload, uri)
    if storage.read_bytes(uri) != payload:
        raise IOError(f"quality receipt readback differs: {uri}")
    return uri
