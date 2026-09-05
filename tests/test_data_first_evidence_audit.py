"""Fixture-driven tests for the Phase 1 data-first evidence audit."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from cks_picks_cfb.data.evidence_audit import (
    AUDIT_SCHEMA_VERSION,
    ImmutableAuditWriter,
    add_team_experience,
    canonical_json,
    classify_schedule,
    extract_dataset_refs,
    frame_audit,
    join_cardinality_audit,
    lineage_cycles,
    metrics_match,
    numeric_semantics_audit,
    pregame_timing_audit,
    recompute_prediction_metrics,
    require_resolved_manifest,
    result_disposition,
    sha256,
    stage_coverage,
    validate_output_prefix,
)
from cks_picks_cfb.data.storage import StorageBackend


class MemoryStorage(StorageBackend):
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def read_bytes(self, path):
        return self.objects[path]

    def write_bytes(self, data, path):
        self.objects[path] = data

    def exists(self, path):
        return path in self.objects

    def list_files(self, prefix):
        return sorted(path for path in self.objects if path.startswith(prefix))

    def read_parquet(self, path):
        raise NotImplementedError

    def write_parquet(self, df, path):
        raise NotImplementedError

    def read_csv(self, path, **kwargs):
        raise NotImplementedError

    def write_csv(self, df, path, **kwargs):
        raise NotImplementedError

    def get_full_path(self, path):
        return path

    def read_index(self, entity, filters, columns=None):
        raise NotImplementedError

    def write(self, entity, records, partition, *, overwrite=True):
        raise NotImplementedError

    def root(self):
        return "memory"


def _games() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "season": 2025,
                "id": 1,
                "season_type": "regular",
                "start_date": "2025-08-30T16:00:00Z",
                "home_team": "Alpha",
                "away_team": "Beta",
                "home_classification": "fbs",
                "away_classification": "fbs",
                "completed": True,
                "home_points": 28,
                "away_points": 21,
            },
            {
                "season": 2025,
                "id": 2,
                "season_type": "regular",
                "start_date": "2025-09-06T16:00:00Z",
                "home_team": "Alpha",
                "away_team": "FCS State",
                "home_classification": "fbs",
                "away_classification": "fcs",
                "completed": True,
                "home_points": 35,
                "away_points": 7,
            },
            {
                "season": 2025,
                "id": 3,
                "season_type": "postseason",
                "start_date": "2025-12-20T16:00:00Z",
                "home_team": "Beta",
                "away_team": "Gamma",
                "home_classification": None,
                "away_classification": "fbs",
                "completed": False,
                "status": "canceled",
            },
            {
                "season": 2025,
                "id": 4,
                "season_type": "regular",
                "start_date": "2025-09-13T16:00:00Z",
                "home_team": "Unknown",
                "away_team": "FCS State",
                "home_classification": None,
                "away_classification": "fcs",
                "completed": False,
            },
        ]
    )


def test_schedule_includes_fbs_fcs_postseason_and_unresolved_classification():
    teams = pd.DataFrame(
        [
            {"season": 2025, "team": "Beta", "classification": "fbs"},
            {"season": 2025, "team": "Gamma", "classification": "fbs"},
        ]
    )
    schedule, conflicts = classify_schedule(_games(), teams)

    assert set(schedule["game_id"]) == {1, 2, 3, 4}
    assert schedule.set_index("game_id").loc[2, "population"] == "fbs_fcs"
    assert schedule.set_index("game_id").loc[3, "season_type"] == "postseason"
    assert schedule.set_index("game_id").loc[3, "completion_status"] == "canceled"
    assert schedule.set_index("game_id").loc[4, "population"] == "unresolved"
    assert conflicts == []


def test_schedule_reports_classification_conflict_and_rejects_duplicate_or_2020():
    teams = pd.DataFrame([{"season": 2025, "team": "Alpha", "classification": "fcs"}])
    _, conflicts = classify_schedule(_games().iloc[:1], teams)
    assert conflicts[0]["side"] == "home"

    with pytest.raises(ValueError, match="duplicate"):
        classify_schedule(pd.concat([_games().iloc[:1]] * 2, ignore_index=True))
    forbidden = _games().iloc[:1].assign(season=2020)
    with pytest.raises(ValueError, match="2020"):
        classify_schedule(forbidden)


def test_team_experience_uses_each_teams_own_completed_games_and_byes():
    schedule, _ = classify_schedule(_games().iloc[:3])
    result = add_team_experience(schedule).set_index("game_id")

    assert result.loc[1, "home_completed_before"] == 0
    assert result.loc[2, "home_completed_before"] == 1
    assert result.loc[2, "away_completed_before"] == 0
    assert bool(result.loc[2, "asymmetric_experience"])
    assert result.loc[3, "away_completed_before"] == 0
    assert result.loc[3, "matchup_max_completed"] == 1


def test_stage_coverage_reconciles_exclusions_and_preserves_cancellations():
    schedule, _ = classify_schedule(_games().iloc[:3])
    coverage, exclusions = stage_coverage(
        add_team_experience(schedule),
        {"outcomes": {1, 2}, "plays": {1}},
    )
    for row in coverage.to_dict("records"):
        assert row["denominator_count"] == row["admitted_count"] + row["excluded_count"]
    canceled = exclusions[exclusions["game_id"].eq(3)]
    assert set(canceled["reason_code"]) == {"canceled"}


def test_frame_audit_reports_duplicates_infinity_nulls_and_forbidden_season():
    frame = pd.DataFrame(
        [
            {"season": 2020, "game_id": 1, "value": np.inf},
            {"season": 2020, "game_id": 1, "value": None},
        ]
    )
    result = frame_audit(frame, dataset="fixture", key_columns=("season", "game_id"))
    assert result["duplicate_key_rows"] == 2
    assert result["infinite_numeric_values"] == 1
    assert result["null_counts"]["value"] == 1
    assert result["forbidden_2020"]

    no_key = frame_audit(pd.DataFrame({"value": [1]}), dataset="no-key", key_columns=())
    assert no_key["duplicate_key_rows"] is None


def test_join_cardinality_exposes_invalid_and_many_to_many_joins():
    left = pd.DataFrame({"game_id": [1, 1, 2]})
    right = pd.DataFrame({"game_id": [1, 1, 3]})
    result = join_cardinality_audit(left, right, keys=("game_id",))
    assert result["many_to_many"]
    assert result["left_only_keys"] == 1
    assert result["right_only_keys"] == 1
    missing = join_cardinality_audit(left, right, keys=("season", "game_id"))
    assert missing["missing_left_keys"] == ["season"]


def test_numeric_semantics_exposes_units_exposure_ranges_and_conditioning():
    frame = pd.DataFrame(
        {
            "exposure": [0.0, None, 2.0],
            "rate": [-0.1, 0.5, 1.1],
            "x": [1.0, 2.0, 3.0],
            "x_copy": [2.0, 4.0, 6.0],
        }
    )
    result = numeric_semantics_audit(
        frame, exposures=("exposure", "missing"), bounded={"rate": (0.0, 1.0)}
    )
    assert result["missing_exposure_columns"] == ["missing"]
    assert result["zero_exposure_rows"]["exposure"] == 1
    assert result["null_exposure_rows"]["exposure"] == 1
    assert result["range_failure_rows"]["rate"] == 2
    assert result["condition_number"] is not None


def test_pregame_timing_keeps_reconstructed_and_unresolved_rows_visible():
    frame = pd.DataFrame(
        [
            {"game_id": 1, "captured_at": "2025-08-29T00:00:00Z"},
            {"game_id": 1, "captured_at": "2025-08-31T00:00:00Z"},
            {"game_id": 2, "captured_at": None},
        ]
    )
    result = pregame_timing_audit(
        frame,
        kickoff_by_game={1: pd.Timestamp("2025-08-30T16:00:00Z")},
    )
    assert result["pregame_rows"] == 1
    assert result["postgame_or_reconstructed_rows"] == 1
    assert result["unresolved_rows"] == 1


def test_prediction_metrics_distinguish_stacked_rows_unique_games_and_nonfinite():
    frame = pd.DataFrame(
        [
            {
                "candidate_id": "a",
                "season": 2025,
                "game_id": 1,
                "predicted_margin": 3.0,
                "actual_margin": 1.0,
            },
            {
                "candidate_id": "a",
                "season": 2025,
                "game_id": 1,
                "predicted_margin": 3.0,
                "actual_margin": 1.0,
            },
            {
                "candidate_id": "a",
                "season": 2025,
                "game_id": 2,
                "predicted_margin": np.inf,
                "actual_margin": 1.0,
            },
        ]
    )
    result = recompute_prediction_metrics(frame).iloc[0]
    assert result["candidate_rows"] == 3
    assert result["unique_games"] == 2
    assert result["duplicate_game_rows"] == 2
    assert result["nonfinite_rows"] == 1
    assert result["finite_unique_games"] == 0


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (
            {
                "lineage_resolved": True,
                "evidence_readable": True,
                "counts_match": True,
                "metrics_match_report": True,
                "correctness_defect": False,
            },
            "reproducible",
        ),
        (
            {
                "lineage_resolved": True,
                "evidence_readable": True,
                "counts_match": False,
                "metrics_match_report": True,
                "correctness_defect": False,
            },
            "requires-correction",
        ),
        (
            {
                "lineage_resolved": False,
                "evidence_readable": False,
                "counts_match": False,
                "metrics_match_report": False,
                "correctness_defect": False,
            },
            "unsupported",
        ),
    ],
)
def test_result_disposition_statuses(kwargs, expected):
    result = result_disposition(
        result_id="fixture",
        modeling_status="historical-only",
        **kwargs,
    )
    assert result["evidence_status"] == expected


def test_metric_tolerance_handles_exact_and_reported_rounding():
    assert metrics_match(1.0, 1.0 + 1e-10)
    assert metrics_match(13.30, 13.304, rounded_digits=2)
    assert not metrics_match(13.30, 13.31, rounded_digits=2)


def test_lineage_ref_extraction_cycles_and_sealed_manifest_identity():
    payload = {
        "nested": {
            "dataset": "games",
            "version_id": "v1",
            "schema_version": "1",
            "content_sha": "a" * 64,
            "uri": "lake/games.parquet",
        }
    }
    assert extract_dataset_refs(payload)[0].version_id == "v1"
    cycles = lineage_cycles(
        [
            {"child_version_id": "a", "parent_version_id": "b"},
            {"child_version_id": "b", "parent_version_id": "a"},
        ]
    )
    assert cycles == [["a", "b", "a"]]

    manifest = {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "state": "resolved_with_blockers",
        "blockers": [{"error": "missing"}],
    }
    manifest["manifest_sha256"] = sha256(canonical_json(manifest))
    require_resolved_manifest(manifest)
    manifest["state"] = "resolved"
    with pytest.raises(Exception, match="identity"):
        require_resolved_manifest(manifest)


def test_immutable_writer_is_idempotent_and_namespace_constrained():
    storage = MemoryStorage()
    writer = ImmutableAuditWriter(storage, run_id="run-1")
    uri = writer.write_json("summary.json", {"value": 1})
    assert writer.write_json("summary.json", {"value": 1}) == uri
    with pytest.raises(FileExistsError, match="collision"):
        writer.write_json("summary.json", {"value": 2})
    with pytest.raises(ValueError, match="relative"):
        writer.write_bytes("../escape", b"bad")
    with pytest.raises(ValueError, match="exactly"):
        validate_output_prefix("artifacts/production/run", "run")
    assert json.loads(storage.read_bytes(uri)) == {"value": 1}


def test_canonical_columns_prefers_canonical_and_survives_duplicate_aliases():
    from scripts.research.audit_data_first_evidence import _canonical_columns

    aliases = {"year": "season", "id": "game_id"}
    alias_only = _canonical_columns(pd.DataFrame({"year": [2025], "id": [7]}), aliases)
    assert list(alias_only.columns) == ["season", "game_id"]
    canonical_only = _canonical_columns(
        pd.DataFrame({"season": [2025], "game_id": [7]}), aliases
    )
    assert list(canonical_only.columns) == ["season", "game_id"]
    both = _canonical_columns(
        pd.DataFrame({"season": [2025], "year": [2025], "game_id": [7], "id": [7]}),
        aliases,
    )
    assert list(both.columns) == ["season", "game_id"]
    assert both["season"].iloc[0] == 2025
    empty = _canonical_columns(pd.DataFrame(), aliases)
    assert empty.empty

    crash_case = _games().assign(year=_games()["season"], game_id=_games()["id"])
    normalized = _canonical_columns(crash_case, {"year": "season", "id": "game_id"})
    assert isinstance(normalized["season"], pd.Series)
    schedule, conflicts = classify_schedule(normalized)
    assert set(schedule["game_id"]) == {1, 2, 3, 4}
    assert conflicts == []
