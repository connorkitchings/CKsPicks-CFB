"""Immutable contracts for repaired-population Phase 3 v2 research.

The v1 Phase 3 implementation remains a sealed historical record. This module
contains the population, timing, schema, and selection contracts for its repaired
successor and deliberately performs no storage or production operations.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import numpy as np
import pandas as pd

from cks_picks_cfb.data.data_first_phase2 import DEVELOPMENT_SEASONS, FORBIDDEN_SEASONS
from cks_picks_cfb.data.data_first_phase2d import (
    canonical_bytes,
    signed_payload,
    verify_signed_payload,
)
from cks_picks_cfb.data.data_first_phase3 import CANDIDATE_COMPONENTS, CORE_CANDIDATES
from cks_picks_cfb.data.data_first_repair_v2 import (
    RECONSTRUCTED_TIMING,
    REPAIR_MANIFEST_SCHEMA,
    REPAIR_POPULATION_DATASET,
    REPAIR_POPULATION_SCHEMA,
)

PHASE3_V2_IDENTITY_SCHEMA = "data_first_phase3_run_identity_v2"
PHASE3_V2_CERTIFICATION_SCHEMA = "data_first_phase3_certification_v2"
PHASE3_V2_RETAINED_CORE_SCHEMA = "data_first_phase3_retained_core_v2"
PHASE3_V2_OUTPUT_ROOT = "artifacts/research/data-first-football-v1/phase3/v2/runs"
REQUIRED_REPAIR_RAW_SHA256 = (
    "b55af0dd7952a4b5e0d663b82182b351ec5496a292246a934a857c354058e0b4"
)
REQUIRED_REPAIR_CANONICAL_SHA256 = (
    "2fefcb95a2e8b4ae27e8fb2bf740328413aa576bcd725ebd9a18378edd50ac48"
)
VALIDATION_SEASONS = (2018, 2019, 2021, 2022, 2023, 2024, 2025)
RECENCY_MODES = ("primary", "half_life_4_games")
TARGETS = ("margin", "total")
ADJUSTED_COMPONENTS = (
    "epa_per_play",
    "success_rate",
    "explosive_rate_20",
    "points_per_scoring_opportunity",
    "epa_pass",
    "epa_rush",
)
MEASUREMENT_ROLE_GRID = (
    ("epa_per_play", "offense"),
    ("epa_per_play", "defense"),
    ("success_rate", "offense"),
    ("success_rate", "defense"),
    ("explosive_rate_20", "offense"),
    ("explosive_rate_20", "defense"),
    ("points_per_scoring_opportunity", "offense"),
    ("points_per_scoring_opportunity", "defense"),
    ("average_start_field_position", "offense"),
    ("average_start_field_position", "defense"),
    ("plays_per_drive", "offense"),
    ("turnover_rate", "offense"),
    ("turnover_rate", "defense"),
    ("epa_pass", "offense"),
    ("epa_pass", "defense"),
    ("epa_rush", "offense"),
    ("epa_rush", "defense"),
)
AVAILABILITY_BUFFER_HOURS = 6
BOOTSTRAP_REPLICATES = 2000
BOOTSTRAP_SEED = 20260908

POPULATION_COLUMNS = (
    "season",
    "week",
    "game_id",
    "kickoff_utc",
    "home_team",
    "away_team",
    "home_points",
    "away_points",
    "forecast_eligible",
    "measurement_usable",
    "missing_reason",
    "timing_class",
    "outer_validation",
)
OBSERVATION_COLUMNS_V2 = (
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
    "coverage_status",
    "missing_reason",
    "timing_class",
)
SNAPSHOT_COLUMNS_V2 = (
    "season",
    "week",
    "as_of_game_id",
    "as_of_kickoff_utc",
    "target_week_cutoff_utc",
    "team",
    "measurement_id",
    "unit_role",
    "recency_mode",
    "adjustment_iteration",
    "raw_value",
    "adjusted_value",
    "primary_exposure",
    "games_exposure",
    "source_game_count",
    "timing_class",
    "availability_policy",
)
HISTORY_COLUMNS_V2 = (
    "season",
    "week",
    "as_of_game_id",
    "as_of_kickoff_utc",
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
    "recency_mode",
    "raw_value",
    "numerator",
    "denominator",
    "iteration_three_opponent_value",
    "schedule_strength_component",
    "iteration_zero_value",
    "iteration_four_value",
    "included",
    "missing_reason",
    "timing_class",
)
TERMINAL_COLUMNS_V2 = (
    "season",
    "team",
    "measurement_id",
    "unit_role",
    "recency_mode",
    "raw_value",
    "adjusted_value",
    "primary_exposure",
    "games_exposure",
    "source_game_count",
    "timing_class",
)
PREDICTION_COLUMNS_V2 = (
    "season",
    "week",
    "game_id",
    "kickoff_utc",
    "candidate",
    "recency_mode",
    "target",
    "actual",
    "prediction",
    "absolute_error",
    "fold_id",
    "training_seasons",
    "feature_fallback",
    "fallback_count",
)
ATTRIBUTION_COLUMNS_V2 = (
    "candidate",
    "components",
    "component_count",
    "validation_rows",
    "validation_games",
    "pooled_mae",
    "baseline_mae",
    "improvement_pct",
    "bootstrap_mean_improvement",
    "bootstrap_90_lower",
    "bootstrap_90_upper",
    "bootstrap_excludes_zero",
    "coverage_equal",
    "maximum_seasonal_regression_pct",
    "seasonal_gate_passed",
    "sensitivity_mae",
    "sensitivity_baseline_mae",
    "sensitivity_regression_pct",
    "sensitivity_gate_passed",
    "primary_gate_passed",
    "selected",
)
PHASE3_V2_DATASETS = {
    "population": ("phase3_population", "data_first_phase3_population_v2"),
    "observations": ("phase3_observation", "data_first_phase3_observation_v2"),
    "pregame_snapshots": (
        "phase3_pregame_snapshot",
        "data_first_phase3_pregame_snapshot_v2",
    ),
    "adjusted_history": (
        "phase3_adjusted_history",
        "data_first_phase3_adjusted_history_v2",
    ),
    "terminal": ("phase3_terminal", "data_first_phase3_terminal_v2"),
    "predictions": ("phase3_prediction", "data_first_phase3_prediction_v2"),
    "attribution": ("phase3_attribution", "data_first_phase3_attribution_v2"),
}


class Phase3V2Error(ValueError):
    """Raised when repaired-population Phase 3 v2 evidence is invalid."""


@dataclass(frozen=True)
class WeekCutoff:
    season: int
    week: int
    cutoff_utc: pd.Timestamp


def sha256(value: Any) -> str:
    """Return the canonical SHA-256 used by all v2 evidence."""
    if isinstance(value, bytes):
        return hashlib.sha256(value).hexdigest()
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _records_digest(frame: pd.DataFrame, columns: Iterable[str]) -> str:
    return sha256(frame.loc[:, list(columns)].to_dict("records"))


def validate_phase3_v2_config(payload: Mapping[str, Any]) -> None:
    """Reject drift from the sealed Phase 3 v2 registry and timing policy."""
    if payload.get("schema_version") != "data_first_phase3_v2_config_v1":
        raise Phase3V2Error("Phase 3 v2 requires data_first_phase3_v2_config_v1")
    if tuple(payload.get("development_seasons") or ()) != DEVELOPMENT_SEASONS:
        raise Phase3V2Error("Phase 3 v2 config has incorrect development seasons")
    if tuple(payload.get("forbidden_seasons") or ()) != FORBIDDEN_SEASONS:
        raise Phase3V2Error("Phase 3 v2 config has incorrect forbidden seasons")
    if tuple(payload.get("candidates") or ()) != CORE_CANDIDATES:
        raise Phase3V2Error("Phase 3 v2 candidate registry drifted")
    selection = payload.get("selection") or {}
    expected = {
        "primary_rho": 0.60,
        "ridge_alpha": 10,
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "minimum_pooled_improvement_pct": 0.5,
        "maximum_seasonal_regression_pct": 5.0,
    }
    if any(selection.get(key) != value for key, value in expected.items()):
        raise Phase3V2Error("Phase 3 v2 selection scaffold drifted")
    policy = payload.get("availability_policy") or {}
    if (
        policy.get("classification") != RECONSTRUCTED_TIMING
        or policy.get("source_week_relation") != "strictly_prior_canonical_week"
        or policy.get("source_kickoff_buffer_hours") != AVAILABILITY_BUFFER_HOURS
        or policy.get("target_cutoff") != "earliest_eligible_target_kickoff"
    ):
        raise Phase3V2Error("Phase 3 v2 availability policy drifted")
    materialization = payload.get("materialization") or {}
    if materialization != {
        "artifact_kind": "partitioned_dataset_v1",
        "maximum_partition_rows": 100000,
        "maximum_compact_rows": 250000,
        "raw_iteration_four_component_rows": 428880,
        "compact_tournament_feature_rows": 142960,
    }:
        raise Phase3V2Error("Phase 3 v2 materialization policy drifted")


def verify_repair_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the eligible, exact Repair v2 parent before it can be decoded."""
    if payload.get("schema_version") != REPAIR_MANIFEST_SCHEMA:
        raise Phase3V2Error("Phase 3 v2 requires a Repair v2 manifest")
    try:
        verify_signed_payload(payload, label="Repair v2 manifest")
    except ValueError as exc:
        raise Phase3V2Error(str(exc)) from exc
    if payload.get("state") != "repaired_reconstructed_only":
        raise Phase3V2Error("Repair parent is not reconstructed repaired evidence")
    if payload.get("timing_class") != RECONSTRUCTED_TIMING:
        raise Phase3V2Error("Repair parent has an invalid timing classification")
    if payload.get("production_activation_authorized") is not False:
        raise Phase3V2Error("Repair parent authorizes production")
    expected = {
        "scheduled_games": 8936,
        "forecast_eligible_games": 8935,
        "measurement_usable_games": 8903,
        "measurement_missing_games": 33,
    }
    population = payload.get("population") or {}
    if any(population.get(key) != value for key, value in expected.items()):
        raise Phase3V2Error("Repair parent population does not match sealed counts")
    ref = (payload.get("output_refs") or {}).get("population") or {}
    if (
        ref.get("dataset") != REPAIR_POPULATION_DATASET
        or ref.get("schema_version") != REPAIR_POPULATION_SCHEMA
    ):
        raise Phase3V2Error("Repair parent does not expose population")
    if (payload.get("identity") or {}).get("environment") != "preview":
        raise Phase3V2Error("Repair parent is not Preview evidence")
    return dict(payload)


