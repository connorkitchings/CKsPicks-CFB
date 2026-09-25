"""Exact-artifact production release authorization checks."""

from __future__ import annotations

import hashlib
import io
import json

import pandas as pd
import pytest

from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.ops.v5_release import (
    V5ReleaseError,
    assert_v5_database_environment,
    require_release_record,
    require_replay_release_record,
    validate_release_record,
    validate_replay_release_record,
)


class MemoryStorage:
    def __init__(self, objects: dict[str, bytes]):
        self.objects = objects

    def read_bytes(self, uri: str) -> bytes:
        return self.objects[uri]


def _raw(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True).encode()


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def release_fixture():
    forecast = signed_payload(
        {
            "identity": {"season": 2026, "environment": "preview"},
            "production_activation_authorized": False,
        }
    )
    forecast_raw = _raw(forecast)
    frame_bytes = io.BytesIO()
    pd.DataFrame([{"season": 2026, "week": 5, "source": "schedule"}]).to_parquet(
        frame_bytes, index=False
    )
    readiness = signed_payload(
        {
            "readiness_overall": "ready",
            "parents": {
                "forecast_manifest_uri": "forecast.json",
                "forecast_manifest_raw_sha256": _sha(forecast_raw),
            },
            "output_refs": {"readiness": {"uri": "readiness.parquet"}},
        }
    )
    receipt = signed_payload(
        {
            "state": "verified",
            "verified": True,
            "kind": "readiness",
            "readiness_overall": "ready",
            "manifest_uri": "readiness.json",
        }
    )
    receipt_raw = _raw(receipt)
    artifact = b"game_id,model\n123,v5\n"
    objects = {
        "forecast.json": forecast_raw,
        "readiness.json": _raw(readiness),
        "receipt.json": receipt_raw,
        "readiness.parquet": frame_bytes.getvalue(),
        "predictions.csv": artifact,
    }
    record = {
        "authorization_id": "approval-2026w5",
        "environment": "production",
        "season": 2026,
        "week": 5,
        "prediction_run_id": "2026w5-v5",
        "model_id": "v5-possession-ppp-rho060-exposure",
        "inference_bundle_sha256": "a" * 64,
        "forecast_manifest_uri": "forecast.json",
        "forecast_manifest_sha256": _sha(forecast_raw),
        "readiness_verifier_uri": "receipt.json",
        "readiness_verifier_sha256": _sha(receipt_raw),
        "serving_config_sha256": "b" * 64,
        "prediction_artifact_uri": "predictions.csv",
        "prediction_artifact_sha256": _sha(artifact),
        "decision_ref": "review/2026w5",
    }
    manifest = {
        "run_id": record["prediction_run_id"],
        "model_id": record["model_id"],
        "inference_bundle_sha256": record["inference_bundle_sha256"],
        "v5_live_forecast_manifest_uri": record["forecast_manifest_uri"],
        "v5_live_forecast_manifest_sha256": record["forecast_manifest_sha256"],
        "config_sha": record["serving_config_sha256"],
        "artifact_uri": record["prediction_artifact_uri"],
        "artifact_sha256": record["prediction_artifact_sha256"],
    }
    return record, manifest, MemoryStorage(objects)


def test_exact_release_packet_validates():
    record, manifest, storage = release_fixture()
    validate_release_record(
        record,
        manifest=manifest,
        storage=storage,
        environment="production",
        season=2026,
        week=5,
    )


@pytest.mark.parametrize(
    "field,replacement",
    [
        ("environment", "preview"),
        ("season", 2025),
        ("week", 6),
        ("prediction_run_id", "another-run"),
        ("model_id", "another-model"),
        ("inference_bundle_sha256", "c" * 64),
        ("forecast_manifest_uri", "another.json"),
        ("forecast_manifest_sha256", "c" * 64),
        ("serving_config_sha256", "c" * 64),
        ("prediction_artifact_uri", "another.csv"),
        ("prediction_artifact_sha256", "c" * 64),
    ],
)
def test_release_rejects_changed_identity(field, replacement):
    record, manifest, storage = release_fixture()
    record[field] = replacement
    with pytest.raises(V5ReleaseError, match="release does not match"):
        validate_release_record(
            record,
            manifest=manifest,
            storage=storage,
            environment="production",
            season=2026,
            week=5,
        )


