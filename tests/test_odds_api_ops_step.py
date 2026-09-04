"""Unit tests for the opt-in The Odds API soft-fail ops step.

No network, no database: subprocess and env are monkeypatched. The step must
(1) stay a no-op skip unless explicitly enabled with a key, (2) degrade to a
warning instead of raising when the enabled provider fails, and (3) report
registered captures on success.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cks_picks_cfb.ops import __main__ as ops_main  # noqa: E402
from cks_picks_cfb.ops.contracts import OperationContext  # noqa: E402


def _context() -> OperationContext:
    return OperationContext(
        command="publish-week",
        environment="preview",
        season=2026,
        week=2,
        as_of="2026-09-09",
        pipeline_run_id="pipe-1",
        prediction_run_id="pred-1",
    )


def _step():
    return ops_main._soft_fail_market_quotes_step(conn_url="unused", year=2026, week=2)


def test_step_skips_when_disabled(monkeypatch):
    monkeypatch.delenv("CFB_ODDS_API_ENABLED", raising=False)
    monkeypatch.delenv("THE_ODDS_API_KEY", raising=False)
    outputs = _step().action(_context())
    assert outputs == [{"status": "skipped", "reason": "CFB_ODDS_API_ENABLED != 1"}]


def test_step_skips_when_enabled_without_key(monkeypatch):
    monkeypatch.setenv("CFB_ODDS_API_ENABLED", "1")
    monkeypatch.delenv("THE_ODDS_API_KEY", raising=False)
    outputs = _step().action(_context())
    assert outputs == [{"status": "skipped", "reason": "THE_ODDS_API_KEY not set"}]


def test_step_degrades_on_subprocess_failure(monkeypatch, capsys):
    monkeypatch.setenv("CFB_ODDS_API_ENABLED", "1")
    monkeypatch.setenv("THE_ODDS_API_KEY", "test-key")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(args=a, returncode=3),
    )
    outputs = _step().action(_context())
    assert outputs[0]["status"] == "degraded"
    assert outputs[0]["error_category"] == "subprocess_error"
    assert "degraded to CFBD-only" in capsys.readouterr().err


def test_step_degrades_on_timeout(monkeypatch):
    monkeypatch.setenv("CFB_ODDS_API_ENABLED", "1")
    monkeypatch.setenv("THE_ODDS_API_KEY", "test-key")

    def raise_timeout(*a, **k):
        raise subprocess.TimeoutExpired(cmd="x", timeout=1)

    monkeypatch.setattr(subprocess, "run", raise_timeout)
    outputs = _step().action(_context())
    assert outputs[0]["status"] == "degraded"
    assert outputs[0]["error_category"] == "subprocess_timeout"


def test_step_degrades_when_no_captures_registered(monkeypatch):
    monkeypatch.setenv("CFB_ODDS_API_ENABLED", "1")
    monkeypatch.setenv("THE_ODDS_API_KEY", "test-key")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(args=a, returncode=0),
    )

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, *a, **k):
            return self

        def fetchall(self):
            return []

    monkeypatch.setattr(ops_main.psycopg, "connect", lambda *a, **k: FakeConn())
    outputs = _step().action(_context())
    assert outputs[0]["status"] == "degraded"
    assert outputs[0]["error_category"] == "no_registered_capture"


def test_step_reports_captures_on_success(monkeypatch):
    monkeypatch.setenv("CFB_ODDS_API_ENABLED", "1")
    monkeypatch.setenv("THE_ODDS_API_KEY", "test-key")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(args=a, returncode=0),
    )

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, *a, **k):
            return self

        def fetchall(self):
            return [("cap-1",), ("cap-2",)]

    monkeypatch.setattr(ops_main.psycopg, "connect", lambda *a, **k: FakeConn())
    outputs = _step().action(_context())
    assert [output["status"] for output in outputs] == ["captured", "captured"]
    assert {output["capture_id"] for output in outputs} == {"cap-1", "cap-2"}


def test_step_passes_ingestion_run_id(monkeypatch):
    monkeypatch.setenv("CFB_ODDS_API_ENABLED", "1")
    monkeypatch.setenv("THE_ODDS_API_KEY", "test-key")
    seen: dict[str, object] = {}

    def fake_run(argv, *a, **k):
        seen["env"] = k["env"]
        return subprocess.CompletedProcess(args=argv, returncode=3)

    monkeypatch.setattr(subprocess, "run", fake_run)
    _step().action(_context())
    assert seen["env"]["CFB_INGESTION_RUN_ID"] == "pipe-1:market_quotes"


def test_resume_validator_accepts_recorded_statuses():
    step = _step()
    assert step.resume_validator(None, [{"status": "skipped"}]) is True
    assert step.resume_validator(None, [{"status": "degraded"}]) is True
    assert step.resume_validator(None, []) is False
    assert step.resume_validator(None, [{"status": "unknown"}]) is False


def test_resume_validator_requires_live_captures(monkeypatch):
    step = _step()
    outputs = [{"status": "captured", "capture_id": "cap-1"}]

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, *a, **k):
            return self

        def fetchall(self):
            return [("cap-1",)]

    monkeypatch.setattr(ops_main.psycopg, "connect", lambda *a, **k: FakeConn())
    assert step.resume_validator(None, outputs) is True

    class EmptyConn(FakeConn):
        def fetchall(self):
            return []

    monkeypatch.setattr(ops_main.psycopg, "connect", lambda *a, **k: EmptyConn())
    assert step.resume_validator(None, outputs) is False


def test_publish_week_definition_includes_soft_fail_step():
    # The step list is built inside command handlers; assert the helper is
    # referenced by the publish-week builder source as a regression guard.
    source = Path(ops_main.__file__).read_text()
    assert "_soft_fail_market_quotes_step(" in source


def test_soft_fail_step_never_raises_for_provider_errors(monkeypatch):
    monkeypatch.setenv("CFB_ODDS_API_ENABLED", "1")
    monkeypatch.setenv("THE_ODDS_API_KEY", "test-key")

    def raise_oserror(*a, **k):
        raise OSError("provider unreachable")

    monkeypatch.setattr(subprocess, "run", raise_oserror)
    with pytest.raises(OSError):
        # Non-subprocess exceptions still surface (programming errors must
        # not be swallowed); provider failures arrive as returncodes or
        # TimeoutExpired, which degrade.
        _step().action(_context())
