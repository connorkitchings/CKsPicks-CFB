"""Contract 11A conditional verification publication boundary.

The computational work stays in the independent forecast verifier.  This
module binds its exact result to the four frozen historical artifacts and
publishes only ``conditional_historical_results_only`` Preview evidence.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from cks_picks_cfb.data.data_first_phase2d import (
    canonical_bytes,
    sha256,
    signed_payload,
    verify_signed_payload,
)
from cks_picks_cfb.forecast.forecast_verification import (
    VerificationError,
    verify_forecast_artifact,
)

CONDITIONAL_VERIFICATION_SCHEMA = "data_first_conditional_forecast_verification_v1"
CONDITIONAL_MANIFEST_SCHEMA = "data_first_conditional_forecast_verification_manifest_v1"
CONDITIONAL_IDENTITY_SCHEMA = "data_first_conditional_forecast_verification_identity_v1"
PERMITTED_USE = "conditional_historical_results_only"
OUTPUT_ROOT = (
    "artifacts/research/data-first-football-v1/forecast-verification/"
    "conditional-v1/runs"
)
REPAIR_MANIFEST_URI = (
    "artifacts/research/data-first-football-v1/repair/v2/runs/"
    "repair-v2-20260909T1417Z/repair-manifest.json"
)
MEASUREMENT_MANIFEST_URI = (
    "artifacts/research/data-first-football-v1/possession-v1/measurements/runs/"
    "possession-v1-measurements-20260915-18fb0aa-r6/measurement-manifest.json"
)
RATING_MANIFEST_URI = (
    "artifacts/research/data-first-football-v1/possession-v1/ratings/runs/"
    "possession-v1-ratings-20260917-d029526-cert/retained-rating-manifest.json"
)
FORECAST_MANIFEST_URI = (
    "artifacts/research/data-first-football-v1/forecasts/runs/"
    "forecast-v1-20260917-4600ddd-04b/forecast-manifest.json"
)
FORECAST_CODE_SHA = "4600dddd3e97373880d29a549f4447367940cf37"

FROZEN_IDENTITIES = {
    "repair": "repair-v2-20260909T1417Z",
    "measurement": "possession-v1-measurements-20260915-18fb0aa-r6",
    "rating": "possession-v1-ratings-20260917-d029526-cert",
    "forecast": "forecast-v1-20260917-4600ddd-04b",
}
FROZEN_RAW_SHA256 = {
    "repair": "b55af0dd7952a4b5e0d663b82182b351ec5496a292246a934a857c354058e0b4",
    "measurement": "449cdebc762495b0f3a392ca1b90b980a1ec589b8be59c97845eab03dde7c815",
    "rating": "7568c9101e6110c98c8522293ef4fd8b21a1c02b3ccba4a6722de6b5d4e27d56",
    "forecast": "e28b278bd702cf8626967da38a8fa41e9b774198cb7192df1675237b548d8f0c",
}
FORECAST_CANONICAL_SHA256 = (
    "09dc06054777b6f6a0ad69bc7ebfc6cde35f3a82f9cca4650eceb8eb96d64956"
)
FROZEN_OUTPUT_HASHES = {
    "forecast_calibration": "355be409264392bec8e035bb2e6d09be7d42bc97c9a49cee5c17ad24391a0c1c",
    "forecast_model": "35d94a587e0be5f20833021c434112154b54f6c5b1cb7870fa747654e5839d19",
    "forecast_prediction": "939200a9e9d1f6cceab29cc020d9f61f6372a6920e104a459f646e3d676c00e8",
    "forecast_registry": "62412c16972624657a3c62a5e9fb38ed800ed3e0b574cbf2f27a0b4e64b8391f",
    "forecast_selection": "65b3cbcc4ed59a33e86d9a9af59ab0478175eb2686c74160aeae5cb5442ad172",
    "window_comparison": "db3f2949412da42d68ce0b1c3cfd8680415b9c8492310008d8d2de9a662e5dea",
}

OPEN_LIMITATIONS = (
    {
        "finding_id": "audit-structural-001",
        "summary": "Repair v2 verification imports producer computation",
        "disposition": "prohibited_until_closed",
        "closure_state": "open",
    },
    {
        "finding_id": "audit-structural-002",
        "summary": "Original forecast verification did not reconstruct stored outputs",
        "disposition": "historical_evidence_only",
        "closure_state": "open",
    },
    {
        "finding_id": "audit-ledger-score_reconciliation-1de3aaaf7d",
        "summary": "81 score-ledger excess team-game keys",
        "disposition": "prohibited_until_closed",
        "closure_state": "open",
    },
    {
        "finding_id": "audit-forecast-final_fit_existence-b1bc852294",
        "summary": "No through-2025 final forecast fit exists",
        "disposition": "historical_evidence_only",
        "closure_state": "open",
    },
)


class ConditionalVerificationError(ValueError):
    """Raised when Contract 11A evidence cannot be created or trusted."""


def conditional_identity(*, run_id: str, as_of: str, code_sha: str) -> dict[str, Any]:
    if not run_id or not as_of or len(code_sha) != 40:
        raise ConditionalVerificationError("conditional identity is incomplete")
    payload = {
        "schema_version": CONDITIONAL_IDENTITY_SCHEMA,
        "run_id": run_id,
        "environment": "preview",
        "as_of": as_of,
        "code_sha": code_sha,
        "forecast_manifest_uri": FORECAST_MANIFEST_URI,
        "development_seasons": [
            2015,
            2016,
            2017,
            2018,
            2019,
            2021,
            2022,
            2023,
            2024,
            2025,
        ],
        "rejected_seasons": [2020, 2026],
        "permitted_use": PERMITTED_USE,
    }
    payload["identity_sha256"] = sha256(payload)
    return payload


def _artifact_block(result: Mapping[str, Any]) -> dict[str, Any]:
    parent_hashes = result.get("parent_raw_sha256") or {}
    return {
        "repair": {
            "identity": FROZEN_IDENTITIES["repair"],
            "manifest_uri": REPAIR_MANIFEST_URI,
            "manifest_raw_sha256": parent_hashes.get("repair"),
        },
        "measurement": {
            "identity": FROZEN_IDENTITIES["measurement"],
            "manifest_uri": MEASUREMENT_MANIFEST_URI,
            "manifest_raw_sha256": parent_hashes.get("measurement"),
        },
        "rating": {
            "identity": FROZEN_IDENTITIES["rating"],
            "manifest_uri": RATING_MANIFEST_URI,
            "manifest_raw_sha256": parent_hashes.get("rating"),
        },
        "forecast": {
            "identity": FROZEN_IDENTITIES["forecast"],
            "manifest_uri": FORECAST_MANIFEST_URI,
            "manifest_raw_sha256": result.get("manifest_raw_sha256"),
            "manifest_canonical_sha256": result.get("manifest_canonical_sha256"),
        },
    }


def _frozen_artifact_block() -> dict[str, Any]:
    return {
        "repair": {
            "identity": FROZEN_IDENTITIES["repair"],
            "manifest_uri": REPAIR_MANIFEST_URI,
            "manifest_raw_sha256": FROZEN_RAW_SHA256["repair"],
        },
        "measurement": {
            "identity": FROZEN_IDENTITIES["measurement"],
            "manifest_uri": MEASUREMENT_MANIFEST_URI,
            "manifest_raw_sha256": FROZEN_RAW_SHA256["measurement"],
        },
        "rating": {
            "identity": FROZEN_IDENTITIES["rating"],
            "manifest_uri": RATING_MANIFEST_URI,
            "manifest_raw_sha256": FROZEN_RAW_SHA256["rating"],
        },
        "forecast": {
            "identity": FROZEN_IDENTITIES["forecast"],
            "manifest_uri": FORECAST_MANIFEST_URI,
            "manifest_raw_sha256": FROZEN_RAW_SHA256["forecast"],
            "manifest_canonical_sha256": FORECAST_CANONICAL_SHA256,
        },
    }


def run_conditional_verification(
    storage: Any,
    *,
    identity: Mapping[str, Any],
    progress: Any = None,
) -> dict[str, Any]:
    """Run a no-write 11A reconstruction and return deterministic evidence."""
    if identity.get("permitted_use") != PERMITTED_USE:
        raise ConditionalVerificationError("conditional identity use boundary changed")
    result = verify_forecast_artifact(
        storage,
        manifest_uri=FORECAST_MANIFEST_URI,
        expected_code_sha=FORECAST_CODE_SHA,
        environment="preview",
        rating_manifest_uri=RATING_MANIFEST_URI,
        measurement_manifest_uri=MEASUREMENT_MANIFEST_URI,
        repair_manifest_uri=REPAIR_MANIFEST_URI,
        progress=progress,
    )
    if result.get("run_id") != FROZEN_IDENTITIES["forecast"]:
        raise ConditionalVerificationError("frozen forecast identity changed")
    if _artifact_block(result) != _frozen_artifact_block():
        raise ConditionalVerificationError("frozen artifact hashes changed")
    output_hashes = {
        name: value["records_sha"]
        for name, value in sorted((result.get("comparisons") or {}).items())
    }
    if output_hashes != FROZEN_OUTPUT_HASHES:
        raise ConditionalVerificationError("frozen forecast output hashes changed")
    evidence = {
        "state": "dry_run",
        "identity": dict(identity),
        "verification": result,
        "verification_sha256": sha256(result),
        "frozen_artifacts": _frozen_artifact_block(),
        "output_hashes": dict(FROZEN_OUTPUT_HASHES),
        "open_limitations": [dict(value) for value in OPEN_LIMITATIONS],
        "permitted_use": PERMITTED_USE,
        "prospective_evidence": False,
        "forecast_eligibility_restored": False,
        "production_activation_authorized": False,
    }
    evidence["evidence_sha256"] = sha256(evidence)
    return evidence


def _write_immutable(storage: Any, uri: str, payload: Mapping[str, Any]) -> None:
    encoded = canonical_bytes(payload)
    if storage.exists(uri):
        if storage.read_bytes(uri) != encoded:
            raise ConditionalVerificationError(f"immutable collision at {uri}")
        return
    storage.write_bytes(encoded, uri)


def _existing_manifest(
    storage: Any, *, manifest_uri: str, identity: Mapping[str, Any]
) -> dict[str, Any] | None:
    if not storage.exists(manifest_uri):
        return None
    try:
        manifest = json.loads(storage.read_bytes(manifest_uri))
        verify_signed_payload(manifest, label="conditional verification manifest")
    except (json.JSONDecodeError, ValueError) as exc:
        raise ConditionalVerificationError(
            "existing conditional verification manifest is invalid"
        ) from exc
    if (
        manifest.get("schema_version") != CONDITIONAL_MANIFEST_SCHEMA
        or manifest.get("identity") != dict(identity)
        or manifest.get("permitted_use") != PERMITTED_USE
        or manifest.get("production_activation_authorized") is not False
    ):
        raise ConditionalVerificationError(
            "conditional run ID is bound to different evidence"
        )
    return manifest


def publish_conditional_verification(
    storage: Any,
    *,
    identity: Mapping[str, Any],
    reviewed_evidence: Mapping[str, Any],
    progress: Any = None,
) -> dict[str, Any]:
    """Re-run 11A and publish a signed record plus terminal manifest last."""
    prefix = f"{OUTPUT_ROOT}/{identity['run_id']}"
    record_uri = f"{prefix}/verification-record.json"
    manifest_uri = f"{prefix}/verification-manifest.json"
    existing = _existing_manifest(storage, manifest_uri=manifest_uri, identity=identity)
    if existing is not None:
        verified = verify_conditional_publication(storage, manifest_uri=manifest_uri)
        return {"state": "already_applied", **verified}
    if storage.list_files(prefix):
        raise ConditionalVerificationError(
            "conditional verification prefix contains a partial artifact"
        )
    if (
        reviewed_evidence.get("state") != "dry_run"
        or reviewed_evidence.get("identity") != dict(identity)
        or reviewed_evidence.get("permitted_use") != PERMITTED_USE
    ):
        raise ConditionalVerificationError("reviewed evidence identity mismatch")
    rerun = run_conditional_verification(storage, identity=identity, progress=progress)
    if rerun != dict(reviewed_evidence):
        raise ConditionalVerificationError(
            "apply reconstruction differs from reviewed evidence"
        )
    record = signed_payload(
        {
            "schema_version": CONDITIONAL_VERIFICATION_SCHEMA,
            "state": "verified",
            **{
                key: value
                for key, value in rerun.items()
                if key not in {"state", "evidence_sha256"}
            },
            "reviewed_evidence_sha256": rerun["evidence_sha256"],
        }
    )
    _write_immutable(storage, record_uri, record)
    record_raw = storage.read_bytes(record_uri)
    manifest = signed_payload(
        {
            "schema_version": CONDITIONAL_MANIFEST_SCHEMA,
            "state": "verified",
            "identity": dict(identity),
            "record_uri": record_uri,
            "record_raw_sha256": hashlib.sha256(record_raw).hexdigest(),
            "record_manifest_sha256": record["manifest_sha256"],
            "frozen_artifacts": rerun["frozen_artifacts"],
            "output_hashes": rerun["output_hashes"],
            "open_limitations": rerun["open_limitations"],
            "permitted_use": PERMITTED_USE,
            "prospective_evidence": False,
            "forecast_eligibility_restored": False,
            "production_activation_authorized": False,
        }
    )
    _write_immutable(storage, manifest_uri, manifest)
    verified = verify_conditional_publication(storage, manifest_uri=manifest_uri)
    return {"state": "applied", **verified}


def verify_conditional_publication(
    storage: Any, *, manifest_uri: str
) -> dict[str, Any]:
    """Independently re-read the signed 11A record and terminal manifest."""
    try:
        manifest_raw = storage.read_bytes(manifest_uri)
        manifest = json.loads(manifest_raw)
        verify_signed_payload(manifest, label="conditional verification manifest")
        record_uri = str(manifest["record_uri"])
        record_raw = storage.read_bytes(record_uri)
        record = json.loads(record_raw)
        verify_signed_payload(record, label="conditional verification record")
    except (KeyError, json.JSONDecodeError, ValueError) as exc:
        raise ConditionalVerificationError(
            "conditional verification publication is unreadable"
        ) from exc
    if (
        manifest.get("schema_version") != CONDITIONAL_MANIFEST_SCHEMA
        or manifest.get("state") != "verified"
        or record.get("schema_version") != CONDITIONAL_VERIFICATION_SCHEMA
        or record.get("state") != "verified"
        or manifest.get("identity") != record.get("identity")
        or manifest.get("record_raw_sha256") != hashlib.sha256(record_raw).hexdigest()
        or manifest.get("record_manifest_sha256") != record.get("manifest_sha256")
        or manifest.get("frozen_artifacts") != record.get("frozen_artifacts")
        or manifest.get("output_hashes") != record.get("output_hashes")
        or manifest.get("open_limitations") != record.get("open_limitations")
        or manifest.get("permitted_use") != PERMITTED_USE
        or record.get("permitted_use") != PERMITTED_USE
        or manifest.get("production_activation_authorized") is not False
        or record.get("production_activation_authorized") is not False
        or manifest.get("forecast_eligibility_restored") is not False
        or record.get("forecast_eligibility_restored") is not False
        or manifest.get("prospective_evidence") is not False
        or record.get("prospective_evidence") is not False
    ):
        raise ConditionalVerificationError(
            "conditional verification publication does not reconcile"
        )
    return {
        "verified": True,
        "manifest_uri": manifest_uri,
        "manifest_raw_sha256": hashlib.sha256(manifest_raw).hexdigest(),
        "manifest_sha256": manifest["manifest_sha256"],
        "record_uri": record_uri,
        "record_raw_sha256": manifest["record_raw_sha256"],
        "permitted_use": PERMITTED_USE,
        "production_activation_authorized": False,
    }


def failure_record(
    *, identity: Mapping[str, Any], error: VerificationError
) -> dict[str, Any]:
    """Create bounded failure evidence without claiming conditional permission."""
    return signed_payload(
        {
            "schema_version": CONDITIONAL_VERIFICATION_SCHEMA,
            "state": "failed",
            "identity": dict(identity),
            "failure_type": type(error).__name__,
            "failure_message": str(error),
            "frozen_artifacts": _frozen_artifact_block(),
            "output_hashes": dict(FROZEN_OUTPUT_HASHES),
            "open_limitations": [dict(value) for value in OPEN_LIMITATIONS],
            "permitted_use": None,
            "scorecard_authorized": False,
            "production_activation_authorized": False,
        }
    )


def publish_failure(
    storage: Any,
    *,
    identity: Mapping[str, Any],
    error: VerificationError,
) -> dict[str, Any]:
    """Publish terminal failure evidence; it grants no downstream use."""
    prefix = f"{OUTPUT_ROOT}/{identity['run_id']}"
    record_uri = f"{prefix}/verification-failure.json"
    manifest_uri = f"{prefix}/verification-manifest.json"
    if storage.list_files(prefix):
        raise ConditionalVerificationError(
            "conditional verification prefix contains a partial artifact"
        )
    record = failure_record(identity=identity, error=error)
    _write_immutable(storage, record_uri, record)
    record_raw = storage.read_bytes(record_uri)
    manifest = signed_payload(
        {
            "schema_version": CONDITIONAL_MANIFEST_SCHEMA,
            "state": "failed",
            "identity": dict(identity),
            "record_uri": record_uri,
            "record_raw_sha256": hashlib.sha256(record_raw).hexdigest(),
            "record_manifest_sha256": record["manifest_sha256"],
            "frozen_artifacts": _frozen_artifact_block(),
            "output_hashes": dict(FROZEN_OUTPUT_HASHES),
            "open_limitations": [dict(value) for value in OPEN_LIMITATIONS],
            "permitted_use": None,
            "scorecard_authorized": False,
            "production_activation_authorized": False,
        }
    )
    _write_immutable(storage, manifest_uri, manifest)
    return {
        "state": "failed",
        "manifest_uri": manifest_uri,
        "record_uri": record_uri,
        "permitted_use": None,
        "production_activation_authorized": False,
    }
