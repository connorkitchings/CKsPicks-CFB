"""Fail-closed checks for the Preview successor release packaging boundary."""

import pytest

from scripts.pipeline.authorize_v5_intended_update_preview import authorization_record
from scripts.pipeline.build_v5_intended_update_live_serving import build, run_uris
from scripts.pipeline.package_v5_intended_update_runs import _write_once, package_week


def test_package_rejects_non_preview_namespace_before_storage_access(monkeypatch):
    monkeypatch.setenv("CFB_ARTIFACT_ENV", "production")
    with pytest.raises(ValueError, match="Preview artifact namespace"):
        package_week(object(), {}, "a" * 64, 0)


def test_preview_authorization_binds_every_immutable_parent():
    manifest = {
        "run_id": "2026w0-v5repair-20260929-p1",
        "week": 0,
        "evidence_class": "replay",
        "model_id": "v5-intended-update-2026-v1",
        "inference_bundle_sha256": "a" * 64,
        "v5_rating_replay_manifest_sha256": "b" * 64,
        "v5_live_forecast_manifest_uri": "forecast.json",
        "v5_live_forecast_manifest_sha256": "c" * 64,
        "v5_intended_update_serving_manifest_uri": "serving.json",
        "v5_intended_update_serving_manifest_sha256": "d" * 64,
        "v5_intended_update_verifier_uri": "verifier.json",
        "v5_intended_update_verifier_sha256": "e" * 64,
        "artifact_uri": "prediction.csv",
        "artifact_sha256": "f" * 64,
    }
    record = authorization_record(manifest, decision_ref="approved Preview rehearsal")
    assert record["environment"] == "preview"
    assert record["rating_manifest_sha256"] == "b" * 64
    assert record["serving_manifest_sha256"] == "d" * 64
    assert record["prediction_artifact_sha256"] == "f" * 64
    with pytest.raises(ValueError, match="decision reference"):
        authorization_record(manifest, decision_ref=" ")

    live = {
        **manifest,
        "run_id": "2026w5-v5repair-20260929-p1",
        "week": 5,
        "evidence_class": "pending",
    }
    live_record = authorization_record(live, decision_ref="approved Preview rehearsal")
    assert (live_record["week"], live_record["evidence_class"]) == (5, "pending")
    assert live_record["authorization_id"] != record["authorization_id"]


def test_immutable_package_write_refuses_different_bytes():
    class Storage:
        def __init__(self):
            self.data = {}

        def exists(self, uri):
            return uri in self.data

        def read_bytes(self, uri):
            return self.data[uri]

        def write_bytes(self, raw, uri):
            self.data[uri] = raw

    storage = Storage()
    _write_once(storage, "run/artifact", b"first")
    _write_once(storage, "run/artifact", b"first")
    with pytest.raises(FileExistsError, match="collision"):
        _write_once(storage, "run/artifact", b"changed")
    assert storage.data["run/artifact"] == b"first"


def test_refreshed_live_run_requires_new_market_refs_and_cutoff():
    run_id, forecast_uri, serving_uri = run_uris("20260929-p2")
    assert run_id == "2026w5-v5repair-20260929-p2"
    assert "20260929-p2/week=5" in forecast_uri
    assert run_id in serving_uri
    with pytest.raises(ValueError, match="fresh market refs and cutoff"):
        build(object(), b"{}", release_tag="20260929-p2")
    with pytest.raises(ValueError, match="invalid live release tag"):
        run_uris("../production")


def test_package_only_serves_weeks_before_the_locks_active_week(monkeypatch):
    monkeypatch.setenv("CFB_ARTIFACT_ENV", "preview")
    lock = {"active_week": {"week": 6}}
    for week in (-1, 6, 7):
        with pytest.raises(ValueError, match="before the lock's active week"):
            package_week(object(), lock, "a" * 64, week)
