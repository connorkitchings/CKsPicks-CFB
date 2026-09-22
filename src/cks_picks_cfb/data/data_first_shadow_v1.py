"""Fail-closed contracts for Preview-only V5 shadow operations.

Covers readiness validation, frozen replay, shadow freezes, outcome-versioned
scoring, the evidence ledger, and diagnostic rehearsal for the certified V5
forecast candidate. All six record schemas are registered here so Phases
05B/05C build on stable interfaces.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from cks_picks_cfb.data.data_first_forecast_v1 import (
    FORECAST_DATASETS,
    FORECAST_MANIFEST_SCHEMA,
    REQUIRED_RATING_CANDIDATE,
    verify_rating_parent,
)
from cks_picks_cfb.data.data_first_live_forecast_v1 import (
    LIVE_FORECAST_MANIFEST_SCHEMA,
    LiveForecastContractError,
    verify_application_parents,
)
from cks_picks_cfb.data.data_first_phase2d import (
    sha256,
    signed_payload,
    verify_signed_payload,
)
from cks_picks_cfb.data.data_first_phase3_v2 import verify_repair_manifest

SHADOW_CONFIG_SCHEMA = "data_first_shadow_config_v1"
LIVE_SHADOW_CONFIG_SCHEMA = "data_first_shadow_live_config_v1"
SHADOW_IDENTITY_SCHEMA = "data_first_shadow_identity_v1"
SHADOW_MANIFEST_SCHEMA = "data_first_shadow_manifest_v1"
SHADOW_MANIFEST_NAME = "shadow-manifest.json"
SHADOW_OUTPUT_ROOT = (
    "artifacts/research/data-first-football-v1/possession-v1/shadow/runs"
)
REQUIRED_FORECAST_RUN_ID = "forecast-v1-20260917-4600ddd-04b"
REQUIRED_FORECAST_MANIFEST_URI = (
    "artifacts/research/data-first-football-v1/forecasts/runs/"
    "forecast-v1-20260917-4600ddd-04b/forecast-manifest.json"
)
REQUIRED_FORECAST_HORIZON = "expanding"
REQUIRED_RATING_MANIFEST_URI = (
    "artifacts/research/data-first-football-v1/possession-v1/ratings/runs/"
    "possession-v1-ratings-20260917-d029526-cert/retained-rating-manifest.json"
)
REQUIRED_MEASUREMENT_MANIFEST_URI = (
    "artifacts/research/data-first-football-v1/possession-v1/measurements/runs/"
    "possession-v1-measurements-20260915-18fb0aa-r6/measurement-manifest.json"
)
REQUIRED_REPAIR_MANIFEST_URI = (
    "artifacts/research/data-first-football-v1/repair/v2/runs/"
    "repair-v2-20260909T1417Z/repair-manifest.json"
)
FREEZE_TARGET_LEAD_SECONDS = 7200
FREEZE_HARD_LEAD_SECONDS = 3600
SCORE_STABILIZATION_SECONDS = 86400
MINIMUM_PAIRED_GAMES = 40
DIAGNOSTIC_CLASS = "diagnostic_only"
IDENTITY_PARENT_KEYS = (
    "forecast_manifest_uri",
    "forecast_raw_sha256",
    "rating_manifest_uri",
    "rating_raw_sha256",
    "measurement_manifest_uri",
    "measurement_raw_sha256",
    "repair_manifest_uri",
    "repair_raw_sha256",
)

SHADOW_DATASETS = {
    "readiness": ("shadow_readiness", "data_first_possession_shadow_readiness_v1"),
    "shadow_freeze": (
        "shadow_freeze",
        "data_first_possession_shadow_freeze_v1",
    ),
    "shadow_prediction": (
        "shadow_prediction",
        "data_first_possession_shadow_prediction_v1",
    ),
    "shadow_evaluation": (
        "shadow_evaluation",
        "data_first_possession_shadow_evaluation_v1",
    ),
    "evidence_counter": (
        "shadow_evidence_counter",
        "data_first_possession_evidence_counter_v1",
    ),
    "shadow_rehearsal": (
        "shadow_rehearsal",
        "data_first_possession_shadow_rehearsal_v1",
    ),
}

READINESS_COLUMNS = (
    "candidate",
    "season",
    "week",
    "run_id",
    "source",
    "status",
    "timing_class",
    "fallback",
    "blocked_reason",
    "overall",
)
SHADOW_FREEZE_COLUMNS = (
    "candidate",
    "season",
    "week",
    "run_id",
    "freeze_time",
    "first_kickoff",
    "lead_seconds",
    "v4_ref_uri",
    "slate_digest",
    "paired_count",
    "broader_count",
    "excluded_count",
    "identity_sha256",
)
SHADOW_PREDICTION_COLUMNS = (
    "candidate",
    "season",
    "week",
    "run_id",
    "game_id",
    "target",
    "mean",
    "variance",
    "interval_lower_95",
    "interval_upper_95",
    "offset",
    "model_ref",
    "state_ref",
)
SHADOW_EVALUATION_COLUMNS = (
    "candidate",
    "season",
    "week",
    "run_id",
    "outcome_version",
    "game_id",
    "target",
    "actual",
    "error",
    "crps",
    "coverage_95",
)
EVIDENCE_COUNTER_COLUMNS = (
    "candidate",
    "season",
    "week",
    "qualifying",
    "reason",
    "freeze_ref",
    "evaluation_ref",
)
SHADOW_REHEARSAL_COLUMNS = (
    "candidate",
    "run_id",
    "season_range",
    "diagnostic_only",
    "cases_passed",
    "cases_failed",
    "verifier_ref",
)


class ShadowContractError(ValueError):
    """Raised when a shadow input leaves the sealed V5-05 boundary."""


def validate_shadow_config(payload: Mapping[str, Any]) -> None:
    schema_version = payload.get("schema_version")
    if schema_version not in (SHADOW_CONFIG_SCHEMA, LIVE_SHADOW_CONFIG_SCHEMA):
        raise ShadowContractError("unexpected shadow config schema")
    if payload.get("environment") != "preview":
        raise ShadowContractError("shadow config must target preview")
    if schema_version == SHADOW_CONFIG_SCHEMA:
        if payload.get("candidate_manifest_uri") != REQUIRED_FORECAST_MANIFEST_URI:
            raise ShadowContractError(
                "shadow config must pin the certified 04 candidate"
            )
    elif payload.get("candidate_manifest_source") != "explicit_cli_parent":
        raise ShadowContractError(
            "live shadow config must use the explicit CLI candidate parent"
        )
    if payload.get("rating_candidate") != REQUIRED_RATING_CANDIDATE:
        raise ShadowContractError(
            "shadow config must pin the retained rating candidate"
        )
    if payload.get("freeze_target_lead_seconds") != FREEZE_TARGET_LEAD_SECONDS:
        raise ShadowContractError("shadow freeze target lead drifted")
    if payload.get("freeze_hard_lead_seconds") != FREEZE_HARD_LEAD_SECONDS:
        raise ShadowContractError("shadow freeze hard lead drifted")
    if payload.get("score_stabilization_seconds") != SCORE_STABILIZATION_SECONDS:
        raise ShadowContractError("shadow scoring stabilization window drifted")
    if payload.get("minimum_paired_games") != MINIMUM_PAIRED_GAMES:
        raise ShadowContractError("shadow paired-game gate drifted")
    if payload.get("diagnostic_class") != DIAGNOSTIC_CLASS:
        raise ShadowContractError("shadow diagnostic class drifted")
    if payload.get("production_activation_authorized") is not False:
        raise ShadowContractError("shadow config may not authorize production")


def verify_candidate_parents(
    forecast: Mapping[str, Any],
    rating: Mapping[str, Any],
    measurement: Mapping[str, Any],
    repair: Mapping[str, Any],
    *,
    forecast_manifest_uri: str,
    forecast_raw_sha256: str,
    rating_manifest_uri: str,
    rating_raw_sha256: str,
    measurement_manifest_uri: str,
    measurement_raw_sha256: str,
    repair_manifest_uri: str,
    repair_raw_sha256: str,
    bridge: Mapping[str, Any] | None = None,
    bridge_raw_sha256: str = "",
) -> dict[str, Any]:
    """Validate the exact certified 04 candidate and its full parent chain."""
    if forecast.get("schema_version") == LIVE_FORECAST_MANIFEST_SCHEMA:
        return verify_live_candidate_parents(
            forecast,
            rating,
            measurement,
            repair,
            bridge=bridge,
            bridge_raw_sha256=bridge_raw_sha256,
            forecast_manifest_uri=forecast_manifest_uri,
            forecast_raw_sha256=forecast_raw_sha256,
            rating_manifest_uri=rating_manifest_uri,
            rating_raw_sha256=rating_raw_sha256,
            measurement_manifest_uri=measurement_manifest_uri,
            measurement_raw_sha256=measurement_raw_sha256,
            repair_manifest_uri=repair_manifest_uri,
            repair_raw_sha256=repair_raw_sha256,
        )
    try:
        verify_signed_payload(forecast, label="certified forecast manifest")
    except ValueError as exc:
        raise ShadowContractError(str(exc)) from exc
    identity = forecast.get("identity") or {}
    if (
        forecast.get("schema_version") != FORECAST_MANIFEST_SCHEMA
        or forecast.get("state") != "frozen"
        or identity.get("environment") != "preview"
        or identity.get("run_id") != REQUIRED_FORECAST_RUN_ID
        or forecast.get("selected_horizon") != REQUIRED_FORECAST_HORIZON
        or forecast.get("production_activation_authorized") is not False
    ):
        raise ShadowContractError("shadow requires the exact certified 04 candidate")
    if forecast_manifest_uri != REQUIRED_FORECAST_MANIFEST_URI:
        raise ShadowContractError(
            "forecast manifest URI is not the certified 04 candidate"
        )
    if not forecast_raw_sha256:
        raise ShadowContractError("forecast manifest checksum is missing")
    forecast_parents = forecast.get("parents") or {}
    if forecast_parents.get("rating_manifest_uri") != rating_manifest_uri:
        raise ShadowContractError(
            "rating manifest URI differs from the candidate's pinned parent"
        )
    if forecast_parents.get("measurement_manifest_uri") != measurement_manifest_uri:
        raise ShadowContractError(
            "measurement manifest URI differs from the candidate's pinned parent"
        )
    if forecast_parents.get("repair_manifest_uri") != repair_manifest_uri:
        raise ShadowContractError(
            "repair manifest URI differs from the candidate's pinned parent"
        )
    try:
        chain = verify_rating_parent(
            rating,
            rating_manifest_uri=rating_manifest_uri,
            rating_raw_sha256=rating_raw_sha256,
            measurement=measurement,
            measurement_manifest_uri=measurement_manifest_uri,
            measurement_raw_sha256=measurement_raw_sha256,
            repair=repair,
            repair_manifest_uri=repair_manifest_uri,
            repair_raw_sha256=repair_raw_sha256,
        )
    except ValueError as exc:
        raise ShadowContractError(str(exc)) from exc
    if set(forecast.get("output_refs") or {}) != set(FORECAST_DATASETS) - {
        "candidate_manifest"
    }:
        raise ShadowContractError("certified candidate output roles changed")
    return {
        "forecast": dict(forecast),
        "rating": chain["rating"],
        "measurement": chain["measurement"],
        "repair": chain["repair"],
        "forecast_manifest_uri": forecast_manifest_uri,
        "forecast_raw_sha256": forecast_raw_sha256,
        "rating_manifest_uri": rating_manifest_uri,
        "rating_raw_sha256": rating_raw_sha256,
        "measurement_manifest_uri": measurement_manifest_uri,
        "measurement_raw_sha256": measurement_raw_sha256,
        "repair_manifest_uri": repair_manifest_uri,
        "repair_raw_sha256": repair_raw_sha256,
    }


def verify_live_candidate_parents(
    forecast: Mapping[str, Any],
    rating: Mapping[str, Any],
    measurement: Mapping[str, Any],
    repair: Mapping[str, Any],
    *,
    bridge: Mapping[str, Any] | None,
    bridge_raw_sha256: str,
    forecast_manifest_uri: str,
    forecast_raw_sha256: str,
    rating_manifest_uri: str,
    rating_raw_sha256: str,
    measurement_manifest_uri: str,
    measurement_raw_sha256: str,
    repair_manifest_uri: str,
    repair_raw_sha256: str,
) -> dict[str, Any]:
    """Validate the versioned live forecast and exact 07/08/11C parent chain."""
    from cks_picks_cfb.data.data_first_live_forecast_v1 import (
        LIVE_FORECAST_DATASET,
        LIVE_FORECAST_MANIFEST_SCHEMA,
    )

    if bridge is None:
        raise ShadowContractError("live forecast bridge manifest is required")
    try:
        verify_signed_payload(forecast, label="live forecast manifest")
    except ValueError as exc:
        raise ShadowContractError(str(exc)) from exc
    if (
        forecast.get("schema_version") != LIVE_FORECAST_MANIFEST_SCHEMA
        or forecast.get("state") != "frozen"
        or (forecast.get("identity") or {}).get("environment") != "preview"
        or (forecast.get("identity") or {}).get("season") != 2026
        or forecast.get("production_activation_authorized") is not False
        or not forecast_raw_sha256
    ):
        raise ShadowContractError("live forecast manifest is not eligible")
    parents = forecast.get("parents") or {}
    expected = {
        "measurement_uri": measurement_manifest_uri,
        "measurement_raw_sha256": measurement_raw_sha256,
        "rating_replay_uri": rating_manifest_uri,
        "rating_replay_raw_sha256": rating_raw_sha256,
        "bridge_uri": parents.get("bridge_uri"),
        "bridge_raw_sha256": bridge_raw_sha256,
    }
    if any(parents.get(key) != value for key, value in expected.items()):
        raise ShadowContractError(
            "live forecast parent envelope differs from supplied manifests"
        )
    if parents.get("bridge_uri") != (
        "artifacts/research/data-first-football-v1/forecasts/runs/"
        "forecast-v1-20260921-5afd577-11c/forecast-manifest.json"
    ):
        raise ShadowContractError("live forecast does not use the certified 11C bridge")
    if not parents.get("schedule_ref_uri") or not parents.get("schedule_raw_sha256"):
        raise ShadowContractError(
            "live forecast does not bind its full schedule source"
        )
    measured_repair_uri = measurement.get("repair_manifest_uri")
    measured_repair_sha = measurement.get("repair_manifest_raw_sha256")
    if (
        measured_repair_uri != repair_manifest_uri
        or measured_repair_sha != repair_raw_sha256
    ):
        raise ShadowContractError(
            "measurement parent does not bind the supplied Repair parent"
        )
    try:
        verify_repair_manifest(repair)
    except ValueError as exc:
        raise ShadowContractError(str(exc)) from exc
    try:
        chain = verify_application_parents(
            measurement=measurement,
            measurement_uri=measurement_manifest_uri,
            measurement_raw_sha256=measurement_raw_sha256,
            rating_replay=rating,
            rating_replay_uri=rating_manifest_uri,
            rating_replay_raw_sha256=rating_raw_sha256,
            bridge=bridge,
            bridge_uri=str(parents.get("bridge_uri") or ""),
            bridge_raw_sha256=bridge_raw_sha256,
        )
    except (LiveForecastContractError, ValueError) as exc:
        raise ShadowContractError(str(exc)) from exc
    output_ref = forecast.get("output_ref") or {}
    if (
        output_ref.get("dataset") != LIVE_FORECAST_DATASET[0]
        or output_ref.get("schema_version") != LIVE_FORECAST_DATASET[1]
        or int(output_ref.get("row_count", 0)) != int(forecast.get("row_count", -1))
        or not output_ref.get("uri")
        or int(forecast.get("row_count", 0)) <= 0
    ):
        raise ShadowContractError("live forecast output reference is malformed")
    return {
        "forecast": dict(forecast),
        "rating": chain["rating_replay"],
        "measurement": chain["measurement"],
        "repair": dict(repair),
        "bridge": chain["bridge"],
        "forecast_manifest_uri": forecast_manifest_uri,
        "forecast_raw_sha256": forecast_raw_sha256,
        "rating_manifest_uri": rating_manifest_uri,
        "rating_raw_sha256": rating_raw_sha256,
        "measurement_manifest_uri": measurement_manifest_uri,
        "measurement_raw_sha256": measurement_raw_sha256,
        "repair_manifest_uri": repair_manifest_uri,
        "repair_raw_sha256": repair_raw_sha256,
    }


def shadow_identity(
    *,
    run_id: str,
    as_of: str,
    code_sha: str,
    config_sha: str,
    parents: Mapping[str, Any],
    candidate: str = REQUIRED_FORECAST_RUN_ID,
) -> dict[str, Any]:
    if not all((run_id, as_of, code_sha, config_sha)):
        raise ShadowContractError("shadow identity is incomplete")
    if any(not parents.get(key) for key in IDENTITY_PARENT_KEYS):
        raise ShadowContractError(
            "shadow identity parents must pin exact URIs and checksums"
        )
    value = {
        "schema_version": SHADOW_IDENTITY_SCHEMA,
        "run_id": run_id,
        "environment": "preview",
        "as_of": as_of,
        "code_sha": code_sha,
        "config_sha": config_sha,
        "parents": dict(parents),
        "candidate": candidate,
    }
    return value | {"identity_sha256": sha256(value)}


def records_sha(records: Any) -> str:
    return hashlib.sha256(sha256(records).encode()).hexdigest()


def shadow_manifest(
    *,
    identity: Mapping[str, Any],
    parents: Mapping[str, Any],
    output_refs: Mapping[str, Any],
    readiness_overall: str,
) -> dict[str, Any]:
    """Build the signed terminal shadow manifest.

    The manifest is written last during apply. Its absence makes any partial
    prefix permanently ineligible.
    """
    if readiness_overall not in ("ready", "blocked"):
        raise ShadowContractError("shadow manifest readiness verdict is unknown")
    if set(output_refs) != {"readiness"}:
        raise ShadowContractError(
            "05A shadow manifest must reference exactly the readiness output"
        )
    return signed_payload(
        {
            "schema_version": SHADOW_MANIFEST_SCHEMA,
            "state": "frozen",
            "identity": dict(identity),
            "parents": dict(parents),
            "output_refs": dict(output_refs),
            "readiness_overall": readiness_overall,
            "production_activation_authorized": False,
        }
    )
