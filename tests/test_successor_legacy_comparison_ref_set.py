"""Tests for the R1 legacy comparison-evidence bootstrap command."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def _module():
    path = (
        Path(__file__).parents[1]
        / "scripts/pipeline/build_successor_legacy_comparison_ref_set.py"
    )
    spec = importlib.util.spec_from_file_location("successor_comparison_bootstrap", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Storage:
    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def exists(self, uri: str) -> bool:
        return uri in self.objects

    def read_bytes(self, uri: str) -> bytes:
        return self.objects[uri]

    def write_bytes(self, payload: bytes, uri: str) -> None:
        self.objects[uri] = payload


def test_missing_catalog_evidence_writes_immutable_failure_diagnostic(monkeypatch):
    module = _module()
    storage = _Storage()
    monkeypatch.setattr(module, "get_storage", lambda **_: storage)
    monkeypatch.setattr(
        module,
        "resolve_runtime_target",
        lambda _: SimpleNamespace(database_url="postgresql://fixture"),
    )
    monkeypatch.setattr(
        module,
        "_catalog_entries",
        lambda *_: (_ for _ in ()).throw(
            LookupError("No legacy games comparison ref exists for season 2019")
        ),
    )

    output_uri = "artifacts/research/rating-successor-v2/r1/run/comparison-ref-set.json"
    with pytest.raises(SystemExit, match="Legacy comparison evidence preflight failed"):
        module.main(
            [
                "--environment",
                "preview",
                "--as-of",
                "2026-08-27T00:00:00Z",
                "--output-uri",
                output_uri,
            ]
        )

    diagnostic_uri = output_uri.replace(".json", ".failure.json")
    payload = json.loads(storage.objects[diagnostic_uri])
    assert payload["state"] == "failed"
    assert payload["selection_mode"] == "catalog_preflight"
    assert payload["failure"]["error_type"] == "LookupError"
    assert output_uri not in storage.objects
