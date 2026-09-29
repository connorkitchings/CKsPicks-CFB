"""Exact run authorization for the V5 intended-update successor."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload
from cks_picks_cfb.ratings.possession_intended_update import MODEL_ID

AUTH_COLUMNS = (
    "authorization_id",
    "environment",
    "season",
    "week",
    "prediction_run_id",
    "evidence_class",
    "model_id",
    "inference_bundle_sha256",
    "rating_manifest_sha256",
    "forecast_manifest_uri",
    "forecast_manifest_sha256",
    "serving_manifest_uri",
    "serving_manifest_sha256",
    "verifier_uri",
    "verifier_sha256",
    "prediction_artifact_uri",
    "prediction_artifact_sha256",
    "decision_ref",
)


class IntendedUpdateReleaseError(ValueError):
    """The proposed successor run lacks exact reviewed authorization."""


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read_signed(storage: Any, uri: str, digest: str, label: str) -> dict[str, Any]:
    raw = storage.read_bytes(uri)
    if _sha(raw) != digest:
        raise IntendedUpdateReleaseError(f"{label} checksum changed")
    value = json.loads(raw)
    verify_signed_payload(value, label=label)
    return value


def validate_intended_update_release_record(
    record: Mapping[str, Any],
    *,
    manifest: Mapping[str, Any],
    storage: Any,
    season: int,
    week: int,
) -> None:
    """Check every release field and its immutable source chain before a write."""
    expected = {
        "environment": "production",
        "season": season,
        "week": week,
        "prediction_run_id": manifest.get("run_id"),
        "evidence_class": manifest.get("evidence_class"),
        "model_id": MODEL_ID,
        "inference_bundle_sha256": manifest.get("inference_bundle_sha256"),
        "rating_manifest_sha256": manifest.get("v5_rating_replay_manifest_sha256"),
        "forecast_manifest_uri": manifest.get("v5_live_forecast_manifest_uri"),
        "forecast_manifest_sha256": manifest.get("v5_live_forecast_manifest_sha256"),
        "serving_manifest_uri": manifest.get("v5_intended_update_serving_manifest_uri"),
        "serving_manifest_sha256": manifest.get(
            "v5_intended_update_serving_manifest_sha256"
        ),
        "verifier_uri": manifest.get("v5_intended_update_verifier_uri"),
        "verifier_sha256": manifest.get("v5_intended_update_verifier_sha256"),
        "prediction_artifact_uri": manifest.get("artifact_uri"),
        "prediction_artifact_sha256": manifest.get("artifact_sha256"),
    }
    if (
        not record.get("authorization_id")
        or not str(record.get("decision_ref") or "").strip()
    ):
        raise IntendedUpdateReleaseError("release decision is absent")
    for field, value in expected.items():
        if value is None or record.get(field) != value:
            raise IntendedUpdateReleaseError(f"release does not match {field}")
    if manifest.get("production_activation_authorized") is not False:
        raise IntendedUpdateReleaseError(
            "prediction run source must not self-authorize"
        )
    if record["evidence_class"] not in {"replay", "pending"}:
        raise IntendedUpdateReleaseError("successor release has unsupported timing")
    serving = _read_signed(
        storage,
        str(record["serving_manifest_uri"]),
        str(record["serving_manifest_sha256"]),
        "successor serving manifest",
    )
    if (
        serving.get("schema_version") != "v5_intended_update_2026_serving_manifest_v1"
        or serving.get("state") != "candidate"
        or serving.get("evidence_class") != record["evidence_class"]
        or serving.get("identity", {}).get("run_id") != record["prediction_run_id"]
        or serving.get("identity", {}).get("week") != week
        or serving.get("production_activation_authorized") is not False
    ):
        raise IntendedUpdateReleaseError("serving source differs from released run")
    forecast = _read_signed(
        storage,
        str(record["forecast_manifest_uri"]),
        str(record["forecast_manifest_sha256"]),
        "successor forecast manifest",
    )
    if (
        serving.get("parents", {}).get("forecast_manifest_raw_sha256")
        != record["forecast_manifest_sha256"]
        or forecast.get("schema_version")
        != "v5_intended_update_2026_forecast_manifest_v1"
        or forecast.get("identity", {}).get("run_id") != record["prediction_run_id"]
        or forecast.get("identity", {}).get("week") != week
        or forecast.get("model_id") != MODEL_ID
        or forecast.get("parents", {}).get("rating_manifest_raw_sha256")
        != record["rating_manifest_sha256"]
        or forecast.get("parents", {}).get("inference_bundle_sha256")
        != record["inference_bundle_sha256"]
        or forecast.get("production_activation_authorized") is not False
    ):
        raise IntendedUpdateReleaseError("forecast source differs from released model")
    expected_forecast_state = (
        "frozen" if record["evidence_class"] == "replay" else "candidate"
    )
    if forecast.get("state") != expected_forecast_state:
        raise IntendedUpdateReleaseError("forecast timing state differs")
    receipt = _read_signed(
        storage,
        str(record["verifier_uri"]),
        str(record["verifier_sha256"]),
        "successor serving verifier",
    )
    if (
        receipt.get("schema_version")
        != "v5_intended_update_2026_serving_verification_v1"
        or receipt.get("state") != "verified"
        or receipt.get("serving_manifest_raw_sha256")
        != record["serving_manifest_sha256"]
    ):
        raise IntendedUpdateReleaseError("serving verification is absent or mismatched")
    prediction_raw = storage.read_bytes(str(record["prediction_artifact_uri"]))
    if (
        _sha(prediction_raw) != record["prediction_artifact_sha256"]
        or serving.get("prediction_ref", {}).get("raw_sha256")
        != record["prediction_artifact_sha256"]
    ):
        raise IntendedUpdateReleaseError("selected prediction artifact differs")


def require_intended_update_release_record(
    cur: Any,
    *,
    manifest: Mapping[str, Any],
    storage: Any,
    season: int,
    week: int,
) -> None:
    cur.execute(
        "SELECT "
        + ", ".join(AUTH_COLUMNS)
        + " FROM v5_intended_update_release_authorizations "
        "WHERE environment = 'production' AND season = %s AND week = %s "
        "AND prediction_run_id = %s",
        (season, week, manifest.get("run_id")),
    )
    row = cur.fetchone()
    if row is None:
        raise IntendedUpdateReleaseError(
            "exact successor release authorization is absent"
        )
    record = dict(zip(AUTH_COLUMNS, row, strict=True))
    validate_intended_update_release_record(
        record, manifest=manifest, storage=storage, season=season, week=week
    )
