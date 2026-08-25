"""Focused tests for the Phase 3 Phase 1--2 certification gate."""

from __future__ import annotations

import pandas as pd
import pytest

from cks_picks_cfb.ratings.foundation_review import (
    _observation_checks,
    _recompute_adjustment,
    _snapshot_checks,
    _state_algebra_checks,
    load_foundation_review_config,
)
from scripts.pipeline import build_rating_foundation_review as cli


def test_foundation_config_locks_authoritative_phase1_and_phase2_refs():
    config = load_foundation_review_config("conf/ratings/foundation_review_v1.yaml")

    assert config.phase1["expected_snapshots_version"] == "3163c5e6a18cc01a30542cb2"
    assert config.phase2["expected_team_states_version"] == "1fdcb1ca6d235bf2ecf87414"
    assert config.adjustment_sample_targets_per_season == 1


def test_observation_checks_enforce_ratio_and_zero_exposure_reason():
    rows = pd.DataFrame(
        [
            {
                "season": 2021,
                "game_id": 1,
                "team": "A",
                "measurement_id": "epa_per_play",
                "unit_role": "offense",
                "numerator": 3.0,
                "denominator": 2.0,
                "raw_value": 1.5,
                "missing_reason": None,
                "temporal_status": "reconstructed",
                "effective_at": None,
            },
            {
                "season": 2021,
                "game_id": 1,
                "team": "A",
                "measurement_id": "points_per_scoring_opportunity",
                "unit_role": "offense",
                "numerator": 0.0,
                "denominator": 0.0,
                "raw_value": None,
                "missing_reason": "zero_denominator",
                "temporal_status": "reconstructed",
                "effective_at": None,
            },
        ]
    )

    checks = _observation_checks(rows)

    assert checks["observation_ratio_and_exposure"] is True
    assert checks["zero_exposure_has_null_reason"] is True
    rows.loc[1, "missing_reason"] = None
    assert _observation_checks(rows)["zero_exposure_has_null_reason"] is False


def test_snapshot_checks_reject_future_evidence():
    rows = pd.DataFrame(
        [
            {
                "season": 2021,
                "as_of_game_id": 1,
                "team": "A",
                "measurement_id": "epa_per_play",
                "unit_role": "offense",
                "as_of_kickoff_utc": "2021-09-01T12:00:00Z",
                "evidence_max_kickoff_utc": "2021-08-31T12:00:00Z",
                "evidence_max_effective_at": None,
                "coverage_status": "observed",
                "primary_exposure": 10.0,
                "adjusted_value": 0.2,
                "missing_reason": None,
            }
        ]
    )

    assert _snapshot_checks(rows)["snapshot_pregame_bounds"] is True
    rows.loc[0, "evidence_max_kickoff_utc"] = "2021-09-01T12:00:00Z"
    assert _snapshot_checks(rows)["snapshot_pregame_bounds"] is False


def test_independent_adjustment_omits_unavailable_opponents():
    rows = pd.DataFrame(
        [
            {
                "game_id": 1,
                "team": "A",
                "opponent": "B",
                "unit_role": role,
                "numerator": numerator,
                "denominator": 10.0,
            }
            for role, numerator in (("offense", 10.0), ("defense", 20.0))
        ]
        + [
            {
                "game_id": 2,
                "team": "C",
                "opponent": "unavailable",
                "unit_role": role,
                "numerator": 5.0,
                "denominator": 5.0,
            }
            for role in ("offense", "defense")
        ]
    )

    offense, defense = _recompute_adjustment(rows, iterations=4)

    assert offense["C"] == 1.0
    assert defense["C"] == 1.0


def test_component_algebra_rejects_wrong_defensive_direction():
    rows = pd.DataFrame(
        [
            {
                "state_id": "game:2021:1",
                "team": "A",
                "measurement_id": "epa_per_play",
                "unit_role": "defense",
                "native_adjusted_value": 0.2,
                "primary_exposure": 100.0,
                "standardization_center": 0.0,
                "standardization_scale": 0.1,
                "observed_z": -2.0,
                "prior_mean": 0.0,
                "prior_variance": 1.0,
                "prior_precision": 1.0,
                "observation_precision": 1.0,
                "posterior_variance": 0.5,
                "posterior_mean": -1.0,
                "posterior_sd": 0.5**0.5,
                "observed_weight": 0.5,
                "prior_weight": 0.5,
            }
        ]
    )

    checks = _state_algebra_checks(rows)
    assert checks["component_standardization_and_direction"] is True
    assert checks["component_posterior_algebra"] is True
    rows.loc[0, "observed_z"] = 2.0
    assert (
        _state_algebra_checks(rows)["component_standardization_and_direction"] is False
    )


def test_cli_rejects_production_before_reading_inputs():
    with pytest.raises(ValueError, match="only in preview"):
        cli.main(
            [
                "--environment",
                "production",
                "--as-of",
                "2026-08-25T00:00:00Z",
                "--run-id",
                "test",
                "--report-uri",
                "unused",
            ]
        )
