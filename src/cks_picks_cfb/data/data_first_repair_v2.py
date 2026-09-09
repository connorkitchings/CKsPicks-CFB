"""Leakage-safe Repair v2 contracts for data-first historical research.

This module deliberately does not mutate the sealed Phase 2/3 implementations.
It rebuilds their diagnostic population and auxiliary semantics from exact parents
so the succeeding v2 stages can prove their own lineage.
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd

from cks_picks_cfb.data.data_first_phase2 import DEVELOPMENT_SEASONS, FORBIDDEN_SEASONS
from cks_picks_cfb.data.data_first_phase2d import (
    canonical_bytes,
    signed_payload,
    verify_signed_payload,
)
from cks_picks_cfb.preseason_features import canonical_team

REPAIR_IDENTITY_SCHEMA = "data_first_repair_run_identity_v2"
REPAIR_MANIFEST_SCHEMA = "data_first_repair_manifest_v2"
REPAIR_POPULATION_DATASET = "repair_population"
REPAIR_POPULATION_SCHEMA = "data_first_repair_population_v2"
REPAIR_AUXILIARY_DATASET = "repair_auxiliary"
REPAIR_AUXILIARY_SCHEMA = "data_first_repair_auxiliary_v2"
REPAIR_COVERAGE_DATASET = "repair_coverage"
REPAIR_COVERAGE_SCHEMA = "data_first_repair_coverage_v2"
REPAIR_ISSUE_DATASET = "repair_issue"
REPAIR_ISSUE_SCHEMA = "data_first_repair_issue_v2"
REPAIR_CAPTURE_PLAN_DATASET = "repair_capture_plan"
REPAIR_CAPTURE_PLAN_SCHEMA = "data_first_repair_capture_plan_v2"
RECONSTRUCTED_TIMING = "historically_reconstructed"
FOOTBALL_FAMILIES = (
    "recruiting",
    "returning_production",
    "coaching",
    "roster_continuity",
)
FAMILY_FEATURES: dict[str, tuple[str, ...]] = {
    "recruiting": (
        "recruiting_current_points",
        "recruiting_available_average_points",
        "recruiting_available_class_count",
        "recruiting_strict_four_class_average_points",
        "recruiting_current_minus_available_average",
    ),
    "returning_production": (
        "return_total_ppa",
        "return_passing_ppa",
        "return_rushing_ppa",
        "return_receiving_ppa",
        "return_percent_ppa",
        "return_passing_usage",
        "return_rushing_usage",
    ),
    "coaching": ("coach_tenure", "coach_tenure_lower_bound", "coach_new"),
    "roster_continuity": (
        "roster_same_team_return_share",
        "roster_same_team_return_qb_count",
        "roster_incoming_experienced_share",
        "roster_incoming_experienced_qb_count",
    ),
}

POPULATION_COLUMNS = (
    "season",
    "week",
    "game_id",
    "kickoff_utc",
    "home_team",
    "away_team",
    "schedule_completed",
    "home_points",
    "away_points",
    "outcome_valid",
    "forecast_eligible",
    "measurement_usable",
    "measurement_exposure",
    "missing_measurement_sources",
    "missing_reason",
    "reconciliation_classification",
    "disposition",
    "timing_class",
)
AUXILIARY_COLUMNS = (
    "family",
    "season",
    "team",
    "timing_class",
    "historical_eligible",
    "live_eligible",
    "permitted_role",
    "missing_reason",
    "source_capture_ids",
    "recruiting_current_points",
    "recruiting_available_average_points",
    "recruiting_available_class_count",
    "recruiting_available_start_year",
    "recruiting_available_end_year",
    "recruiting_available_span_years",
    "recruiting_strict_four_class_average_points",
    "recruiting_current_minus_available_average",
    "return_total_ppa",
    "return_passing_ppa",
    "return_rushing_ppa",
    "return_receiving_ppa",
    "return_percent_ppa",
    "return_passing_usage",
    "return_rushing_usage",
    "coach_identity",
    "coach_tenure",
    "coach_tenure_lower_bound",
    "coach_tenure_censored",
    "coach_new",
    "roster_current_observed_size",
    "roster_current_usable_size",
    "roster_same_team_return_count",
    "roster_same_team_return_share",
    "roster_same_team_return_qb_count",
    "roster_current_qb_count",
    "roster_incoming_experienced_count",
    "roster_incoming_experienced_share",
    "roster_incoming_experienced_qb_count",
    "roster_predecessor_season",
    "roster_identity_exclusions",
)
COVERAGE_COLUMNS = (
    "family",
    "season",
    "slice",
    "required_rows",
    "non_null_rows",
    "missing_rows",
    "coverage_fraction",
    "distinct_values",
    "constant_warning",
    "ambiguity_rows",
    "structural_missing_rows",
    "historical_eligible",
    "live_eligible",
    "timing_class",
)
ISSUE_COLUMNS = (
    "issue_id",
    "affected_key",
    "category",
    "family",
    "season",
    "game_id",
    "team",
    "source_branch",
    "observed_status",
    "outcome_valid",
    "disposition",
    "core_blocker",
    "resolved",
    "details",
)
CAPTURE_PLAN_COLUMNS = (
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
    "capture_id",
    "attempt_count",
    "captured_at",
    "content_sha",
    "row_count",
    "timing_class",
)


class RepairV2Error(ValueError):
    """Raised when Repair v2 evidence is incomplete or semantically unsafe."""


def sha256(value: Any) -> str:
    return hashlib.sha256(
        value if isinstance(value, bytes) else canonical_bytes(value)
    ).hexdigest()


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _key_issue(
    *,
    category: str,
    family: str | None = None,
    season: int | None = None,
    game_id: int | None = None,
    team: str | None = None,
    source_branch: str | None = None,
    observed_status: str | None = None,
    outcome_valid: bool | None = None,
    disposition: str | None = None,
    core_blocker: bool = False,
    resolved: bool = False,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    identity = {
        "category": category,
        "family": family,
        "season": season,
        "game_id": game_id,
        "team": team,
        "source_branch": source_branch,
    }
    return {
        "issue_id": sha256(identity),
        "affected_key": _stable_json(identity),
        **identity,
        "observed_status": observed_status,
        "outcome_valid": outcome_valid,
        "disposition": disposition,
        "core_blocker": core_blocker,
        "resolved": resolved,
        "details": _stable_json(details or {}),
    }


def verify_parent(
    payload: Mapping[str, Any],
    *,
    raw_sha256: str,
    expected_raw_sha256: str,
    expected_manifest_sha256: str,
    schema_version: str,
    state: str,
    label: str,
) -> None:
    """Validate a pinned parent by both physical and canonical identities."""
    if raw_sha256 != expected_raw_sha256:
        raise RepairV2Error(f"{label} raw checksum is not the approved parent")
    if payload.get("schema_version") != schema_version or payload.get("state") != state:
        raise RepairV2Error(f"{label} schema or state is not approved")
    try:
        verify_signed_payload(payload, label=label)
    except ValueError as exc:
        raise RepairV2Error(str(exc)) from exc
    if payload.get("manifest_sha256") != expected_manifest_sha256:
        raise RepairV2Error(f"{label} canonical checksum is not approved")
    if tuple(payload.get("development_seasons") or ()) != DEVELOPMENT_SEASONS:
        raise RepairV2Error(f"{label} development season set changed")
    if tuple(payload.get("forbidden_seasons") or ()) != FORBIDDEN_SEASONS:
        raise RepairV2Error(f"{label} forbidden season set changed")


def repair_identity(
    *,
    run_id: str,
    environment: str,
    as_of: str,
    code_sha: str,
    config_sha: str,
    core_eligibility_uri: str,
    core_eligibility_raw_sha256: str,
    auxiliary_eligibility_uri: str,
    auxiliary_eligibility_raw_sha256: str,
    phase3_retained_uri: str,
    phase3_retained_raw_sha256: str,
) -> dict[str, Any]:
    if environment != "preview":
        raise RepairV2Error("Repair v2 is Preview-only")
    if not run_id or not code_sha or not config_sha:
        raise RepairV2Error("Repair v2 identity is incomplete")
    value = {
        "schema_version": REPAIR_IDENTITY_SCHEMA,
        "run_id": run_id,
        "environment": environment,
        "as_of": as_of,
        "code_sha": code_sha,
        "config_sha": config_sha,
        "core_eligibility_uri": core_eligibility_uri,
        "core_eligibility_raw_sha256": core_eligibility_raw_sha256,
        "auxiliary_eligibility_uri": auxiliary_eligibility_uri,
        "auxiliary_eligibility_raw_sha256": auxiliary_eligibility_raw_sha256,
        "phase3_retained_uri": phase3_retained_uri,
        "phase3_retained_raw_sha256": phase3_retained_raw_sha256,
        "development_seasons": list(DEVELOPMENT_SEASONS),
        "forbidden_seasons": list(FORBIDDEN_SEASONS),
    }
    value["identity_sha256"] = sha256(value)
    return value


def _require_columns(frame: pd.DataFrame, columns: set[str], label: str) -> None:
    missing = sorted(columns - set(frame))
    if missing:
        raise RepairV2Error(f"{label} is missing columns: {missing}")


def _canonical_team_frame(
    frame: pd.DataFrame, team_column: str = "team"
) -> pd.DataFrame:
    result = frame.copy()
    result[team_column] = result[team_column].map(canonical_team)
    return result


def _clean_universe(universe: pd.DataFrame) -> pd.DataFrame:
    _require_columns(universe, {"season", "team"}, "team universe")
    result = _canonical_team_frame(universe.loc[:, ["season", "team"]])
    result["season"] = pd.to_numeric(result["season"], errors="raise").astype(int)
    if result["team"].isna().any() or result.duplicated().any():
        raise RepairV2Error("team universe contains invalid keys")
    return result.sort_values(["season", "team"], kind="mergesort").reset_index(
        drop=True
    )


def build_team_universe(schedule: pd.DataFrame) -> pd.DataFrame:
    """Return the FBS schedule-side team-season universe without outcome filtering."""
    _require_columns(
        schedule,
        {
            "season",
            "home_team",
            "away_team",
            "home_classification",
            "away_classification",
        },
        "schedule",
    )
    sides = pd.concat(
        [
            schedule[["season", "home_team", "home_classification"]].rename(
                columns={"home_team": "team", "home_classification": "classification"}
            ),
            schedule[["season", "away_team", "away_classification"]].rename(
                columns={"away_team": "team", "away_classification": "classification"}
            ),
        ],
        ignore_index=True,
    )
    sides["season"] = pd.to_numeric(sides["season"], errors="raise").astype(int)
    if set(sides["season"]) - set(DEVELOPMENT_SEASONS):
        raise RepairV2Error("team universe contains an impermissible season")
    sides = _canonical_team_frame(sides)
    result = sides.loc[
        sides["classification"].astype(str).str.casefold().eq("fbs"), ["season", "team"]
    ].drop_duplicates()
    if result["team"].isna().any() or result.duplicated().any():
        raise RepairV2Error("team universe contains invalid keys")
    return result.sort_values(["season", "team"], kind="mergesort").reset_index(
        drop=True
    )


def reconcile_population(
    *,
    schedule: pd.DataFrame,
    outcomes: pd.DataFrame,
    observed_games: pd.DataFrame,
    reconciliation: pd.DataFrame,
    omissions: Mapping[str, Sequence[Mapping[str, Any]]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Separate completed-game evaluation from measurement availability."""
    _require_columns(
        schedule,
        {
            "season",
            "week",
            "game_id",
            "kickoff_utc",
            "home_team",
            "away_team",
            "completed",
        },
        "schedule",
    )
    _require_columns(
        outcomes,
        {"season", "game_id", "completed", "home_points", "away_points"},
        "outcomes",
    )
    _require_columns(observed_games, {"season", "game_id"}, "Phase 3 observations")
    _require_columns(
        reconciliation, {"season", "game_id", "classification"}, "reconciliation"
    )
    base = schedule.loc[
        :,
        [
            "season",
            "week",
            "game_id",
            "kickoff_utc",
            "home_team",
            "away_team",
            "completed",
        ],
    ].copy()
    base["season"] = pd.to_numeric(base["season"], errors="raise").astype(int)
    base["game_id"] = pd.to_numeric(base["game_id"], errors="raise").astype(int)
    base["week"] = pd.to_numeric(base["week"], errors="raise").astype(int)
    if (
        set(base["season"]) - set(DEVELOPMENT_SEASONS)
        or base["season"].isin(FORBIDDEN_SEASONS).any()
    ):
        raise RepairV2Error("population contains impermissible seasons")
    if base.duplicated(["season", "game_id"]).any():
        raise RepairV2Error("schedule repeats a game key")
    result = base.merge(
        outcomes[
            ["season", "game_id", "completed", "home_points", "away_points"]
        ].rename(columns={"completed": "outcome_completed"}),
        on=["season", "game_id"],
        how="left",
        validate="one_to_one",
    )
    reconciliation_rows = reconciliation[
        ["season", "game_id", "classification"]
    ].drop_duplicates()
    if reconciliation_rows.duplicated(["season", "game_id"]).any():
        raise RepairV2Error("reconciliation repeats a game key")
    result = result.merge(
        reconciliation_rows, on=["season", "game_id"], how="left", validate="one_to_one"
    )
    observed = set(
        observed_games[["season", "game_id"]]
        .drop_duplicates()
        .itertuples(index=False, name=None)
    )
    omission_by_game: dict[tuple[int, int], list[str]] = {}
    for source, rows in omissions.items():
        if source == "postseason_omissions":
            continue
        for row in rows:
            key = (int(row["season"]), int(row["game_id"]))
            omission_by_game.setdefault(key, []).append(str(source))
    issues: list[dict[str, Any]] = []
    output: list[dict[str, Any]] = []
    for row in result.itertuples(index=False):
        schedule_completed = bool(row.completed)
        values = pd.to_numeric(
            pd.Series([row.home_points, row.away_points]), errors="coerce"
        )
        outcome_valid = bool(
            schedule_completed
            and bool(row.outcome_completed)
            and values.notna().all()
            and np.isfinite(values.to_numpy(dtype=float)).all()
        )
        key = (int(row.season), int(row.game_id))
        missing_sources = sorted(omission_by_game.get(key, []))
        measurement_usable = key in observed
        if outcome_valid and measurement_usable:
            disposition, missing_reason = "eligible_with_measurements", None
        elif outcome_valid:
            disposition, missing_reason = (
                "eligible_without_measurements",
                "measurement_source_omission",
            )
        else:
            disposition = "unscorable_incomplete_or_invalid_outcome"
            missing_reason = "incomplete_or_invalid_outcome"
        if not measurement_usable or not outcome_valid:
            issues.append(
                _key_issue(
                    category="population_reconciliation",
                    season=key[0],
                    game_id=key[1],
                    source_branch=",".join(missing_sources) or None,
                    observed_status="measurement_usable"
                    if measurement_usable
                    else "missing_measurements",
                    outcome_valid=outcome_valid,
                    disposition=disposition,
                    core_blocker=not outcome_valid and schedule_completed,
                    resolved=outcome_valid,
                    details={"reconciliation_classification": row.classification},
                )
            )
        output.append(
            {
                "season": key[0],
                "week": int(row.week),
                "game_id": key[1],
                "kickoff_utc": row.kickoff_utc,
                "home_team": canonical_team(row.home_team),
                "away_team": canonical_team(row.away_team),
                "schedule_completed": schedule_completed,
                "home_points": float(values.iloc[0]) if outcome_valid else np.nan,
                "away_points": float(values.iloc[1]) if outcome_valid else np.nan,
                "outcome_valid": outcome_valid,
                "forecast_eligible": outcome_valid,
                "measurement_usable": measurement_usable,
                "measurement_exposure": int(measurement_usable and outcome_valid),
                "missing_measurement_sources": _stable_json(missing_sources),
                "missing_reason": missing_reason,
                "reconciliation_classification": row.classification,
                "disposition": disposition,
                "timing_class": RECONSTRUCTED_TIMING,
            }
        )
    frame = (
        pd.DataFrame(output, columns=POPULATION_COLUMNS)
        .sort_values(["season", "game_id"], kind="mergesort")
        .reset_index(drop=True)
    )
    if frame.duplicated(["season", "game_id"]).any():
        raise RepairV2Error("population output repeats a key")
    return frame, pd.DataFrame(issues, columns=ISSUE_COLUMNS)


