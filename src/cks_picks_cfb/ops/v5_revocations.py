"""Transaction-scoped revocation guards for V5 release records."""

from __future__ import annotations

import hashlib
from typing import Any, Literal

RecordType = Literal["bundle_approval", "intended_update_authorization"]


class V5RevocationError(ValueError):
    """A V5 release record is revoked or cannot be safely revoked."""


def _lock_key(record_type: RecordType, record_id: str) -> int:
    raw = f"v5-release:{record_type}:{record_id}".encode()
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big", signed=True)


def lock_release_records(
    cur: Any,
    records: list[tuple[RecordType, str]],
    *,
    exclusive: bool = False,
) -> None:
    """Acquire the same deterministic xact lock for readers and revokers."""
    normalized = sorted({(kind, str(record_id)) for kind, record_id in records})
    for kind, record_id in normalized:
        if not record_id.strip():
            raise V5RevocationError("release record ID is empty")
        key = _lock_key(kind, record_id)
        lock_fn = (
            "pg_advisory_xact_lock" if exclusive else "pg_advisory_xact_lock_shared"
        )
        cur.execute(f"SELECT {lock_fn}(%s)", (key,))


def assert_release_records_active(
    cur: Any,
    records: list[tuple[RecordType, str]],
) -> None:
    """Hold shared locks and fail if any referenced record is revoked."""
    lock_release_records(cur, records)
    for kind, record_id in sorted(set(records)):
        cur.execute(
            "SELECT decision_ref FROM ops.v5_release_revocations "
            "WHERE record_type = %s AND record_id = %s",
            (kind, record_id),
        )
        if cur.fetchone() is not None:
            raise V5RevocationError(f"V5 {kind} {record_id} has been revoked")


def append_release_revocation(
    cur: Any,
    *,
    record_type: RecordType,
    record_id: str,
    decision_ref: str,
) -> dict[str, Any]:
    """Append one revocation inside the caller's transaction; never commits."""
    if record_type not in {"bundle_approval", "intended_update_authorization"}:
        raise V5RevocationError("unsupported V5 revocation record type")
    if not record_id.strip() or not decision_ref.strip():
        raise V5RevocationError("revocation ID and decision reference are required")
    lock_release_records(cur, [(record_type, record_id)], exclusive=True)
    cur.execute(
        "INSERT INTO ops.v5_release_revocations (record_type, record_id, decision_ref) "
        "VALUES (%s, %s, %s) ON CONFLICT (record_type, record_id) DO NOTHING",
        (record_type, record_id, decision_ref),
    )
    cur.execute(
        "SELECT record_type, record_id, decision_ref, revoked_at "
        "FROM ops.v5_release_revocations WHERE record_type = %s AND record_id = %s",
        (record_type, record_id),
    )
    row = cur.fetchone()
    if row is None or row[2] != decision_ref:
        raise V5RevocationError("revocation retry conflicts with retained decision")
    return {
        "record_type": row[0],
        "record_id": row[1],
        "decision_ref": row[2],
        "revoked_at": row[3].isoformat(),
    }
