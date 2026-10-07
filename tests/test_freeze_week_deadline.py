"""Freeze ordering: a missed deadline is recorded before the decision-ref gate."""

from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pipeline" / "freeze_week.py"
_spec = importlib.util.spec_from_file_location("_freeze_week_under_test", _PATH)
freeze_week = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(freeze_week)

_NOW = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)


class _Cursor:
    def __init__(self, row: tuple) -> None:
        self.row = row
        self.statements: list[str] = []

    def execute(self, sql: str, params=None) -> None:
        self.statements.append(" ".join(sql.split()))

    def fetchone(self):
        return self.row

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        return None


class _Connection:
    def __init__(self, cursor: _Cursor) -> None:
        self._cursor = cursor
        self.commits = 0

    def cursor(self) -> _Cursor:
        return self._cursor

    def commit(self) -> None:
        self.commits += 1

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        return None


def _row(first_kickoff: datetime) -> tuple:
    # run_id, state, expected, predicted, lined, artifact_uri, artifact_sha,
    # evidence_class, model_id, bundle_sha256, first_kickoff, db_now
    return (
        "2026w6-v5-test",
        "published",
        10,
        10,
        10,
        "artifacts/x.json",
        "a" * 64,
        "pending",
        "v5-possession",
        "b" * 64,
        first_kickoff,
        _NOW,
    )


def _patch(monkeypatch, row: tuple) -> _Connection:
    cursor = _Cursor(row)
    conn = _Connection(cursor)
    monkeypatch.setattr(freeze_week.psycopg, "connect", lambda *_a, **_k: conn)
    monkeypatch.setattr(freeze_week, "assert_active_pipeline_lease", lambda _c: None)
    import cks_picks_cfb.ops.v5_freeze_guard as guard

    monkeypatch.setattr(guard, "require_v5_freeze_authorization", lambda *a, **k: {})
    return conn


def test_past_deadline_run_is_recorded_missed_without_a_decision_ref(monkeypatch):
    conn = _patch(monkeypatch, _row(_NOW - timedelta(hours=12)))

    result = freeze_week.freeze_run("postgresql://unused", year=2026, week=6)

    assert result == {
        "run_id": "2026w6-v5-test",
        "state": "missed",
        "reason": "freeze deadline passed",
    }
    assert conn.commits == 1
    assert any("evidence_class = 'missed'" in sql for sql in conn._cursor.statements)


def test_open_window_run_still_requires_a_decision_ref(monkeypatch):
    conn = _patch(monkeypatch, _row(_NOW + timedelta(hours=48)))

    with pytest.raises(RuntimeError, match="decision reference is required"):
        freeze_week.freeze_run("postgresql://unused", year=2026, week=6)

    assert conn.commits == 0
    assert not any("state = 'frozen'" in sql for sql in conn._cursor.statements)