def _source_rows(raw: pd.DataFrame, required: set[str], family: str) -> pd.DataFrame:
    _require_columns(raw, required, family)
    result = raw.copy()
    result["season"] = pd.to_numeric(result["season"], errors="raise").astype(int)
    result = result[~result["season"].isin(FORBIDDEN_SEASONS)].copy()
    result["team"] = result["team"].map(canonical_team)
    return result[result["team"].notna()].copy()


def normalize_recruiting_v2(
    raw: pd.DataFrame, universe: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    universe = _clean_universe(universe)
    source = raw.copy()
    if "year" not in source and "season" in source:
        source["year"] = source["season"]
    _require_columns(source, {"year", "team", "points"}, "recruiting")
    source["year"] = pd.to_numeric(source["year"], errors="raise").astype(int)
    source = source[~source["year"].isin(FORBIDDEN_SEASONS)].copy()
    source["team"] = source["team"].map(canonical_team)
    source["points"] = pd.to_numeric(source["points"], errors="coerce")
    source = source[source["team"].notna()].copy()
    issues: list[dict[str, Any]] = []
    usable: list[dict[str, Any]] = []
    for (year, team), group in source.groupby(["year", "team"], sort=True):
        values = group["points"].dropna().unique()
        if len(values) != 1 or not math.isfinite(float(values[0])):
            issues.append(
                _key_issue(
                    category="auxiliary_source_conflict",
                    family="recruiting",
                    season=int(year),
                    team=str(team),
                    disposition="null_source_value",
                    details={"rows": len(group)},
                )
            )
            continue
        usable.append(
            {"year": int(year), "team": str(team), "points": float(values[0])}
        )
    clean = pd.DataFrame(usable, columns=["year", "team", "points"])
    rows: list[dict[str, Any]] = []
    for target in universe.itertuples(index=False):
        years = list(range(int(target.season) - 3, int(target.season) + 1))
        permitted = [year for year in years if year not in FORBIDDEN_SEASONS]
        values = clean[(clean["team"] == target.team) & clean["year"].isin(permitted)]
        by_year = dict(values[["year", "points"]].itertuples(index=False, name=None))
        available = [float(by_year[year]) for year in permitted if year in by_year]
        current = by_year.get(int(target.season), np.nan)
        strict = np.nan
        if (
            len(years) == 4
            and len(permitted) == 4
            and all(year in by_year for year in years)
        ):
            strict = float(np.mean([by_year[year] for year in years]))
        if pd.isna(current):
            reason = "missing_current_recruiting"
        elif pd.isna(strict):
            reason = (
                "forbidden_2020_four_class_window"
                if 2020 in years
                else "incomplete_four_class_history"
            )
        else:
            reason = None
        rows.append(
            {
                "season": int(target.season),
                "team": target.team,
                "recruiting_current_points": current,
                "recruiting_available_average_points": float(np.mean(available))
                if available
                else np.nan,
                "recruiting_available_class_count": len(available),
                "recruiting_available_start_year": min(by_year) if by_year else np.nan,
                "recruiting_available_end_year": max(by_year) if by_year else np.nan,
                "recruiting_available_span_years": max(by_year) - min(by_year) + 1
                if by_year
                else np.nan,
                "recruiting_strict_four_class_average_points": strict,
                "recruiting_current_minus_available_average": float(
                    current - np.mean(available)
                )
                if available and pd.notna(current)
                else np.nan,
                "missing_reason": reason,
            }
        )
    return pd.DataFrame(rows), pd.DataFrame(issues, columns=ISSUE_COLUMNS)


def normalize_returning_production_v2(
    raw: pd.DataFrame, universe: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    universe = _clean_universe(universe)
    aliases = {
        "return_total_ppa": ("totalPPA", "total_ppa"),
        "return_passing_ppa": ("totalPassingPPA", "total_passing_ppa"),
        "return_rushing_ppa": ("totalRushingPPA", "total_rushing_ppa"),
        "return_receiving_ppa": ("totalReceivingPPA", "total_receiving_ppa"),
        "return_percent_ppa": ("percentPPA", "percent_ppa"),
        "return_passing_usage": ("passingUsage", "passing_usage"),
        "return_rushing_usage": ("rushingUsage", "rushing_usage"),
    }
    source = _source_rows(raw, {"season", "team"}, "returning_production")
    for target, names in aliases.items():
        source[target] = next(
            (
                pd.to_numeric(source[name], errors="coerce")
                for name in names
                if name in source
            ),
            pd.Series(np.nan, index=source.index),
        )
    issues: list[dict[str, Any]] = []
    clean: dict[tuple[int, str], dict[str, Any]] = {}
    for (season, team), group in source.groupby(["season", "team"], sort=True):
        candidates = group[list(aliases)].drop_duplicates()
        valid = len(candidates) == 1
        value = candidates.iloc[0].to_dict() if valid else {}
        if valid:
            numeric = np.asarray(list(value.values()), dtype=float)
            valid = bool(np.isfinite(numeric).all()) and all(
                0 <= float(value[name]) <= 1
                for name in (
                    "return_percent_ppa",
                    "return_passing_usage",
                    "return_rushing_usage",
                )
            )
        if not valid:
            issues.append(
                _key_issue(
                    category="auxiliary_source_conflict",
                    family="returning_production",
                    season=int(season),
                    team=str(team),
                    disposition="null_source_value",
                    details={"rows": len(group)},
                )
            )
            continue
        clean[(int(season), str(team))] = value
    rows = []
    for item in universe.itertuples(index=False):
        value = clean.get((int(item.season), str(item.team)))
        rows.append(
            {
                "season": int(item.season),
                "team": item.team,
                **(value or {name: np.nan for name in aliases}),
                "missing_reason": None
                if value
                else "missing_or_invalid_returning_production",
            }
        )
    return pd.DataFrame(rows), pd.DataFrame(issues, columns=ISSUE_COLUMNS)


def _season_records(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, str):
        try:
            value = ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return []
    return [row for row in value or [] if isinstance(row, Mapping)]


def _coach_identity(
    row: Mapping[str, Any], name_counts: Mapping[str, int]
) -> str | None:
    name = " ".join(
        str(row.get(key) or "").strip().casefold() for key in ("firstName", "lastName")
    ).strip()
    hire = str(row.get("hireDate") or "").strip()
    if not name:
        return None
    if hire:
        return sha256({"name": name, "hire_date": hire})
    return sha256({"name": name}) if name_counts.get(name, 0) == 1 else None


def normalize_coaching_v2(
    raw: pd.DataFrame, universe: pd.DataFrame, first_kickoffs: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    universe = _clean_universe(universe)
    _require_columns(raw, {"firstName", "lastName", "seasons"}, "coaching")
    _require_columns(
        first_kickoffs, {"season", "team", "first_kickoff_utc"}, "first kickoff"
    )
    names = [
        " ".join(
            str(row.get(key) or "").strip().casefold()
            for key in ("firstName", "lastName")
        ).strip()
        for row in raw.to_dict("records")
    ]
    name_counts = pd.Series(names).value_counts().to_dict()
    records: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for coach in raw.to_dict("records"):
        identity = _coach_identity(coach, name_counts)
        hire_raw = coach.get("hireDate")
        hire = (
            pd.to_datetime(hire_raw, utc=True, errors="coerce") if hire_raw else pd.NaT
        )
        for season in _season_records(coach.get("seasons")):
            year = pd.to_numeric(season.get("year"), errors="coerce")
            team = canonical_team(season.get("school"))
            if pd.isna(year) or team is None or int(year) in FORBIDDEN_SEASONS:
                continue
            if identity is None:
                issues.append(
                    _key_issue(
                        category="ambiguous_coach_identity",
                        family="coaching",
                        season=int(year),
                        team=team,
                        disposition="null_assignment",
                    )
                )
                continue
            records.append(
                {
                    "season": int(year),
                    "team": team,
                    "coach_identity": identity,
                    "hire_date": hire,
                }
            )
    history = pd.DataFrame(
        records, columns=["season", "team", "coach_identity", "hire_date"]
    ).drop_duplicates()
    kickoff = _canonical_team_frame(first_kickoffs).copy()
    kickoff["season"] = pd.to_numeric(kickoff["season"], errors="raise").astype(int)
    rows: list[dict[str, Any]] = []
    for item in universe.itertuples(index=False):
        cutoff_rows = kickoff[
            (kickoff["season"] == item.season) & (kickoff["team"] == item.team)
        ]
        if len(cutoff_rows) != 1:
            raise RepairV2Error("each team-season requires one first kickoff")
        cutoff = pd.to_datetime(
            cutoff_rows.iloc[0]["first_kickoff_utc"], utc=True, errors="coerce"
        )
        candidates = history[
            (history["season"] == item.season) & (history["team"] == item.team)
        ].copy()
        valid: list[pd.Series] = []
        for candidate in candidates.itertuples(index=False):
            hire_ok = pd.notna(candidate.hire_date) and candidate.hire_date <= cutoff
            prior_season = int(item.season) - 1
            continuing = (
                prior_season not in FORBIDDEN_SEASONS
                and not history[
                    (history["season"] == prior_season)
                    & (history["team"] == item.team)
                    & (history["coach_identity"] == candidate.coach_identity)
                ].empty
            )
            if hire_ok or (pd.isna(candidate.hire_date) and continuing):
                valid.append(candidate)
        identities = {row.coach_identity for row in valid}
        base = {
            "season": int(item.season),
            "team": item.team,
            "coach_identity": None,
            "coach_tenure": np.nan,
            "coach_tenure_lower_bound": np.nan,
            "coach_tenure_censored": np.nan,
            "coach_new": np.nan,
        }
        if len(identities) != 1:
            rows.append(
                base
                | {
                    "missing_reason": "ambiguous_coach_assignment"
                    if len(identities) > 1
                    else "missing_or_post_cutoff_coach_assignment"
                }
            )
            continue
        candidate = next(row for row in valid if row.coach_identity in identities)
        coach_history = history[
            (history["coach_identity"] == candidate.coach_identity)
            & (history["team"] == item.team)
            & (history["season"] <= item.season)
        ]
        years = set(coach_history["season"].astype(int))
        lower, expected = 0, int(item.season)
        while expected in years and expected not in FORBIDDEN_SEASONS:
            lower += 1
            expected -= 1
        hire_year = (
            int(candidate.hire_date.year) if pd.notna(candidate.hire_date) else None
        )
        exact = (
            hire_year is not None
            and expected < hire_year
            and all(
                year not in FORBIDDEN_SEASONS
                for year in range(hire_year, int(item.season) + 1)
            )
        )
        censored = not exact
        coach_new: bool | float
        if exact:
            coach_new = lower == 1
        elif lower >= 2 or (hire_year is not None and hire_year < int(item.season)):
            coach_new = False
        else:
            coach_new = np.nan
        rows.append(
            base
            | {
                "coach_identity": candidate.coach_identity,
                "coach_tenure": float(lower) if exact else np.nan,
                "coach_tenure_lower_bound": float(lower),
                "coach_tenure_censored": censored,
                "coach_new": coach_new,
                "missing_reason": "censored_coach_tenure" if censored else None,
            }
        )
    return pd.DataFrame(rows), pd.DataFrame(issues, columns=ISSUE_COLUMNS)


def normalize_roster_continuity_v2(
    raw: pd.DataFrame, universe: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    universe = _clean_universe(universe)
    _require_columns(raw, {"season", "id", "team", "position"}, "roster")
    source = _source_rows(raw, {"season", "id", "team", "position"}, "roster")
    source["id"] = source["id"].astype(str)
    source["position"] = source["position"].astype(str).str.upper()
    conflicts = source.groupby(["season", "id"])["team"].nunique()
    bad = set(conflicts[conflicts > 1].index)
    issues = [
        _key_issue(
            category="roster_identity_conflict",
            family="roster_continuity",
            season=int(season),
            team=None,
            disposition="identity_excluded",
            details={"player_id": player_id},
        )
        for season, player_id in sorted(bad)
    ]
    source["identity_excluded"] = source.apply(
        lambda row: (int(row.season), str(row.id)) in bad, axis=1
    )
    usable = source[~source["identity_excluded"]].drop_duplicates(
        ["season", "team", "id"]
    )
    rows: list[dict[str, Any]] = []
    for item in universe.itertuples(index=False):
        current_all = source[
            (source["season"] == item.season) & (source["team"] == item.team)
        ]
        current = usable[
            (usable["season"] == item.season) & (usable["team"] == item.team)
        ]
        predecessor = int(item.season) - 1
        valid_predecessor = predecessor not in FORBIDDEN_SEASONS
        prior = (
            usable[usable["season"] == predecessor]
            if valid_predecessor
            else pd.DataFrame(columns=usable.columns)
        )
        base = {
            "season": int(item.season),
            "team": item.team,
            "roster_current_observed_size": int(current_all["id"].nunique()),
            "roster_current_usable_size": int(current["id"].nunique()),
            "roster_current_qb_count": int(
                current[current["position"].eq("QB")]["id"].nunique()
            ),
            "roster_identity_exclusions": int(current_all["identity_excluded"].sum()),
            "roster_predecessor_season": predecessor if valid_predecessor else np.nan,
            "roster_same_team_return_count": np.nan,
            "roster_same_team_return_share": np.nan,
            "roster_same_team_return_qb_count": np.nan,
            "roster_incoming_experienced_count": np.nan,
            "roster_incoming_experienced_share": np.nan,
            "roster_incoming_experienced_qb_count": np.nan,
        }
        if not valid_predecessor or prior.empty:
            rows.append(
                base
                | {
                    "missing_reason": "prior_roster_outside_lineage"
                    if not valid_predecessor
                    else "missing_predecessor_roster"
                }
            )
            continue
        current_ids = set(current["id"])
        same_ids = current_ids & set(prior[prior["team"] == item.team]["id"])
        other_ids = set(prior[prior["team"] != item.team]["id"])
        incoming = (current_ids - same_ids) & other_ids
        denominator = len(current_ids)
        rows.append(
            base
            | {
                "roster_same_team_return_count": len(same_ids),
                "roster_same_team_return_share": len(same_ids) / denominator
                if denominator
                else np.nan,
                "roster_same_team_return_qb_count": int(
                    current[
                        current["id"].isin(same_ids) & current["position"].eq("QB")
                    ]["id"].nunique()
                ),
                "roster_incoming_experienced_count": len(incoming),
                "roster_incoming_experienced_share": len(incoming) / denominator
                if denominator
                else np.nan,
                "roster_incoming_experienced_qb_count": int(
                    current[
                        current["id"].isin(incoming) & current["position"].eq("QB")
                    ]["id"].nunique()
                ),
                "missing_reason": None if denominator else "missing_current_roster",
            }
        )
    return pd.DataFrame(rows), pd.DataFrame(issues, columns=ISSUE_COLUMNS)


def assemble_auxiliary(
    *,
    universe: pd.DataFrame,
    recruiting: pd.DataFrame,
    returning_production: pd.DataFrame,
    coaching: pd.DataFrame,
    roster_continuity: pd.DataFrame,
    source_capture_ids: Mapping[str, Sequence[str]],
) -> pd.DataFrame:
    universe = _clean_universe(universe)
    frames = {
        "recruiting": recruiting,
        "returning_production": returning_production,
        "coaching": coaching,
        "roster_continuity": roster_continuity,
    }
    rows: list[pd.DataFrame] = []
    for family in FOOTBALL_FAMILIES:
        frame = frames[family].copy()
        expected = universe[["season", "team"]]
        frame = expected.merge(
            frame, on=["season", "team"], how="left", validate="one_to_one"
        )
        frame["family"] = family
        frame["timing_class"] = RECONSTRUCTED_TIMING
        frame["historical_eligible"] = False
        frame["live_eligible"] = False
        frame["permitted_role"] = "phase4a_prior_research_only"
        frame["source_capture_ids"] = _stable_json(
            sorted(source_capture_ids.get(family, ()))
        )
        for column in AUXILIARY_COLUMNS:
            if column not in frame:
                frame[column] = np.nan
        rows.append(frame.loc[:, AUXILIARY_COLUMNS])
    result = (
        pd.concat(rows, ignore_index=True)
        .sort_values(["family", "season", "team"], kind="mergesort")
        .reset_index(drop=True)
    )
    if result.duplicated(["family", "season", "team"]).any():
        raise RepairV2Error("auxiliary output repeats a key")
    return result


def coverage_and_admission(
    auxiliary: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, dict[str, Any]]]:
    _require_columns(
        auxiliary, {"family", "season", "team", "missing_reason"}, "auxiliary"
    )
    rows: list[dict[str, Any]] = []
    admission: dict[str, dict[str, Any]] = {}
    for family in FOOTBALL_FAMILIES:
        family_frame = auxiliary[auxiliary["family"] == family]
        for season, group in family_frame.groupby("season", sort=True):
            ambiguity = int(
                group["missing_reason"]
                .fillna("")
                .str.contains("ambiguous|conflict", case=False)
                .sum()
            )
            structural = int(
                group["missing_reason"]
                .fillna("")
                .str.contains("outside_lineage|forbidden_2020", case=False)
                .sum()
            )
            rows.append(
                {
                    "family": family,
                    "season": int(season),
                    "slice": "family",
                    "required_rows": len(group),
                    "non_null_rows": int(
                        group[list(FAMILY_FEATURES[family])].notna().all(axis=1).sum()
                    ),
                    "missing_rows": int(
                        group[list(FAMILY_FEATURES[family])]
                        .notna()
                        .all(axis=1)
                        .eq(False)
                        .sum()
                    ),
                    "coverage_fraction": float(
                        group[list(FAMILY_FEATURES[family])].notna().all(axis=1).mean()
                    ),
                    "distinct_values": int(
                        group[list(FAMILY_FEATURES[family])].stack().nunique()
                    ),
                    "constant_warning": False,
                    "ambiguity_rows": ambiguity,
                    "structural_missing_rows": structural,
                    "historical_eligible": False,
                    "live_eligible": False,
                    "timing_class": RECONSTRUCTED_TIMING,
                }
            )
            for feature in FAMILY_FEATURES[family]:
                values = group[feature].dropna()
                constant = len(values) > 0 and values.nunique() <= 1
                rows.append(
                    {
                        "family": family,
                        "season": int(season),
                        "slice": feature,
                        "required_rows": len(group),
                        "non_null_rows": len(values),
                        "missing_rows": len(group) - len(values),
                        "coverage_fraction": len(values) / len(group)
                        if len(group)
                        else 0.0,
                        "distinct_values": int(values.nunique()),
                        "constant_warning": constant,
                        "ambiguity_rows": ambiguity,
                        "structural_missing_rows": structural,
                        "historical_eligible": not constant and len(values) > 0,
                        "live_eligible": False,
                        "timing_class": RECONSTRUCTED_TIMING,
                    }
                )
        feature_admitted = []
        for feature in FAMILY_FEATURES[family]:
            values = family_frame[feature].dropna()
            feature_admitted.append(len(values) > 0 and values.nunique() > 1)
        admitted = bool(feature_admitted) and all(feature_admitted)
        admission[family] = {
            "historical_eligible": admitted,
            "live_eligible": False,
            "permitted_role": "phase4a_prior_research_only" if admitted else "rejected",
            "reason": None if admitted else "missing_or_constant_modeled_feature",
        }
    report = pd.DataFrame(rows, columns=COVERAGE_COLUMNS)
    report["historical_eligible"] = report.apply(
        lambda row: admission[row.family]["historical_eligible"]
        if row.slice == "family"
        else row.historical_eligible,
        axis=1,
    )
    for family, detail in admission.items():
        auxiliary.loc[auxiliary["family"] == family, "historical_eligible"] = detail[
            "historical_eligible"
        ]
        auxiliary.loc[auxiliary["family"] == family, "permitted_role"] = detail[
            "permitted_role"
        ]
    return report.sort_values(
        ["family", "season", "slice"], kind="mergesort"
    ).reset_index(drop=True), admission


def repair_manifest(
    *,
    identity: Mapping[str, Any],
    parents: Mapping[str, Any],
    output_refs: Mapping[str, Any],
    output_rows: Mapping[str, int],
    population: pd.DataFrame,
    family_admission: Mapping[str, Any],
    capture_plan_ref: Mapping[str, Any] | None,
) -> dict[str, Any]:
    summary = {
        "scheduled_games": int(len(population)),
        "forecast_eligible_games": int(population["forecast_eligible"].sum()),
        "measurement_usable_games": int(population["measurement_usable"].sum()),
        "measurement_missing_games": int((~population["measurement_usable"]).sum()),
        "population_sha256": sha256(
            population.loc[:, POPULATION_COLUMNS].to_dict("records")
        ),
    }
    return signed_payload(
        {
            "schema_version": REPAIR_MANIFEST_SCHEMA,
            "state": "repaired_reconstructed_only",
            "identity": dict(identity),
            "parents": dict(parents),
            "output_refs": dict(output_refs),
            "output_rows": dict(output_rows),
            "population": summary,
            "family_admission": dict(family_admission),
            "capture_plan_ref": dict(capture_plan_ref) if capture_plan_ref else None,
            "timing_class": RECONSTRUCTED_TIMING,
            "production_activation_authorized": False,
            "model_selection_authorized": False,
        }
    )
