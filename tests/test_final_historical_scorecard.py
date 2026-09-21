"""Focused tests for Contract 12 V5 Historical Results and Readiness Review."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from cks_picks_cfb.data.data_first_phase2d import canonical_bytes, signed_payload
from cks_picks_cfb.forecast.final_historical_scorecard import (
    EXPECTED_ROWS_BY_SEASON,
    EXPECTED_STAGE_COUNTS,
    EXPECTED_TOTAL_ROWS,
    PERMITTED_USE,
    READINESS_RECOMMENDATION,
    SCORECARD_MANIFEST_SCHEMA,
    SCORECARD_SCHEMA,
    TARGETS,
    VERIFICATION_MANIFEST_URI,
    ScorecardError,
    compute_scorecard,
    render_report,
    validate_population,
    validate_verification_manifest,
)
from cks_picks_cfb.forecast.final_scorecard_publication import (
    OUTPUT_ROOT,
    ScorecardPublicationError,
    publish_scorecard,
    verify_scorecard_publication,
)

_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# In-memory storage fixture
# ---------------------------------------------------------------------------


class _MemStorage:
    def __init__(self, objects: dict[str, bytes] | None = None) -> None:
        self.objects: dict[str, bytes] = dict(objects or {})

    def read_bytes(self, uri: str) -> bytes:
        if uri not in self.objects:
            raise FileNotFoundError(uri)
        return self.objects[uri]

    def write_bytes(self, data: bytes, uri: str) -> None:
        self.objects[uri] = data

    def exists(self, uri: str) -> bool:
        return uri in self.objects

    def list_files(self, prefix: str) -> list[str]:
        return sorted(u for u in self.objects if u.startswith(prefix))


def _make_valid_manifest() -> tuple[dict[str, Any], bytes]:
    manifest_body = {
        "schema_version": "data_first_forecast_verification_v1",
        "state": "verified",
        "run_id": "forecast-v1-20260921-5afd577-11c",
        "forecast_manifest_uri": "artifacts/forecast-manifest.json",
        "final_fit_verified": True,
        "training_max_season": 2025,
        "closes_findings": [
            "audit-structural-002",
            "audit-forecast-final_fit_existence-b1bc852294",
        ],
        "permitted_use": "full_lane_forecast_eligibility_closure_only",
        "production_activation_authorized": False,
        "readiness_recommendation": None,
    }
    payload = signed_payload(manifest_body)
    raw_bytes = canonical_bytes(payload)
    return payload, raw_bytes


def _make_valid_population() -> tuple[pd.DataFrame, pd.DataFrame]:
    pred_rows = []
    game_counter = 0

    stage_targets = {
        0: EXPECTED_STAGE_COUNTS["0"],
        1: EXPECTED_STAGE_COUNTS["1"],
        2: EXPECTED_STAGE_COUNTS["2"],
        3: EXPECTED_STAGE_COUNTS["3"],
        4: EXPECTED_STAGE_COUNTS["4_plus"],
    }
    stage_assignments: list[int] = []
    for s_val, count in stage_targets.items():
        stage_assignments.extend([s_val] * count)

    for season, n_games in sorted(EXPECTED_ROWS_BY_SEASON.items()):
        for _ in range(n_games):
            game_counter += 1
            game_id = f"game_{game_counter:05d}"
            stage = stage_assignments[game_counter - 1]
            for target in TARGETS:
                pred_rows.append(
                    {
                        "game_id": game_id,
                        "season": season,
                        "target": target,
                        "prediction": 24.5,
                        "actual": 27.0,
                        "completed_games": stage,
                    }
                )

    pred_df = pd.DataFrame(pred_rows)

    cal_rows = []
    for target in TARGETS:
        for season in (0, 2022, 2023, 2024, 2025):
            cal_rows.append(
                {
                    "target": target,
                    "season": season,
                    "variance": 100.0,
                    "residual_count": 800,
                    "fallback_reason": "",
                }
            )
    cal_df = pd.DataFrame(cal_rows)
    return pred_df, cal_df


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------


def test_ast_boundary_no_producer_imports():
    """Scorecard module must not import any producer modeling modules."""
    path = (
        _ROOT / "src" / "cks_picks_cfb" / "forecast" / "final_historical_scorecard.py"
    )
    tree = ast.parse(path.read_text())
    prohibited = {"heads", "horizons", "calibration", "offsets", "train"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            parts = node.module.split(".")
            overlap = prohibited.intersection(parts)
            assert not overlap, f"Prohibited producer import found: {node.module}"


def test_validate_verification_manifest_accepts_valid():
    storage = _MemStorage()
    payload, raw_bytes = _make_valid_manifest()
    import cks_picks_cfb.forecast.final_historical_scorecard as mod

    orig_raw_sha = mod.VERIFICATION_MANIFEST_RAW_SHA256
    orig_can_sha = mod.VERIFICATION_MANIFEST_CANONICAL_SHA256
    mod.VERIFICATION_MANIFEST_RAW_SHA256 = hashlib.sha256(raw_bytes).hexdigest()
    mod.VERIFICATION_MANIFEST_CANONICAL_SHA256 = payload["manifest_sha256"]
    try:
        storage.write_bytes(raw_bytes, VERIFICATION_MANIFEST_URI)
        manifest = validate_verification_manifest(storage)
        assert manifest["state"] == "verified"
        assert manifest["final_fit_verified"] is True
    finally:
        mod.VERIFICATION_MANIFEST_RAW_SHA256 = orig_raw_sha
        mod.VERIFICATION_MANIFEST_CANONICAL_SHA256 = orig_can_sha


def test_validate_verification_manifest_rejects_missing():
    storage = _MemStorage()
    with pytest.raises(ScorecardError, match="not found"):
        validate_verification_manifest(storage)


def test_validate_verification_manifest_rejects_tampered_sha():
    storage = _MemStorage()
    storage.write_bytes(b'{"bad": "content"}', VERIFICATION_MANIFEST_URI)
    with pytest.raises(ScorecardError, match="raw SHA mismatch"):
        validate_verification_manifest(storage)


def test_validate_verification_manifest_rejects_unverified_state():
    manifest_body = {
        "schema_version": "data_first_forecast_verification_v1",
        "state": "failed",
        "final_fit_verified": True,
        "training_max_season": 2025,
        "closes_findings": [
            "audit-structural-002",
            "audit-forecast-final_fit_existence-b1bc852294",
        ],
        "permitted_use": "full_lane_forecast_eligibility_closure_only",
        "production_activation_authorized": False,
    }
    payload = signed_payload(manifest_body)
    raw_bytes = canonical_bytes(payload)

    storage = _MemStorage()
    storage.write_bytes(raw_bytes, VERIFICATION_MANIFEST_URI)

    import cks_picks_cfb.forecast.final_historical_scorecard as mod

    orig_raw_sha = mod.VERIFICATION_MANIFEST_RAW_SHA256
    orig_can_sha = mod.VERIFICATION_MANIFEST_CANONICAL_SHA256
    mod.VERIFICATION_MANIFEST_RAW_SHA256 = hashlib.sha256(raw_bytes).hexdigest()
    mod.VERIFICATION_MANIFEST_CANONICAL_SHA256 = payload["manifest_sha256"]
    try:
        with pytest.raises(ScorecardError, match="expected 'verified'"):
            validate_verification_manifest(storage)
    finally:
        mod.VERIFICATION_MANIFEST_RAW_SHA256 = orig_raw_sha
        mod.VERIFICATION_MANIFEST_CANONICAL_SHA256 = orig_can_sha


def test_validate_population_accepts_valid():
    pred_df, cal_df = _make_valid_population()
    summary = validate_population(pred_df, cal_df)
    assert summary["source_count"] == EXPECTED_TOTAL_ROWS
    assert summary["excluded_count"] == 0
    assert summary["games_count"] == 3659


def test_validate_population_rejects_row_mismatch():
    pred_df, cal_df = _make_valid_population()
    short_df = pred_df.iloc[:-2].copy()
    with pytest.raises(ScorecardError, match="Expected 7318 prediction rows"):
        validate_population(short_df, cal_df)


def test_validate_population_rejects_duplicate():
    pred_df, cal_df = _make_valid_population()
    dup_df = pd.concat([pred_df, pred_df.iloc[:1]], ignore_index=True)
    with pytest.raises(ScorecardError):
        validate_population(dup_df, cal_df)


def test_compute_scorecard_metrics_accuracy():
    pred_df, cal_df = _make_valid_population()
    summary = validate_population(pred_df, cal_df)
    scorecard = compute_scorecard(
        pred_df,
        cal_df,
        window_comparison=pd.DataFrame(),
        head_recipes={"margin": {"alpha": 10.0}},
        population_summary=summary,
    )

    assert scorecard["readiness_recommendation"] == READINESS_RECOMMENDATION
    assert scorecard["permitted_use"] == PERMITTED_USE
    assert scorecard["production_activation_authorized"] is False

    for target in TARGETS:
        t_block = scorecard["targets"][target]
        assert "headline_2025" in t_block
        assert "context_by_season" in t_block
        assert "pooled_2022_2025" in t_block
        assert "by_completed_game_stage" in t_block
        # pred=24.5, actual=27.0 => error = -2.5 => MAE = 2.5
        assert t_block["headline_2025"]["mae"] == pytest.approx(2.5, abs=0.01)


def test_render_report_clean_output():
    pred_df, cal_df = _make_valid_population()
    summary = validate_population(pred_df, cal_df)
    scorecard = compute_scorecard(
        pred_df,
        cal_df,
        window_comparison=pd.DataFrame(),
        head_recipes={"margin": {"alpha": 10.0}},
        population_summary=summary,
    )
    report = render_report(
        scorecard,
        run_id="test-run-12",
        manifest_uri="artifacts/test/scorecard-manifest.json",
        manifest_raw_sha256="abc123raw",
    )
    assert "# V5 Historical Results and Readiness Review Report" in report
    assert "accepted_for_prospective_evaluation" in report
    assert "audit-structural-001" in report
    assert "audit-structural-002" in report
    assert "audit-ledger-score_reconciliation-1de3aaaf7d" in report
    assert "audit-forecast-final_fit_existence-b1bc852294" in report


def test_verify_scorecard_publication_storage_roundtrip():
    storage = _MemStorage()
    run_id = "test-run-scorecard-12"
    prefix = f"{OUTPUT_ROOT}/{run_id}"
    scorecard_uri = f"{prefix}/historical-scorecard.json"
    manifest_uri = f"{prefix}/scorecard-manifest.json"

    scorecard_payload = signed_payload(
        {
            "schema_version": SCORECARD_SCHEMA,
            "state": "published",
            "run_id": run_id,
            "permitted_use": PERMITTED_USE,
            "production_activation_authorized": False,
            "readiness_recommendation": READINESS_RECOMMENDATION,
        }
    )
    scorecard_bytes = canonical_bytes(scorecard_payload)
    scorecard_raw_sha256 = hashlib.sha256(scorecard_bytes).hexdigest()
    storage.write_bytes(scorecard_bytes, scorecard_uri)

    manifest_payload = signed_payload(
        {
            "schema_version": SCORECARD_MANIFEST_SCHEMA,
            "state": "published",
            "run_id": run_id,
            "scorecard_uri": scorecard_uri,
            "scorecard_raw_sha256": scorecard_raw_sha256,
            "scorecard_canonical_sha256": scorecard_payload["manifest_sha256"],
            "permitted_use": PERMITTED_USE,
            "production_activation_authorized": False,
            "readiness_recommendation": READINESS_RECOMMENDATION,
        }
    )
    manifest_bytes = canonical_bytes(manifest_payload)
    storage.write_bytes(manifest_bytes, manifest_uri)

    verified = verify_scorecard_publication(storage, manifest_uri=manifest_uri)
    assert verified["verified"] is True
    assert verified["run_id"] == run_id
    assert verified["readiness_recommendation"] == READINESS_RECOMMENDATION


def test_publish_scorecard_rejects_mismatched_evidence():
    storage = _MemStorage()
    run_id = "test-run-mismatch"
    bad_evidence = {
        "state": "dry_run",
        "run_id": "other-run-id",
        "permitted_use": PERMITTED_USE,
    }
    with pytest.raises(ScorecardPublicationError, match="Reviewed evidence identity"):
        publish_scorecard(storage, run_id=run_id, reviewed_evidence=bad_evidence)


def test_publish_scorecard_rejects_partial_prefix_collision():
    storage = _MemStorage()
    run_id = "test-run-partial"
    prefix = f"{OUTPUT_ROOT}/{run_id}"
    storage.write_bytes(b"partial-data", f"{prefix}/partial-file.json")
    valid_evidence = {
        "state": "dry_run",
        "run_id": run_id,
        "permitted_use": PERMITTED_USE,
    }
    with pytest.raises(ScorecardPublicationError, match="partial content"):
        publish_scorecard(storage, run_id=run_id, reviewed_evidence=valid_evidence)
