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
    labeled_training_frame,
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
        # Validate live inference rows without labeling them, then apply the
        # stricter 2021-2025 contract only to the training slice.
        labeled = labeled_training_frame(frame, policy)
        checks["temporal_lineage"] = True
    except ValueError as exc:
        checks["temporal_lineage"] = False
        errors.append(str(exc))
        labeled = frame.iloc[0:0].copy()
    observed_years = tuple(sorted(labeled["season"].astype(int).unique()))
    checks["labeled_year_coverage"] = observed_years == policy.labeled_years
    if not checks["labeled_year_coverage"]:
        errors.append(f"labeled season coverage is {observed_years}")
    # Key uniqueness is a dataset-level invariant, including future inference
    # rows. Target/reproducibility checks below intentionally only use labeled
    # historical rows.
    duplicates = frame.duplicated(["season", "game_id"]).sum()
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
    legacy_regimes = {
        "preseason",
        "one_game",
        "two_games",
        "three_games",
        "established",
    }
    canonical_regimes = {"game_1", "game_2", "game_3", "game_4", "established"}
    checks["route_coverage"] = regimes == legacy_regimes or regimes == canonical_regimes
    if not checks["route_coverage"]:
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
    required_silver = {"games", "plays", "reconciled_team_game"}
    legacy_query = (
        "SELECT COALESCE(SUM(dv.row_count), 0) FROM catalog.dataset_versions dv "
        "WHERE dv.dataset = 'legacy_market_references' AND dv.tier = 'silver' "
        "AND dv.state = 'validated'"
    )
    canonical_market_query = (
        "SELECT COUNT(*) FROM catalog.dataset_versions dv "
        "WHERE dv.dataset IN ('market_quotes', 'market_snapshots') "
        "AND dv.tier = 'silver' AND dv.state = 'validated'"
    )
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT dataset FROM catalog.dataset_versions "
                "WHERE tier = 'silver' AND state = 'validated'"
            )
            silver_datasets = {str(row[0]) for row in cur.fetchall()}
            cur.execute(legacy_query)
            legacy_reference_rows = int(cur.fetchone()[0])
            cur.execute(canonical_market_query)
            canonical_market_versions = int(cur.fetchone()[0])
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
                "WITH RECURSIVE ancestry(child_version_id, ancestor_version_id) AS ("
                "  SELECT dv.version_id, dv.version_id "
                "  FROM catalog.dataset_versions dv "
                "  WHERE dv.tier = 'silver' AND dv.state = 'validated' "
                "  UNION "
                "  SELECT ancestry.child_version_id, dependency.parent_version_id "
                "  FROM ancestry "
                "  JOIN catalog.dataset_dependencies dependency "
                "    ON dependency.child_version_id = ancestry.ancestor_version_id"
                "), linked AS ("
                "  SELECT DISTINCT ancestry.child_version_id "
                "  FROM ancestry "
                "  JOIN catalog.dataset_capture_dependencies capture_dependency "
                "    ON capture_dependency.child_version_id = ancestry.ancestor_version_id"
                ") "
                "SELECT COUNT(*) FROM catalog.dataset_versions dv "
                "WHERE dv.tier = 'silver' AND dv.state = 'validated' "
                "AND NOT EXISTS ("
                "  SELECT 1 FROM linked WHERE linked.child_version_id = dv.version_id"
                ")"
            )
            unlinked_silver_versions = int(cur.fetchone()[0])
    checks = {
        **result.checks,
        "schedule_2026_week0": schedule_ok,
        "required_silver_datasets": required_silver.issubset(silver_datasets),
        "legacy_market_references_preserved": legacy_reference_rows > 0,
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
        "legacy_market_reference_rows": legacy_reference_rows,
        "canonical_market_versions": canonical_market_versions,
        "exact_historical_market_replay_blocked": True,
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


def audit_exact_markets(
    conn_url: str, storage: StorageBackend
) -> tuple[DatasetRef, AuditResult]:
    """Report legacy market quarantine without treating it as a data failure."""
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT version_id, schema_version, content_sha, uri, row_count "
                "FROM catalog.dataset_versions "
                "WHERE dataset = 'legacy_market_references' AND tier = 'silver' "
                "AND state = 'validated' "
                "ORDER BY as_of DESC, created_at DESC LIMIT 1"
            )
            legacy_row = cur.fetchone()
            cur.execute(
                "SELECT COUNT(*) FROM catalog.dataset_versions dv "
                "WHERE dv.dataset IN ('market_quotes', 'market_snapshots') "
                "AND dv.tier = 'silver' AND dv.state = 'validated'"
            )
            canonical_market_versions = int(cur.fetchone()[0])
            cur.execute(
                "SELECT COUNT(*) FROM catalog.dataset_versions dv "
                "JOIN catalog.dataset_capture_dependencies dcd "
                "ON dcd.child_version_id = dv.version_id "
                "JOIN catalog.source_captures sc "
                "ON sc.capture_id = dcd.capture_id "
                "WHERE dv.dataset IN ('market_quotes', 'market_snapshots') "
                "AND dv.tier = 'silver' AND dv.state = 'validated' "
                "AND sc.provider = 'legacy_cfbd_export'"
            )
            legacy_in_canonical = int(cur.fetchone()[0])
            cur.execute(
                "SELECT COUNT(*) FROM catalog.dataset_versions dv "
                "JOIN catalog.dataset_capture_dependencies dcd "
                "ON dcd.child_version_id = dv.version_id "
                "JOIN catalog.source_captures sc "
                "ON sc.capture_id = dcd.capture_id "
                "WHERE dv.dataset = 'legacy_market_references' "
                "AND dv.tier = 'silver' AND dv.state = 'validated' "
                "AND sc.provider != 'legacy_cfbd_export'"
            )
            non_legacy_in_legacy = int(cur.fetchone()[0])
    checks: dict[str, bool] = {
        "legacy_references_preserved": legacy_row is not None,
        "canonical_markets_exclude_legacy": legacy_in_canonical == 0,
        "legacy_lineage_pure": non_legacy_in_legacy == 0,
    }
    errors: list[str] = []
    coverage: dict[str, object] = {
        "canonical_market_versions": canonical_market_versions,
        "legacy_in_canonical_capture_links": legacy_in_canonical,
        "non_legacy_in_legacy_capture_links": non_legacy_in_legacy,
        "exact_replay_available": False,
        "grading_available": False,
        "lean_available": False,
        "market_promotion_gate": "blocked_until_authentic_quotes",
    }
    if not checks["legacy_references_preserved"]:
        errors.append("no validated legacy_market_references dataset exists")
    if not checks["canonical_markets_exclude_legacy"]:
        errors.append(
            f"canonical market datasets depend on {legacy_in_canonical} "
            "legacy_cfbd_export captures"
        )
    if not checks["legacy_lineage_pure"]:
        errors.append(
            f"legacy_market_references depends on {non_legacy_in_legacy} "
            "non-legacy captures"
        )
    if legacy_row is not None:
        legacy_ref = DatasetRef(
            "legacy_market_references",
            str(legacy_row[0]),
            str(legacy_row[1]),
            str(legacy_row[2]),
            str(legacy_row[3]),
        )
        frame = read_dataset(storage, legacy_ref)
        legacy_row_count = int(legacy_row[4])
        flags_ok = bool(
            not frame["exact_replay_eligible"].any()
            and not frame["grading_eligible"].any()
            and not frame["lean_eligible"].any()
            and (frame["timestamp_status"] == "missing_authentic_timestamp").all()
        )
        checks["legacy_flags_constant"] = flags_ok
        coverage["legacy_rows"] = legacy_row_count
        coverage["legacy_seasons"] = sorted(
            frame["season"].astype(int).unique().tolist()
        )
        coverage["legacy_games"] = int(frame["game_id"].nunique())
        if not flags_ok:
            errors.append(
                "legacy market reference flags are not the constant quarantine"
            )
    else:
        legacy_ref = DatasetRef(
            "legacy_market_references", "none", "legacy_market_references_v1", "", ""
        )
    return legacy_ref, AuditResult(
        all(checks.values()), checks, coverage, tuple(errors)
    )


def result_json(ref: DatasetRef, result: AuditResult) -> str:
    def json_default(value: object) -> object:
        """Convert scalar values returned by pandas/numpy to JSON primitives."""
        if hasattr(value, "item"):
            return value.item()  # type: ignore[no-any-return]
        raise TypeError(
            f"Object of type {type(value).__name__} is not JSON serializable"
        )

    return json.dumps(
        {"dataset_ref": asdict(ref), **result.to_dict()},
        indent=2,
        sort_keys=True,
        default=json_default,
    )
