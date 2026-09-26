"""Unit tests for the V5 best-quote production release driver."""

import pytest

from scripts.pipeline.release_v5_bestquote_replacement_production import (
    authorization_record,
    production_manifest,
    run_id_for,
)

SAMPLE_MANIFEST = {
    "run_id": "2026w1-v5replay-bestquote-20260926-r2",
    "model_id": "v5-possession-ppp-rho060-exposure",
    "inference_bundle_sha256": "f" * 64,
    "v5_replay_manifest_uri": "artifacts/research/data-first-football-v1/forecasts/replay-runs/v5-replay-20260924-cb2252a/replay-manifest.json",
    "v5_replay_manifest_sha256": "3" * 64,
    "replay_verification_sha256": "1" * 64,
    "config_sha": "9" * 64,
    "artifact_uri": "artifacts/preview/predictions/year=2026/week=1/run_id=2026w1-v5replay-bestquote-20260926-r2/predictions.csv",
    "artifact_sha256": "a" * 64,
    "feature_snapshot_uri": "artifacts/preview/predictions/year=2026/week=1/run_id=2026w1-v5replay-bestquote-20260926-r2/point_in_time_features.csv",
}


def test_production_manifest_rewrites_only_artifact_uris():
    manifest = production_manifest(dict(SAMPLE_MANIFEST))
    assert manifest["artifact_uri"] == (
        "artifacts/production/predictions/year=2026/week=1/"
        "run_id=2026w1-v5replay-bestquote-20260926-r2/predictions.csv"
    )
    assert manifest["feature_snapshot_uri"].startswith("artifacts/production/")
    preserved = dict(SAMPLE_MANIFEST)
    preserved["artifact_uri"] = manifest["artifact_uri"]
    preserved["feature_snapshot_uri"] = manifest["feature_snapshot_uri"]
    assert manifest == preserved


def test_production_manifest_refuses_non_preview_uri():
    bad = dict(SAMPLE_MANIFEST, artifact_uri="artifacts/staging/x.csv")
    with pytest.raises(ValueError, match="non-preview manifest URI"):
        production_manifest(bad)


def test_authorization_record_binds_manifest_identities():
    manifest = production_manifest(dict(SAMPLE_MANIFEST))
    record = authorization_record(1, manifest)
    assert record["authorization_id"] == "v5-bestquote-2026w1-" + "a" * 8
    assert record["environment"] == "production"
    assert record["season"] == 2026
    assert record["week"] == 1
    assert record["prediction_run_id"] == SAMPLE_MANIFEST["run_id"]
    assert record["model_id"] == SAMPLE_MANIFEST["model_id"]
    assert (
        record["prediction_artifact_uri"]
        == "artifacts/production/predictions/year=2026/week=1/"
        "run_id=2026w1-v5replay-bestquote-20260926-r2/predictions.csv"
    )
    assert record["prediction_artifact_sha256"] == "a" * 64
    assert record["verifier_sha256"] == "1" * 64
    assert record["verifier_uri"] == (
        "artifacts/research/data-first-football-v1/forecasts/replay-runs/"
        "v5-replay-20260924-cb2252a/verification/verifier-manifest.json"
    )
    assert record["decision_ref"] == "v5-bestquote-replacement-review-2026-09-26"


def test_authorization_record_rejects_wrong_run():
    bad = dict(SAMPLE_MANIFEST, run_id="someone-elses-run")
    with pytest.raises(ValueError, match="is not the release run"):
        authorization_record(1, bad)


def test_release_run_ids_are_stable():
    for week in range(5):
        assert run_id_for(week).startswith(f"2026w{week}-v5replay-bestquote-")