def test_release_rejects_wrong_readiness_slate():
    record, manifest, storage = release_fixture()
    data = io.BytesIO()
    pd.DataFrame([{"season": 2026, "week": 6}]).to_parquet(data, index=False)
    storage.objects["readiness.parquet"] = data.getvalue()
    with pytest.raises(V5ReleaseError, match="another slate"):
        validate_release_record(
            record,
            manifest=manifest,
            storage=storage,
            environment="production",
            season=2026,
            week=5,
        )


def test_release_rejects_changed_readiness_receipt():
    record, manifest, storage = release_fixture()
    storage.objects["receipt.json"] += b" "
    with pytest.raises(V5ReleaseError, match="checksum changed"):
        validate_release_record(
            record,
            manifest=manifest,
            storage=storage,
            environment="production",
            season=2026,
            week=5,
        )


def test_missing_admin_record_fails_before_any_insert():
    record, manifest, storage = release_fixture()

    class Cursor:
        def __init__(self):
            self.sql = []

        def execute(self, sql, params):
            self.sql.append(sql)

        def fetchone(self):
            return None

    cur = Cursor()
    with pytest.raises(V5ReleaseError, match="absent"):
        require_release_record(
            cur, manifest=manifest, storage=storage, season=2026, week=5
        )
    assert len(cur.sql) == 1 and cur.sql[0].startswith("SELECT")


class RoleCursor:
    def __init__(self, session_user, current_user):
        self.session_user = session_user
        self.current_user = current_user
        self.queries = []

    def execute(self, sql, params=None):
        self.queries.append(sql)

    def fetchone(self):
        if "session_user" in self.queries[-1]:
            return (self.session_user, self.current_user)
        return None


@pytest.mark.parametrize(
    "environment,role",
    [
        ("production", "cks_prod_pipeline"),
        ("preview", "cks_preview_pipeline"),
    ],
)
def test_guard_accepts_the_exact_restricted_pipeline_roles(environment, role):
    assert_v5_database_environment(RoleCursor(role, role), environment) is None


@pytest.mark.parametrize(
    "session_user,current_user",
    [
        ("neondb_owner", "neondb_owner"),
        ("cks_prod_migrator", "cks_prod_migrator"),
        ("cks_prod_web", "cks_prod_web"),
        ("cks_preview_pipeline", "cks_preview_pipeline"),
        ("cks_prod_pipeline_admin", "cks_prod_pipeline_admin"),
        ("neondb_owner", "cks_prod_pipeline"),
        ("cks_prod_pipeline", "neondb_owner"),
    ],
)
def test_guard_rejects_non_pipeline_production_identities(session_user, current_user):
    with pytest.raises(V5ReleaseError, match="exact restricted pipeline role"):
        assert_v5_database_environment(
            RoleCursor(session_user, current_user), "production"
        )


@pytest.mark.parametrize(
    "session_user,current_user",
    [
        ("neondb_owner", "neondb_owner"),
        ("cks_preview_migrator", "cks_preview_migrator"),
        ("cks_prod_pipeline", "cks_prod_pipeline"),
        ("neondb_owner", "cks_preview_pipeline"),
    ],
)
def test_guard_rejects_non_pipeline_preview_identities(session_user, current_user):
    with pytest.raises(V5ReleaseError, match="exact restricted pipeline role"):
        assert_v5_database_environment(
            RoleCursor(session_user, current_user), "preview"
        )


def test_guard_rejects_an_unreadable_identity():
    class EmptyCursor(RoleCursor):
        def fetchone(self):
            return None

    with pytest.raises(V5ReleaseError, match="unreadable"):
        assert_v5_database_environment(
            EmptyCursor("cks_prod_pipeline", "cks_prod_pipeline"), "production"
        )


def test_guard_rejects_an_unknown_environment():
    with pytest.raises(V5ReleaseError, match="invalid V5 database environment"):
        assert_v5_database_environment(
            RoleCursor("cks_prod_pipeline", "cks_prod_pipeline"), "staging"
        )


