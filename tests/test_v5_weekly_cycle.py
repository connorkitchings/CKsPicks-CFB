"""Focused identity and preflight gates for the manual V5 controller."""

from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

from cks_picks_cfb.ops import v5_cycle
from cks_picks_cfb.ops.state_machine import InMemoryStateStore


def _spec(tmp_path, component="repair"):
    config = tmp_path / "v5.yaml"
    config.write_text("version: 1\n")
    args = (
        {"season-2026-inputs-uri": "inputs.json", "repair-v2-anchor-uri": "anchor.json"}
        if component == "repair"
        else {"repair-manifest-uri": "repair.json"}
    )
    item = {
        "run_id": "research-2026w5",
        "as_of": "2026-09-30T12:00:00Z",
        "config": str(config),
        "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
        "arguments": args,
        "parents": {
            uri: hashlib.sha256(uri.encode()).hexdigest() for uri in args.values()
        },
    }
    return v5_cycle.CycleSpec(
        "cycle-2026w5", 2026, 5, "preview", "a" * 40, {component: item}
    )


class Storage:
    def read_bytes(self, uri):
        return uri.encode()


def test_preflight_writes_reviewable_binding(tmp_path, monkeypatch):
    spec = _spec(tmp_path)
    monkeypatch.setattr(v5_cycle, "_git_sha", lambda: "a" * 40)
    monkeypatch.setattr(v5_cycle, "get_storage", lambda **_: Storage())
    monkeypatch.setattr(
        v5_cycle.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout='{"population": 157}'),
    )
    path = tmp_path / "preflight.json"
    evidence = v5_cycle.preflight(spec, "repair", path)
    assert evidence["result"]["population"] == 157
    assert json.loads(path.read_text()) == evidence
    assert evidence["binding"]["parents"] == spec.components["repair"]["parents"]


def test_changed_parent_fails_before_runner(tmp_path, monkeypatch):
    spec = _spec(tmp_path)
    monkeypatch.setattr(v5_cycle, "_git_sha", lambda: "a" * 40)

    class ChangedStorage:
        def read_bytes(self, uri):
            return b"changed"

    monkeypatch.setattr(v5_cycle, "get_storage", lambda **_: ChangedStorage())
    with pytest.raises(v5_cycle.V5CycleError, match="checksum changed"):
        v5_cycle.preflight(spec, "repair", tmp_path / "preflight.json")


def test_tampered_preflight_cannot_apply(tmp_path, monkeypatch):
    spec = _spec(tmp_path)
    monkeypatch.setattr(v5_cycle, "_git_sha", lambda: "a" * 40)
    monkeypatch.setattr(v5_cycle, "_clean_committed", lambda: None)
    monkeypatch.setattr(v5_cycle, "get_storage", lambda **_: Storage())
    monkeypatch.setattr(
        v5_cycle.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout='{"population": 157}'),
    )
    path = tmp_path / "preflight.json"
    evidence = v5_cycle.preflight(spec, "repair", path)
    evidence["result"]["population"] = 158
    path.write_text(json.dumps(evidence))
    with pytest.raises(v5_cycle.V5CycleError, match="another component identity"):
        v5_cycle.apply_component(spec, "repair", path, "test-db")


def test_missing_prior_component_cannot_apply(tmp_path, monkeypatch):
    spec = _spec(tmp_path, "measurement")
    monkeypatch.setattr(v5_cycle, "_git_sha", lambda: "a" * 40)
    monkeypatch.setattr(v5_cycle, "_clean_committed", lambda: None)
    monkeypatch.setattr(v5_cycle, "get_storage", lambda **_: Storage())
    monkeypatch.setattr(
        v5_cycle.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout='{"population": 157}'),
    )
    path = tmp_path / "preflight.json"
    v5_cycle.preflight(spec, "measurement", path)
    with pytest.raises(v5_cycle.V5CycleError, match="lacks prerequisite"):
        v5_cycle.apply_component(spec, "measurement", path, "test-db")


def test_cycle_descriptor_rejects_wrong_environment(tmp_path):
    path = tmp_path / "cycle.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "v5_weekly_cycle_v1",
                "cycle_id": "cycle-2026w5",
                "season": 2026,
                "week": 5,
                "environment": "other",
                "code_sha": "a" * 40,
                "components": {},
            }
        )
    )
    with pytest.raises(v5_cycle.V5CycleError, match="environment"):
        v5_cycle.CycleSpec.load(path)


def test_runner_json_can_follow_progress_lines():
    output = 'progress: loading\n{\n  "status": "verified",\n  "rows": 157\n}\n'
    assert v5_cycle._read_json_output(output)["rows"] == 157


def test_identical_apply_resumes_without_second_research_write(tmp_path, monkeypatch):
    spec = _spec(tmp_path)
    monkeypatch.setattr(v5_cycle, "_git_sha", lambda: "a" * 40)
    monkeypatch.setattr(v5_cycle, "_clean_committed", lambda: None)
    monkeypatch.setattr(v5_cycle, "get_storage", lambda **_: Storage())
    applied = []

    def run(argv, **kwargs):
        if "--apply" in argv:
            applied.append(argv)
            return SimpleNamespace(stdout='{"manifest_uri": "repair-manifest.json"}')
        return SimpleNamespace(stdout='{"population": 157}')

    monkeypatch.setattr(v5_cycle.subprocess, "run", run)
    monkeypatch.setattr(
        v5_cycle,
        "_verified_result",
        lambda *_: {"manifest_uri": None, "manifest_sha256": "a" * 64},
    )
    store = InMemoryStateStore()

    class StoreContext:
        def __init__(self, url):
            assert url == "test-db"

        def __enter__(self):
            return store

        def __exit__(self, *_):
            return None

    monkeypatch.setattr(v5_cycle, "PostgresStateStore", StoreContext)
    evidence = tmp_path / "preflight.json"
    v5_cycle.preflight(spec, "repair", evidence)
    first = v5_cycle.apply_component(spec, "repair", evidence, "test-db")
    again = v5_cycle.apply_component(spec, "repair", evidence, "test-db")
    assert first.pipeline_run_id == again.pipeline_run_id
    assert len(applied) == 1
    assert store.runs[first.pipeline_run_id] == "succeeded"
