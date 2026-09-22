"""Outcome-free contract for application of the frozen V5 forecast bridge."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from cks_picks_cfb.data.data_first_phase2d import (
    sha256,
    signed_payload,
    verify_signed_payload,
)
from cks_picks_cfb.data.data_first_possession_v1 import POSSESSION_MANIFEST_SCHEMA

LIVE_FORECAST_CONFIG_SCHEMA = "data_first_live_forecast_config_v1"
LIVE_FORECAST_IDENTITY_SCHEMA = "data_first_live_forecast_identity_v1"
LIVE_FORECAST_MANIFEST_SCHEMA = "data_first_live_forecast_manifest_v1"
LIVE_FORECAST_MANIFEST_NAME = "live-forecast-manifest.json"
LIVE_FORECAST_OUTPUT_ROOT = (
    "artifacts/research/data-first-football-v1/forecasts/live-runs"
)
BRIDGE_RUN_ID = "forecast-v1-20260921-5afd577-11c"
BRIDGE_MANIFEST_URI = (
    "artifacts/research/data-first-football-v1/forecasts/runs/"
    f"{BRIDGE_RUN_ID}/forecast-manifest.json"
)
RATING_CANDIDATE = "ppp__rho_0_60__exposure"
LIVE_FORECAST_DATASET = (
    "live_forecast_prediction",
    "data_first_live_forecast_prediction_v1",
)
LIVE_FORECAST_COLUMNS = (
    "run_id",
    "season",
    "week",
    "game_id",
    "target",
    "mean",
    "variance",
    "interval_lower_95",
    "interval_upper_95",
    "offset",
    "completed_game_stage",
    "timing_class",
    "model_ref",
    "state_ref",
    "source_ref",
)
LIVE_FORECAST_PARTITIONS = ("season", "week")
PREDICTION_KEYS = ("run_id", "season", "week", "game_id", "target")


class LiveForecastContractError(ValueError):
    """Raised when a live forecast leaves the frozen V5 application contract."""


def validate_config(value: Mapping[str, Any]) -> None:
    if value.get("schema_version") != LIVE_FORECAST_CONFIG_SCHEMA:
        raise LiveForecastContractError("unexpected live forecast config schema")
    if value.get("environment") != "preview":
        raise LiveForecastContractError("live forecast config must target Preview")
    if value.get("bridge_manifest_uri") != BRIDGE_MANIFEST_URI:
        raise LiveForecastContractError(
            "live forecast must pin the certified 11C bridge"
        )
    if (
        value.get("horizon") != "expanding"
        or float(value.get("reference_alpha", 0)) != 10.0
    ):
        raise LiveForecastContractError("live forecast bridge definition drifted")
    if tuple(value.get("development_seasons") or ()) != (
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
    ):
        raise LiveForecastContractError("live forecast development chronology drifted")
    if 2020 not in tuple(value.get("forbidden_seasons") or ()):
        raise LiveForecastContractError("2020 must remain forbidden")
    if value.get("production_activation_authorized") is not False:
        raise LiveForecastContractError("live forecast cannot authorize activation")


def validate_prediction_frame(frame: pd.DataFrame, *, run_id: str) -> None:
    missing = sorted(set(LIVE_FORECAST_COLUMNS) - set(frame.columns))
    if missing:
        raise LiveForecastContractError(f"live forecast columns missing: {missing}")
    if frame.empty:
        raise LiveForecastContractError("live forecast population is empty")
    if frame.duplicated(list(PREDICTION_KEYS)).any():
        raise LiveForecastContractError("live forecast duplicates a prediction key")
    if not frame["run_id"].astype(str).eq(run_id).all():
        raise LiveForecastContractError("live forecast contains another run identity")
    if not pd.to_numeric(frame["season"], errors="coerce").eq(2026).all():
        raise LiveForecastContractError("live forecast rows must be for 2026")
    if not frame["target"].isin(("margin", "total")).all():
        raise LiveForecastContractError("live forecast has an unknown target")
    if not frame["timing_class"].eq("live").all():
        raise LiveForecastContractError("live forecast rows must retain live timing")
    if frame.loc[:, ["model_ref", "state_ref", "source_ref"]].isna().any().any():
        raise LiveForecastContractError("live forecast lineage refs cannot be null")
    for column in (
        "mean",
        "variance",
        "interval_lower_95",
        "interval_upper_95",
        "offset",
    ):
        values = pd.to_numeric(frame[column], errors="coerce").to_numpy(float)
        if not np.isfinite(values).all():
            raise LiveForecastContractError(f"live forecast {column} must be finite")
    if (pd.to_numeric(frame["variance"], errors="coerce") <= 0).any():
        raise LiveForecastContractError("live forecast variance must be positive")
    forbidden = {"actual", "absolute_error", "gaussian_crps"} & set(frame.columns)
    if forbidden:
        raise LiveForecastContractError(
            f"live prediction records cannot contain outcomes: {sorted(forbidden)}"
        )


def verify_application_parents(
    *,
    measurement: Mapping[str, Any],
    measurement_uri: str,
    measurement_raw_sha256: str,
    rating_replay: Mapping[str, Any],
    rating_replay_uri: str,
    rating_replay_raw_sha256: str,
    bridge: Mapping[str, Any],
    bridge_uri: str,
    bridge_raw_sha256: str,
) -> dict[str, Any]:
    """Validate exact signed lineage and keep live and development roles clear."""
    try:
        verify_signed_payload(measurement, label="Contract 07 measurement manifest")
        verify_signed_payload(rating_replay, label="Contract 08 replay manifest")
        verify_signed_payload(bridge, label="Contract 11C bridge manifest")
    except ValueError as exc:
        raise LiveForecastContractError(str(exc)) from exc
    measurement_identity = measurement.get("identity") or {}
    if (
        measurement.get("schema_version") != POSSESSION_MANIFEST_SCHEMA
        or measurement_identity.get("environment") != "preview"
        or tuple(measurement_identity.get("development_seasons") or ()) != (2026,)
        or measurement.get("production_activation_authorized") is not False
        or not measurement.get("output_refs")
    ):
        raise LiveForecastContractError(
            "measurement parent is not a live Contract 07 manifest"
        )
    replay_identity = rating_replay.get("identity") or {}
    replay_parents = rating_replay.get("parents") or {}
    if (
        rating_replay.get("schema_version")
        != "data_first_possession_rating_replay_manifest_v1"
        or rating_replay.get("state") != "frozen"
        or replay_identity.get("environment") != "preview"
        or rating_replay.get("selected_candidate") != RATING_CANDIDATE
        or rating_replay.get("production_activation_authorized") is not False
        or replay_parents.get("measurement_manifest_uri") != measurement_uri
        or replay_parents.get("measurement_manifest_raw_sha256")
        != measurement_raw_sha256
        or not {"team_states", "rating_states", "priors"}
        <= set(rating_replay.get("output_refs") or {})
    ):
        raise LiveForecastContractError(
            "rating replay does not bind the supplied live measurement parent"
        )
    bridge_identity = bridge.get("identity") or {}
    if (
        bridge_uri != BRIDGE_MANIFEST_URI
        or bridge.get("schema_version") != "data_first_forecast_manifest_v1"
        or bridge.get("state") != "frozen"
        or bridge_identity.get("run_id") != BRIDGE_RUN_ID
        or bridge.get("selected_horizon") != "expanding"
        or bridge.get("production_activation_authorized") is not False
    ):
        raise LiveForecastContractError(
            "bridge parent is not the certified 11C final fit"
        )
    if not all((measurement_raw_sha256, rating_replay_raw_sha256, bridge_raw_sha256)):
        raise LiveForecastContractError("raw parent checksums are required")
    return {
        "measurement": dict(measurement),
        "rating_replay": dict(rating_replay),
        "bridge": dict(bridge),
        "measurement_uri": measurement_uri,
        "measurement_raw_sha256": measurement_raw_sha256,
        "rating_replay_uri": rating_replay_uri,
        "rating_replay_raw_sha256": rating_replay_raw_sha256,
        "bridge_uri": bridge_uri,
        "bridge_raw_sha256": bridge_raw_sha256,
    }


def live_forecast_manifest(
    *,
    identity: Mapping[str, Any],
    parents: Mapping[str, Any],
    output_ref: Mapping[str, Any],
    prediction_count: int,
    prediction_records_sha256: str,
    population_sha256: str,
    bridge_recipes: Mapping[str, Any],
    source_cutoff: str,
) -> dict[str, Any]:
    if prediction_count <= 0 or not population_sha256 or not prediction_records_sha256:
        raise LiveForecastContractError(
            "live forecast manifest lacks population evidence"
        )
    required = {
        "measurement_uri",
        "measurement_raw_sha256",
        "rating_replay_uri",
        "rating_replay_raw_sha256",
        "bridge_uri",
        "bridge_raw_sha256",
        "schedule_ref_uri",
        "schedule_raw_sha256",
    }
    if set(parents) != required:
        raise LiveForecastContractError("live forecast manifest parent roles changed")
    payload = {
        "schema_version": LIVE_FORECAST_MANIFEST_SCHEMA,
        "state": "frozen",
        "identity": dict(identity),
        "parents": dict(parents),
        "output_ref": dict(output_ref),
        "row_count": int(prediction_count),
        "prediction_records_sha256": prediction_records_sha256,
        "population_sha256": population_sha256,
        "bridge_recipes": dict(bridge_recipes),
        "source_cutoff": source_cutoff,
        "production_activation_authorized": False,
    }
    return signed_payload(payload)


def live_identity(
    *,
    run_id: str,
    as_of: str,
    code_sha: str,
    config_sha256: str,
    parents: Mapping[str, Any],
) -> dict[str, Any]:
    required = {
        "measurement_uri",
        "measurement_raw_sha256",
        "rating_replay_uri",
        "rating_replay_raw_sha256",
        "bridge_uri",
        "bridge_raw_sha256",
        "schedule_ref_uri",
        "schedule_raw_sha256",
    }
    if not all((run_id, as_of, code_sha, config_sha256)):
        raise LiveForecastContractError("live forecast identity is incomplete")
    if required - set(parents) or any(not parents.get(key) for key in required):
        raise LiveForecastContractError("live forecast identity parents are incomplete")
    value = {
        "schema_version": LIVE_FORECAST_IDENTITY_SCHEMA,
        "run_id": run_id,
        "environment": "preview",
        "as_of": as_of,
        "code_sha": code_sha,
        "config_sha256": config_sha256,
        "parents": dict(parents),
        "season": 2026,
        "production_activation_authorized": False,
    }
    return value | {"identity_sha256": sha256(value)}


def raw_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