def phase3_v2_identity(
    *,
    run_id: str,
    environment: str,
    as_of: str,
    code_sha: str,
    config_sha: str,
    repair_manifest_uri: str,
    repair_manifest_raw_sha256: str,
    repair_manifest_canonical_sha256: str,
) -> dict[str, Any]:
    """Create a deterministic Preview-only Phase 3 v2 identity."""
    if environment != "preview":
        raise Phase3V2Error("Phase 3 v2 is Preview-only")
    if not all(
        (
            run_id,
            as_of,
            code_sha,
            config_sha,
            repair_manifest_uri,
            repair_manifest_raw_sha256,
            repair_manifest_canonical_sha256,
        )
    ):
        raise Phase3V2Error("Phase 3 v2 identity fields are required")
    payload = {
        "schema_version": PHASE3_V2_IDENTITY_SCHEMA,
        "run_id": run_id,
        "environment": environment,
        "as_of": as_of,
        "code_sha": code_sha,
        "config_sha": config_sha,
        "repair_manifest_uri": repair_manifest_uri,
        "repair_manifest_raw_sha256": repair_manifest_raw_sha256,
        "repair_manifest_canonical_sha256": repair_manifest_canonical_sha256,
        "timing_class": RECONSTRUCTED_TIMING,
        "production_activation_authorized": False,
    }
    return payload | {"identity_sha256": sha256(payload)}


