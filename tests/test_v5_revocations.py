from datetime import datetime, timezone

import pytest

from cks_picks_cfb.ops.v5_revocations import (
    V5RevocationError,
    append_release_revocation,
    assert_release_records_active,
    lock_release_records,
)


class Cursor:
    def __init__(self, revoked=(), retained=None):
        self.revoked = set(revoked)
        self.retained = retained
        self.executed = []
        self.params_seen = []
        self.params = None

    def execute(self, sql, params=()):
        self.executed.append(sql)
        self.params = params
        self.params_seen.append(params)

    def fetchone(self):
        sql = self.executed[-1]
        if "ops.v5_release_revocations" in sql and sql.startswith("SELECT decision_ref"):
            return ("stop",) if self.params[:2] in self.revoked else None
        if "ops.v5_release_revocations" in sql and sql.startswith("SELECT record_type"):
            return self.retained
        return None


def test_shared_locks_are_deterministic_and_use_transaction_scope():
    first = Cursor()
    second = Cursor()
    records = [
        ("intended_update_authorization", "auth-2"),
        ("bundle_approval", "bundle-1"),
        ("bundle_approval", "bundle-1"),
    ]
    lock_release_records(first, records)
    lock_release_records(second, list(reversed(records)))
    assert first.executed == second.executed
    assert all("pg_advisory_xact_lock_shared" in statement for statement in first.executed)
    assert first.params_seen == second.params_seen
    assert len(first.params_seen) == 2


def test_shared_guard_rejects_revoked_record_after_locking():
    cur = Cursor(revoked={("bundle_approval", "bundle-1")})
    with pytest.raises(V5RevocationError, match="has been revoked"):
        assert_release_records_active(cur, [("bundle_approval", "bundle-1")])
    assert any("pg_advisory_xact_lock_shared" in sql for sql in cur.executed)


def test_revocation_retry_is_idempotent_and_conflicts_fail():
    retained = (
        "bundle_approval",
        "bundle-1",
        "decision-1",
        datetime(2026, 10, 6, tzinfo=timezone.utc),
    )
    cur = Cursor(retained=retained)
    result = append_release_revocation(
        cur,
        record_type="bundle_approval",
        record_id="bundle-1",
        decision_ref="decision-1",
    )
    assert result["record_id"] == "bundle-1"
    assert any("pg_advisory_xact_lock(%s)" in sql for sql in cur.executed)
    assert any("ON CONFLICT (record_type, record_id) DO NOTHING" in sql for sql in cur.executed)

    conflict = Cursor(retained=(*retained[:2], "another-decision", retained[3]))
    with pytest.raises(V5RevocationError, match="conflicts"):
        append_release_revocation(
            conflict,
            record_type="bundle_approval",
            record_id="bundle-1",
            decision_ref="decision-1",
        )
