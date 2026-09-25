"""Read-only verification of one exact V5 serving authorization."""

from __future__ import annotations

import hashlib
import io
import json
from typing import Any, Mapping

import pandas as pd

from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload

AUTH_COLUMNS = (
    "authorization_id",
    "environment",
    "season",
    "week",
    "prediction_run_id",
    "model_id",
    "inference_bundle_sha256",
    "forecast_manifest_uri",
    "forecast_manifest_sha256",
    "readiness_verifier_uri",
    "readiness_verifier_sha256",
    "serving_config_sha256",
    "prediction_artifact_uri",
    "prediction_artifact_sha256",
    "decision_ref",
)

REPLAY_AUTH_COLUMNS = (
    "authorization_id",
    "environment",
    "season",
    "week",
    "prediction_run_id",
    "model_id",
    "inference_bundle_sha256",
    "replay_manifest_uri",
    "replay_manifest_sha256",
    "verifier_uri",
    "verifier_sha256",
    "serving_config_sha256",
    "prediction_artifact_uri",
    "prediction_artifact_sha256",
    "decision_ref",
)

REPLAY_MANIFEST_SCHEMAS = frozenset(
    {"v5_replay_manifest_v1", "v5_week4_replay_manifest_v1"}
)

REPLAY_VERIFIER_SCHEMAS = frozenset(
    {"v5_replay_verification_v1", "v5_week4_replay_verification_v1"}
)


class V5ReleaseError(ValueError):
    """The reviewed release does not authorize this exact immutable run."""


V5_PIPELINE_ROLE_BY_ENVIRONMENT = {
    "preview": "cks_preview_pipeline",
    "production": "cks_prod_pipeline",
}


def assert_v5_database_environment(cur: Any, environment: str) -> None:
    """Require the exact restricted pipeline login for this environment.

    Both the login identity (``session_user``) and the effective identity
    (``current_user``) must equal the branch-scoped pipeline role, so owner,
    migrator, web, wrong-branch, and ``SET ROLE`` sessions are all rejected
    before any V5 prediction or selection write.
    """
    expected = V5_PIPELINE_ROLE_BY_ENVIRONMENT.get(environment)
    if expected is None:
        raise V5ReleaseError("invalid V5 database environment")
    cur.execute("SELECT session_user, current_user")
    row = cur.fetchone()
    if not row or len(row) < 2:
        raise V5ReleaseError("V5 database identity is unreadable")
    session_role, effective_role = str(row[0]), str(row[1])
    if session_role != expected or effective_role != expected:
        raise V5ReleaseError(
            "V5 writes require the exact restricted pipeline role "
            f"{expected} for environment {environment}; got "
            f"session_user={session_role!r}, current_user={effective_role!r}"
        )


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read_bound_json(storage: Any, uri: str, expected_sha: str) -> dict[str, Any]:
    raw = storage.read_bytes(uri)
    if _sha(raw) != expected_sha:
        raise V5ReleaseError(f"release source checksum changed: {uri}")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise V5ReleaseError("release source is not a JSON object")
    return value