def build_population(repair_population: pd.DataFrame) -> pd.DataFrame:
    """Copy Repair's full schedule population without measurement-driven loss."""
    required = {
        "season",
        "week",
        "game_id",
        "kickoff_utc",
        "home_team",
        "away_team",
        "home_points",
        "away_points",
        "forecast_eligible",
        "measurement_usable",
        "missing_reason",
        "timing_class",
    }
    missing = sorted(required - set(repair_population))
    if missing:
        raise Phase3V2Error(f"Repair population is missing columns: {missing}")
    population = repair_population.loc[:, list(required)].copy()
    for column in ("season", "week", "game_id"):
        population[column] = pd.to_numeric(population[column], errors="raise").astype(
            int
        )
    population["kickoff_utc"] = pd.to_datetime(population["kickoff_utc"], utc=True)
    if population.duplicated(["season", "game_id"]).any():
        raise Phase3V2Error("Repair population has duplicate season/game keys")
    if population["season"].isin(FORBIDDEN_SEASONS).any():
        raise Phase3V2Error("Repair population contains forbidden 2020")
    if not population["timing_class"].eq(RECONSTRUCTED_TIMING).all():
        raise Phase3V2Error("Repair population timing classification changed")
    population["outer_validation"] = population["season"].isin(VALIDATION_SEASONS)
    population = (
        population.loc[:, POPULATION_COLUMNS]
        .sort_values(["season", "week", "game_id"], kind="mergesort")
        .reset_index(drop=True)
    )
    summary = (
        len(population),
        int(population["forecast_eligible"].sum()),
        int(population["measurement_usable"].sum()),
    )
    if summary != (8936, 8935, 8903):
        raise Phase3V2Error(f"Repair population reconciliation failed: {summary}")
    return population