def replay_fixture():
    replay = signed_payload(
        {
            "schema_version": "v5_week4_replay_manifest_v1",
            "state": "frozen",
            "evidence_class": "replay",
            "production_activation_authorized": False,
            "prediction_records_sha256": "d" * 64,
        }
    )
    replay_raw = _raw(replay)
    receipt = signed_payload(
        {
            "schema_version": "v5_week4_replay_verification_v1",
            "state": "verified",
            "replay_manifest_raw_sha256": _sha(replay_raw),
            "prediction_records_sha256": "d" * 64,
            "production_activation_authorized": False,
        }
    )
    receipt_raw = _raw(receipt)
    artifact = b"game_id,model\n123,v5\n"
    objects = {
        "replay.json": replay_raw,
        "receipt.json": receipt_raw,
        "predictions.csv": artifact,
    }
    record = {
        "authorization_id": "replay-approval-2026w4",
        "environment": "production",
        "season": 2026,
        "week": 4,
        "prediction_run_id": "2026w4-v5-replay",
        "model_id": "v5-possession-ppp-rho060-exposure",
        "inference_bundle_sha256": "a" * 64,
        "replay_manifest_uri": "replay.json",
        "replay_manifest_sha256": _sha(replay_raw),
        "verifier_uri": "receipt.json",
        "verifier_sha256": _sha(receipt_raw),
        "serving_config_sha256": "b" * 64,
        "prediction_artifact_uri": "predictions.csv",
        "prediction_artifact_sha256": _sha(artifact),
        "decision_ref": "review/2026w4-replay",
    }
    manifest = {
        "run_id": record["prediction_run_id"],
        "model_id": record["model_id"],
        "inference_bundle_sha256": record["inference_bundle_sha256"],
        "config_sha": record["serving_config_sha256"],
        "artifact_uri": record["prediction_artifact_uri"],
        "artifact_sha256": record["prediction_artifact_sha256"],
        "v5_replay_manifest_uri": record["replay_manifest_uri"],
        "v5_replay_manifest_sha256": record["replay_manifest_sha256"],
        "replay_verification_sha256": record["verifier_sha256"],
    }
    return record, manifest, MemoryStorage(objects)


def test_replay_release_packet_validates():
    record, manifest, storage = replay_fixture()
    validate_replay_release_record(
        record,
        manifest=manifest,
        storage=storage,
        environment="production",
        season=2026,
        week=4,
    )


@pytest.mark.parametrize(
    "field",
    [
        "season",
        "week",
        "prediction_run_id",
        "model_id",
        "inference_bundle_sha256",
        "replay_manifest_uri",
        "replay_manifest_sha256",
        "verifier_sha256",
        "serving_config_sha256",
        "prediction_artifact_uri",
        "prediction_artifact_sha256",
    ],
)
def test_replay_release_rejects_changed_identity(field):
    record, manifest, storage = replay_fixture()
    record[field] = "changed"
    with pytest.raises(V5ReleaseError, match="replay release does not match"):
        validate_replay_release_record(
            record,
            manifest=manifest,
            storage=storage,
            environment="production",
            season=2026,
            week=4,
        )


def test_replay_release_rejects_a_live_manifest():
    record, _, _ = replay_fixture()
    _, live_manifest, live_storage = release_fixture()
    with pytest.raises(V5ReleaseError, match="replay"):
        validate_replay_release_record(
            record,
            manifest=live_manifest,
            storage=live_storage,
            environment="production",
            season=2026,
            week=5,
        )


def test_replay_release_rejects_an_unfrozen_replay():
    record, manifest, storage = replay_fixture()
    replay = signed_payload(
        {
            "schema_version": "v5_week4_replay_manifest_v1",
            "state": "dry_run",
            "evidence_class": "replay",
            "production_activation_authorized": False,
            "prediction_records_sha256": "d" * 64,
        }
    )
    replay_raw = _raw(replay)
    storage.objects["replay.json"] = replay_raw
    record = dict(record)
    record["replay_manifest_sha256"] = _sha(replay_raw)
    manifest = dict(manifest)
    manifest["v5_replay_manifest_sha256"] = _sha(replay_raw)
    with pytest.raises(V5ReleaseError, match="not frozen replay"):
        validate_replay_release_record(
            record,
            manifest=manifest,
            storage=storage,
            environment="production",
            season=2026,
            week=4,
        )


def test_missing_replay_record_fails_before_any_insert():
    record, manifest, storage = replay_fixture()

    class Cursor:
        def __init__(self):
            self.sql = []

        def execute(self, sql, params=None):
            self.sql.append(sql)

        def fetchone(self):
            return None

    cur = Cursor()
    with pytest.raises(V5ReleaseError, match="replay release authorization is absent"):
        require_replay_release_record(
            cur,
            manifest=manifest,
            storage=storage,
            environment="production",
            season=2026,
            week=4,
        )
    assert len(cur.sql) == 1
    assert "v5_replay_release_authorizations" in cur.sql[0]
    assert "v5_serving_authorizations" not in cur.sql[0]
