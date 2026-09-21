"""Focused unit tests for Contract 02 V5 Foundation-Blocker Diagnosis."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from cks_picks_cfb.audit.foundation_blocker_diagnosis import (
    AUDIT_10B_MANIFEST_CANONICAL_SHA256,
    AUDIT_10B_MANIFEST_URI,
    EXPECTED_EXCESS_SHA256,
    MEASUREMENT_R6_IDENTITY,
    MEASUREMENT_R6_MANIFEST_URI,
    REPAIR_V2_IDENTITY,
    REPAIR_V2_MANIFEST_URI,
    TAXONOMY_CAUSES,
    classify_key,
    render_diagnosis_report,
    verify_repair_independence_contract,
)

_ROOT = Path(__file__).resolve().parents[1]


class _MockStorage:
    def __init__(self, data: dict[str, bytes]) -> None:
        self.data = dict(data)

    def read_bytes(self, uri: str) -> bytes:
        if uri not in self.data:
            raise FileNotFoundError(f"URI not found: {uri}")
        return self.data[uri]


def _valid_parents_storage() -> _MockStorage:
    """Build mock storage with valid 10B, Repair v2, and Measurement R6 manifests."""
    manifest_10b = json.dumps(
        {
            "schema_version": "data_first_historical_audit_manifest_v1",
            "manifest_sha256": AUDIT_10B_MANIFEST_CANONICAL_SHA256,
            "findings": [],
        }
    ).encode()
    # Ensure raw bytes hash matches AUDIT_10B_MANIFEST_RAW_SHA256 or mock it directly:
    manifest_repair = json.dumps(
        {
            "schema_version": "data_first_repair_manifest_v2",
            "identity": {"run_id": REPAIR_V2_IDENTITY},
            "output_refs": {"population": "lake/gold/population.parquet"},
        }
    ).encode()
    manifest_meas = json.dumps(
        {
            "schema_version": "data_first_possession_measurement_manifest_v1",
            "identity": {"run_id": MEASUREMENT_R6_IDENTITY},
            "output_refs": {"scoring_events": "lake/gold/events.parquet"},
        }
    ).encode()

    return _MockStorage(
        {
            AUDIT_10B_MANIFEST_URI: manifest_10b,
            REPAIR_V2_MANIFEST_URI: manifest_repair,
            MEASUREMENT_R6_MANIFEST_URI: manifest_meas,
        }
    )


def test_taxonomy_causes_defined() -> None:
    assert len(TAXONOMY_CAUSES) == 5
    assert "score_regression_quarantine" in TAXONOMY_CAUSES
    assert "duplicate_event_or_end_of_game" in TAXONOMY_CAUSES
    assert "pat_or_conversion_double_counting" in TAXONOMY_CAUSES
    assert "overtime_attribution" in TAXONOMY_CAUSES
    assert "provider_team_inversion_or_misattribution" in TAXONOMY_CAUSES


def test_classify_key_score_regression() -> None:
    events = pd.DataFrame(
        [
            {
                "season": 2015,
                "game_id": 400603867,
                "team": "Kentucky",
                "score_increment": 7,
                "period_class": "regulation",
                "quality_reason": None,
                "drive_number": 4,
            },
            {
                "season": 2015,
                "game_id": 400603867,
                "team": "Kentucky",
                "score_increment": 0,
                "period_class": "regulation",
                "quality_reason": "score_regression_or_nonintegral",
                "drive_number": 20,
            },
        ]
    )
    key_info = {
        "season": 2015,
        "game_id": 400603867,
        "team": "Kentucky",
        "ledger": 28.0,
        "final": 26.0,
        "diff": 2.0,
    }
    ck = classify_key(key_info, events)
    assert ck.cause == "score_regression_quarantine"
    assert ck.diff == 2.0


def test_classify_key_team_inversion() -> None:
    events = pd.DataFrame(
        [
            {
                "season": 2023,
                "game_id": 401551755,
                "team": "Eastern Michigan",
                "score_increment": 7,
                "period_class": "regulation",
                "quality_reason": None,
                "drive_number": 3,
            },
        ]
    )
    key_info = {
        "season": 2023,
        "game_id": 401551755,
        "team": "Eastern Michigan",
        "ledger": 59.0,
        "final": 10.0,
        "diff": 49.0,
    }
    ck = classify_key(key_info, events)
    assert ck.cause == "provider_team_inversion_or_misattribution"
    assert ck.diff == 49.0


def test_classify_key_overtime() -> None:
    events = pd.DataFrame(
        [
            {
                "season": 2025,
                "game_id": 401777328,
                "team": "Virginia",
                "score_increment": 20,
                "period_class": "regulation",
                "quality_reason": None,
                "drive_number": 4,
            },
            {
                "season": 2025,
                "game_id": 401777328,
                "team": "Virginia",
                "score_increment": 7,
                "period_class": "overtime",
                "quality_reason": None,
                "drive_number": 20,
            },
        ]
    )
    key_info = {
        "season": 2025,
        "game_id": 401777328,
        "team": "Virginia",
        "ledger": 27.0,
        "final": 20.0,
        "diff": 7.0,
    }
    ck = classify_key(key_info, events)
    assert ck.cause == "overtime_attribution"


def test_classify_key_pat_double_counting() -> None:
    events = pd.DataFrame(
        [
            {
                "season": 2024,
                "game_id": 401628468,
                "team": "Ohio State",
                "score_increment": 7,
                "period_class": "regulation",
                "quality_reason": None,
                "drive_number": 24,
            },
            {
                "season": 2024,
                "game_id": 401628468,
                "team": "Ohio State",
                "score_increment": 1,
                "period_class": "regulation",
                "quality_reason": None,
                "drive_number": 24,
            },
        ]
    )
    key_info = {
        "season": 2024,
        "game_id": 401628468,
        "team": "Ohio State",
        "ledger": 57.0,
        "final": 56.0,
        "diff": 1.0,
    }
    ck = classify_key(key_info, events)
    assert ck.cause == "pat_or_conversion_double_counting"


def test_classify_key_duplicate_or_end_of_game() -> None:
    events = pd.DataFrame(
        [
            {
                "season": 2015,
                "game_id": 400763616,
                "team": "Marshall",
                "score_increment": 27,
                "period_class": "regulation",
                "quality_reason": None,
                "drive_number": 26,
            },
            {
                "season": 2015,
                "game_id": 400763616,
                "team": "Marshall",
                "score_increment": 6,
                "period_class": "regulation",
                "quality_reason": None,
                "drive_number": 31,
            },
        ]
    )
    key_info = {
        "season": 2015,
        "game_id": 400763616,
        "team": "Marshall",
        "ledger": 33.0,
        "final": 27.0,
        "diff": 6.0,
    }
    ck = classify_key(key_info, events)
    assert ck.cause == "duplicate_event_or_end_of_game"


def test_independent_repair_verification_contract() -> None:
    contract = verify_repair_independence_contract()
    assert contract["finding_id"] == "audit-structural-001"
    assert contract["repair_data_valid"] is True
    assert "compute_repair" in contract["forbidden_imports"]
    assert len(contract["behavioral_matrix"]) == 5


def test_render_diagnosis_report() -> None:
    diagnosis = {
        "total_keys": 81,
        "sha256": EXPECTED_EXCESS_SHA256,
        "by_season": {"2015": 4, "2025": 17},
        "cause_counts": {
            "score_regression_quarantine": 55,
            "duplicate_event_or_end_of_game": 19,
            "overtime_attribution": 3,
            "provider_team_inversion_or_misattribution": 2,
            "pat_or_conversion_double_counting": 2,
        },
        "keys": [
            {
                "season": 2015,
                "game_id": 400603867,
                "team": "Kentucky",
                "ledger": 28.0,
                "final": 26.0,
                "diff": 2.0,
                "cause": "score_regression_quarantine",
                "details": "Provider feed regressed score",
            }
        ],
    }
    independence = verify_repair_independence_contract()
    report = render_diagnosis_report(diagnosis, independence)
    assert "# V5 Foundation-Blocker Diagnosis Report" in report
    assert "Finding 001" in report
    assert "Finding 003" in report
    assert "Total Affected Keys:** 81" in report
    assert EXPECTED_EXCESS_SHA256 in report
    assert "01-v5-foundation-corrective-rebuild.md" in report
    assert "graph TD" in report