def _exposure_unit(measurement_id: str) -> str:
    if measurement_id == "points_per_scoring_opportunity":
        return "opportunities"
    if measurement_id in {"average_start_field_position", "plays_per_drive"}:
        return "drives"
    return "plays"


def complete_observation_grid(
    *, population: pd.DataFrame, observed: pd.DataFrame
) -> pd.DataFrame:
    """Left-complete observations for every eligible schedule/team/role key."""
    required = {
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
        "coverage_status",
        "missing_reason",
    }
    missing = sorted(required - set(observed))
    if missing:
        raise Phase3V2Error(f"Observed measurements are missing columns: {missing}")
    known = observed.copy()
    for column in ("season", "week", "game_id"):
        known[column] = pd.to_numeric(known[column], errors="raise").astype(int)
    key = ["season", "game_id", "team", "measurement_id", "unit_role"]
    if known.duplicated(key).any():
        raise Phase3V2Error("Observed measurements contain duplicate keys")
    lookup = {
        tuple(row[field] for field in key): row for row in known.to_dict("records")
    }
    records: list[dict[str, Any]] = []
    for game in population[population["forecast_eligible"]].itertuples(index=False):
        for team, opponent, side in (
            (game.home_team, game.away_team, "home"),
            (game.away_team, game.home_team, "away"),
        ):
            for measurement_id, unit_role in MEASUREMENT_ROLE_GRID:
                source = lookup.get(
                    (
                        int(game.season),
                        int(game.game_id),
                        team,
                        measurement_id,
                        unit_role,
                    )
                )
                if source is None:
                    reason = (
                        str(game.missing_reason)
                        if pd.notna(game.missing_reason)
                        else "missing_measurement_evidence"
                    )
                    source = {
                        "numerator": 0.0,
                        "denominator": 0.0,
                        "raw_value": None,
                        "coverage_status": "missing",
                        "missing_reason": reason,
                    }
                records.append(
                    {
                        "season": int(game.season),
                        "week": int(game.week),
                        "game_id": int(game.game_id),
                        "kickoff_utc": game.kickoff_utc,
                        "team": str(team),
                        "opponent": str(opponent),
                        "side": side,
                        "measurement_id": measurement_id,
                        "unit_role": unit_role,
                        "numerator": float(source.get("numerator") or 0.0),
                        "denominator": float(source.get("denominator") or 0.0),
                        "raw_value": source.get("raw_value"),
                        "exposure_unit": source.get(
                            "exposure_unit", _exposure_unit(measurement_id)
                        ),
                        "coverage_status": source.get("coverage_status", "observed"),
                        "missing_reason": source.get("missing_reason"),
                        "timing_class": RECONSTRUCTED_TIMING,
                    }
                )
    frame = pd.DataFrame.from_records(records, columns=OBSERVATION_COLUMNS_V2)
    if frame.duplicated(key).any():
        raise Phase3V2Error("Completed observation grid contains duplicate keys")
    expected = int(population["forecast_eligible"].sum()) * 34
    if len(frame) != expected:
        raise Phase3V2Error(
            f"Completed observation grid has {len(frame)}, expected {expected}"
        )
    return frame.sort_values(key, kind="mergesort").reset_index(drop=True)


