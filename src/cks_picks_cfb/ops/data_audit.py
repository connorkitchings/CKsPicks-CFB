"""Data-readiness audit for the 2026 training and live Week 0 path."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Mapping

import pandas as pd
import psycopg

from cks_picks_cfb.data.lake import DatasetRef, read_dataset
from cks_picks_cfb.data.storage import StorageBackend
from cks_picks_cfb.models.training_policy import (
    TrainingPolicy,
    validate_feature_lineage,
)


@dataclass(frozen=True)
class AuditResult:
    passed: bool
    checks: Mapping[str, bool]
    coverage: Mapping[str, object]
    errors: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def audit_feature_frame(
    frame: pd.DataFrame,
    policy: TrainingPolicy,
    *,
    mode: str = "model-ready",
) -> AuditResult:
    """Validate one immutable Gold frame without consulting mutable partitions."""
    if mode not in {"structural", "model-ready"}:
        raise ValueError("audit mode must be structural or model-ready")
    errors: list[str] = []
    checks: dict[str, bool] = {}
    required = {
        "season",
        "game_id",
        "spread_target",
        "total_target",
        "prior_source_season",
        "prior_season_gap",
        "home_completed_games",
        "away_completed_games",
        "prediction_regime",
    }
    missing = sorted(required - set(frame.columns))
    checks["required_schema"] = not missing
    if missing:
        errors.append(f"missing columns: {missing}")
        return AuditResult(False, checks, {}, tuple(errors))
    try:
        validate_feature_lineage(frame, policy)
        checks["temporal_lineage"] = True
    except ValueError as exc:
        checks["temporal_lineage"] = False
        errors.append(str(exc))
    labeled = frame[frame["season"].isin(policy.labeled_years)]
    observed_years = tuple(sorted(labeled["season"].astype(int).unique()))
    checks["labeled_year_coverage"] = observed_years == policy.labeled_years
    if not checks["labeled_year_coverage"]:
        errors.append(f"labeled season coverage is {observed_years}")
    duplicates = labeled.duplicated(["season", "game_id"]).sum()
    checks["unique_game_keys"] = duplicates == 0
    if duplicates:
        errors.append(f"duplicate season/game_id rows: {duplicates}")
    missing_targets = int(
        labeled[["spread_target", "total_target"]].isna().any(axis=1).sum()
    )
    checks["reproducible_targets"] = missing_targets == 0
    if missing_targets:
        errors.append(f"rows with missing outcomes: {missing_targets}")
    regimes = set(labeled["prediction_regime"].dropna().astype(str))
    expected_regimes = {
        "preseason",
        "one_game",
        "two_games",
        "three_games",
        "established",
    }
    checks["five_regimes"] = regimes == expected_regimes
    if not checks["five_regimes"]:
        errors.append(f"regime coverage is {sorted(regimes)}")
    baseline_columns = {
        "baseline_spread_prediction",
        "baseline_total_prediction",
    }
    if mode == "model-ready":
        baseline_rows = labeled[labeled["season"].astype(int).isin({2022, 2023, 2024})]
        checks["baseline_predictions"] = (
            baseline_columns.issubset(frame.columns)
            and not baseline_rows[list(baseline_columns)].isna().any().any()
        )
        if not checks["baseline_predictions"]:
            errors.append("explicit spread/total baseline predictions are incomplete")
    prior_features = [
        column for column in frame if column.startswith(("home_prior_", "away_prior_"))
    ]
    current_features = [
        column
        for column in frame
        if column.startswith(
            ("home_adj_", "away_adj_", "home_current_", "away_current_")
        )
    ]
    checks["separate_prior_current_features"] = bool(
        prior_features and current_features
    )
    if not checks["separate_prior_current_features"]:
        errors.append(
            "Gold data does not contain separate prior and current feature blocks"
        )
    lined = (
        labeled.get("home_team_spread_line", pd.Series(index=labeled.index)).notna()
        & labeled.get("total_line", pd.Series(index=labeled.index)).notna()
    )
    coverage = {
        "rows_by_season": {
            str(year): int(count)
            for year, count in labeled.groupby("season").size().items()
        },
        "rows_by_regime": {
            str(regime): int(count)
            for regime, count in labeled.groupby("prediction_regime").size().items()
        },
        "complete_market_rows": int(lined.sum()),
        "market_coverage": float(lined.mean()) if len(lined) else 0.0,
    }
    return AuditResult(all(checks.values()), checks, coverage, tuple(errors))


def latest_gold_feature_ref(conn_url: str, *, mode: str) -> DatasetRef:
    dataset = (
        "point_in_time_matchups_core"
        if mode == "structural"
        else "point_in_time_matchups"
    )
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT version_id, schema_version, content_sha, uri "
                "FROM catalog.dataset_versions "
                "WHERE dataset = %s AND tier = 'gold' "
                "AND state = 'validated' ORDER BY as_of DESC, created_at DESC LIMIT 1",
                (dataset,),
            )
            row = cur.fetchone()
    if not row:
        raise LookupError(f"No validated Gold {dataset} dataset exists")
    return DatasetRef(dataset, str(row[0]), str(row[1]), str(row[2]), str(row[3]))


def latest_2026_schedule_ref(conn_url: str) -> DatasetRef:
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT dataset, version_id, schema_version, content_sha, uri "
                "FROM catalog.dataset_versions WHERE dataset IN ('games', 'schedules') "
                "AND tier = 'silver' AND state = 'validated' "
                "AND partitions @> '{\"seasons\": [2026]}'::jsonb "
                "ORDER BY as_of DESC, created_at DESC LIMIT 1"
            )
            row = cur.fetchone()
    if not row:
        raise LookupError("No validated Silver 2026 schedule dataset exists")
    return DatasetRef(str(row[0]), str(row[1]), str(row[2]), str(row[3]), str(row[4]))


def audit_catalog(
    conn_url: str,
    storage: StorageBackend,
    policy: TrainingPolicy,
    *,
    mode: str = "model-ready",
) -> tuple[DatasetRef, AuditResult]:
    ref = latest_gold_feature_ref(conn_url, mode=mode)
    frame = read_dataset(storage, ref)
    result = audit_feature_frame(frame, policy, mode=mode)
    schedule_ref = latest_2026_schedule_ref(conn_url)
    schedule = read_dataset(storage, schedule_ref)
    game_column = "game_id" if "game_id" in schedule else "id"
    schedule_ok = bool(
        not schedule.empty
        and game_column in schedule
        and not schedule[game_column].isna().any()
        and not schedule[game_column].duplicated().any()
        and "week" in schedule
        and 0
        in set(pd.to_numeric(schedule["week"], errors="coerce").dropna().astype(int))
    )
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT dataset FROM catalog.dataset_versions "
                "WHERE tier = 'silver' AND state = 'validated'"
            )
            silver_datasets = {str(row[0]) for row in cur.fetchall()}
            cur.execute(
                "SELECT COUNT(*) FROM catalog.source_captures "
                "WHERE state IN ('failed', 'quarantined')"
            )
            invalid_capture_count = int(cur.fetchone()[0])
            cur.execute(
                "SELECT COUNT(*) FROM catalog.source_reconciliations WHERE blocking"
            )
            blocking_reconciliations = int(cur.fetchone()[0])
            cur.execute(
                "SELECT COUNT(*) FROM catalog.dataset_versions dv "
                "WHERE dv.tier = 'silver' AND dv.state = 'validated' "
                "AND NOT EXISTS (SELECT 1 FROM catalog.dataset_capture_dependencies dcd "
                "WHERE dcd.child_version_id = dv.version_id)"
            )
            unlinked_silver_versions = int(cur.fetchone()[0])
    required_silver = {
        "games",
        "plays",
        "team_game_stats",
        "market_quotes",
        "market_snapshots",
    }
    checks = {
        **result.checks,
        "schedule_2026_week0": schedule_ok,
        "required_silver_datasets": required_silver.issubset(silver_datasets),
        "source_capture_health": invalid_capture_count == 0,
        "reconciliation_clear": blocking_reconciliations == 0,
        "silver_bronze_lineage": unlinked_silver_versions == 0,
    }
    schedule_weeks = pd.to_numeric(
        schedule.get("week", pd.Series(index=schedule.index, dtype=float)),
        errors="coerce",
    )
    coverage = {
        **result.coverage,
        "schedule_2026_version": schedule_ref.version_id,
        "schedule_2026_rows": len(schedule),
        "schedule_2026_week0_rows": int((schedule_weeks == 0).sum()),
        "silver_datasets": sorted(silver_datasets),
        "invalid_source_captures": invalid_capture_count,
        "blocking_reconciliations": blocking_reconciliations,
        "unlinked_silver_versions": unlinked_silver_versions,
    }
    errors = list(result.errors)
    if not schedule_ok:
        errors.append("2026 schedule is missing, duplicated, or has no Week 0 rows")
    if not checks["required_silver_datasets"]:
        errors.append(
            f"missing required Silver datasets: {sorted(required_silver - silver_datasets)}"
        )
    if invalid_capture_count:
        errors.append(f"failed/quarantined source captures: {invalid_capture_count}")
    if blocking_reconciliations:
        errors.append(f"blocking source reconciliations: {blocking_reconciliations}")
    if unlinked_silver_versions:
        errors.append(
            f"Silver versions without Bronze lineage: {unlinked_silver_versions}"
        )
    return ref, AuditResult(all(checks.values()), checks, coverage, tuple(errors))


def result_json(ref: DatasetRef, result: AuditResult) -> str:
    return json.dumps(
        {"dataset_ref": asdict(ref), **result.to_dict()},
        indent=2,
        sort_keys=True,
    )
