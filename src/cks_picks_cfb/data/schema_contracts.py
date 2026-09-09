"""Executable dataset schemas for immutable Silver and Gold datasets."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from typing import Any, Mapping

import pandas as pd

from cks_picks_cfb.data.data_first_phase3 import (
    PHASE3_ADJUSTED_COLUMNS,
    PHASE3_ADJUSTED_DATASET,
    PHASE3_ADJUSTED_SCHEMA,
    PHASE3_ATTRIBUTION_COLUMNS,
    PHASE3_ATTRIBUTION_DATASET,
    PHASE3_ATTRIBUTION_SCHEMA,
    PHASE3_OBSERVATION_DATASET,
    PHASE3_OBSERVATION_SCHEMA,
    PHASE3_PREDICTION_COLUMNS,
    PHASE3_PREDICTION_DATASET,
    PHASE3_PREDICTION_SCHEMA,
)
from cks_picks_cfb.data.data_first_phase4a import (
    ATTRIBUTION_COLUMNS as PHASE4A_ATTRIBUTION_COLUMNS,
)
from cks_picks_cfb.data.data_first_phase4a import (
    PHASE4A_ATTRIBUTION_DATASET,
    PHASE4A_ATTRIBUTION_SCHEMA,
    PHASE4A_PREDICTION_DATASET,
    PHASE4A_PREDICTION_SCHEMA,
    PHASE4A_RATING_STATE_DATASET,
    PHASE4A_RATING_STATE_SCHEMA,
    PHASE4A_TEAM_STATE_DATASET,
    PHASE4A_TEAM_STATE_SCHEMA,
)
from cks_picks_cfb.data.data_first_phase4a import (
    PREDICTION_COLUMNS as PHASE4A_PREDICTION_COLUMNS,
)
from cks_picks_cfb.data.data_first_phase4a import (
    RATING_STATE_COLUMNS as PHASE4A_RATING_STATE_COLUMNS,
)
from cks_picks_cfb.data.data_first_phase4a import (
    TEAM_STATE_COLUMNS as PHASE4A_TEAM_STATE_COLUMNS,
)
from cks_picks_cfb.data.data_first_phase4b import (
    ATTRIBUTION_COLUMNS as PHASE4B_ATTRIBUTION_COLUMNS,
)
from cks_picks_cfb.data.data_first_phase4b import (
    COVERAGE_COLUMNS as PHASE4B_COVERAGE_COLUMNS,
)
from cks_picks_cfb.data.data_first_phase4b import (
    PHASE4B_ATTRIBUTION_DATASET,
    PHASE4B_ATTRIBUTION_SCHEMA,
    PHASE4B_COVERAGE_DATASET,
    PHASE4B_COVERAGE_SCHEMA,
    PHASE4B_PREDICTION_DATASET,
    PHASE4B_PREDICTION_SCHEMA,
)
from cks_picks_cfb.data.data_first_phase4b import (
    PREDICTION_COLUMNS as PHASE4B_PREDICTION_COLUMNS,
)
from cks_picks_cfb.data.data_first_repair_v2 import (
    AUXILIARY_COLUMNS as REPAIR_AUXILIARY_COLUMNS,
)
from cks_picks_cfb.data.data_first_repair_v2 import (
    CAPTURE_PLAN_COLUMNS as REPAIR_CAPTURE_PLAN_COLUMNS,
)
from cks_picks_cfb.data.data_first_repair_v2 import (
    COVERAGE_COLUMNS as REPAIR_COVERAGE_COLUMNS,
)
from cks_picks_cfb.data.data_first_repair_v2 import (
    ISSUE_COLUMNS as REPAIR_ISSUE_COLUMNS,
)
from cks_picks_cfb.data.data_first_repair_v2 import (
    POPULATION_COLUMNS as REPAIR_POPULATION_COLUMNS,
)
from cks_picks_cfb.data.data_first_repair_v2 import (
    REPAIR_AUXILIARY_DATASET,
    REPAIR_AUXILIARY_SCHEMA,
    REPAIR_CAPTURE_PLAN_DATASET,
    REPAIR_CAPTURE_PLAN_SCHEMA,
    REPAIR_COVERAGE_DATASET,
    REPAIR_COVERAGE_SCHEMA,
    REPAIR_ISSUE_DATASET,
    REPAIR_ISSUE_SCHEMA,
    REPAIR_POPULATION_DATASET,
    REPAIR_POPULATION_SCHEMA,
)
from cks_picks_cfb.ratings.contracts import (
    OBSERVATION_COLUMNS,
    OBSERVATION_KEYS,
    OBSERVATION_SCHEMA_VERSION,
    SNAPSHOT_COLUMNS,
    SNAPSHOT_KEYS,
    SNAPSHOT_SCHEMA_VERSION,
    TERMINAL_SNAPSHOT_COLUMNS,
    TERMINAL_SNAPSHOT_KEYS,
    TERMINAL_SNAPSHOT_SCHEMA_VERSION,
)
from cks_picks_cfb.ratings.state_contracts import (
    MEASUREMENT_STATE_COLUMNS,
    MEASUREMENT_STATE_DATASET,
    MEASUREMENT_STATE_KEYS,
    MEASUREMENT_STATE_SCHEMA_VERSION,
    TEAM_STATE_COLUMNS,
    TEAM_STATE_DATASET,
    TEAM_STATE_KEYS,
    TEAM_STATE_SCHEMA_VERSION,
)
from cks_picks_cfb.ratings.v4_benchmark import (
    BENCHMARK_COLUMNS,
    BENCHMARK_KEYS,
    V4_BENCHMARK_SCHEMA_VERSION,
)


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
    "fbs_involved_games": (
        "season",
        "game_id",
        "week",
        "provider_week",
        "kickoff_utc",
        "home_team",
        "away_team",
        "season_type",
        "population",
        "classification_unresolved",
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
    "fbs_involved_games": ("season", "game_id"),
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
    "v4_preseason_team_features": ("season", "team"),
    "point_in_time_matchups_v5": ("season", "game_id"),
}

_DERIVED_SILVER_SCHEMAS: dict[str, DatasetSchema] = {
    "byplay": DatasetSchema(
        dataset="byplay",
        schema_version="byplay_v1",
        required=(
            "season",
            "week",
            "game_id",
            "drive_number",
            "play_number",
            "offense",
            "defense",
            "st",
            "penalty",
            "twopoint",
            "play_type",
            "garbage",
            "ppa",
            "success",
            "yards_gained",
            "turnover",
            "quarter",
            "offense_score",
            "defense_score",
        ),
        keys=("game_id", "drive_number", "play_number"),
        integer_columns=(
            "season",
            "week",
            "game_id",
            "drive_number",
            "play_number",
            "quarter",
        ),
        nonnullable=(
            "season",
            "week",
            "game_id",
            "drive_number",
            "play_number",
            "offense",
            "defense",
            "quarter",
        ),
    ),
    "drives": DatasetSchema(
        dataset="drives",
        schema_version="drives_v1",
        required=(
            "season",
            "week",
            "game_id",
            "drive_number",
            "offense",
            "defense",
            "start_yards_to_goal",
            "had_scoring_opportunity",
            "points",
            "points_on_opps",
        ),
        keys=("game_id", "drive_number", "offense", "defense"),
        integer_columns=("season", "week", "game_id", "drive_number"),
        nonnullable=(
            "season",
            "week",
            "game_id",
            "drive_number",
            "offense",
            "defense",
        ),
    ),
    "source_reconciliation": DatasetSchema(
        dataset="source_reconciliation",
        schema_version="reconciliation_v1",
        required=(
            "reconciliation_id",
            "season",
            "game_id",
            "classification",
            "blocking",
            "details",
            "policy_version",
        ),
        keys=("reconciliation_id",),
        integer_columns=("season", "game_id"),
        boolean_columns=("blocking",),
        nonnullable=(
            "reconciliation_id",
            "season",
            "game_id",
            "classification",
            "blocking",
            "details",
            "policy_version",
        ),
        allowed_values={
            "classification": (
                "exact_match",
                "incomplete_source",
                "blocking_conflict",
            )
        },
    ),
}

_PHASE2E_SCHEMAS: dict[str, DatasetSchema] = {
    "phase2e_recruiting": DatasetSchema(
        dataset="phase2e_recruiting",
        schema_version="phase2e_recruiting_v1",
        required=(
            "season",
            "team",
            "recruiting_4yr",
            "recruiting_current",
            "recruiting_trend",
            "missing_reason",
            "timing_class",
        ),
        keys=("season", "team"),
        integer_columns=("season",),
        nonnullable=("season", "team", "timing_class"),
        allowed_values={"timing_class": ("historically_reconstructed",)},
    ),
    "phase2e_returning_production": DatasetSchema(
        dataset="phase2e_returning_production",
        schema_version="phase2e_returning_production_v1",
        required=(
            "season",
            "team",
            "return_total_ppa",
            "return_passing_ppa",
            "return_rushing_ppa",
            "return_receiving_ppa",
            "return_percent_ppa",
            "return_passing_usage",
            "return_rushing_usage",
            "missing_reason",
            "timing_class",
        ),
        keys=("season", "team"),
        integer_columns=("season",),
        nonnullable=("season", "team", "timing_class"),
        allowed_values={"timing_class": ("historically_reconstructed",)},
    ),
    "phase2e_coaching": DatasetSchema(
        dataset="phase2e_coaching",
        schema_version="phase2e_coaching_v1",
        required=(
            "season",
            "team",
            "coach_tenure",
            "coach_new",
            "missing_reason",
            "timing_class",
        ),
        keys=("season", "team"),
        integer_columns=("season",),
        boolean_columns=("coach_new",),
        nonnullable=("season", "team", "timing_class"),
        allowed_values={"timing_class": ("historically_reconstructed",)},
    ),
    "phase2e_roster_continuity": DatasetSchema(
        dataset="phase2e_roster_continuity",
        schema_version="phase2e_roster_continuity_v1",
        required=(
            "season",
            "team",
            "roster_size",
            "roster_returning_share",
            "roster_returning_qb_count",
            "identity_exclusion_count",
            "missing_reason",
            "timing_class",
        ),
        keys=("season", "team"),
        integer_columns=("season", "identity_exclusion_count"),
        nonnullable=("season", "team", "identity_exclusion_count", "timing_class"),
        allowed_values={"timing_class": ("historically_reconstructed",)},
    ),
    "phase2e_lagged_rankings": DatasetSchema(
        dataset="phase2e_lagged_rankings",
        schema_version="phase2e_lagged_rankings_v1",
        required=(
            "season",
            "week",
            "game_id",
            "team",
            "lagged_ap_rank",
            "lagged_coaches_rank",
            "lagged_ranked_either",
            "missing_reason",
            "timing_class",
        ),
        keys=("season", "game_id", "team"),
        integer_columns=("season", "week", "game_id"),
        nonnullable=("season", "week", "game_id", "team", "timing_class"),
        allowed_values={"timing_class": ("historically_reconstructed",)},
    ),
    "phase2e_market_references": DatasetSchema(
        dataset="phase2e_market_references",
        schema_version="phase2e_market_references_v1",
        required=(
            "game_id",
            "spread_line",
            "total_line",
            "market_policy_version",
            "spread_selection_rule",
            "total_selection_rule",
            "spread_provider_count",
            "total_provider_count",
            "source_quote_ids",
            "market_snapshot_id",
            "market_captured_at",
            "timing_class",
            "usage",
        ),
        keys=("market_snapshot_id",),
        integer_columns=("game_id", "spread_provider_count", "total_provider_count"),
        timestamp_columns=("market_captured_at",),
        nonnullable=(
            "game_id",
            "market_policy_version",
            "source_quote_ids",
            "market_snapshot_id",
            "market_captured_at",
            "timing_class",
            "usage",
        ),
        allowed_values={
            "timing_class": ("historically_reconstructed",),
            "usage": ("post_phase5_diagnostic_only",),
        },
    ),
}

_REPAIR_V2_SCHEMAS: dict[str, DatasetSchema] = {
    REPAIR_POPULATION_DATASET: DatasetSchema(
        dataset=REPAIR_POPULATION_DATASET,
        schema_version=REPAIR_POPULATION_SCHEMA,
        required=REPAIR_POPULATION_COLUMNS,
        keys=("season", "game_id"),
        integer_columns=("season", "week", "game_id", "measurement_exposure"),
        boolean_columns=(
            "schedule_completed",
            "outcome_valid",
            "forecast_eligible",
            "measurement_usable",
        ),
        timestamp_columns=("kickoff_utc",),
        nonnullable=(
            "season",
            "week",
            "game_id",
            "kickoff_utc",
            "home_team",
            "away_team",
            "schedule_completed",
            "outcome_valid",
            "forecast_eligible",
            "measurement_usable",
            "measurement_exposure",
            "missing_measurement_sources",
            "disposition",
            "timing_class",
        ),
        allowed_values={"timing_class": ("historically_reconstructed",)},
    ),
    REPAIR_AUXILIARY_DATASET: DatasetSchema(
        dataset=REPAIR_AUXILIARY_DATASET,
        schema_version=REPAIR_AUXILIARY_SCHEMA,
        required=REPAIR_AUXILIARY_COLUMNS,
        keys=("family", "season", "team"),
        integer_columns=("season",),
        boolean_columns=(
            "historical_eligible",
            "live_eligible",
            "coach_tenure_censored",
            "coach_new",
        ),
        nonnullable=(
            "family",
            "season",
            "team",
            "timing_class",
            "historical_eligible",
            "live_eligible",
            "permitted_role",
            "source_capture_ids",
        ),
        allowed_values={"timing_class": ("historically_reconstructed",)},
    ),
    REPAIR_COVERAGE_DATASET: DatasetSchema(
        dataset=REPAIR_COVERAGE_DATASET,
        schema_version=REPAIR_COVERAGE_SCHEMA,
        required=REPAIR_COVERAGE_COLUMNS,
        keys=("family", "season", "slice"),
        integer_columns=(
            "season",
            "required_rows",
            "non_null_rows",
            "missing_rows",
            "distinct_values",
            "ambiguity_rows",
            "structural_missing_rows",
        ),
        boolean_columns=("constant_warning", "historical_eligible", "live_eligible"),
        nonnullable=REPAIR_COVERAGE_COLUMNS,
        allowed_values={"timing_class": ("historically_reconstructed",)},
    ),
    REPAIR_ISSUE_DATASET: DatasetSchema(
        dataset=REPAIR_ISSUE_DATASET,
        schema_version=REPAIR_ISSUE_SCHEMA,
        required=REPAIR_ISSUE_COLUMNS,
        keys=("issue_id", "affected_key"),
        boolean_columns=("outcome_valid", "core_blocker", "resolved"),
        nonnullable=(
            "issue_id",
            "affected_key",
            "category",
            "core_blocker",
            "resolved",
            "details",
        ),
    ),
    REPAIR_CAPTURE_PLAN_DATASET: DatasetSchema(
        dataset=REPAIR_CAPTURE_PLAN_DATASET,
        schema_version=REPAIR_CAPTURE_PLAN_SCHEMA,
        required=REPAIR_CAPTURE_PLAN_COLUMNS,
        keys=("request_id",),
        integer_columns=(
            "max_attempts",
            "max_total_requests",
            "attempt_count",
            "row_count",
        ),
        nonnullable=(
            "request_id",
            "provider",
            "entity",
            "endpoint",
            "parameters",
            "reason",
            "existing_captures_checked",
            "max_attempts",
            "max_total_requests",
            "state",
            "attempt_count",
            "timing_class",
        ),
        allowed_values={"timing_class": ("historically_reconstructed",)},
    ),
}

_RATING_SCHEMA_BASES: dict[str, DatasetSchema] = {
    "rating_measurement_observations": DatasetSchema(
        dataset="rating_measurement_observations",
        schema_version=OBSERVATION_SCHEMA_VERSION,
        required=OBSERVATION_COLUMNS,
        keys=OBSERVATION_KEYS,
        integer_columns=("season", "week", "game_id"),
        timestamp_columns=("kickoff_utc",),
        nonnullable=(
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
            "exposure_unit",
            "temporal_status",
            "coverage_status",
            "measurement_schema_version",
            "measurement_design_id",
            "parent_ref_shas",
            "code_sha",
            "config_sha",
        ),
        allowed_values={
            "side": ("home", "away"),
            "unit_role": ("offense", "defense"),
            "temporal_status": ("reconstructed", "authentic"),
            "coverage_status": ("observed", "missing"),
            "exposure_unit": ("plays", "drives", "opportunities"),
        },
    ),
    "rating_adjusted_measurement_snapshots": DatasetSchema(
        dataset="rating_adjusted_measurement_snapshots",
        schema_version=SNAPSHOT_SCHEMA_VERSION,
        required=SNAPSHOT_COLUMNS,
        keys=SNAPSHOT_KEYS,
        integer_columns=(
            "season",
            "week",
            "as_of_game_id",
            "games_exposure",
            "included_observations",
            "adjustment_iteration",
        ),
        timestamp_columns=("as_of_kickoff_utc",),
        nonnullable=(
            "season",
            "week",
            "as_of_game_id",
            "as_of_kickoff_utc",
            "team",
            "measurement_id",
            "unit_role",
            "games_exposure",
            "primary_exposure",
            "included_observations",
            "adjustment_method",
            "adjustment_iteration",
            "coverage_status",
            "measurement_schema_version",
            "measurement_design_id",
            "parent_observation_version_id",
            "parent_ref_shas",
            "code_sha",
            "config_sha",
        ),
        allowed_values={
            "unit_role": ("offense", "defense"),
            "coverage_status": ("observed", "missing"),
            "adjustment_method": (
                "iterative_additive_league_centered",
                "none",
            ),
        },
    ),
    "rating_adjusted_measurement_terminal_snapshots": DatasetSchema(
        dataset="rating_adjusted_measurement_terminal_snapshots",
        schema_version=TERMINAL_SNAPSHOT_SCHEMA_VERSION,
        required=TERMINAL_SNAPSHOT_COLUMNS,
        keys=TERMINAL_SNAPSHOT_KEYS,
        integer_columns=(
            "season",
            "games_exposure",
            "included_observations",
            "adjustment_iteration",
        ),
        timestamp_columns=("terminal_at_utc",),
        nonnullable=(
            "season",
            "terminal_at_utc",
            "team",
            "measurement_id",
            "unit_role",
            "games_exposure",
            "primary_exposure",
            "included_observations",
            "adjustment_method",
            "adjustment_iteration",
            "coverage_status",
            "measurement_schema_version",
            "measurement_design_id",
            "parent_observation_version_id",
            "parent_ref_shas",
            "code_sha",
            "config_sha",
        ),
        allowed_values={
            "unit_role": ("offense", "defense"),
            "coverage_status": ("observed", "missing"),
            "adjustment_method": ("iterative_additive_league_centered", "none"),
        },
    ),
    MEASUREMENT_STATE_DATASET: DatasetSchema(
        dataset=MEASUREMENT_STATE_DATASET,
        schema_version=MEASUREMENT_STATE_SCHEMA_VERSION,
        required=MEASUREMENT_STATE_COLUMNS,
        keys=MEASUREMENT_STATE_KEYS,
        integer_columns=("season", "week", "completed_games"),
        timestamp_columns=("as_of_utc",),
        nonnullable=(
            "state_id",
            "state_kind",
            "season",
            "week",
            "as_of_utc",
            "team",
            "measurement_id",
            "unit_role",
            "standardization_center",
            "standardization_scale",
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
            "state_schema_version",
            "state_design_id",
            "parent_measurement_refs",
            "code_sha",
            "config_sha",
        ),
        allowed_values={
            "state_kind": ("pregame", "season_terminal"),
            "unit_role": ("offense", "defense"),
        },
    ),
    TEAM_STATE_DATASET: DatasetSchema(
        dataset=TEAM_STATE_DATASET,
        schema_version=TEAM_STATE_SCHEMA_VERSION,
        required=TEAM_STATE_COLUMNS,
        keys=TEAM_STATE_KEYS,
        integer_columns=("season", "week", "completed_games", "component_count"),
        timestamp_columns=("as_of_utc",),
        nonnullable=(
            "state_id",
            "state_kind",
            "season",
            "week",
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
            "state_schema_version",
            "state_design_id",
            "parent_measurement_refs",
            "code_sha",
            "config_sha",
        ),
        allowed_values={"state_kind": ("pregame", "season_terminal")},
    ),
    "rating_shadow_measurement_states": DatasetSchema(
        dataset="rating_shadow_measurement_states",
        schema_version="rating_shadow_measurement_states_v1",
        required=MEASUREMENT_STATE_COLUMNS,
        keys=MEASUREMENT_STATE_KEYS,
        integer_columns=("season", "week", "completed_games"),
        timestamp_columns=("as_of_utc",),
        nonnullable=(
            "state_id",
            "season",
            "week",
            "as_of_utc",
            "team",
            "measurement_id",
            "unit_role",
        ),
    ),
    "rating_shadow_team_states": DatasetSchema(
        dataset="rating_shadow_team_states",
        schema_version="rating_shadow_team_states_v1",
        required=TEAM_STATE_COLUMNS,
        keys=TEAM_STATE_KEYS,
        integer_columns=("season", "week", "completed_games", "component_count"),
        timestamp_columns=("as_of_utc",),
        nonnullable=("state_id", "season", "week", "as_of_utc", "team"),
    ),
}

# Historical rating datasets were sealed under schema versions this registry
# never learned: the lake write path tolerates unknown versions and records
# ``schema_sha: null``, which left the objects writable but unregistrable.
# The corrected Phase 1 audit reproduced those registration gaps, so each
# additional version below reuses its dataset's sealed column contract, and
# the four datasets after the version map were derived from the sealed
# objects' parquet columns and their writer contracts.
_RATING_SCHEMA_EXTRA_VERSIONS: dict[str, tuple[str, ...]] = {
    "rating_measurement_observations": ("rating_measurement_observations_v3",),
    "rating_adjusted_measurement_snapshots": (
        "rating_adjusted_measurement_snapshots_v3",
    ),
    "rating_adjusted_measurement_terminal_snapshots": (
        "rating_adjusted_measurement_terminal_snapshots_v2",
    ),
    MEASUREMENT_STATE_DATASET: (
        "rating_measurement_states_v2",
        "rating_measurement_states_v3",
    ),
    TEAM_STATE_DATASET: ("rating_team_states_v2", "rating_team_states_v3"),
}

_SCORE_PREDICTION_COLUMNS = (
    "season",
    "week",
    "game_id",
    "kickoff_utc",
    "home_state_id",
    "away_state_id",
    "home_completed_games",
    "away_completed_games",
    "home_pace_source",
    "away_pace_source",
    "fold_id",
    "score_model_family",
    "predicted_home_score",
    "predicted_away_score",
    "home_score_sd",
    "away_score_sd",
    "score_covariance",
    "distribution_family",
    "target",
    "actual",
    "prediction_mean",
    "prediction_sd",
    "interval_50_lower",
    "interval_50_upper",
    "interval_80_lower",
    "interval_80_upper",
    "interval_95_lower",
    "interval_95_upper",
)

_SCORE_PREDICTION_NONNULLABLE = (
    "season",
    "week",
    "game_id",
    "kickoff_utc",
    "home_state_id",
    "away_state_id",
    "fold_id",
    "score_model_family",
    "predicted_home_score",
    "predicted_away_score",
    "distribution_family",
    "target",
    "prediction_mean",
    "prediction_sd",
)

_RATING_SCHEMA_BASES.update(
    {
        PHASE3_OBSERVATION_DATASET: DatasetSchema(
            dataset=PHASE3_OBSERVATION_DATASET,
            schema_version=PHASE3_OBSERVATION_SCHEMA,
            required=OBSERVATION_COLUMNS,
            keys=OBSERVATION_KEYS,
            integer_columns=("season", "week", "game_id"),
            timestamp_columns=("kickoff_utc",),
            nonnullable=(
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
                "exposure_unit",
                "temporal_status",
                "coverage_status",
                "measurement_schema_version",
                "measurement_design_id",
                "parent_ref_shas",
                "code_sha",
                "config_sha",
            ),
            allowed_values={
                "unit_role": ("offense", "defense"),
                "coverage_status": ("observed", "missing"),
            },
        ),
        PHASE3_ADJUSTED_DATASET: DatasetSchema(
            dataset=PHASE3_ADJUSTED_DATASET,
            schema_version=PHASE3_ADJUSTED_SCHEMA,
            required=PHASE3_ADJUSTED_COLUMNS,
            keys=(
                "season",
                "as_of_game_id",
                "team",
                "measurement_id",
                "unit_role",
                "recency_mode",
                "adjustment_iteration",
            ),
            integer_columns=(
                "season",
                "week",
                "as_of_game_id",
                "games_exposure",
                "adjustment_iteration",
            ),
            timestamp_columns=("as_of_kickoff_utc",),
            nonnullable=(
                "season",
                "week",
                "as_of_game_id",
                "as_of_kickoff_utc",
                "team",
                "measurement_id",
                "unit_role",
                "recency_mode",
                "adjustment_iteration",
                "numerator",
                "denominator",
                "primary_exposure",
                "games_exposure",
                "coverage_status",
                "parent_identity_sha",
                "code_sha",
                "config_sha",
            ),
            allowed_values={
                "unit_role": ("offense", "defense"),
                "recency_mode": ("primary", "half_life_4_games"),
                "coverage_status": ("observed", "missing"),
            },
        ),
        PHASE3_PREDICTION_DATASET: DatasetSchema(
            dataset=PHASE3_PREDICTION_DATASET,
            schema_version=PHASE3_PREDICTION_SCHEMA,
            required=PHASE3_PREDICTION_COLUMNS,
            keys=("season", "game_id", "candidate", "recency_mode", "target"),
            integer_columns=("season", "week", "game_id", "fallback_count"),
            timestamp_columns=("kickoff_utc",),
            boolean_columns=("feature_fallback",),
            nonnullable=PHASE3_PREDICTION_COLUMNS,
            allowed_values={
                "recency_mode": ("primary", "half_life_4_games"),
                "target": ("margin", "total"),
            },
        ),
        PHASE3_ATTRIBUTION_DATASET: DatasetSchema(
            dataset=PHASE3_ATTRIBUTION_DATASET,
            schema_version=PHASE3_ATTRIBUTION_SCHEMA,
            required=PHASE3_ATTRIBUTION_COLUMNS,
            keys=("candidate",),
            integer_columns=(
                "component_count",
                "validation_rows",
                "validation_games",
                "fallback_rows",
            ),
            boolean_columns=(
                "bootstrap_excludes_zero",
                "coverage_equal",
                "seasonal_gate_passed",
                "sensitivity_gate_passed",
                "primary_gate_passed",
                "selected",
            ),
            nonnullable=PHASE3_ATTRIBUTION_COLUMNS,
        ),
        PHASE4A_RATING_STATE_DATASET: DatasetSchema(
            dataset=PHASE4A_RATING_STATE_DATASET,
            schema_version=PHASE4A_RATING_STATE_SCHEMA,
            required=PHASE4A_RATING_STATE_COLUMNS,
            keys=("candidate", "season", "game_id", "team", "unit_role"),
            integer_columns=(
                "season",
                "week",
                "game_id",
                "annual_decay_steps",
                "completed_games",
            ),
            boolean_columns=("fallback_used",),
            timestamp_columns=("kickoff_utc",),
            nonnullable=(
                "candidate",
                "season",
                "week",
                "game_id",
                "kickoff_utc",
                "team",
                "unit_role",
                "prior_source",
                "annual_decay_steps",
                "standardization_center",
                "standardization_scale",
                "effective_exposure",
                "completed_games",
                "prior_mean",
                "prior_variance",
                "prior_precision",
                "observed_precision",
                "posterior_mean",
                "posterior_variance",
                "posterior_sd",
                "movement",
                "fallback_used",
                "parent_identity_sha",
                "code_sha",
                "config_sha",
            ),
            allowed_values={
                "unit_role": ("offense", "defense"),
                "prior_source": ("neutral", "fixed_rho"),
            },
        ),
        PHASE4A_TEAM_STATE_DATASET: DatasetSchema(
            dataset=PHASE4A_TEAM_STATE_DATASET,
            schema_version=PHASE4A_TEAM_STATE_SCHEMA,
            required=PHASE4A_TEAM_STATE_COLUMNS,
            keys=("candidate", "season", "game_id", "team"),
            integer_columns=("season", "week", "game_id"),
            boolean_columns=("offense_fallback", "defense_fallback"),
            timestamp_columns=("kickoff_utc",),
            nonnullable=PHASE4A_TEAM_STATE_COLUMNS,
        ),
        PHASE4A_PREDICTION_DATASET: DatasetSchema(
            dataset=PHASE4A_PREDICTION_DATASET,
            schema_version=PHASE4A_PREDICTION_SCHEMA,
            required=PHASE4A_PREDICTION_COLUMNS,
            keys=("candidate", "season", "game_id", "target"),
            integer_columns=("season", "week", "game_id", "fallback_count"),
            boolean_columns=("feature_fallback",),
            timestamp_columns=("kickoff_utc",),
            nonnullable=PHASE4A_PREDICTION_COLUMNS,
            allowed_values={"target": ("margin", "total")},
        ),
        PHASE4A_ATTRIBUTION_DATASET: DatasetSchema(
            dataset=PHASE4A_ATTRIBUTION_DATASET,
            schema_version=PHASE4A_ATTRIBUTION_SCHEMA,
            required=PHASE4A_ATTRIBUTION_COLUMNS,
            keys=("candidate",),
            integer_columns=("mechanism_count", "validation_rows", "validation_games"),
            boolean_columns=(
                "bootstrap_excludes_zero",
                "coverage_equal",
                "seasonal_gate_passed",
                "primary_gate_passed",
                "selected",
            ),
            nonnullable=PHASE4A_ATTRIBUTION_COLUMNS,
        ),
        PHASE4B_PREDICTION_DATASET: DatasetSchema(
            dataset=PHASE4B_PREDICTION_DATASET,
            schema_version=PHASE4B_PREDICTION_SCHEMA,
            required=PHASE4B_PREDICTION_COLUMNS,
            keys=("family", "target", "season", "game_id"),
            integer_columns=("season", "week", "game_id", "fallback_count"),
            boolean_columns=("feature_fallback",),
            timestamp_columns=("kickoff_utc",),
            nonnullable=PHASE4B_PREDICTION_COLUMNS,
            allowed_values={"target": ("margin", "total")},
        ),
        PHASE4B_ATTRIBUTION_DATASET: DatasetSchema(
            dataset=PHASE4B_ATTRIBUTION_DATASET,
            schema_version=PHASE4B_ATTRIBUTION_SCHEMA,
            required=PHASE4B_ATTRIBUTION_COLUMNS,
            keys=("target", "family"),
            integer_columns=("feature_count", "validation_rows", "validation_games"),
            boolean_columns=(
                "bootstrap_excludes_zero",
                "coverage_equal",
                "seasonal_gate_passed",
                "primary_gate_passed",
                "selected",
            ),
            nonnullable=PHASE4B_ATTRIBUTION_COLUMNS,
            allowed_values={"target": ("margin", "total")},
        ),
        PHASE4B_COVERAGE_DATASET: DatasetSchema(
            dataset=PHASE4B_COVERAGE_DATASET,
            schema_version=PHASE4B_COVERAGE_SCHEMA,
            required=PHASE4B_COVERAGE_COLUMNS,
            keys=("family", "target", "season"),
            integer_columns=("total_rows", "complete_rows", "imputed_rows"),
            nonnullable=PHASE4B_COVERAGE_COLUMNS,
            allowed_values={"target": ("margin", "total")},
        ),
        "rating_score_models": DatasetSchema(
            dataset="rating_score_models",
            schema_version="rating_score_models_v3",
            required=(
                "family",
                "training_seasons",
                "feature_names",
                "coefficients",
                "residual_covariance",
                "dispersion",
                "optimizer_success",
                "model_stage",
                "fold_id",
            ),
            keys=("family", "model_stage", "fold_id"),
            boolean_columns=("optimizer_success",),
            nonnullable=(
                "family",
                "training_seasons",
                "feature_names",
                "coefficients",
                "optimizer_success",
                "model_stage",
                "fold_id",
            ),
        ),
        "rating_score_predictions": DatasetSchema(
            dataset="rating_score_predictions",
            schema_version="rating_score_predictions_v3",
            required=_SCORE_PREDICTION_COLUMNS,
            keys=(
                "season",
                "game_id",
                "target",
                "fold_id",
                "score_model_family",
            ),
            integer_columns=(
                "season",
                "week",
                "game_id",
                "home_completed_games",
                "away_completed_games",
            ),
            timestamp_columns=("kickoff_utc",),
            nonnullable=_SCORE_PREDICTION_NONNULLABLE,
        ),
        "rating_shadow_predictions": DatasetSchema(
            dataset="rating_shadow_predictions",
            schema_version="rating_shadow_predictions_v1",
            required=_SCORE_PREDICTION_COLUMNS,
            keys=(
                "season",
                "game_id",
                "target",
                "fold_id",
                "score_model_family",
            ),
            integer_columns=(
                "season",
                "week",
                "game_id",
                "home_completed_games",
                "away_completed_games",
            ),
            timestamp_columns=("kickoff_utc",),
            nonnullable=_SCORE_PREDICTION_NONNULLABLE,
        ),
        "rating_shadow_evidence": DatasetSchema(
            dataset="rating_shadow_evidence",
            schema_version="rating_shadow_evidence_v1",
            required=_SCORE_PREDICTION_COLUMNS
            + (
                "v4_prediction",
                "source_kind",
                "rehearsal_only",
                "freeze_manifest_sha256",
                "scored_at",
                "candidate_absolute_error",
                "v4_absolute_error",
            ),
            keys=(
                "season",
                "game_id",
                "target",
                "fold_id",
                "score_model_family",
                "source_kind",
            ),
            integer_columns=(
                "season",
                "week",
                "game_id",
                "home_completed_games",
                "away_completed_games",
            ),
            boolean_columns=("rehearsal_only",),
            timestamp_columns=("kickoff_utc", "scored_at"),
            nonnullable=_SCORE_PREDICTION_NONNULLABLE
            + (
                "v4_prediction",
                "source_kind",
                "freeze_manifest_sha256",
                "scored_at",
            ),
        ),
        "rating_v4_historical_predictions": DatasetSchema(
            dataset="rating_v4_historical_predictions",
            schema_version=V4_BENCHMARK_SCHEMA_VERSION,
            required=BENCHMARK_COLUMNS,
            keys=BENCHMARK_KEYS,
            integer_columns=("season", "game_id"),
            nonnullable=(
                "season",
                "game_id",
                "target",
                "regime",
                "actual",
                "v4_prediction",
                "source_kind",
                "benchmark_schema_version",
                "benchmark_design_id",
            ),
        ),
    }
)

_RATING_SCHEMAS: dict[str, dict[str, DatasetSchema]] = {
    dataset: {
        base.schema_version: base,
        **{
            version: replace(base, schema_version=version)
            for version in _RATING_SCHEMA_EXTRA_VERSIONS.get(dataset, ())
        },
    }
    for dataset, base in _RATING_SCHEMA_BASES.items()
}


def schema_for(dataset: str, schema_version: str) -> DatasetSchema:
    """Return the executable contract for every active immutable dataset."""
    if dataset in _DERIVED_SILVER_SCHEMAS:
        schema = _DERIVED_SILVER_SCHEMAS[dataset]
        if schema_version != schema.schema_version:
            raise DatasetSchemaError(
                f"{dataset} must use schema version {schema.schema_version}, "
                f"got {schema_version}"
            )
        return schema
    if dataset in _PHASE2E_SCHEMAS:
        schema = _PHASE2E_SCHEMAS[dataset]
        if schema_version != schema.schema_version:
            raise DatasetSchemaError(
                f"{dataset} must use schema version {schema.schema_version}, "
                f"got {schema_version}"
            )
        return schema
    if dataset in _REPAIR_V2_SCHEMAS:
        schema = _REPAIR_V2_SCHEMAS[dataset]
        if schema_version != schema.schema_version:
            raise DatasetSchemaError(
                f"{dataset} must use schema version {schema.schema_version}, "
                f"got {schema_version}"
            )
        return schema
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
                "classification_unresolved",
            }
        )
        timestamps = tuple(
            c
            for c in required
            if c.endswith("_at")
            or c
            in {"kickoff_utc", "as_of", "observed_at", "captured_at", "approved_at"}
        )
        if dataset == "legacy_market_references":
            allowed = {"timestamp_status": ("missing_authentic_timestamp",)}
        elif dataset == "fbs_involved_games":
            allowed = {
                "population": ("fbs_fbs", "fbs_fcs", "unresolved"),
                "season_type": ("regular", "postseason"),
            }
        else:
            allowed = {}
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
            ("season",)
            if dataset == "v4_preseason_team_features"
            else ("season", "game_id"),
            (),
            (),
            required,
            {},
            True,
        )
    if dataset in _RATING_SCHEMAS:
        versions = _RATING_SCHEMAS[dataset]
        schema = versions.get(schema_version)
        if schema is None:
            raise DatasetSchemaError(
                f"{dataset} has no registered schema version {schema_version}; "
                f"known versions: {sorted(versions)}"
            )
        return schema
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
            "side",
            "regime",
            "team_regime",
            "as_of",
            "prediction_regime",
            "feature_as_of",
            "feature_provenance",
            "home_line_scores",
            "away_line_scores",
            "v4_feature_track",
            "v4_reference_sha",
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
