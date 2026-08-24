"""Immutable contracts for the Phase 2 empirical-Bayes team-state baseline."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd
import yaml

from cks_picks_cfb.ratings.contracts import (
    MeasurementContractError,
    assert_no_market_fields,
)

STATE_CONFIG_VERSION = "team_state_baseline_v1"
MEASUREMENT_STATE_DATASET = "rating_measurement_states"
TEAM_STATE_DATASET = "rating_team_states"
MEASUREMENT_STATE_SCHEMA_VERSION = "rating_measurement_states_v1"
TEAM_STATE_SCHEMA_VERSION = "rating_team_states_v1"
STATE_KINDS = ("pregame", "season_terminal")
CORE_MEASUREMENTS = (
    "epa_per_play",
    "success_rate",
    "explosive_rate_20",
    "points_per_scoring_opportunity",
)

MEASUREMENT_STATE_COLUMNS = (
    "state_id",
    "state_kind",
    "season",
    "week",
    "as_of_game_id",
    "as_of_utc",
    "team",
    "measurement_id",
    "unit_role",
    "prior_source_season",
    "standardization_center",
    "standardization_scale",
    "native_adjusted_value",
    "observed_z",
    "primary_exposure",
    "completed_games",
    "prior_mean",
    "prior_variance",
    "prior_precision",
    "observation_precision",
    "prior_weight",
    "observed_weight",
    "posterior_mean",
    "posterior_variance",
    "posterior_sd",
    "quality_flags",
    "state_schema_version",
    "state_design_id",
    "parent_measurement_refs",
    "code_sha",
    "config_sha",
)
MEASUREMENT_STATE_KEYS = ("state_id", "team", "measurement_id", "unit_role")
TEAM_STATE_COLUMNS = (
    "state_id",
    "state_kind",
    "season",
    "week",
    "as_of_game_id",
    "as_of_utc",
    "team",
    "offense_mean",
    "offense_sd",
    "defense_mean",
    "defense_sd",
    "overall_mean",
    "overall_sd",
    "completed_games",
    "offense_observed_weight",
    "defense_observed_weight",
    "component_count",
    "quality_flags",
    "state_schema_version",
    "state_design_id",
    "parent_measurement_refs",
    "code_sha",
    "config_sha",
)
TEAM_STATE_KEYS = ("state_id", "team")


def _sha(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@dataclass(frozen=True)
class ComponentSpec:
    measurement_id: str
    weight: float
    equivalent_prior_exposure: float
    fallback_center: float
    fallback_scale: float
    scale_floor: float


@dataclass(frozen=True)
class TeamStateConfig:
    components: tuple[ComponentSpec, ...]
    offseason_rho: float
    neutral_mean: float
    neutral_variance: float
    research_prefix: str
    raw_config: Mapping[str, Any]

    @property
    def design_id(self) -> str:
        return _sha(self.raw_config)

    def component(self, measurement_id: str) -> ComponentSpec:
        return next(
            item for item in self.components if item.measurement_id == measurement_id
        )


def load_team_state_config(path: str | Path) -> TeamStateConfig:
    raw = yaml.safe_load(Path(path).read_text())
    if (
        not isinstance(raw, Mapping)
        or raw.get("team_state_config_version") != STATE_CONFIG_VERSION
    ):
        raise MeasurementContractError("Unsupported team-state configuration")
    assert_no_market_fields(raw.keys(), context="team-state configuration keys")
    core = raw.get("core_measurements")
    if not isinstance(core, Mapping) or tuple(core) != CORE_MEASUREMENTS:
        raise MeasurementContractError(
            "Team-state core measurements must be frozen in canonical order"
        )
    components = tuple(
        ComponentSpec(
            measurement_id=measurement_id,
            weight=float(values["weight"]),
            equivalent_prior_exposure=float(values["equivalent_prior_exposure"]),
            fallback_center=float(values["fallback_center"]),
            fallback_scale=float(values["fallback_scale"]),
            scale_floor=float(values["scale_floor"]),
        )
        for measurement_id, values in core.items()
    )
    if not np.isclose(sum(item.weight for item in components), 1.0) or any(
        item.weight <= 0 for item in components
    ):
        raise MeasurementContractError("Team-state component weights must sum to one")
    prior = raw.get("prior")
    if not isinstance(prior, Mapping):
        raise MeasurementContractError("Team-state prior configuration is required")
    rho = float(prior["offseason_rho"])
    variance = float(prior["neutral_variance"])
    if not 0 <= rho <= 1 or variance <= 0:
        raise MeasurementContractError("Invalid team-state prior configuration")
    return TeamStateConfig(
        components,
        rho,
        float(prior["neutral_mean"]),
        variance,
        str(raw["research_prefix"]).rstrip("/"),
        raw,
    )


def _validate_common(
    frame: pd.DataFrame, columns: tuple[str, ...], keys: tuple[str, ...], label: str
) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise MeasurementContractError(f"{label} missing columns: {missing}")
    assert_no_market_fields(frame.columns, context=f"{label} columns")
    if frame.duplicated(list(keys)).any():
        raise MeasurementContractError(f"{label} has duplicate keys")
    if not set(frame["state_kind"].dropna()).issubset(STATE_KINDS):
        raise MeasurementContractError(f"{label} has invalid state kind")


def validate_measurement_state_frame(
    frame: pd.DataFrame, config: TeamStateConfig
) -> None:
    _validate_common(
        frame,
        MEASUREMENT_STATE_COLUMNS,
        MEASUREMENT_STATE_KEYS,
        MEASUREMENT_STATE_DATASET,
    )
    numeric = (
        "standardization_scale",
        "primary_exposure",
        "prior_variance",
        "prior_precision",
        "observation_precision",
        "prior_weight",
        "observed_weight",
        "posterior_variance",
        "posterior_sd",
    )
    for column in numeric:
        values = pd.to_numeric(frame[column], errors="coerce")
        if values.isna().any() or (values < 0).any() or not np.isfinite(values).all():
            raise MeasurementContractError(f"Invalid {column} in measurement state")
    if (pd.to_numeric(frame["standardization_scale"]) <= 0).any() or (
        pd.to_numeric(frame["posterior_sd"]) <= 0
    ).any():
        raise MeasurementContractError(
            "Team-state scale and uncertainty must be positive"
        )
    if not set(frame["measurement_id"]).issubset(CORE_MEASUREMENTS):
        raise MeasurementContractError("Unexpected team-state measurement")


def validate_team_state_frame(frame: pd.DataFrame, config: TeamStateConfig) -> None:
    _validate_common(frame, TEAM_STATE_COLUMNS, TEAM_STATE_KEYS, TEAM_STATE_DATASET)
    for column in (
        "offense_mean",
        "offense_sd",
        "defense_mean",
        "defense_sd",
        "overall_mean",
        "overall_sd",
    ):
        values = pd.to_numeric(frame[column], errors="coerce")
        if (
            values.isna().any()
            or not np.isfinite(values).all()
            or (column.endswith("_sd") and (values <= 0).any())
        ):
            raise MeasurementContractError(f"Invalid {column} in team state")
