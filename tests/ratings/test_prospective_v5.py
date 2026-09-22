from __future__ import annotations

import pandas as pd
import pytest

from cks_picks_cfb.ratings.prospective_v5 import (
    V5EvidenceError,
    derive_eligibility,
    football_metrics,
    quote_diagnostic,
    recommendation,
)


def _attempt(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "candidate": "v5-live-candidate",
        "season": 2026,
        "week": 5,
        "run_id": "freeze-1",
        "diagnostic_only": False,
        "readiness_verified": True,
        "readiness_overall": "ready",
        "first_kickoff": "2026-10-01T23:30:00Z",
        "freeze_completed_at": "2026-10-01T21:00:00Z",
        "declared_games": 55,
        "paired_games": 48,
        "normal_coverage": True,
        "freeze_manifest_sha256": "freeze-sha",
        "freeze_ref": "freeze-ref",
    }
    value.update(overrides)
    return value


def _evaluation(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "candidate": "v5-live-candidate",
        "season": 2026,
        "week": 5,
        "run_id": "freeze-1",
        "outcome_version": "final-1",
        "score_completed_at": "2026-10-04T12:00:00Z",
        "last_game_completed_at": "2026-10-03T12:00:00Z",
        "outcome_ref": "outcome-ref",
        "evaluation_ref": "eval-ref",
        "evaluation_manifest_sha256": "eval-sha",
        "evaluation_verified": True,
    }
    value.update(overrides)
    return value


def test_eligibility_requires_ready_timing_coverage_and_stable_verified_score() -> None:
    attempts = pd.DataFrame(
        [
            _attempt(),
            _attempt(run_id="late", freeze_completed_at="2026-10-01T22:45:00Z"),
            _attempt(run_id="small", paired_games=39),
            _attempt(run_id="diag", diagnostic_only=True),
        ]
    )
    evaluations = pd.DataFrame(
        [
            _evaluation(run_id="freeze-1"),
            _evaluation(run_id="late"),
            _evaluation(run_id="small"),
            _evaluation(run_id="diag"),
        ]
    )
    ledger = derive_eligibility(
        attempts, evaluations, expected_candidate="v5-live-candidate"
    )
    assert int(ledger.qualifying.sum()) == 1
    assert (
        ledger.loc[ledger.run_id.eq("late"), "reason"].iloc[0].find("t_minus_1h") >= 0
    )
    assert ledger.loc[ledger.run_id.eq("small"), "reason"].iloc[0].find("below_40") >= 0
    assert not ledger.loc[ledger.run_id.eq("diag"), "qualifying"].iloc[0]


def test_duplicate_qualifying_attempt_counts_once_and_correction_stays_linked() -> None:
    attempts = pd.DataFrame([_attempt(), _attempt(run_id="freeze-2")])
    evaluations = pd.DataFrame(
        [
            _evaluation(run_id="freeze-1", outcome_version="final-1"),
            _evaluation(run_id="freeze-1", outcome_version="corrected-2"),
        ]
    )
    ledger = derive_eligibility(
        attempts, evaluations, expected_candidate="v5-live-candidate"
    )
    assert ledger.qualifying.sum() == 1
    assert (
        "evaluation_missing"
        in ledger.loc[ledger.run_id.eq("freeze-2"), "reason"].iloc[0]
    )
    early = pd.DataFrame(
        [_evaluation(run_id="freeze-1", score_completed_at="2026-10-04T11:59:00Z")]
    )
    blocked = derive_eligibility(
        pd.DataFrame([_attempt()]),
        early,
        expected_candidate="v5-live-candidate",
    )
    assert not blocked.qualifying.iloc[0]
    assert "24h" in blocked.reason.iloc[0]


def test_missing_final_timestamp_and_unverified_readiness_remain_excluded() -> None:
    attempts = pd.DataFrame([_attempt(readiness_overall="blocked")])
    evaluations = pd.DataFrame(
        [_evaluation(run_id="freeze-1", last_game_completed_at=None)]
    )
    ledger = derive_eligibility(
        attempts, evaluations, expected_candidate="v5-live-candidate"
    )
    assert not ledger.qualifying.iloc[0]
    assert "readiness_not_verified_ready" in ledger.reason.iloc[0]
    assert "final_completion_time_missing" in ledger.reason.iloc[0]


def test_quotes_cannot_change_football_metrics_and_require_authentic_times() -> None:
    football = pd.DataFrame(
        [
            {
                "season": 2026,
                "week": 5,
                "game_id": 1,
                "target": target,
                "actual": actual,
                "v5_mean": pred,
                "v5_variance": 4.0,
                "v4_mean": v4,
                "completed_game_stage": stage,
                "broader_population": True,
                "paired_population": True,
            }
            for target, actual, pred, v4, stage in (
                ("margin", 3.0, 2.0, 4.0, 1),
                ("total", 44.0, 45.0, 43.0, 1),
            )
        ]
    )
    before = football_metrics(football)
    quotes = pd.DataFrame(
        [
            {
                "game_id": 1,
                "target": "margin",
                "provider": "example",
                "quote_id": "q1",
                "captured_at": "2026-10-01T18:00:00Z",
                "effective_at": "2026-10-01T18:00:00Z",
                "line": -2.5,
            }
        ]
    )
    diagnostic = quote_diagnostic(football, quotes, cutoff="2026-10-01T20:00:00Z")
    assert diagnostic["covered_games"] == 1
    assert football_metrics(football) == before
    with pytest.raises(V5EvidenceError, match="exceeds its declared cutoff"):
        quote_diagnostic(football, quotes, cutoff="2026-10-01T17:00:00Z")
    with pytest.raises(V5EvidenceError, match="timezone-aware"):
        quote_diagnostic(football, pd.DataFrame(), cutoff="not-a-time")


def test_recommendation_uses_existing_three_categories_without_early_promotion() -> (
    None
):
    assert (
        recommendation(
            qualifying_slates=5,
            validity_passed=True,
            material_regression=False,
            operational_problem=False,
            satisfactory_review=True,
        )
        == "continue_shadowing"
    )
    assert (
        recommendation(
            qualifying_slates=6,
            validity_passed=True,
            material_regression=True,
            operational_problem=False,
            satisfactory_review=True,
        )
        == "retain_v4"
    )
    assert (
        recommendation(
            qualifying_slates=6,
            validity_passed=True,
            material_regression=False,
            operational_problem=False,
            satisfactory_review=True,
        )
        == "prepare_phase7"
    )
