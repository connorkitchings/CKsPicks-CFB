"""Isolated rating-successor research package (Phase 1: measurements only).

This namespace must never be imported from V4 feature, bundle, ops, or
publication paths. Phase 1 provides measurement contracts, raw observations,
pregame adjusted snapshots, and audit tooling only — no rating estimator,
prediction, or production activation lives here.
"""

from cks_picks_cfb.ratings.contracts import (
    ADJUSTMENT_METHOD_ADJUSTED,
    ADJUSTMENT_METHOD_NONE,
    BASELINE_MEASUREMENT_IDS,
    OBSERVATION_COLUMNS,
    OBSERVATION_DATASET,
    OBSERVATION_KEYS,
    OBSERVATION_SCHEMA_VERSION,
    SNAPSHOT_COLUMNS,
    SNAPSHOT_DATASET,
    SNAPSHOT_KEYS,
    SNAPSHOT_SCHEMA_VERSION,
    MeasurementConfig,
    MeasurementContractError,
    load_measurement_config,
    market_field_conflicts,
    validate_observation_frame,
    validate_snapshot_frame,
    verify_design_id,
)

__all__ = [
    "ADJUSTMENT_METHOD_ADJUSTED",
    "ADJUSTMENT_METHOD_NONE",
    "BASELINE_MEASUREMENT_IDS",
    "OBSERVATION_COLUMNS",
    "OBSERVATION_DATASET",
    "OBSERVATION_KEYS",
    "OBSERVATION_SCHEMA_VERSION",
    "SNAPSHOT_COLUMNS",
    "SNAPSHOT_DATASET",
    "SNAPSHOT_KEYS",
    "SNAPSHOT_SCHEMA_VERSION",
    "MeasurementConfig",
    "MeasurementContractError",
    "load_measurement_config",
    "market_field_conflicts",
    "validate_observation_frame",
    "validate_snapshot_frame",
    "verify_design_id",
]
