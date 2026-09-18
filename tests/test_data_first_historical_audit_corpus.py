"""Bounded-fixture tests for full-corpus audit checks and findings policy."""

from __future__ import annotations

import pandas as pd

from cks_picks_cfb.audit import corpus, corpus_ratings
from cks_picks_cfb.audit.corpus import finding


def _pop(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def test_key_agreement_detects_omitted_game() -> None:
    repair = _pop(
        [
            {
                "season": 2021,
                "game_id": 1,
                "forecast_eligible": True,
                "measurement_usable": True,
            },
            {
                "season": 2021,
                "game_id": 2,
                "forecast_eligible": True,
                "measurement_usable": True,
            },
        ]
    )
    measurement = _pop(
        [
            {
                "season": 2021,
                "game_id": 1,
                "forecast_eligible": True,
                "measurement_usable": True,
            },
        ]
    )
    (check,) = [
        c
        for c in corpus.check_population_agreement(repair, measurement, "r", "m")
        if c["check_id"] == "corpus.population.key_agreement"
    ]
    assert check["status"] == "fail"
    assert "only_repair=[(2021, 2)]" in check["observed"]


def test_denominator_parity_detects_mismatch() -> None:
    observations = _pop(
        [
            {
                "season": 2021,
                "game_id": 1,
                "team": "A",
                "opponent": "B",
                "unit_role": "offense",
                "measurement_id": "ppp",
                "usable_exposure": 10.0,
                "numerator": 20.0,
            },
            {
                "season": 2021,
                "game_id": 1,
                "team": "A",
                "opponent": "B",
                "unit_role": "offense",
                "measurement_id": "epa_per_possession",
                "usable_exposure": 9.0,
                "numerator": 5.0,
            },
        ]
    )
    (check,) = corpus.check_denominator_parity(observations, "uri")
    assert check["status"] == "fail"
    assert "mismatched=1" in check["observed"]


def test_role_orientation_detects_reversal() -> None:
    observations = _pop(
        [
            {
                "season": 2021,
                "game_id": 1,
                "team": "A",
                "opponent": "B",
                "unit_role": "offense",
                "measurement_id": "ppp",
                "numerator": 20.0,
            },
            {
                "season": 2021,
                "game_id": 1,
                "team": "B",
                "opponent": "A",
                "unit_role": "defense",
                "measurement_id": "ppp",
                "numerator": 21.0,
            },
        ]
    )
    (check,) = corpus.check_role_orientation(observations, "uri")
    assert check["status"] == "fail"


def test_role_orientation_pairs_opponent_defense() -> None:
    observations = _pop(
        [
            {
                "season": 2021,
                "game_id": 1,
                "team": "A",
                "opponent": "B",
                "unit_role": "offense",
                "measurement_id": "ppp",
                "numerator": 20.0,
            },
            {
                "season": 2021,
                "game_id": 1,
                "team": "B",
                "opponent": "A",
                "unit_role": "defense",
                "measurement_id": "ppp",
                "numerator": 20.0,
            },
        ]
    )
    (check,) = corpus.check_role_orientation(observations, "uri")
    assert check["status"] == "pass"
    assert check["affected_stages"] == ["measurements"]


def test_unresolved_quarantine_detects_leak() -> None:
    events = _pop(
        [
            {
                "season": 2021,
                "game_id": 1,
                "team": "A",
                "scoring_category": "unresolved",
                "period_class": "regulation",
                "score_increment": 2,
            },
        ]
    )
    observations = _pop(
        [
            {
                "season": 2021,
                "game_id": 1,
                "team": "A",
                "unit_role": "offense",
                "measurement_id": "ppp",
                "usable_exposure": 10.0,
                "numerator": 20.0,
            },
        ]
    )
    (check,) = corpus.check_unresolved_quarantine(events, observations, "uri")
    assert check["status"] == "fail"
    assert '"affected_count": 1' in check["observed"]


def test_zero_unresolved_increment_does_not_quarantine() -> None:
    events = _pop(
        [
            {
                "season": 2021,
                "game_id": 1,
                "team": "A",
                "scoring_category": "unresolved",
                "score_increment": 0,
            }
        ]
    )
    observations = _pop(
        [
            {
                "season": 2021,
                "game_id": 1,
                "team": "A",
                "measurement_id": "ppp",
                "usable_exposure": 10.0,
            }
        ]
    )
    (check,) = corpus.check_unresolved_quarantine(events, observations, "uri")
    assert check["status"] == "pass"


def test_score_reconciliation_blocks_excess_but_reports_shortfall() -> None:
    population = _pop(
        [
            {
                "season": 2021,
                "game_id": 1,
                "outcome_valid": True,
                "home_team": "A",
                "away_team": "B",
                "home_points": 7,
                "away_points": 0,
            }
        ]
    )
    short_events = _pop(
        [{"season": 2021, "game_id": 1, "team": "A", "score_increment": 3}]
    )
    (shortfall,) = corpus.check_score_reconciliation(
        short_events, population, "events", "repair"
    )
    assert shortfall["status"] == "pass"
    assert '"shortfall_count": 1' in shortfall["observed"]
    excess_events = _pop(
        [{"season": 2021, "game_id": 1, "team": "A", "score_increment": 8}]
    )
    (excess,) = corpus.check_score_reconciliation(
        excess_events, population, "events", "repair"
    )
    assert excess["status"] == "fail"


def test_adjustment_chronology_detects_future_source() -> None:
    history = _pop(
        [
            {
                "adjustment_iteration": 4,
                "iteration_zero_value": 1.0,
                "iteration_four_value": 0.1,
                "source_available_utc": "2021-09-02T00:00:00Z",
                "target_week_cutoff_utc": "2021-09-01T00:00:00Z",
                "source_season": 2021,
                "included": True,
                "missing_reason": None,
            },
        ]
    )
    (check,) = corpus_ratings.check_adjustment_chronology(history, "uri")
    assert check["status"] == "fail"
    assert "future_sources=1" in check["observed"]


def test_adjustment_chronology_compares_equivalent_timestamps() -> None:
    history = _pop(
        [
            {
                "source_available_utc": "2021-09-01 00:00:00+00:00",
                "target_week_cutoff_utc": "2021-09-01T00:00:00Z",
                "source_season": 2021,
                "included": True,
                "missing_reason": None,
            }
        ]
    )
    (check,) = corpus_ratings.check_adjustment_chronology(history, "uri")
    assert check["status"] == "fail"


def test_league_centering_detects_drift() -> None:
    state = {
        ("2021-09-01T00:00:00Z", "ppp", "offense"): {
            "sum": 50.0,
            "count": 10,
            "cutoff": "x",
        }
    }
    (check,) = corpus_ratings.check_league_centering(state, "uri")
    assert check["status"] == "fail"
    assert "worst_mean=5.0000" in check["observed"]


def test_prior_chronology_detects_future_training_and_gap() -> None:
    priors = _pop(
        [
            {
                "candidate_id": "c",
                "season": 2022,
                "team": "A",
                "unit_role": "offense",
                "prior_mean": 0.0,
                "prior_variance": 1.0,
                "prior_source": "continuity_ridge",
                "prior_source_season": 2021,
                "annual_decay_steps": 1,
                "training_seasons": "2021 2022",
                "fallback_reason": "",
            },
            {
                "candidate_id": "c",
                "season": 2021,
                "team": "A",
                "unit_role": "offense",
                "prior_mean": 0.0,
                "prior_variance": 1.0,
                "prior_source": "carryover",
                "prior_source_season": 2019,
                "annual_decay_steps": 1,
                "training_seasons": "",
                "fallback_reason": "",
            },
        ]
    )
    (check,) = corpus_ratings.check_prior_chronology(priors, "uri")
    assert check["status"] == "fail"
    assert "trains on" in check["observed"]
    assert "decay_violations=1" in check["observed"]


def test_registry_selection_detects_wrong_winner() -> None:
    registry = _pop(
        [
            {
                "candidate_id": f"c{i}",
                "definition": "ppp",
                "prior_family": "rho_0_60",
                "updater": "exposure",
                "reference_candidate": "c0",
                "prior_feature_count": 0,
            }
            for i in range(60)
        ]
    )
    attribution = _pop(
        [
            {
                "candidate_id": f"c{i}",
                "definition": "ppp",
                "prior_family": "rho_0_60",
                "updater": "exposure",
                "reference_candidate": "c0",
                "pooled_mae": 1.0,
                "reference_mae": 1.0,
                "improvement_pct": 0.0,
                "bootstrap_90_lower": 0.0,
                "bootstrap_90_upper": 0.0,
                "full_gate": True,
                "early_gate": True,
                "regression_gate": True,
                "valid": True,
                "selected": i == 5,
                "selection_reason": "x",
            }
            for i in range(60)
        ]
    )
    results = corpus_ratings.check_registry_selection(
        registry, attribution, "c0", "r", "a"
    )
    assert results[0]["status"] == "pass"
    assert results[1]["status"] == "fail"


def test_final_fit_missing_is_blocker_policy() -> None:
    model = _pop(
        [
            {
                "horizon": "expanding",
                "target": "margin",
                "outer_season": 2025,
                "head": "reference",
                "alpha": 10.0,
                "training_seasons": "2021 2022 2023 2024",
                "inner_fallback": False,
                "retained": True,
                "fallback_reason": "",
            },
            {
                "horizon": "expanding",
                "target": "total",
                "outer_season": 2025,
                "head": "reference",
                "alpha": 10.0,
                "training_seasons": "2021 2022 2023 2024",
                "inner_fallback": False,
                "retained": True,
                "fallback_reason": "",
            },
        ]
    )
    registry = _pop([{"horizon": "expanding"}])
    selection = _pop([{"selected_horizon": "expanding"}])
    results = corpus_ratings.check_forecast_model(model, registry, selection, "uri")
    assert results[0]["status"] == "pass"
    assert results[1]["status"] == "fail"
    assert results[1]["check_id"] == "corpus.forecast.final_fit_existence"
    check = dict(results[1])
    check["population"] = "forecast model forecasts"
    check["evidence_refs"] = ["uri"]
    found = corpus.finding_from_check(check, finding_id="audit-corpus-999")
    assert found["severity"] == "blocker"
    assert found["disposition"] == "historical_evidence_only"
    assert found["closure_state"] == "open"


def test_policy_maps_categories() -> None:
    assert corpus.disposition_for("blocker", ["repair"]) == "prohibited_until_closed"
    assert (
        corpus.disposition_for("blocker", ["forecasts"]) == "historical_evidence_only"
    )
    assert corpus.disposition_for("major", ["ratings"]) == "historical_evidence_only"
    assert corpus.disposition_for("minor", ["ratings"]) == "eligible_for_next_contract"
    assert (
        corpus_ratings.overall_disposition(
            [{"severity": "major", "closure_state": "open"}]
        )
        == "clear"
    )
    assert (
        corpus_ratings.overall_disposition(
            [{"severity": "blocker", "closure_state": "closed"}]
        )
        == "clear"
    )
    assert (
        corpus_ratings.overall_disposition(
            [{"severity": "blocker", "closure_state": "open"}]
        )
        == "blocked"
    )


def test_finalize_behavioral_findings_final() -> None:
    cells = [
        {
            "cell_id": "behavioral.ratings.wrong_parent",
            "verifier": "ratings",
            "case": "wrong_parent",
            "method": "m",
            "expected": "reject",
            "observed": "accepted",
            "match": False,
        }
    ]
    (found,) = corpus.finalize_behavioral_findings(cells)
    assert found["severity"] == "blocker"
    assert found["disposition"] == "prohibited_until_closed"
    assert found["closure_state"] == "open"


def test_finding_builder_validates() -> None:
    import pytest

    with pytest.raises(corpus.CorpusError):
        finding(
            finding_id="x",
            severity="critical",
            disposition="historical_evidence_only",
            title="t",
            description="d",
            affected_stages=["ratings"],
            evidence=[],
            required_action="a",
            closure_criteria="c",
        )
