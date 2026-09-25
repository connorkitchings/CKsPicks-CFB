"""Focused dispatch tests for the V5 replay-to-serving converter."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

# Make scripts/pipeline importable
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts" / "pipeline"
sys.path.insert(0, str(SCRIPTS_DIR))

import generate_v5_replay_weekly_bets as serving  # noqa: E402

from cks_picks_cfb.data.data_first_phase2d import signed_payload  # noqa: E402
from cks_picks_cfb.inference.v5_serving import V5ServingError  # noqa: E402


class MemoryStorage:
    def __init__(self, objects=None):
        self.objects = dict(objects or {})

    def exists(self, uri):
        return uri in self.objects

    def read_bytes(self, uri):
        return self.objects[uri]


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str
    ).encode()


def _manifest(schema, parents):
    manifest = signed_payload(
        {
            "schema_version": schema,
            "state": "frozen",
            "evidence_class": "replay",
            "production_activation_authorized": False,
            "identity": {"run_id": "replay-run", "code_sha": "c" * 40},
            "parents": parents,
            "prediction_raw_sha256": hashlib.sha256(b"a,b\n1,2\n").hexdigest(),
        }
    )
    return manifest, _canonical(manifest)


def _w4_parents():
    return {
        "measurement_uri": "measurement.json",
        "measurement_raw_sha256": "a" * 64,
        "rating_replay_uri": "rating.json",
        "rating_replay_raw_sha256": "b" * 64,
        "bridge_uri": "bridge.json",
        "bridge_raw_sha256": "c" * 64,
        "schedule_ref_uri": "schedule.parquet",
        "schedule_raw_sha256": "d" * 64,
        "bundle_uri": "bundle.json",
        "bundle_sha256": "e" * 64,
    }


def _spec(manifest_uri, manifest_raw):
    config = (
        Path(__file__).resolve().parent.parent
        / "conf"
        / "research"
        / "data_first_football_v1"
        / "live_forecast_v1.yaml"
    )
    return {
        "schema_version": "v5_replay_serving_v1",
        "replay_manifest_uri": manifest_uri,
        "replay_manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
        "forecast_config": str(config),
    }


def _receipt():
    return {"state": "verified", "records_sha256": "f" * 64}


def test_week4_manifest_dispatches_to_week4_verifier(monkeypatch):
    manifest, raw = _manifest("v5_week4_replay_manifest_v1", _w4_parents())
    receipt = _receipt()
    storage = MemoryStorage(
        {
            "replay/manifest.json": raw,
            "replay/predictions.csv": b"a,b\n1,2\n",
            "replay/verification/verifier-manifest.json": _canonical(receipt),
        }
    )
    calls = []
    monkeypatch.setattr(
        serving, "verify_week4_replay", lambda *a, **k: calls.append("week4") or receipt
    )
    monkeypatch.setattr(
        serving,
        "verify_replay",
        lambda *a, **k: calls.append("v1") or receipt,
    )
    out_manifest, forecasts, fields, schedule_uri = serving.verify_v5_replay_source(
        _spec("replay/manifest.json", raw), storage
    )
    assert calls == ["week4"]
    assert schedule_uri == "schedule.parquet"
    assert fields["v5_rating_replay_manifest_sha256"] == "b" * 64
    assert fields["inference_bundle_sha256"] == "e" * 64
    assert out_manifest["schema_version"] == "v5_week4_replay_manifest_v1"


def test_legacy_manifest_still_dispatches_to_v1_verifier(monkeypatch):
    parents = {
        "measurement_uri": "m",
        "measurement_raw_sha256": "a" * 64,
        "rating_uri": "r",
        "rating_raw_sha256": "b" * 64,
        "bridge_uri": "br",
        "bridge_raw_sha256": "c" * 64,
        "schedule_uri": "sched.parquet",
        "schedule_raw_sha256": "d" * 64,
        "bundle_uri": "bundle.json",
        "bundle_sha256": "e" * 64,
    }
    manifest, raw = _manifest("v5_replay_manifest_v1", parents)
    receipt = _receipt()
    storage = MemoryStorage(
        {
            "replay/manifest.json": raw,
            "replay/predictions.csv": b"a,b\n1,2\n",
            "replay/verification/verifier-manifest.json": _canonical(receipt),
        }
    )
    calls = []
    monkeypatch.setattr(
        serving, "verify_week4_replay", lambda *a, **k: calls.append("week4") or receipt
    )
    monkeypatch.setattr(
        serving,
        "verify_replay",
        lambda *a, **k: calls.append("v1") or receipt,
    )
    _, _, fields, schedule_uri = serving.verify_v5_replay_source(
        _spec("replay/manifest.json", raw), storage
    )
    assert calls == ["v1"]
    assert schedule_uri == "sched.parquet"
    assert fields["v5_rating_replay_manifest_sha256"] == "b" * 64


def test_unknown_manifest_schema_is_rejected(monkeypatch):
    manifest, raw = _manifest("v5_replay_manifest_v9", _w4_parents())
    storage = MemoryStorage({"replay/manifest.json": raw})
    with pytest.raises(V5ServingError, match="manifest schema"):
        serving.verify_v5_replay_source(_spec("replay/manifest.json", raw), storage)


def test_missing_rating_lineage_is_rejected(monkeypatch):
    parents = _w4_parents()
    del parents["rating_replay_raw_sha256"]
    manifest, raw = _manifest("v5_week4_replay_manifest_v1", parents)
    receipt = _receipt()
    storage = MemoryStorage(
        {
            "replay/manifest.json": raw,
            "replay/predictions.csv": b"a,b\n1,2\n",
            "replay/verification/verifier-manifest.json": _canonical(receipt),
        }
    )
    monkeypatch.setattr(serving, "verify_week4_replay", lambda *a, **k: receipt)
    with pytest.raises(V5ServingError, match="rating lineage"):
        serving.verify_v5_replay_source(_spec("replay/manifest.json", raw), storage)


def test_manifest_checksum_mismatch_is_rejected():
    manifest, raw = _manifest("v5_week4_replay_manifest_v1", _w4_parents())
    storage = MemoryStorage({"replay/manifest.json": raw + b" "})
    spec = _spec("replay/manifest.json", raw)
    with pytest.raises(V5ServingError, match="checksum differs"):
        serving.verify_v5_replay_source(spec, storage)
