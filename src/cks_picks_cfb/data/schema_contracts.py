"""Executable dataset schemas for immutable Silver and Gold datasets."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

import pandas as pd


class DatasetSchemaError(ValueError):
    """Raised when a frame does not satisfy its published schema contract."""


@dataclass(frozen=True)
class DatasetSchema:
    dataset: str
    schema_version: str
    required: tuple[str, ...]
    keys: tuple[str, ...]
    integer_columns: tuple[str, ...] = ()
    boolean_columns: tuple[str, ...] = ()
    timestamp_columns: tuple[str, ...] = ()
    nonnullable: tuple[str, ...] = ()
    allowed_values: Mapping[str, tuple[Any, ...]] | None = None
    dynamic_features: bool = False

    def json(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "schema_version": self.schema_version,
            "required": list(self.required),
            "keys": list(self.keys),
            "integer_columns": list(self.integer_columns),
            "boolean_columns": list(self.boolean_columns),
            "timestamp_columns": list(self.timestamp_columns),
            "nonnullable": list(self.nonnullable),
            "allowed_values": {
                key: list(values) for key, values in (self.allowed_values or {}).items()
            },
            "dynamic_features": self.dynamic_features,
        }

    @property
    def sha256(self) -> str:
        return hashlib.sha256(
            json.dumps(self.json(), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


_SILVER_REQUIRED: dict[str, tuple[str, ...]] = {
    "teams": ("team_id", "team"),
    "team_aliases": ("provider", "provider_name", "team"),
    "venues": ("venue_id", "name"),
    "schedule_revisions": ("season", "game_id", "kickoff_utc"),
    "games": (
        "season",
        "game_id",
        "week",
        "provider_week",
        "kickoff_utc",
        "home_team",
        "away_team",
    ),
    "schedule_week_policy": (
        "season",
        "game_id",
        "provider_week",
        "canonical_week",
        "kickoff_utc",
    ),
    "game_outcomes": ("season", "game_id", "completed", "home_points", "away_points"),
    "plays": ("season", "week", "game_id", "play_id"),
    "team_game_stats": ("season", "week", "game_id", "team"),
    "reconciled_team_game": ("season", "game_id", "team"),
    "market_quotes": ("quote_id", "game_id", "provider", "captured_at"),
    "market_snapshots": ("market_snapshot_id", "game_id", "market_captured_at"),
    "legacy_market_references": (
        "season",
        "game_id",
        "provider",
        "provider_week",
        "source_capture_id",
        "source_uri",
        "source_sha256",
        "timestamp_status",
        "exact_replay_eligible",
        "grading_eligible",
        "lean_eligible",
    ),
    "weather_observations": ("game_id", "observed_at"),
    "preseason_team_inputs": ("season", "team", "as_of"),
    "data_corrections": (
        "correction_id",
        "dataset",
        "record_key",
        "changed_field",
        "old_value",
        "new_value",
        "reason",
        "source",
        "approved_by",
        "approved_at",
    ),
}

_SILVER_KEYS: dict[str, tuple[str, ...]] = {
    "teams": ("team_id",),
    "team_aliases": ("provider", "provider_name"),
    "venues": ("venue_id",),
    "schedule_revisions": ("season", "game_id", "captured_at"),
    "games": ("season", "game_id"),
    "schedule_week_policy": ("season", "game_id"),
    "game_outcomes": ("season", "game_id"),
    "plays": ("game_id", "play_id"),
    "team_game_stats": ("season", "game_id", "team"),
    "reconciled_team_game": ("season", "game_id", "team"),
    "market_quotes": ("quote_id",),
    "market_snapshots": ("market_snapshot_id",),
    "legacy_market_references": ("game_id", "provider", "source_capture_id"),
    "weather_observations": ("game_id", "observed_at"),
    "preseason_team_inputs": ("season", "team", "as_of"),
    "data_corrections": ("correction_id",),
}

_GOLD_REQUIRED: dict[str, tuple[str, ...]] = {
    "temporal_matchup_inputs": ("season", "game_id"),
    "point_in_time_team_features": ("season", "game_id", "team"),
    "point_in_time_matchups": ("season", "game_id"),
    "baseline_predictions_oof": ("season", "game_id"),
}


def schema_for(dataset: str, schema_version: str) -> DatasetSchema:
    """Return the executable contract for every active immutable dataset."""
    if dataset in _SILVER_REQUIRED:
        required = _SILVER_REQUIRED[dataset]
        integer = tuple(
            c
            for c in required
            if c
            in {
                "season",
                "week",
                "provider_week",
                "canonical_week",
                "game_id",
                "play_id",
                "team_id",
                "venue_id",
            }
        )
        boolean = tuple(
            c
            for c in required
            if c
            in {
                "completed",
                "exact_replay_eligible",
                "grading_eligible",
                "lean_eligible",
            }
        )
        timestamps = tuple(
            c
            for c in required
            if c.endswith("_at")
            or c
            in {"kickoff_utc", "as_of", "observed_at", "captured_at", "approved_at"}
        )
        allowed = (
            {"timestamp_status": ("missing_authentic_timestamp",)}
            if dataset == "legacy_market_references"
            else {}
        )
        return DatasetSchema(
            dataset,
            schema_version,
            required,
            _SILVER_KEYS[dataset],
            integer,
            boolean,
            timestamps,
            _SILVER_KEYS[dataset],
            allowed,
        )
    if dataset in _GOLD_REQUIRED:
        required = _GOLD_REQUIRED[dataset]
        return DatasetSchema(
            dataset,
            schema_version,
            required,
            required,
            ("season", "game_id"),
            (),
            (),
            required,
            {},
            True,
        )
    raise DatasetSchemaError(
        f"No executable schema registered for {dataset}/{schema_version}"
    )


def validate_frame(frame: pd.DataFrame, schema: DatasetSchema) -> dict[str, Any]:
    """Validate named fields and reject non-scalar data before immutable writes."""
    missing = sorted(set(schema.required) - set(frame.columns))
    if missing:
        raise DatasetSchemaError(f"{schema.dataset} missing columns: {missing}")
    null_columns = [
        column for column in schema.nonnullable if frame[column].isna().any()
    ]
    if null_columns:
        raise DatasetSchemaError(
            f"{schema.dataset} has null required values: {null_columns}"
        )
    duplicate_count = int(frame.duplicated(list(schema.keys)).sum())
    if duplicate_count:
        raise DatasetSchemaError(
            f"{schema.dataset} has {duplicate_count} duplicate keys"
        )
    for column in schema.integer_columns:
        values = pd.to_numeric(frame[column], errors="coerce")
        if values.isna().any() or not (values.dropna() % 1 == 0).all():
            raise DatasetSchemaError(f"{schema.dataset}.{column} must be integral")
    for column in schema.boolean_columns:
        if not pd.api.types.is_bool_dtype(frame[column]):
            values = set(frame[column].dropna().tolist())
            if not values.issubset({True, False}):
                raise DatasetSchemaError(f"{schema.dataset}.{column} must be boolean")
    for column in schema.timestamp_columns:
        if pd.to_datetime(frame[column], utc=True, errors="coerce").isna().any():
            raise DatasetSchemaError(
                f"{schema.dataset}.{column} must be timestamp-like"
            )
    for column, allowed in (schema.allowed_values or {}).items():
        if not set(frame[column].dropna().astype(str)).issubset(set(map(str, allowed))):
            raise DatasetSchemaError(
                f"{schema.dataset}.{column} has unsupported values"
            )
    for column in frame.columns:
        if frame[column].map(lambda value: isinstance(value, (dict, list, set))).any():
            raise DatasetSchemaError(
                f"{schema.dataset}.{column} contains nested values"
            )
    if schema.dynamic_features:
        metadata = set(schema.required) | {
            "week",
            "kickoff_utc",
            "start_date",
            "home_team",
            "away_team",
            "team",
            "opponent",
            "regime",
            "as_of",
        }
        dynamic = [column for column in frame.columns if column not in metadata]
        nonnumeric = [
            column
            for column in dynamic
            if not (
                pd.api.types.is_numeric_dtype(frame[column])
                or pd.api.types.is_bool_dtype(frame[column])
                or pd.api.types.is_datetime64_any_dtype(frame[column])
            )
        ]
        if nonnumeric:
            raise DatasetSchemaError(
                f"{schema.dataset} has non-feature dynamic columns: {nonnumeric}"
            )
    return {
        "schema_valid": True,
        "schema_sha": schema.sha256,
        "schema_version": schema.schema_version,
    }
