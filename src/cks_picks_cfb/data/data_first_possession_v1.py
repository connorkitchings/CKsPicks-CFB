"""Contracts for Preview-only V5 possession measurement certification.

This module defines only versioned data meanings and lineage checks.  It is
intentionally isolated from V4 and from the historical Phase 3 artifacts.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import timedelta
from typing import Any

import pandas as pd

from cks_picks_cfb.data.data_first_phase2 import DEVELOPMENT_SEASONS, FORBIDDEN_SEASONS
from cks_picks_cfb.data.data_first_phase2d import canonical_bytes, signed_payload
from cks_picks_cfb.data.data_first_repair_v2 import RECONSTRUCTED_TIMING

POSSESSION_IDENTITY_SCHEMA = "data_first_possession_measurement_identity_v1"
POSSESSION_MANIFEST_SCHEMA = "data_first_possession_measurement_manifest_v1"
POSSESSION_CERTIFICATION_SCHEMA = "data_first_possession_measurement_certification_v1"
POSSESSION_OUTPUT_ROOT = (
    "artifacts/research/data-first-football-v1/possession-v1/measurements/runs"
)
REQUIRED_REPAIR_RAW_SHA256 = (
    "b55af0dd7952a4b5e0d663b82182b351ec5496a292246a934a857c354058e0b4"
)
REQUIRED_REPAIR_CANONICAL_SHA256 = (
    "2fefcb95a2e8b4ae27e8fb2bf740328413aa576bcd725ebd9a18378edd50ac48"
)
MEASUREMENTS = (
    "eligible_possessions",
    "offensive_possession_points",
    "ppp",
    "eligible_epa",
    "epa_per_possession",
    "eligible_scrimmage_plays",
    "plays_per_possession",
    "non_offense_points",
)
ADJUSTED_MEASUREMENTS = ("ppp", "epa_per_possession")
ROLES = ("offense", "defense")
AVAILABILITY_BUFFER_HOURS = 6

POPULATION_COLUMNS = (
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
    "population_disposition",
    "measurement_disposition",
    "missing_reason",
    "timing_class",
)
POSSESSION_COLUMNS = (
    "season",
    "week",
    "game_id",
    "drive_number",
    "offense",
    "defense",
    "period_class",
    "eligible_play_count",
    "ineligible_play_count",
    "mixed_eligibility",
    "possession_eligible",
    "source_play_ids",
    "quality_reason",
    "timing_class",
)
SCORING_EVENT_COLUMNS = (
    "season",
    "game_id",
    "source_event_id",
    "team",
    "drive_number",
    "period_class",
    "score_increment",
    "scoring_category",
    "unit_category",
    "associated_possession_id",
    "conversion_for_event_id",
    "quality_reason",
    "timing_class",
)
OBSERVATION_COLUMNS = (
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
    "usable_exposure",
    "exposure_unit",
    "coverage_status",
    "missing_reason",
    "quality_flags",
    "timing_class",
)
SNAPSHOT_COLUMNS = (
    "season",
    "week",
    "as_of_game_id",
    "as_of_kickoff_utc",
    "target_week_cutoff_utc",
    "team",
    "measurement_id",
    "unit_role",
    "adjustment_iteration",
    "raw_value",
    "adjusted_value",
    "primary_exposure",
    "games_exposure",
    "source_game_count",
    "timing_class",
    "availability_policy",
)
HISTORY_COLUMNS = (
    "season",
    "week",
    "as_of_game_id",
    "target_week_cutoff_utc",
    "source_season",
    "source_week",
    "source_game_id",
    "source_kickoff_utc",
    "source_available_utc",
    "team",
    "opponent",
    "measurement_id",
    "unit_role",
    "adjustment_iteration",
    "numerator",
    "denominator",
    "iteration_zero_value",
    "iteration_four_value",
    "included",
    "missing_reason",
    "timing_class",
)
TERMINAL_COLUMNS = (
    "season",
    "team",
    "measurement_id",
    "unit_role",
    "adjustment_iteration",
    "raw_value",
    "adjusted_value",
    "primary_exposure",
    "games_exposure",
    "source_game_count",
    "timing_class",
)
COVERAGE_COLUMNS = (
    "season",
    "slice",
    "measurement_id",
    "schedule_games",
    "scoreable_games",
    "usable_team_games",
    "quarantined_team_games",
    "reason_counts",
    "timing_class",
)

POSSESSION_DATASETS = {
    "population": ("possession_population", "data_first_possession_population_v1"),
    "possessions": ("possession_ledger", "data_first_possession_possession_v1"),
    "scoring_events": (
        "possession_scoring_event",
        "data_first_possession_scoring_event_v1",
    ),
    "observations": ("possession_observation", "data_first_possession_observation_v1"),
    "snapshots": ("possession_snapshot", "data_first_possession_snapshot_v1"),
    "adjusted_history": (
        "possession_adjusted_history",
        "data_first_possession_adjusted_history_v1",
    ),
    "terminal": ("possession_terminal", "data_first_possession_terminal_v1"),
    "coverage": ("possession_coverage", "data_first_possession_coverage_v1"),
}


class PossessionContractError(ValueError):
    """Raised when possession evidence violates its certified contract."""


def sha256(value: Any) -> str:
    return hashlib.sha256(
        value if isinstance(value, bytes) else canonical_bytes(value)
    ).hexdigest()


def validate_config(payload: Mapping[str, Any]) -> None:
    if payload.get("schema_version") != "data_first_possession_measurement_config_v1":
        raise PossessionContractError("unexpected possession measurement config schema")
    if tuple(payload.get("development_seasons") or ()) != DEVELOPMENT_SEASONS:
        raise PossessionContractError("possession config development seasons drifted")
    if tuple(payload.get("forbidden_seasons") or ()) != FORBIDDEN_SEASONS:
        raise PossessionContractError("possession config forbidden seasons drifted")
    if tuple(payload.get("adjustment", {}).get("retained_iterations") or ()) != (0, 4):
        raise PossessionContractError(
            "possession config must retain adjustment iterations 0 and 4"
        )
    if int(payload.get("adjustment", {}).get("iterations", -1)) != 4:
        raise PossessionContractError(
            "possession config must use four adjustment passes"
        )


def build_population(repair_population: pd.DataFrame) -> pd.DataFrame:
    required = {
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
        "missing_reason",
        "disposition",
        "timing_class",
    }
    missing = sorted(required - set(repair_population.columns))
    if missing:
        raise PossessionContractError(
            f"Repair population is missing columns: {missing}"
        )
    frame = repair_population.copy()
    for name in ("season", "week", "game_id"):
        frame[name] = pd.to_numeric(frame[name], errors="raise").astype(int)
    frame["kickoff_utc"] = pd.to_datetime(
        frame["kickoff_utc"], utc=True, errors="raise"
    )
    if frame.duplicated(["season", "game_id"]).any():
        raise PossessionContractError(
            "Repair population has duplicate season/game keys"
        )
    if (
        set(frame["season"]) - set(DEVELOPMENT_SEASONS)
        or frame["season"].isin(FORBIDDEN_SEASONS).any()
    ):
        raise PossessionContractError(
            "Repair population contains an impermissible season"
        )
    if not frame["timing_class"].eq(RECONSTRUCTED_TIMING).all():
        raise PossessionContractError("Repair population timing class changed")
    result = pd.DataFrame(
        {
            "season": frame["season"],
            "week": frame["week"],
            "game_id": frame["game_id"],
            "kickoff_utc": frame["kickoff_utc"],
            "home_team": frame["home_team"],
            "away_team": frame["away_team"],
            "schedule_completed": frame["schedule_completed"],
            "outcome_valid": frame["outcome_valid"],
            "forecast_eligible": frame["forecast_eligible"],
            "measurement_usable": frame["measurement_usable"],
            "population_disposition": frame["disposition"],
            "measurement_disposition": frame["disposition"].where(
                frame["measurement_usable"], "measurement_unavailable"
            ),
            "missing_reason": frame["missing_reason"],
            "timing_class": frame["timing_class"],
        }
    )
    if (len(result), int(result["forecast_eligible"].sum())) != (8936, 8935):
        raise PossessionContractError("Repair population reconciliation changed")
    return (
        result.loc[:, POPULATION_COLUMNS]
        .sort_values(["season", "week", "game_id"], kind="mergesort")
        .reset_index(drop=True)
    )


def weekly_cutoffs(population: pd.DataFrame) -> pd.DataFrame:
    eligible = population.loc[population["forecast_eligible"]].copy()
    return (
        eligible.groupby(["season", "week"], as_index=False, sort=True)["kickoff_utc"]
        .min()
        .rename(columns={"kickoff_utc": "target_week_cutoff_utc"})
    )


def source_is_available(
    *,
    source_week: int,
    source_kickoff_utc: Any,
    target_week: int,
    target_week_cutoff_utc: Any,
) -> bool:
    source = pd.Timestamp(source_kickoff_utc)
    target = pd.Timestamp(target_week_cutoff_utc)
    if source.tzinfo is None or target.tzinfo is None:
        raise PossessionContractError("availability timestamps must be timezone-aware")
    return (
        int(source_week) < int(target_week)
        and source + timedelta(hours=AVAILABILITY_BUFFER_HOURS) <= target
    )


def possession_identity(
    *,
    run_id: str,
    as_of: str,
    code_sha: str,
    config_sha: str,
    repair_manifest_uri: str,
    repair_manifest_raw_sha256: str,
    repair_manifest_canonical_sha256: str,
) -> dict[str, Any]:
    value = {
        "schema_version": POSSESSION_IDENTITY_SCHEMA,
        "run_id": run_id,
        "environment": "preview",
        "as_of": as_of,
        "code_sha": code_sha,
        "config_sha": config_sha,
        "repair_manifest_uri": repair_manifest_uri,
        "repair_manifest_raw_sha256": repair_manifest_raw_sha256,
        "repair_manifest_canonical_sha256": repair_manifest_canonical_sha256,
        "development_seasons": list(DEVELOPMENT_SEASONS),
        "forbidden_seasons": list(FORBIDDEN_SEASONS),
    }
    value["identity_sha256"] = sha256(value)
    return value


def certification(
    *,
    population: pd.DataFrame,
    output_rows: Mapping[str, int],
    output_digests: Mapping[str, str],
    coverage: pd.DataFrame,
    scale_diagnostics: Mapping[str, Any],
) -> dict[str, Any]:
    checks = {
        "population_complete": len(population) == 8936
        and int(population["forecast_eligible"].sum()) == 8935,
        "forbidden_2020_absent": not population["season"].astype(int).eq(2020).any(),
        "reconstructed_timing_only": population["timing_class"]
        .eq(RECONSTRUCTED_TIMING)
        .all(),
        "both_efficiency_definitions_present": {"ppp", "epa_per_possession"}.issubset(
            set(coverage["measurement_id"])
        ),
        "coverage_rows_present": not coverage.empty,
    }
    return signed_payload(
        {
            "schema_version": POSSESSION_CERTIFICATION_SCHEMA,
            "checks": checks,
            "all_checks_passed": all(checks.values()),
            "row_counts": dict(output_rows),
            "output_records_sha256": dict(output_digests),
            "population_sha256": sha256(
                population.loc[:, POPULATION_COLUMNS].to_dict("records")
            ),
            "scale_diagnostics": dict(scale_diagnostics),
            "timing_class": RECONSTRUCTED_TIMING,
            "production_activation_authorized": False,
        }
    )