def weekly_cutoffs(population: pd.DataFrame) -> pd.DataFrame:
    """Return earliest eligible kickoff for each canonical target week."""
    eligible = population[population["forecast_eligible"]].copy()
    eligible["kickoff_utc"] = pd.to_datetime(eligible["kickoff_utc"], utc=True)
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
    """Apply the fixed reconstructed six-hour weekly admission rule."""
    if int(source_week) >= int(target_week):
        return False
    source_available = pd.Timestamp(source_kickoff_utc)
    target_cutoff = pd.Timestamp(target_week_cutoff_utc)
    if source_available.tzinfo is None or target_cutoff.tzinfo is None:
        raise Phase3V2Error("Historical availability timestamps must be timezone-aware")
    return (
        source_available + timedelta(hours=AVAILABILITY_BUFFER_HOURS) <= target_cutoff
    )


def common_bootstrap_plan(
    losses: pd.DataFrame,
    *,
    replicates: int = BOOTSTRAP_REPLICATES,
    seed: int = BOOTSTRAP_SEED,
) -> tuple[tuple[tuple[int, int], ...], ...]:
    """Generate one season→week plan shared by every candidate comparison."""
    if replicates != BOOTSTRAP_REPLICATES or seed != BOOTSTRAP_SEED:
        raise Phase3V2Error("Phase 3 v2 bootstrap settings are sealed")
    if missing := sorted({"season", "week"} - set(losses)):
        raise Phase3V2Error(f"Bootstrap losses missing columns: {missing}")
    blocks = sorted(
        {
            (int(row.season), int(row.week))
            for row in losses.loc[:, ["season", "week"]].drop_duplicates().itertuples()
        }
    )
    if not blocks:
        raise Phase3V2Error("Bootstrap requires season/week blocks")
    seasons = sorted({season for season, _ in blocks})
    by_season = {
        season: [block for block in blocks if block[0] == season] for season in seasons
    }
    rng = np.random.default_rng(seed)
    plan = []
    for _ in range(replicates):
        draw = []
        for season in rng.choice(seasons, size=len(seasons), replace=True):
            options = by_season[int(season)]
            draw.extend(
                options[index]
                for index in rng.integers(0, len(options), size=len(options))
            )
        plan.append(tuple(draw))
    return tuple(plan)


