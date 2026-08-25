"""Isolated rating measurement contracts for the Phase 1 research package.

This namespace is intentionally separate from every V4 feature, bundle, and
production path. It defines the frozen measurement catalog, the canonical
configuration hashing that produces ``measurement_design_id``, and the
frame-level validators enforcing exposure, missingness, temporal-status, and
forbidden-market-field rules from the Phase 1 contract.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd
import yaml

OBSERVATION_SCHEMA_VERSION = "rating_measurement_observations_v2"
SNAPSHOT_SCHEMA_VERSION = "rating_adjusted_measurement_snapshots_v2"
TERMINAL_SNAPSHOT_SCHEMA_VERSION = "rating_adjusted_measurement_terminal_snapshots_v1"

OBSERVATION_DATASET = "rating_measurement_observations"
SNAPSHOT_DATASET = "rating_adjusted_measurement_snapshots"
TERMINAL_SNAPSHOT_DATASET = "rating_adjusted_measurement_terminal_snapshots"

BASELINE_CONFIG_VERSION = "measurement_baseline_v2"
BASELINE_MEASUREMENT_IDS = (
    "epa_per_play",
    "success_rate",
    "explosive_rate_20",
    "points_per_scoring_opportunity",
    "average_start_field_position",
    "plays_per_drive",
    "turnover_rate",
)

ROLES = ("offense", "defense")
EXPOSURE_UNITS = ("plays", "drives", "opportunities")
ADJUSTMENT_POSTURES = ("iterative_additive", "none")
ADJUSTMENT_METHOD_ADJUSTED = "iterative_additive_league_centered"
ADJUSTMENT_METHOD_NONE = "none"
TEMPORAL_STATUSES = ("reconstructed", "authentic")
COVERAGE_STATUSES = ("observed", "missing")
SIDES = ("home", "away")

OBSERVATION_MISSING_REASONS = (
    "zero_denominator",
    "source_evidence_missing",
)
SNAPSHOT_MISSING_REASONS = (
    "no_eligible_evidence",
    "zero_primary_exposure",
)

OBSERVATION_COLUMNS: tuple[str, ...] = (
    "season",
    "week",
    "game_id",
    "kickoff_utc",
    "team",
    "opponent",
    "side",
    "measurement_id",
    "unit_role",
    "numerator",
    "denominator",
    "raw_value",
    "exposure_unit",
    "effective_at",
    "temporal_status",
    "eligible_after",
    "coverage_status",
    "missing_reason",
    "quality_flags",
    "measurement_schema_version",
    "measurement_design_id",
    "parent_ref_shas",
    "code_sha",
    "config_sha",
)
OBSERVATION_KEYS = ("season", "game_id", "team", "measurement_id", "unit_role")

SNAPSHOT_COLUMNS: tuple[str, ...] = (
    "season",
    "week",
    "as_of_game_id",
    "as_of_kickoff_utc",
    "team",
    "measurement_id",
    "unit_role",
    "raw_aggregate",
    "adjusted_value_iter0",
    "adjusted_value",
    "games_exposure",
    "primary_exposure",
    "included_observations",
    "adjustment_method",
    "adjustment_iteration",
    "league_center",
    "schedule_strength_component",
    "evidence_max_kickoff_utc",
    "evidence_max_effective_at",
    "coverage_status",
    "missing_reason",
    "quality_flags",
    "measurement_schema_version",
    "measurement_design_id",
    "parent_observation_version_id",
    "parent_ref_shas",
    "code_sha",
    "config_sha",
)
SNAPSHOT_KEYS = ("season", "as_of_game_id", "team", "measurement_id", "unit_role")

TERMINAL_SNAPSHOT_COLUMNS: tuple[str, ...] = (
    "season",
    "terminal_at_utc",
    "team",
    "measurement_id",
    "unit_role",
    "raw_aggregate",
    "adjusted_value_iter0",
    "adjusted_value",
    "games_exposure",
    "primary_exposure",
    "included_observations",
    "adjustment_method",
    "adjustment_iteration",
    "league_center",
    "schedule_strength_component",
    "evidence_max_kickoff_utc",
    "evidence_max_effective_at",
    "coverage_status",
    "missing_reason",
    "quality_flags",
    "measurement_schema_version",
    "measurement_design_id",
    "parent_observation_version_id",
    "parent_ref_shas",
    "code_sha",
    "config_sha",
)
TERMINAL_SNAPSHOT_KEYS = ("season", "team", "measurement_id", "unit_role")

_MARKET_SUBSTRINGS = (
    "spread",
    "moneyline",
    "bookmaker",
    "market",
    "odds",
    "over_under",
    "vig",
    "juice",
    "implied",
    "closing",
    "vegas",
)
_MARKET_EXACT = {"line", "total"}
_MARKET_PATTERN = re.compile(
    "|".join(_MARKET_SUBSTRINGS) + r"|^(?:" + "|".join(_MARKET_EXACT) + r")$",
    re.IGNORECASE,
)


class MeasurementContractError(ValueError):
    """Raised when measurement configuration or frames violate the contract."""


def market_field_conflicts(names: Iterable[str]) -> list[str]:
    """Return names that look bookmaker- or market-derived."""
    return sorted(name for name in names if _MARKET_PATTERN.search(str(name)))


def assert_no_market_fields(names: Iterable[str], *, context: str) -> None:
    """Reject market-derived fields anywhere in the measurement contract."""
    conflicts = market_field_conflicts(names)
    if conflicts:
        raise MeasurementContractError(
            f"Forbidden market-derived fields in {context}: {conflicts}"
        )


def _canonical_sha(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


@dataclass(frozen=True)
class MeasurementSpec:
    measurement_id: str
    source: str
    roles: tuple[str, ...]
    exposure_unit: str
    adjustment: str
    numerator: str
    denominator: str

    @property
    def is_adjusted(self) -> bool:
        return self.adjustment == "iterative_additive"


@dataclass(frozen=True)
class MeasurementConfig:
    config_version: str
    catalog_version: int
    measurements: tuple[MeasurementSpec, ...]
    historical_development_seasons: tuple[int, ...]
    protected_seasons: tuple[int, ...]
    forbidden_seasons: tuple[int, ...]
    out_of_scope_seasons: tuple[int, ...]
    excluded_statuses: tuple[str, ...]
    require_completed: bool
    require_reconciled_team_game: bool
    reconstructed_seasons: tuple[int, ...]
    authentic_seasons: tuple[int, ...]
    authentic_timestamp_columns: tuple[str, ...]
    adjustment_method: str
    adjustment_iterations: int
    retained_iterations: tuple[int, ...]
    research_prefix: str
    raw_config: Mapping[str, Any]

    @property
    def known_seasons(self) -> tuple[int, ...]:
        return self.historical_development_seasons + self.protected_seasons

    @property
    def design_id(self) -> str:
        return _canonical_sha(self.raw_config)

    def spec(self, measurement_id: str) -> MeasurementSpec:
        for candidate in self.measurements:
            if candidate.measurement_id == measurement_id:
                return candidate
        raise MeasurementContractError(
            f"Measurement {measurement_id!r} is not in the frozen catalog"
        )

    def temporal_status_for_season(self, season: int) -> str:
        if season in self.reconstructed_seasons:
            return "reconstructed"
        if season in self.authentic_seasons:
            return "authentic"
        raise MeasurementContractError(
            f"Season {season} has no temporal status in the measurement config"
        )


def _require_mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MeasurementContractError(f"Config {path} must be a mapping")
    return value


def _require_ints(value: Any, path: str) -> tuple[int, ...]:
    if not isinstance(value, list):
        raise MeasurementContractError(f"Config {path} must be a list")
    seasons = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int):
            raise MeasurementContractError(f"Config {path} must contain integers")
        seasons.append(int(item))
    return tuple(seasons)


def load_measurement_config(path: str | Path) -> MeasurementConfig:
    """Load and structurally validate the frozen measurement catalog."""
    raw = yaml.safe_load(Path(path).read_text())
    root = _require_mapping(raw, "root")
    config_version = root.get("measurement_config_version")
    if config_version != BASELINE_CONFIG_VERSION:
        raise MeasurementContractError(
            f"Unsupported measurement config version: {config_version!r}"
        )
    _assert_no_market_keys(root)

    seasons = _require_mapping(root.get("seasons"), "seasons")
    historical = _require_ints(
        seasons.get("historical_development"), "seasons.historical_development"
    )
    protected = _require_ints(seasons.get("protected"), "seasons.protected")
    forbidden = _require_ints(seasons.get("forbidden"), "seasons.forbidden")
    out_of_scope = _require_ints(seasons.get("out_of_scope"), "seasons.out_of_scope")
    overlap = (set(historical) & set(protected)) | (
        set(historical) | set(protected)
    ) & set(forbidden)
    if overlap:
        raise MeasurementContractError(f"Season scopes overlap: {sorted(overlap)}")

    schedule = _require_mapping(root.get("schedule_policy"), "schedule_policy")
    temporal = _require_mapping(root.get("temporal_policy"), "temporal_policy")
    reconstructed = _require_ints(
        temporal.get("reconstructed_seasons"), "temporal_policy.reconstructed_seasons"
    )
    authentic = _require_ints(
        temporal.get("authentic_seasons"), "temporal_policy.authentic_seasons"
    )
    if sorted(reconstructed + authentic) != sorted(historical + protected):
        raise MeasurementContractError(
            "Temporal policy seasons must partition the known season scope"
        )
    timestamp_columns = temporal.get("authentic_timestamp_columns", ())
    if not isinstance(timestamp_columns, list) or not all(
        isinstance(column, str) and column for column in timestamp_columns
    ):
        raise MeasurementContractError(
            "temporal_policy.authentic_timestamp_columns must be nonempty strings"
        )

    adjustment = _require_mapping(root.get("adjustment"), "adjustment")
    method = adjustment.get("method")
    if method != ADJUSTMENT_METHOD_ADJUSTED:
        raise MeasurementContractError(f"Unsupported adjustment method: {method!r}")
    iterations = adjustment.get("iterations")
    if (
        isinstance(iterations, bool)
        or not isinstance(iterations, int)
        or iterations < 1
    ):
        raise MeasurementContractError("adjustment.iterations must be a positive int")
    retained = _require_ints(
        adjustment.get("retained_iterations"), "adjustment.retained"
    )
    if retained != (0, iterations):
        raise MeasurementContractError(
            "retained_iterations must be exactly iteration zero and the final iteration"
        )

    measurements_raw = root.get("measurements")
    if not isinstance(measurements_raw, list) or not measurements_raw:
        raise MeasurementContractError("Config measurements must be a nonempty list")
    measurements = []
    seen: set[str] = set()
    for entry in measurements_raw:
        entry = _require_mapping(entry, "measurements[]")
        measurement_id = entry.get("measurement_id")
        if not isinstance(measurement_id, str) or not measurement_id:
            raise MeasurementContractError("Each measurement needs a string id")
        if measurement_id in seen:
            raise MeasurementContractError(
                f"Duplicate measurement id: {measurement_id}"
            )
        seen.add(measurement_id)
        roles = entry.get("roles")
        if not isinstance(roles, list) or not roles:
            raise MeasurementContractError(f"Measurement {measurement_id} needs roles")
        for role in roles:
            if role not in ROLES:
                raise MeasurementContractError(
                    f"Measurement {measurement_id} has invalid role {role!r}"
                )
        exposure_unit = entry.get("exposure_unit")
        if exposure_unit not in EXPOSURE_UNITS:
            raise MeasurementContractError(
                f"Measurement {measurement_id} has invalid exposure unit"
            )
        posture = entry.get("adjustment")
        if posture not in ADJUSTMENT_POSTURES:
            raise MeasurementContractError(
                f"Measurement {measurement_id} has invalid adjustment posture"
            )
        measurements.append(
            MeasurementSpec(
                measurement_id=measurement_id,
                source=entry.get("source"),
                roles=tuple(roles),
                exposure_unit=exposure_unit,
                adjustment=posture,
                numerator=entry.get("numerator"),
                denominator=entry.get("denominator"),
            )
        )

    research_prefix = root.get("research_prefix")
    if not isinstance(research_prefix, str) or not research_prefix:
        raise MeasurementContractError("Config needs a research_prefix")

    return MeasurementConfig(
        config_version=config_version,
        catalog_version=int(root.get("catalog_version", 0)),
        measurements=tuple(measurements),
        historical_development_seasons=historical,
        protected_seasons=protected,
        forbidden_seasons=forbidden,
        out_of_scope_seasons=out_of_scope,
        excluded_statuses=tuple(schedule.get("excluded_statuses", ())),
        require_completed=bool(schedule.get("require_completed", True)),
        require_reconciled_team_game=bool(
            schedule.get("require_reconciled_team_game", True)
        ),
        reconstructed_seasons=reconstructed,
        authentic_seasons=authentic,
        authentic_timestamp_columns=tuple(timestamp_columns),
        adjustment_method=method,
        adjustment_iterations=iterations,
        retained_iterations=retained,
        research_prefix=research_prefix.rstrip("/"),
        raw_config=root,
    )


def _assert_no_market_keys(payload: Mapping[str, Any]) -> None:
    assert_no_market_fields(payload.keys(), context="measurement configuration keys")
    for value in payload.values():
        if isinstance(value, Mapping):
            _assert_no_market_keys(value)


def verify_design_id(config: MeasurementConfig, expected_design_id: str) -> None:
    """Reject a caller-supplied design id that does not match the config."""
    if expected_design_id != config.design_id:
        raise MeasurementContractError(
            "Measurement design id mismatch: "
            f"expected {expected_design_id!r}, config resolves to {config.design_id!r}"
        )


def _check_finite(frame: pd.DataFrame, columns: Iterable[str], label: str) -> None:
    for column in columns:
        values = pd.to_numeric(frame[column], errors="coerce")
        nonnull = values.dropna()
        if len(nonnull) and not np.isfinite(nonnull.to_numpy()).all():
            raise MeasurementContractError(f"{label} has non-finite values in {column}")


def _check_enum(
    frame: pd.DataFrame, column: str, allowed: Iterable[str], label: str
) -> None:
    values = set(frame[column].dropna().astype(str))
    unexpected = values - set(allowed)
    if unexpected:
        raise MeasurementContractError(
            f"{label}.{column} has unsupported values: {sorted(unexpected)}"
        )


def validate_observation_frame(frame: pd.DataFrame, config: MeasurementConfig) -> None:
    """Enforce the raw observation contract on a built frame."""
    label = OBSERVATION_DATASET
    missing = sorted(set(OBSERVATION_COLUMNS) - set(frame.columns))
    if missing:
        raise MeasurementContractError(f"{label} missing columns: {missing}")
    assert_no_market_fields(frame.columns, context=f"{label} columns")
    if frame.duplicated(list(OBSERVATION_KEYS)).any():
        raise MeasurementContractError(f"{label} has duplicate keys")
    _check_finite(frame, ("numerator", "denominator", "raw_value"), label)
    _check_enum(frame, "side", SIDES, label)
    _check_enum(frame, "unit_role", ROLES, label)
    _check_enum(frame, "temporal_status", TEMPORAL_STATUSES, label)
    _check_enum(frame, "coverage_status", COVERAGE_STATUSES, label)
    _check_enum(frame, "exposure_unit", EXPOSURE_UNITS, label)

    if (pd.to_numeric(frame["denominator"]) < 0).any():
        raise MeasurementContractError(f"{label} exposure must be nonnegative")

    observed = frame["coverage_status"].astype(str) == "observed"
    raw_null = frame["raw_value"].isna()
    reason_null = frame["missing_reason"].isna()
    if (observed & (raw_null | ~reason_null)).any() or (
        ~observed & (~raw_null | reason_null)
    ).any():
        raise MeasurementContractError(
            f"{label} coverage status, raw value, and missing reason are inconsistent"
        )
    denominator = pd.to_numeric(frame["denominator"])
    missing_reasons = set(frame.loc[~observed, "missing_reason"].dropna())
    unexpected = missing_reasons - set(OBSERVATION_MISSING_REASONS)
    if unexpected:
        raise MeasurementContractError(
            f"{label} has unsupported missing reasons: {sorted(unexpected)}"
        )
    if (~frame["raw_value"].isna() & (denominator <= 0)).any():
        raise MeasurementContractError(f"{label} raw values require positive exposure")
    with np.errstate(invalid="ignore", divide="ignore"):
        ratio = frame["numerator"].astype(float) / denominator.replace(0, np.nan)
    has_value = ~frame["raw_value"].isna()
    if (
        has_value
        & (
            np.abs(ratio[has_value] - frame.loc[has_value, "raw_value"].astype(float))
            > 1e-9
        )
    ).any():
        raise MeasurementContractError(
            f"{label} raw_value does not match exposure ratio"
        )

    reconstructed = frame["temporal_status"].astype(str) == "reconstructed"
    if (
        reconstructed
        & (frame["effective_at"].notna() | frame["eligible_after"].notna())
    ).any():
        raise MeasurementContractError(
            f"{label} reconstructed rows must not claim effective times"
        )
    if (
        ~reconstructed & (frame["effective_at"].isna() | frame["eligible_after"].isna())
    ).any():
        raise MeasurementContractError(
            f"{label} authentic rows require effective and eligible-after times"
        )

    seasons = set(pd.to_numeric(frame["season"]).dropna().astype(int))
    forbidden = seasons & set(config.forbidden_seasons)
    if forbidden:
        raise MeasurementContractError(
            f"{label} contains forbidden seasons: {sorted(forbidden)}"
        )
    unknown = seasons - set(config.known_seasons)
    if unknown:
        raise MeasurementContractError(
            f"{label} contains out-of-scope seasons: {sorted(unknown)}"
        )

    catalog_roles = {spec.measurement_id: spec.roles for spec in config.measurements}
    for (measurement_id, role), _ in frame.groupby(["measurement_id", "unit_role"]):
        if measurement_id not in catalog_roles:
            raise MeasurementContractError(
                f"{label} contains unknown measurement {measurement_id!r}"
            )
        if role not in catalog_roles[measurement_id]:
            raise MeasurementContractError(
                f"{label} measurement {measurement_id!r} has unauthorized role {role!r}"
            )
    units = frame.groupby("measurement_id")["exposure_unit"].unique()
    for measurement_id, values in units.items():
        spec = config.spec(str(measurement_id))
        if set(values) != {spec.exposure_unit}:
            raise MeasurementContractError(
                f"{label} measurement {measurement_id!r} has inconsistent exposure units"
            )


def validate_snapshot_frame(frame: pd.DataFrame, config: MeasurementConfig) -> None:
    """Enforce the pregame adjusted snapshot contract on a built frame."""
    label = SNAPSHOT_DATASET
    missing = sorted(set(SNAPSHOT_COLUMNS) - set(frame.columns))
    if missing:
        raise MeasurementContractError(f"{label} missing columns: {missing}")
    assert_no_market_fields(frame.columns, context=f"{label} columns")
    if frame.duplicated(list(SNAPSHOT_KEYS)).any():
        raise MeasurementContractError(f"{label} has duplicate keys")
    _check_finite(
        frame,
        (
            "raw_aggregate",
            "adjusted_value_iter0",
            "adjusted_value",
            "primary_exposure",
            "league_center",
            "schedule_strength_component",
        ),
        label,
    )
    _check_enum(frame, "unit_role", ROLES, label)
    _check_enum(frame, "coverage_status", COVERAGE_STATUSES, label)
    _check_enum(
        frame,
        "adjustment_method",
        (ADJUSTMENT_METHOD_ADJUSTED, ADJUSTMENT_METHOD_NONE),
        label,
    )

    if (
        (pd.to_numeric(frame["games_exposure"]) < 0)
        | (pd.to_numeric(frame["primary_exposure"]) < 0)
        | (pd.to_numeric(frame["included_observations"]) < 0)
    ).any():
        raise MeasurementContractError(f"{label} exposure must be nonnegative")

    observed = frame["coverage_status"].astype(str) == "observed"
    raw_null = frame["raw_aggregate"].isna()
    reason_null = frame["missing_reason"].isna()
    if (observed & (raw_null | ~reason_null)).any() or (
        ~observed & (~raw_null | reason_null)
    ).any():
        raise MeasurementContractError(
            f"{label} coverage status, aggregate, and missing reason are inconsistent"
        )
    missing_reasons = set(frame["missing_reason"].dropna())
    unexpected = missing_reasons - set(SNAPSHOT_MISSING_REASONS)
    if unexpected:
        raise MeasurementContractError(
            f"{label} has unsupported missing reasons: {sorted(unexpected)}"
        )

    adjusted_ids = {
        spec.measurement_id for spec in config.measurements if spec.is_adjusted
    }
    context_ids = {
        spec.measurement_id for spec in config.measurements if not spec.is_adjusted
    }
    is_adjusted = frame["measurement_id"].isin(adjusted_ids)
    is_context = frame["measurement_id"].isin(context_ids)
    method = frame["adjustment_method"].astype(str)
    iterations = pd.to_numeric(frame["adjustment_iteration"])
    if (is_context & (method != ADJUSTMENT_METHOD_NONE)).any():
        raise MeasurementContractError(
            f"{label} context-only measurements must use adjustment_method none"
        )
    context_observed = is_context & observed
    if context_observed.any():
        rows = frame.loc[context_observed]
        if (rows["adjusted_value"] != rows["raw_aggregate"]).any():
            raise MeasurementContractError(
                f"{label} context-only adjusted values must equal raw aggregates"
            )
    if (is_adjusted & (method != ADJUSTMENT_METHOD_ADJUSTED)).any() or (
        is_adjusted & (iterations != config.adjustment_iterations)
    ).any():
        raise MeasurementContractError(
            f"{label} adjusted measurements must use the configured fixed iteration count"
        )
    adjusted_observed = is_adjusted & observed
    if adjusted_observed.any():
        rows = frame.loc[adjusted_observed]
        strength_error = (
            rows["raw_aggregate"].astype(float)
            - rows["adjusted_value"].astype(float)
            - rows["schedule_strength_component"].astype(float)
        ).abs()
        if (strength_error > 1e-9).any():
            raise MeasurementContractError(
                f"{label} schedule strength must equal raw minus adjusted exactly once"
            )
        iter0_error = (
            rows["adjusted_value_iter0"].astype(float)
            - rows["raw_aggregate"].astype(float)
        ).abs()
        if (iter0_error > 1e-9).any():
            raise MeasurementContractError(
                f"{label} retained iteration zero must equal the raw aggregate"
            )

    seasons = set(pd.to_numeric(frame["season"]).dropna().astype(int))
    forbidden = seasons & set(config.forbidden_seasons)
    if forbidden:
        raise MeasurementContractError(
            f"{label} contains forbidden seasons: {sorted(forbidden)}"
        )
    unknown = seasons - set(config.known_seasons)
    if unknown:
        raise MeasurementContractError(
            f"{label} contains out-of-scope seasons: {sorted(unknown)}"
        )


def validate_terminal_snapshot_frame(
    frame: pd.DataFrame, config: MeasurementConfig
) -> None:
    """Validate terminal snapshots using the same value semantics as pregames."""
    renamed = frame.rename(columns={"terminal_at_utc": "as_of_kickoff_utc"}).copy()
    renamed["as_of_game_id"] = -1
    renamed["week"] = 99
    ordered = list(SNAPSHOT_COLUMNS)
    for column in ordered:
        if column not in renamed:
            renamed[column] = None
    renamed = renamed[ordered]
    validate_snapshot_frame(renamed, config)
    if frame.duplicated(list(TERMINAL_SNAPSHOT_KEYS)).any():
        raise MeasurementContractError(
            f"{TERMINAL_SNAPSHOT_DATASET} has duplicate keys"
        )
