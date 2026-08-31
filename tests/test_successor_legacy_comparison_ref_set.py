"""Tests for the R1 legacy comparison-evidence bootstrap command."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from dataclasses import asdict
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
        if uri not in self.objects:
            raise KeyError(uri)
        return self.objects[uri]

    def write_bytes(self, payload: bytes, uri: str) -> None:
        self.objects[uri] = payload


# ---------------------------------------------------------------------------
# Helpers: build valid fixture data
# ---------------------------------------------------------------------------

def _make_ref(dataset: str, season: int) -> dict:
    """Create a minimal DatasetRef-shaped dict for a given dataset/season."""
    return {
        "dataset": dataset,
        "version_id": f"{dataset}-{season}-ver",
        "schema_version": f"{dataset}_v1",
        "content_sha": hashlib.sha256(f"{dataset}{season}".encode()).hexdigest(),
        "uri": f"lake/silver/dataset={dataset}/version={dataset}-{season}/data.parquet",
    }


def _make_restoration_manifest(season: int = 2019) -> bytes:
    """Build a valid 2019 restoration manifest matching the expected contract."""
    module = _module()
    refs = [_make_ref(ds, season) for ds in module.HARD_DATASETS]
    manifest = {
        "contract_version": module.LEGACY_COMPARISON_2019_CONTRACT_VERSION,
        "state": "complete",
        "season": season,
        "run_id": f"legacy-comparison-{season}-fixture",
        "refs": refs,
    }
    return json.dumps(manifest, sort_keys=True).encode()


def _make_catalog_entries(module, seasons=(2021, 2022, 2023, 2024, 2025)) -> list:
    """Build catalog-shaped entries for the given seasons."""
    entries = []
    for season in seasons:
        for dataset in module.HARD_DATASETS:
            ref = _make_ref(dataset, season)
            entries.append({"season": season, **ref})
    return sorted(entries, key=lambda e: (e["season"], e["dataset"]))


# ---------------------------------------------------------------------------
# Task 2 — success path
# ---------------------------------------------------------------------------

def test_success_path_all_18_required_entries(monkeypatch):
    """manifest 2019 + catalog 2021-2025 → all 18 required entries present."""
    module = _module()
    storage = _Storage()

    # Populate the 2019 restoration manifest with the pinned SHA
    manifest_bytes = _make_restoration_manifest(season=2019)
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    storage.objects[module.LEGACY_COMPARISON_2019_MANIFEST_URI] = manifest_bytes

    monkeypatch.setattr(module, "get_storage", lambda **_: storage)
    monkeypatch.setattr(
        module,
        "LEGACY_COMPARISON_2019_MANIFEST_SHA256",
        manifest_sha,
    )
    monkeypatch.setattr(
        module,
        "resolve_runtime_target",
        lambda _: SimpleNamespace(database_url="postgresql://fixture"),
    )
    catalog_entries = _make_catalog_entries(module)
    monkeypatch.setattr(module, "_catalog_entries", lambda *_: catalog_entries)

    output_uri = "artifacts/research/rating-successor-v2/r1/run/comparison-ref-set.json"
    module.main(
        [
            "--environment", "preview",
            "--as-of", "2026-08-31T00:00:00Z",
            "--output-uri", output_uri,
        ]
    )

    payload = json.loads(storage.objects[output_uri])
    assert payload["state"] == "complete"
    entries = payload["entries"]
    assert len(entries) == 18  # 3 datasets × 6 seasons

    seasons_present = {e["season"] for e in entries}
    assert seasons_present == {2019, 2021, 2022, 2023, 2024, 2025}
    datasets_present = {e["dataset"] for e in entries}
    assert datasets_present == set(module.HARD_DATASETS)

    # 2019 entries must come from the restoration manifest (non-successor URIs)
    entries_2019 = [e for e in entries if e["season"] == 2019]
    assert len(entries_2019) == 3
    for e in entries_2019:
        assert e["uri"].startswith("lake/silver/")


# ---------------------------------------------------------------------------
# Task 2 — failure modes
# ---------------------------------------------------------------------------

def test_tampered_manifest_sha_fails_closed(monkeypatch):
    """Tampered manifest SHA → immutable failure diagnostic + SystemExit."""
    module = _module()
    storage = _Storage()

    manifest_bytes = _make_restoration_manifest(season=2019)
    storage.objects[module.LEGACY_COMPARISON_2019_MANIFEST_URI] = manifest_bytes
    # Pin is deliberately wrong
    monkeypatch.setattr(module, "LEGACY_COMPARISON_2019_MANIFEST_SHA256", "bad" * 21 + "0")
    monkeypatch.setattr(module, "get_storage", lambda **_: storage)
    monkeypatch.setattr(
        module,
        "resolve_runtime_target",
        lambda _: SimpleNamespace(database_url="postgresql://fixture"),
    )

    output_uri = "artifacts/research/rating-successor-v2/r1/run/comparison-ref-set.json"
    with pytest.raises(SystemExit, match="Legacy comparison evidence preflight failed"):
        module.main(
            [
                "--environment", "preview",
                "--as-of", "2026-08-31T00:00:00Z",
                "--output-uri", output_uri,
            ]
        )

    diagnostic_uri = output_uri.replace(".json", ".failure.json")
    diagnostic = json.loads(storage.objects[diagnostic_uri])
    assert diagnostic["state"] == "failed"
    assert "SHA-256 mismatch" in diagnostic["failure"]["message"]
    assert output_uri not in storage.objects


def test_missing_manifest_fails_closed(monkeypatch):
    """Missing manifest (R2 KeyError) → failure diagnostic + SystemExit."""
    module = _module()
    storage = _Storage()
    # Do NOT populate the manifest URI — storage will raise KeyError

    monkeypatch.setattr(module, "get_storage", lambda **_: storage)
    monkeypatch.setattr(
        module,
        "resolve_runtime_target",
        lambda _: SimpleNamespace(database_url="postgresql://fixture"),
    )

    output_uri = "artifacts/research/rating-successor-v2/r1/run/comparison-ref-set.json"
    with pytest.raises(SystemExit, match="Legacy comparison evidence preflight failed"):
        module.main(
            [
                "--environment", "preview",
                "--as-of", "2026-08-31T00:00:00Z",
                "--output-uri", output_uri,
            ]
        )

    diagnostic_uri = output_uri.replace(".json", ".failure.json")
    diagnostic = json.loads(storage.objects[diagnostic_uri])
    assert diagnostic["state"] == "failed"
    assert "2019 restoration manifest not found" in diagnostic["failure"]["message"]
    assert output_uri not in storage.objects


def test_incomplete_manifest_state_fails_closed(monkeypatch):
    """Incomplete manifest (state != 'complete') → failure diagnostic + SystemExit."""
    module = _module()
    storage = _Storage()

    manifest = json.loads(_make_restoration_manifest(season=2019))
    manifest["state"] = "in_progress"  # not complete
    manifest_bytes = json.dumps(manifest, sort_keys=True).encode()
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()

    storage.objects[module.LEGACY_COMPARISON_2019_MANIFEST_URI] = manifest_bytes
    monkeypatch.setattr(module, "LEGACY_COMPARISON_2019_MANIFEST_SHA256", manifest_sha)
    monkeypatch.setattr(module, "get_storage", lambda **_: storage)
    monkeypatch.setattr(
        module,
        "resolve_runtime_target",
        lambda _: SimpleNamespace(database_url="postgresql://fixture"),
    )

    output_uri = "artifacts/research/rating-successor-v2/r1/run/comparison-ref-set.json"
    with pytest.raises(SystemExit, match="Legacy comparison evidence preflight failed"):
        module.main(
            [
                "--environment", "preview",
                "--as-of", "2026-08-31T00:00:00Z",
                "--output-uri", output_uri,
            ]
        )

    diagnostic_uri = output_uri.replace(".json", ".failure.json")
    diagnostic = json.loads(storage.objects[diagnostic_uri])
    assert diagnostic["state"] == "failed"
    assert "state is not complete" in diagnostic["failure"]["message"]
    assert output_uri not in storage.objects


# ---------------------------------------------------------------------------
# Preserved: existing test (adapted for two-source flow)
# ---------------------------------------------------------------------------

def test_catalog_failure_writes_immutable_failure_diagnostic(monkeypatch):
    """Catalog LookupError → failure diagnostic + SystemExit (2021-2025 coverage)."""
    module = _module()
    storage = _Storage()

    # Provide a valid 2019 manifest so that path succeeds
    manifest_bytes = _make_restoration_manifest(season=2019)
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    storage.objects[module.LEGACY_COMPARISON_2019_MANIFEST_URI] = manifest_bytes
    monkeypatch.setattr(module, "LEGACY_COMPARISON_2019_MANIFEST_SHA256", manifest_sha)

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
            LookupError("No legacy games comparison ref exists for season 2021")
        ),
    )

    output_uri = "artifacts/research/rating-successor-v2/r1/run/comparison-ref-set.json"
    with pytest.raises(SystemExit, match="Legacy comparison evidence preflight failed"):
        module.main(
            [
                "--environment", "preview",
                "--as-of", "2026-08-27T00:00:00Z",
                "--output-uri", output_uri,
            ]
        )

    diagnostic_uri = output_uri.replace(".json", ".failure.json")
    payload = json.loads(storage.objects[diagnostic_uri])
    assert payload["state"] == "failed"
    assert payload["selection_mode"] == "catalog_preflight"
    assert payload["failure"]["error_type"] == "LookupError"
    assert output_uri not in storage.objects
