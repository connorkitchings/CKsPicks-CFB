"""Focused gates for the Week 4 late-publication V5 replay adapter."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

# Make scripts/pipeline importable
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts" / "pipeline"
sys.path.insert(0, str(SCRIPTS_DIR))

import build_v5_week4_replay as week4_replay  # noqa: E402

from cks_picks_cfb.data.data_first_live_forecast_v1 import (  # noqa: E402
    BRIDGE_MANIFEST_URI,
    LIVE_FORECAST_COLUMNS,
)
from cks_picks_cfb.data.data_first_phase2d import signed_payload  # noqa: E402

CUTOFF = "2026-09-22T14:55:00Z"
KICKOFFS = [f"2026-09-{day:02d}T19:00:00Z" for day in range(24, 30)]
BUNDLE = signed_payload(
    {
        "bridge_manifest_uri": BRIDGE_MANIFEST_URI,
        "bridge_manifest_raw_sha256": "c" * 64,
    }
)
BUNDLE_RAW = json.dumps(BUNDLE, sort_keys=True).encode()


def _frames(*, weeks=(4,), kickoffs=KICKOFFS, population_weeks=(0, 1, 2, 3)):
    games = list(range(2001, 2001 + len(kickoffs)))
    schedule = pd.DataFrame(
        {
            "season": [2026] * len(games),
            "week": [4] * len(games),
            "game_id": games,
            "kickoff_utc": kickoffs,
        }
    )
    features = pd.DataFrame(
        {
            "season": [2026] * len(games),
            "week": list(weeks) * len(games),
            "game_id": games,
        }
    )
    population = pd.DataFrame(
        {
            "season": [2026] * 4,
            "week": list(population_weeks),
            "game_id": [1001, 1002, 1003, 1004],
        }
    )
    return schedule, features, population


def _sources(storage_bytes, **overrides):
    schedule, features, population = _frames(**overrides)
    sources = {
        "live_features": features,
        "population": population,
        "schedule": schedule,
        "measurement": {"identity": {"as_of": CUTOFF}},
        "state_refs": {game: f"state-{game}" for game in features["game_id"]},
        "parents": {
            "measurement_uri": "measurement.json",
            "measurement_raw_sha256": "a" * 64,
            "rating_replay_uri": "rating.json",
            "rating_replay_raw_sha256": "b" * 64,
            "bridge_uri": "bridge.json",
            "bridge_raw_sha256": "c" * 64,
            "schedule_ref_uri": "schedule.parquet",
            "schedule_raw_sha256": "d" * 64,
        },
    }
    storage_bytes["measurement.json"] = b"measurement"
    storage_bytes["rating.json"] = b"rating"
    storage_bytes["bridge.json"] = b"bridge"
    storage_bytes["schedule.parquet"] = b"schedule"
    storage_bytes["bundle.json"] = BUNDLE_RAW
    return sources


def _args(**overrides):
    config_path = (
        Path(__file__).resolve().parent.parent
        / "conf"
        / "research"
        / "data_first_football_v1"
        / "live_forecast_v1.yaml"
    )
    values = {
        "run_id": "v5-week4-replay-test",
        "expected_code_sha": "e" * 40,
        "measurement_manifest_uri": "measurement.json",
        "rating_manifest_uri": "rating.json",
        "schedule_ref_uri": "schedule.parquet",
        "as_of": CUTOFF,
        "config": str(config_path),
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def _config():
    return {
        "inference_bundle_uri": "bundle.json",
        "inference_bundle_sha256": hashlib.sha256(BUNDLE_RAW).hexdigest(),
    }


def _patch(monkeypatch, sources, predictions=None):
    games = list(sources["live_features"]["game_id"])
    frame = pd.DataFrame({"game_id": [g for g in games for _ in (0, 1)]})
    for column in LIVE_FORECAST_COLUMNS:
        if column not in frame.columns:
            frame[column] = frame["game_id"] if column == "game_id" else 0
    frame["target"] = ["margin", "total"] * len(games)
    frame["timing_class"] = "replay"
    frame["run_id"] = "v5-week4-replay-test"
    frame["season"] = 2026
    frame["week"] = 4
    produced = predictions if predictions is not None else frame
    monkeypatch.setattr(week4_replay, "load_live_forecast_sources", lambda **_: sources)
    monkeypatch.setattr(
        week4_replay,
        "apply_exported_bridge",
        lambda _bundle, _frame, **kwargs: SimpleNamespace(predictions=produced),
    )
    monkeypatch.setattr(
        week4_replay, "verify_bundle_predictions", lambda *_a, **_k: produced
    )
    monkeypatch.setattr(
        week4_replay,
        "verify_predictions",
        lambda **_: {"records_sha256": "f" * 64},
    )
    monkeypatch.setattr(
        week4_replay,
        "validate_prediction_frame",
        lambda *_a, **_k: None,
    )
    return produced


class MemoryStorage:
    def __init__(self, objects=None):
        self.objects = dict(objects or {})

    def exists(self, uri):
        return uri in self.objects

    def read_bytes(self, uri):
        return self.objects[uri]

    def write_bytes(self, raw, uri):
        self.objects[uri] = raw

    def list_files(self, prefix):
        return [uri for uri in self.objects if uri.startswith(prefix)]


def test_week4_replay_evidence_is_replay_with_complete_pairs(monkeypatch):
    storage = MemoryStorage()
    sources = _sources(storage.objects)
    _patch(monkeypatch, sources)
    evidence, raw = week4_replay._evidence(_args(), _config(), storage)
    assert evidence["state"] == "dry_run"
    assert evidence["evidence_class"] == "replay"
    assert evidence["timing"]["late_publication"] is True
    assert evidence["game_count"] == len(KICKOFFS)
    assert evidence["prediction_count"] == 2 * len(KICKOFFS)
    assert evidence["identity"]["target_week"] == 4
    assert evidence["production_activation_authorized"] is False
    assert raw  # prediction bytes are reviewable


def test_week4_replay_rejects_wrong_week_features(monkeypatch):
    storage = MemoryStorage()
    sources = _sources(storage.objects, weeks=(5,))
    _patch(monkeypatch, sources)
    with pytest.raises(week4_replay.Week4ReplayError, match="another slate"):
        week4_replay._evidence(_args(), _config(), storage)


def test_week4_replay_rejects_an_incomplete_slate(monkeypatch):
    storage = MemoryStorage()
    sources = _sources(storage.objects)
    schedule = sources["schedule"].iloc[:-1]
    sources_obj = dict(sources)
    produced = pd.DataFrame(
        {
            "game_id": [g for g in schedule["game_id"] for _ in (0, 1)],
            "target": ["margin", "total"] * len(schedule),
        }
    )
    sources_obj["live_features"] = sources["live_features"].iloc[:-1]
    _patch(monkeypatch, sources_obj, predictions=produced)
    with pytest.raises(week4_replay.Week4ReplayError, match="incomplete"):
        week4_replay._evidence(_args(), _config(), storage)


def test_week4_replay_rejects_post_kickoff_cutoff(monkeypatch):
    storage = MemoryStorage()
    sources = _sources(storage.objects)
    _patch(monkeypatch, sources)
    with pytest.raises(week4_replay.Week4ReplayError, match="pre_kickoff"):
        week4_replay._evidence(_args(as_of="2026-09-24T23:30:00Z"), _config(), storage)


def test_week4_replay_rejects_cutoff_before_parents(monkeypatch):
    storage = MemoryStorage()
    sources = _sources(storage.objects)
    _patch(monkeypatch, sources)
    with pytest.raises(week4_replay.Week4ReplayError, match="predates"):
        week4_replay._evidence(_args(as_of="2026-09-20T00:00:00Z"), _config(), storage)


def test_week4_replay_rejects_post_week3_population(monkeypatch):
    storage = MemoryStorage()
    sources = _sources(storage.objects, population_weeks=(0, 1, 2, 4))
    _patch(monkeypatch, sources)
    with pytest.raises(week4_replay.Week4ReplayError, match="leakage"):
        week4_replay._evidence(_args(), _config(), storage)


def test_week4_replay_rejects_a_changed_bundle(monkeypatch):
    storage = MemoryStorage()
    sources = _sources(storage.objects)
    _patch(monkeypatch, sources)
    storage.objects["bundle.json"] = b"changed"
    with pytest.raises(week4_replay.Week4ReplayError, match="checksum"):
        week4_replay._evidence(_args(), _config(), storage)


def test_week4_replay_manifest_verifies_and_records_creation_time(monkeypatch):
    storage = MemoryStorage()
    sources = _sources(storage.objects)
    _patch(monkeypatch, sources)
    args = _args()
    evidence, prediction_raw = week4_replay._evidence(args, _config(), storage)
    prefix = (
        f"artifacts/research/data-first-football-v1/forecasts/replay-runs/{args.run_id}"
    )
    manifest = signed_payload(
        dict(
            evidence,
            schema_version="v5_week4_replay_manifest_v1",
            state="frozen",
            created_at_utc="2026-09-25T16:00:00Z",
        )
    )
    storage.objects[f"{prefix}/week4-replay-manifest.json"] = week4_replay._json_bytes(
        manifest
    )
    storage.objects[f"{prefix}/predictions.csv"] = prediction_raw
    args.verify_manifest_uri = f"{prefix}/week4-replay-manifest.json"
    receipt = week4_replay.verify(args, _config(), storage)
    assert receipt["state"] == "verified"
    assert receipt["late_publication"] is True
    assert receipt["evidence_class"] == "replay"


def test_week4_replay_manifest_freezes_without_dry_run_state():
    evidence = {"state": "dry_run", "identity": {"run_id": "x"}, "extra": 1}
    manifest = week4_replay._manifest(evidence, "2026-09-25T16:00:00Z")
    assert manifest["state"] == "frozen"
    assert manifest["created_at_utc"] == "2026-09-25T16:00:00Z"
    assert manifest["identity"] == {"run_id": "x"}
    assert manifest["extra"] == 1


def test_week4_replay_rejects_prospective_or_live_labels(monkeypatch):
    storage = MemoryStorage()
    sources = _sources(storage.objects)
    _patch(monkeypatch, sources)
    args = _args()
    evidence, prediction_raw = week4_replay._evidence(args, _config(), storage)
    prefix = (
        f"artifacts/research/data-first-football-v1/forecasts/replay-runs/{args.run_id}"
    )
    manifest = signed_payload(
        dict(
            evidence,
            schema_version="v5_week4_replay_manifest_v1",
            state="frozen",
            created_at_utc="2026-09-25T16:00:00Z",
            evidence_class="pending",
        )
    )
    storage.objects[f"{prefix}/week4-replay-manifest.json"] = week4_replay._json_bytes(
        manifest
    )
    storage.objects[f"{prefix}/predictions.csv"] = prediction_raw
    args.verify_manifest_uri = f"{prefix}/week4-replay-manifest.json"
    with pytest.raises(week4_replay.Week4ReplayError, match="identity or policy"):
        week4_replay.verify(args, _config(), storage)