def paired_bootstrap_interval(
    losses: pd.DataFrame,
    *,
    candidate: str,
    plan: tuple[tuple[tuple[int, int], ...], ...],
) -> tuple[float, float, float]:
    """Compute an EPA-only paired interval using a precomputed common plan."""
    if candidate == "epa_only":
        return 0.0, 0.0, 0.0
    pair = losses[losses["candidate"].isin(("epa_only", candidate))].pivot(
        index=["season", "week", "game_id", "target"],
        columns="candidate",
        values="absolute_error",
    )
    if pair[["epa_only", candidate]].isna().any().any():
        raise Phase3V2Error(f"Bootstrap pairing failed for {candidate}")
    paired = pair.reset_index()
    paired["improvement"] = paired["epa_only"] - paired[candidate]
    blocks = {
        key: values["improvement"].to_numpy(dtype=float)
        for key, values in paired.groupby(["season", "week"], sort=True)
    }
    draws = np.array(
        [np.concatenate([blocks[block] for block in draw]).mean() for draw in plan],
        dtype=float,
    )
    return (
        float(paired["improvement"].mean()),
        float(np.quantile(draws, 0.05)),
        float(np.quantile(draws, 0.95)),
    )


def select_retained_core(
    predictions: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Apply frozen gates with one shared bootstrap plan for all candidates."""
    required = {
        "candidate",
        "recency_mode",
        "target",
        "season",
        "week",
        "game_id",
        "absolute_error",
    }
    if missing := sorted(required - set(predictions)):
        raise Phase3V2Error(f"Predictions missing columns: {missing}")
    primary = predictions[predictions["recency_mode"] == "primary"].copy()
    sensitivity = predictions[predictions["recency_mode"] == "half_life_4_games"].copy()
    expected_keys: set[tuple[int, int, int, str]] | None = None
    for candidate in CORE_CANDIDATES:
        for mode in RECENCY_MODES:
            subset = predictions[
                (predictions["candidate"] == candidate)
                & (predictions["recency_mode"] == mode)
            ]
            keys = set(
                subset[["season", "week", "game_id", "target"]].itertuples(
                    index=False, name=None
                )
            )
            if expected_keys is None:
                expected_keys = keys
            elif keys != expected_keys:
                raise Phase3V2Error(
                    "candidate tournament changed comparison population"
                )
    if expected_keys is None:
        raise Phase3V2Error("candidate tournament has no predictions")
    plan = common_bootstrap_plan(primary)
    baseline_mae = float(
        primary.loc[primary["candidate"] == "epa_only", "absolute_error"].mean()
    )
    sensitivity_baseline = float(
        sensitivity.loc[sensitivity["candidate"] == "epa_only", "absolute_error"].mean()
    )
    baseline_keys = set(
        primary.loc[
            primary["candidate"] == "epa_only", ["season", "week", "game_id", "target"]
        ].itertuples(index=False, name=None)
    )
    rows = []
    for candidate in CORE_CANDIDATES:
        candidate_primary = primary[primary["candidate"] == candidate]
        candidate_sensitivity = sensitivity[sensitivity["candidate"] == candidate]
        mae = float(candidate_primary["absolute_error"].mean())
        sensitivity_mae = float(candidate_sensitivity["absolute_error"].mean())
        candidate_keys = set(
            candidate_primary[["season", "week", "game_id", "target"]].itertuples(
                index=False, name=None
            )
        )
        mean, lower, upper = paired_bootstrap_interval(
            primary, candidate=candidate, plan=plan
        )
        regressions = []
        for (season, target), values in candidate_primary.groupby(["season", "target"]):
            baseline = primary[
                (primary["candidate"] == "epa_only")
                & (primary["season"] == season)
                & (primary["target"] == target)
            ]["absolute_error"]
            regressions.append(
                (float(values["absolute_error"].mean()) / float(baseline.mean()) - 1)
                * 100
            )
        maximum_regression = max(regressions)
        improvement = (baseline_mae - mae) / baseline_mae * 100
        sensitivity_regression = (
            (sensitivity_mae - sensitivity_baseline) / sensitivity_baseline * 100
        )
        coverage_equal = candidate_keys == baseline_keys
        bootstrap_passed = candidate != "epa_only" and lower > 0
        seasonal_passed = maximum_regression <= 5.0
        sensitivity_passed = sensitivity_regression <= 0.5
        primary_passed = bool(
            candidate != "epa_only"
            and improvement >= 0.5
            and bootstrap_passed
            and coverage_equal
            and seasonal_passed
            and sensitivity_passed
        )
        rows.append(
            {
                "candidate": candidate,
                "components": json.dumps(CANDIDATE_COMPONENTS[candidate]),
                "component_count": len(CANDIDATE_COMPONENTS[candidate]),
                "validation_rows": int(len(candidate_primary)),
                "validation_games": int(candidate_primary["game_id"].nunique()),
                "pooled_mae": mae,
                "baseline_mae": baseline_mae,
                "improvement_pct": improvement,
                "bootstrap_mean_improvement": mean,
                "bootstrap_90_lower": lower,
                "bootstrap_90_upper": upper,
                "bootstrap_excludes_zero": bootstrap_passed,
                "coverage_equal": coverage_equal,
                "maximum_seasonal_regression_pct": maximum_regression,
                "seasonal_gate_passed": seasonal_passed,
                "sensitivity_mae": sensitivity_mae,
                "sensitivity_baseline_mae": sensitivity_baseline,
                "sensitivity_regression_pct": sensitivity_regression,
                "sensitivity_gate_passed": sensitivity_passed,
                "primary_gate_passed": primary_passed,
                "selected": False,
            }
        )
    attribution = pd.DataFrame.from_records(rows, columns=ATTRIBUTION_COLUMNS_V2)
    passing = attribution[attribution["primary_gate_passed"]]
    if passing.empty:
        selected = "epa_only"
    else:
        best = float(passing["pooled_mae"].min())
        selected = str(
            passing[passing["pooled_mae"] <= best * 1.005]
            .sort_values(["component_count", "candidate"], kind="mergesort")
            .iloc[0]["candidate"]
        )
    attribution.loc[attribution["candidate"] == selected, "selected"] = True
    retained = signed_payload(
        {
            "schema_version": PHASE3_V2_RETAINED_CORE_SCHEMA,
            "state": "frozen",
            "selected_candidate": selected,
            "selected_components": list(CANDIDATE_COMPONENTS[selected]),
            "baseline_candidate": "epa_only",
            "validation_seasons": list(VALIDATION_SEASONS),
            "common_bootstrap_plan_sha256": sha256(
                [[list(block) for block in draw] for draw in plan]
            ),
            "candidate_summary_sha256": sha256(attribution.to_dict("records")),
            "timing_class": RECONSTRUCTED_TIMING,
            "auxiliary_context_consumed": False,
            "production_activation_authorized": False,
        }
    )
    return attribution, retained


def certification(
    *,
    population: pd.DataFrame,
    observations: pd.DataFrame,
    snapshots: pd.DataFrame,
    history: pd.DataFrame,
) -> dict[str, Any]:
    """Build a signed small certification envelope for immutable output evidence."""
    expected_observations = int(population["forecast_eligible"].sum()) * 34
    checks = {
        "population_complete": len(population) == 8936
        and int(population["forecast_eligible"].sum()) == 8935,
        "measurement_population_preserved": int(population["measurement_usable"].sum())
        == 8903,
        "observation_grid_complete": len(observations) == expected_observations,
        "forbidden_2020_absent": not any(
            frame["season"].astype(int).eq(2020).any()
            for frame in (population, observations, snapshots, history)
        ),
        "reconstructed_timing_only": all(
            frame["timing_class"].eq(RECONSTRUCTED_TIMING).all()
            for frame in (population, observations, snapshots, history)
        ),
    }
    return signed_payload(
        {
            "schema_version": PHASE3_V2_CERTIFICATION_SCHEMA,
            "checks": checks,
            "all_checks_passed": all(checks.values()),
            "row_counts": {
                "population": int(len(population)),
                "observations": int(len(observations)),
                "pregame_snapshots": int(len(snapshots)),
                "adjusted_history": int(len(history)),
            },
            "population_sha256": _records_digest(population, POPULATION_COLUMNS),
            "timing_class": RECONSTRUCTED_TIMING,
            "production_activation_authorized": False,
        }
    )