def validate_release_record(
    record: Mapping[str, Any],
    *,
    manifest: Mapping[str, Any],
    storage: Any,
    environment: str,
    season: int,
    week: int,
) -> None:
    """Validate exact identities and signed 09/05 lineage before a Neon write."""
    if environment != "production":
        raise V5ReleaseError("exact release authorization is production-only")
    expected = {
        "environment": environment,
        "season": season,
        "week": week,
        "prediction_run_id": manifest.get("run_id"),
        "model_id": manifest.get("model_id"),
        "inference_bundle_sha256": manifest.get("inference_bundle_sha256"),
        "forecast_manifest_uri": manifest.get("v5_live_forecast_manifest_uri"),
        "forecast_manifest_sha256": manifest.get("v5_live_forecast_manifest_sha256"),
        "serving_config_sha256": manifest.get("config_sha"),
        "prediction_artifact_uri": manifest.get("artifact_uri"),
        "prediction_artifact_sha256": manifest.get("artifact_sha256"),
    }
    if (
        not record.get("authorization_id")
        or not str(record.get("decision_ref", "")).strip()
    ):
        raise V5ReleaseError("release decision identity is missing")
    for key, value in expected.items():
        if value is None or record.get(key) != value:
            raise V5ReleaseError(f"release does not match {key}")
    artifact = storage.read_bytes(str(record["prediction_artifact_uri"]))
    if _sha(artifact) != record["prediction_artifact_sha256"]:
        raise V5ReleaseError("prediction artifact checksum changed")
    forecast = _read_bound_json(
        storage,
        str(record["forecast_manifest_uri"]),
        str(record["forecast_manifest_sha256"]),
    )
    verify_signed_payload(forecast, label="release forecast manifest")
    if (
        forecast.get("production_activation_authorized") is not False
        or (forecast.get("identity") or {}).get("season") != season
        or (forecast.get("identity") or {}).get("environment") != "preview"
    ):
        raise V5ReleaseError("release forecast is not the certified Preview identity")
    receipt = _read_bound_json(
        storage,
        str(record["readiness_verifier_uri"]),
        str(record["readiness_verifier_sha256"]),
    )
    verify_signed_payload(receipt, label="release readiness verifier")
    if (
        receipt.get("state") != "verified"
        or receipt.get("verified") is not True
        or receipt.get("kind") != "readiness"
        or receipt.get("readiness_overall") != "ready"
    ):
        raise V5ReleaseError("readiness receipt is not independently verified ready")
    readiness_uri = receipt.get("manifest_uri")
    if not readiness_uri:
        raise V5ReleaseError("readiness receipt lacks its source manifest")
    readiness = json.loads(storage.read_bytes(str(readiness_uri)))
    verify_signed_payload(readiness, label="release readiness manifest")
    parents = readiness.get("parents") or {}
    if (
        readiness.get("readiness_overall") != "ready"
        or parents.get("forecast_manifest_uri") != record["forecast_manifest_uri"]
        or parents.get("forecast_manifest_raw_sha256")
        != record["forecast_manifest_sha256"]
    ):
        raise V5ReleaseError("ready assessment is bound to another forecast")
    ref = (readiness.get("output_refs") or {}).get("readiness") or {}
    if not ref.get("uri"):
        raise V5ReleaseError("readiness result population is missing")
    frame = pd.read_parquet(io.BytesIO(storage.read_bytes(str(ref["uri"]))))
    if (
        frame.empty
        or set(frame["season"].astype(int)) != {season}
        or set(frame["week"].astype(int)) != {week}
    ):
        raise V5ReleaseError("ready assessment targets another slate")


def require_release_record(
    cur: Any,
    *,
    manifest: Mapping[str, Any],
    storage: Any,
    season: int,
    week: int,
) -> None:
    """Read the admin-only record under the publication transaction."""
    # No locking clause: the restricted pipeline role is SELECT-only on the
    # authorization tables, and row locks require write privilege. Records are
    # append-only with no concurrent writer in any approved flow; integrity
    # comes from the exact byte revalidation inside the transaction.
    cur.execute(
        "SELECT " + ", ".join(AUTH_COLUMNS) + " FROM v5_serving_authorizations "
        "WHERE environment = 'production' AND season = %s AND week = %s "
        "AND prediction_run_id = %s",
        (season, week, manifest.get("run_id")),
    )
    row = cur.fetchone()
    if row is None:
        raise V5ReleaseError("exact V5 production release authorization is absent")
    record = dict(zip(AUTH_COLUMNS, row, strict=True))
    validate_release_record(
        record,
        manifest=manifest,
        storage=storage,
        environment="production",
        season=season,
        week=week,
    )


def _replay_manifest(storage: Any, uri: str, expected_sha: str) -> dict[str, Any]:
    """Load one frozen replay manifest and bind its exact bytes."""
    raw = storage.read_bytes(str(uri))
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise V5ReleaseError(f"replay manifest checksum changed: {uri}")
    manifest = json.loads(raw)
    if not isinstance(manifest, dict):
        raise V5ReleaseError("replay manifest is not a JSON object")
    verify_signed_payload(manifest, label="replay release manifest")
    if (
        manifest.get("schema_version") not in REPLAY_MANIFEST_SCHEMAS
        or manifest.get("state") != "frozen"
        or manifest.get("evidence_class") != "replay"
        or manifest.get("production_activation_authorized") is not False
    ):
        raise V5ReleaseError("replay release manifest is not frozen replay evidence")
    return manifest


