"""Fail-closed contracts for the Preview-only V5 forecast bridge."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from cks_picks_cfb.data.data_first_phase2 import DEVELOPMENT_SEASONS, FORBIDDEN_SEASONS
from cks_picks_cfb.data.data_first_phase2d import sha256, verify_signed_payload
from cks_picks_cfb.data.data_first_possession_rating_v1 import (
    POSSESSION_RATING_MANIFEST_SCHEMA,
    RATING_DATASETS,
    verify_parents,
)

FORECAST_CONFIG_SCHEMA = "data_first_forecast_config_v1"
FORECAST_IDENTITY_SCHEMA = "data_first_forecast_identity_v1"
FORECAST_OUTPUT_ROOT = "artifacts/research/data-first-football-v1/forecasts/runs"
REQUIRED_RATING_RUN_ID = "possession-v1-ratings-20260917-d029526-cert"
REQUIRED_RATING_CANDIDATE = "ppp__rho_0_60__exposure"
HORIZONS = ("expanding", "latest_five")
TARGETS = ("margin", "total")
ALPHAS = (0.1, 1.0, 10.0, 100.0)

FORECAST_DATASETS = {
    "forecast_registry": ("forecast_registry", "data_first_forecast_registry_v1"),
    "forecast_model": ("forecast_model", "data_first_forecast_model_v1"),
    "forecast_prediction": ("forecast_prediction", "data_first_forecast_prediction_v1"),
    "forecast_calibration": (
        "forecast_calibration",
        "data_first_forecast_calibration_v1",
    ),
    "window_comparison": ("window_comparison", "data_first_window_comparison_v1"),
    "forecast_selection": ("forecast_selection", "data_first_forecast_selection_v1"),
    "candidate_manifest": ("candidate_manifest", "data_first_candidate_manifest_v1"),
}

FORECAST_REGISTRY_COLUMNS = ("horizon", "target", "reference_alpha", "alpha_grid")
FORECAST_MODEL_COLUMNS = (
    "horizon",
    "target",
    "outer_season",
    "head",
    "alpha",
    "training_seasons",
    "inner_fallback",
    "retained",
    "fallback_reason",
)
FORECAST_PREDICTION_COLUMNS = (
    "horizon",
    "head",
    "target",
    "season",
    "week",
    "game_id",
    "actual",
    "prediction",
    "absolute_error",
    "gaussian_crps",
    "offset",
    "training_seasons",
    "completed_game_stage",
    "venue_unknown",
)
FORECAST_CALIBRATION_COLUMNS = (
    "target",
    "season",
    "residual_count",
    "variance",
    "fallback_reason",
)
WINDOW_COMPARISON_COLUMNS = (
    "target",
    "metric",
    "expanding",
    "latest_five",
    "improvement_pct",
    "bootstrap_90_lower",
    "bootstrap_90_upper",
    "passes",
)
FORECAST_SELECTION_COLUMNS = (
    "selected_horizon",
    "target",
    "selected_head",
    "selection_reason",
    "horizon_sha256",
)
CANDIDATE_MANIFEST_COLUMNS = ("identity_sha256", "state", "manifest_uri")


class ForecastContractError(ValueError):
    """Raised when a forecast input leaves the sealed V5-04A boundary."""


def validate_config(payload: Mapping[str, Any]) -> None:
    if payload.get("schema_version") != FORECAST_CONFIG_SCHEMA:
        raise ForecastContractError("unexpected forecast config schema")
    if tuple(payload.get("development_seasons") or ()) != DEVELOPMENT_SEASONS:
        raise ForecastContractError("forecast development season policy drifted")
    if tuple(payload.get("forbidden_seasons") or ()) != FORBIDDEN_SEASONS:
        raise ForecastContractError("forecast forbidden season policy drifted")
    if payload.get("rating_candidate") != REQUIRED_RATING_CANDIDATE:
        raise ForecastContractError(
            "forecast may only consume the retained rating candidate"
        )
    if tuple(payload.get("horizons") or ()) != HORIZONS:
        raise ForecastContractError("forecast horizon registry drifted")
    bridge = payload.get("bridge") or {}
    if (
        bridge.get("reference_alpha") != 10.0
        or tuple(bridge.get("alpha_grid") or ()) != ALPHAS
    ):
        raise ForecastContractError("forecast bridge registry drifted")
    if payload.get("production_activation_authorized") is not False:
        raise ForecastContractError("forecast config may not authorize production")


def verify_rating_parent(
    rating: Mapping[str, Any],
    *,
    rating_raw_sha256: str,
    measurement: Mapping[str, Any],
    measurement_raw_sha256: str,
    repair: Mapping[str, Any],
    repair_raw_sha256: str,
) -> dict[str, Any]:
    """Validate exact 03 lineage at forecast consumption time."""
    try:
        verify_signed_payload(rating, label="retained rating manifest")
    except ValueError as exc:
        raise ForecastContractError(str(exc)) from exc
    identity = rating.get("identity") or {}
    if (
        rating.get("schema_version") != POSSESSION_RATING_MANIFEST_SCHEMA
        or rating.get("state") != "frozen"
        or identity.get("environment") != "preview"
        or identity.get("run_id") != REQUIRED_RATING_RUN_ID
        or rating.get("selected_candidate") != REQUIRED_RATING_CANDIDATE
        or rating.get("production_activation_authorized") is not False
    ):
        raise ForecastContractError("forecast requires the exact certified 03 parent")
    parents = rating.get("parents") or {}
    if (
        parents.get("measurement_manifest_raw_sha256") != measurement_raw_sha256
        or parents.get("repair_manifest_raw_sha256") != repair_raw_sha256
        or not rating_raw_sha256
    ):
        raise ForecastContractError("retained rating parent checksums do not reconcile")
    try:
        measurement_verified, repair_verified = verify_parents(measurement, repair)
    except ValueError as exc:
        raise ForecastContractError(str(exc)) from exc
    if set(rating.get("output_refs") or {}) != set(RATING_DATASETS):
        raise ForecastContractError("retained rating output roles changed")
    return {
        "rating": dict(rating),
        "measurement": measurement_verified,
        "repair": repair_verified,
        "rating_raw_sha256": rating_raw_sha256,
        "measurement_raw_sha256": measurement_raw_sha256,
        "repair_raw_sha256": repair_raw_sha256,
    }


def forecast_identity(
    *,
    run_id: str,
    as_of: str,
    code_sha: str,
    config_sha: str,
    parents: Mapping[str, Any],
) -> dict[str, Any]:
    if not all((run_id, as_of, code_sha, config_sha)):
        raise ForecastContractError("forecast identity is incomplete")
    value = {
        "schema_version": FORECAST_IDENTITY_SCHEMA,
        "run_id": run_id,
        "environment": "preview",
        "as_of": as_of,
        "code_sha": code_sha,
        "config_sha": config_sha,
        "parents": dict(parents),
        "development_seasons": list(DEVELOPMENT_SEASONS),
        "forbidden_seasons": list(FORBIDDEN_SEASONS),
    }
    return value | {"identity_sha256": sha256(value)}


def records_sha(records: Any) -> str:
    return hashlib.sha256(sha256(records).encode()).hexdigest()