def _replay_verifier(
    storage: Any,
    uri: str,
    expected_sha: str,
    *,
    replay_manifest_sha256: str,
    replay_records_sha256: str | None,
) -> None:
    """Confirm the independent verifier receipt binds this exact replay run."""
    raw = storage.read_bytes(str(uri))
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise V5ReleaseError(f"replay verifier checksum changed: {uri}")
    receipt = json.loads(raw)
    if not isinstance(receipt, dict):
        raise V5ReleaseError("replay verifier is not a JSON object")
    verify_signed_payload(receipt, label="replay release verifier")
    if (
        receipt.get("schema_version") not in REPLAY_VERIFIER_SCHEMAS
        or receipt.get("state") != "verified"
        or receipt.get("verified", True) is not True
        or receipt.get("production_activation_authorized") is not False
        or receipt.get("replay_manifest_raw_sha256") != replay_manifest_sha256
    ):
        raise V5ReleaseError("replay verifier does not certify this replay run")
    if (
        replay_records_sha256
        and receipt.get("prediction_records_sha256") != replay_records_sha256
    ):
        raise V5ReleaseError("replay verifier binds another prediction record")


def validate_replay_release_record(
    record: Mapping[str, Any],
    *,
    manifest: Mapping[str, Any],
    storage: Any,
    environment: str,
    season: int,
    week: int,
) -> None:
    """Validate exact replay identities and the verifier receipt before a write.

    Replay records never satisfy prospective, readiness, or live gates. A live
    09/05 authorization is a different record in a different table. The
    prediction artifact bytes are always read from the record's own URI, so a
    reviewable candidate must already exist at the bound production location.
    """
    expected = {
        "environment": environment,
        "season": season,
        "week": week,
        "prediction_run_id": manifest.get("run_id"),
        "model_id": manifest.get("model_id"),
        "inference_bundle_sha256": manifest.get("inference_bundle_sha256"),
        "serving_config_sha256": manifest.get("config_sha"),
        "prediction_artifact_uri": manifest.get("artifact_uri"),
        "prediction_artifact_sha256": manifest.get("artifact_sha256"),
        "replay_manifest_uri": manifest.get("v5_replay_manifest_uri"),
        "replay_manifest_sha256": manifest.get("v5_replay_manifest_sha256"),
        "verifier_sha256": manifest.get("replay_verification_sha256"),
    }
    if (
        not record.get("authorization_id")
        or not str(record.get("decision_ref", "")).strip()
    ):
        raise V5ReleaseError("replay decision identity is missing")
    for key, value in expected.items():
        if value is None or record.get(key) != value:
            raise V5ReleaseError(f"replay release does not match {key}")
    artifact = storage.read_bytes(str(record["prediction_artifact_uri"]))
    if hashlib.sha256(artifact).hexdigest() != record["prediction_artifact_sha256"]:
        raise V5ReleaseError("replay prediction artifact checksum changed")
    replay = _replay_manifest(
        storage,
        str(record["replay_manifest_uri"]),
        str(record["replay_manifest_sha256"]),
    )
    _replay_verifier(
        storage,
        str(record["verifier_uri"]),
        str(record["verifier_sha256"]),
        replay_manifest_sha256=str(record["replay_manifest_sha256"]),
        replay_records_sha256=replay.get("prediction_records_sha256"),
    )


def require_replay_release_record(
    cur: Any,
    *,
    manifest: Mapping[str, Any],
    storage: Any,
    environment: str,
    season: int,
    week: int,
) -> None:
    """Read the admin-only replay record under the publication transaction."""
    # No locking clause: see require_release_record. The replay table is
    # append-only with the same SELECT-only pipeline access.
    cur.execute(
        "SELECT "
        + ", ".join(REPLAY_AUTH_COLUMNS)
        + " FROM v5_replay_release_authorizations "
        "WHERE environment = %s AND season = %s AND week = %s "
        "AND prediction_run_id = %s",
        (environment, season, week, manifest.get("run_id")),
    )
    row = cur.fetchone()
    if row is None:
        raise V5ReleaseError("exact V5 replay release authorization is absent")
    record = dict(zip(REPLAY_AUTH_COLUMNS, row, strict=True))
    validate_replay_release_record(
        record,
        manifest=manifest,
        storage=storage,
        environment=environment,
        season=season,
        week=week,
    )
