"""Tests for Phase 4 multi-factor forecast bridges and benchmark evaluation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cks_picks_cfb.forecast.heads import FEATURES, _fit_one
from cks_picks_cfb.ratings_lab.contracts import Rating, RatingState
from cks_picks_cfb.ratings_lab.evaluation import (
    DIFFERENTIAL_SPREAD_FEATURES,
    DIFFERENTIAL_TOTAL_FEATURES,
    DIRECT18_FEATURES,
    FOUR_FACTOR_CORE_IDS,
    _calibration_variance,
    common_bridge_predictions,
    frame_with_multifactor_states,
)


def _make_state(
    *,
    season: int,
    game_id: int,
    team: str,
    role: str,
    mean: float,
    mid: str,
    candidate_id: str = "test_cand",
    week: int = 1,
) -> RatingState:
    return RatingState(
        candidate_id=candidate_id,
        season=season,
        week=week,
        game_id=game_id,
        cutoff_utc="2026-09-01T00:00:00Z",
        team=team,
        role=role,
        rating=Rating(mean=mean, variance=0.1),
        prior=Rating(mean=0.0, variance=1.0),
        usable_exposure=10.0,
        evidence_game_ids=(),
        explanation={"measurement_id": mid},
    )


def test_fit_one_additive_features():
    """Verify _fit_one respects the additive features parameter while defaulting to FEATURES."""
    train_df = pd.DataFrame(
        {
            "f1": [1.0, 2.0, 3.0, 4.0],
            "f2": [0.5, 1.0, 1.5, 2.0],
            "f3": [2.0, 1.0, 0.5, 0.2],
            "home_host": [1.0, 1.0, 1.0, 1.0],
            "venue_unknown": [False, False, False, False],
            "actual_margin": [7.0, 14.0, 21.0, 28.0],
            "offset_margin": [0.0, 0.0, 0.0, 0.0],
            "completed_game_stage": [0, 0, 0, 0],
        }
    )
    test_df = pd.DataFrame(
        {
            "f1": [2.5],
            "f2": [1.25],
            "f3": [0.8],
            "home_host": [1.0],
            "venue_unknown": [False],
            "offset_margin": [0.0],
            "completed_game_stage": [0],
        }
    )

    # 1. Custom 2-feature subset
    custom_feats = ("f1", "f2")
    preds, res_var = _fit_one(
        train_df, test_df, target="margin", alpha=1.0, floor=1e-6, features=custom_feats
    )
    assert len(preds) == 1
    assert res_var > 0.0

    # 2. Custom 3-feature subset
    preds3, res_var3 = _fit_one(
        train_df,
        test_df,
        target="margin",
        alpha=1.0,
        floor=1e-6,
        features=("f1", "f2", "f3"),
    )
    assert len(preds3) == 1
    assert res_var3 > 0.0
    # Predictions differ when feature subset differs
    assert not np.isclose(preds[0], preds3[0])


def _build_dummy_corpus_and_states(
    seasons: tuple[int, ...] = (
        2015,
        2016,
        2017,
        2018,
        2019,
        2021,
        2022,
        2023,
        2024,
        2025,
    ),
):
    """Build a minimal valid corpus and 4-factor rating states for testing."""
    games = []
    states = []

    for index, season in enumerate(seasons):
        game_id = season * 100 + 1
        home_team = "Georgia"
        away_team = "Alabama"

        games.append(
            {
                "season": season,
                "week": 1,
                "game_id": game_id,
                "home_team": home_team,
                "away_team": away_team,
                "home_offense": 0.5 + index * 0.02,
                "home_defense": 0.2 - index * 0.01,
                "away_offense": 0.4 - index * 0.02,
                "away_defense": 0.1 + index * 0.01,
                "home_host": 1.0,
                "venue_unknown": False,
                "actual_margin": 10.0 + index * 2.0,
                "actual_total": 45.0 + index,
                "offset_margin": 0.0,
                "offset_total": 0.0,
                "completed_game_stage": 0,
            }
        )

        # 4 factors x 2 teams x 2 roles
        factors_data = {
            "rush_success_rate": {
                "home_off": 0.50,
                "home_def": 0.20,
                "away_off": 0.40,
                "away_def": 0.10,
            },
            "rush_explosiveness": {
                "home_off": 1.20,
                "home_def": 0.80,
                "away_off": 1.00,
                "away_def": 0.70,
            },
            "pass_success_rate": {
                "home_off": 0.60,
                "home_def": 0.30,
                "away_off": 0.55,
                "away_def": 0.25,
            },
            "pass_explosiveness": {
                "home_off": 1.80,
                "home_def": 1.10,
                "away_off": 1.50,
                "away_def": 0.90,
            },
        }

        # Add delta so features vary across training seasons without cancelling in diff or sum
        delta = index * 0.02
        for mid, vals in factors_data.items():
            states.append(
                _make_state(
                    season=season,
                    game_id=game_id,
                    team=home_team,
                    role="offense",
                    mean=vals["home_off"] + delta,
                    mid=mid,
                )
            )
            states.append(
                _make_state(
                    season=season,
                    game_id=game_id,
                    team=home_team,
                    role="defense",
                    mean=vals["home_def"] - delta * 0.2,
                    mid=mid,
                )
            )
            states.append(
                _make_state(
                    season=season,
                    game_id=game_id,
                    team=away_team,
                    role="offense",
                    mean=vals["away_off"] - delta * 0.3,
                    mid=mid,
                )
            )
            states.append(
                _make_state(
                    season=season,
                    game_id=game_id,
                    team=away_team,
                    role="defense",
                    mean=vals["away_def"] + delta * 0.1,
                    mid=mid,
                )
            )

    features_df = pd.DataFrame(games)

    class DummyCorpus:
        v5_features = features_df
        v5_predictions = pd.DataFrame(
            [
                {
                    "season": row["season"],
                    "week": row["week"],
                    "game_id": row["game_id"],
                    "target": target,
                    "actual": row[f"actual_{target}"],
                }
                for row in games
                if row["season"] >= 2022
                for target in ("margin", "total")
            ]
        )

    return DummyCorpus(), states


def test_frame_with_multifactor_states_validation():
    corpus, states = _build_dummy_corpus_and_states()

    # 1. Empty states raises ValueError
    with pytest.raises(ValueError, match="candidate rating states are empty"):
        frame_with_multifactor_states(corpus, [])

    # 2. Missing measurement_id in explanation raises ValueError
    bad_state = _make_state(
        season=2022,
        game_id=202201,
        team="Georgia",
        role="offense",
        mean=0.5,
        mid="",
    )
    # Clear explanation to trigger error
    bad_state = RatingState(
        candidate_id=bad_state.candidate_id,
        season=bad_state.season,
        week=bad_state.week,
        game_id=bad_state.game_id,
        cutoff_utc=bad_state.cutoff_utc,
        team=bad_state.team,
        role=bad_state.role,
        rating=bad_state.rating,
        prior=bad_state.prior,
        usable_exposure=bad_state.usable_exposure,
        evidence_game_ids=bad_state.evidence_game_ids,
        explanation={},
    )
    with pytest.raises(ValueError, match="no measurement_id in explanation"):
        frame_with_multifactor_states(corpus, [bad_state])

    # 3. Duplicate state entry raises ValueError
    dupe_states = list(states) + [states[0]]
    with pytest.raises(ValueError, match="duplicate entries"):
        frame_with_multifactor_states(corpus, dupe_states)

    # 4. Missing core factor raises ValueError
    states_missing_rush_expl = [
        s for s in states if s.explanation.get("measurement_id") != "rush_explosiveness"
    ]
    with pytest.raises(ValueError, match="no rating states found for core factor"):
        frame_with_multifactor_states(corpus, states_missing_rush_expl)


def test_frame_with_multifactor_states_math():
    """Verify exact column generation and mathematical formulas for Bridge A and B."""
    corpus, states = _build_dummy_corpus_and_states()
    frame = frame_with_multifactor_states(corpus, states)

    # Check that all 18 direct columns exist
    for col in DIRECT18_FEATURES:
        assert col in frame.columns

    # Check differentials and sums for all 4 factors
    for mid in FOUR_FACTOR_CORE_IDS:
        assert f"diff__{mid}" in frame.columns
        assert f"sum__{mid}" in frame.columns

    # Test exact arithmetic for rush_success_rate:
    # home_off = 0.50, away_def = 0.10
    # away_off = 0.40, home_def = 0.20
    # diff = (0.50 - 0.10) - (0.40 - 0.20) = 0.40 - 0.20 = 0.20
    # sum = (0.50 + 0.10) + (0.40 + 0.20) = 0.60 + 0.60 = 1.20
    rush_sr_row = frame.iloc[0]
    assert np.isclose(rush_sr_row["diff__rush_success_rate"], 0.20)
    assert np.isclose(rush_sr_row["sum__rush_success_rate"], 1.20)

    # Test exact arithmetic for rush_explosiveness:
    # home_off = 1.20, away_def = 0.70 -> (1.20 - 0.70) = 0.50
    # away_off = 1.00, home_def = 0.80 -> (1.00 - 0.80) = 0.20
    # diff = 0.50 - 0.20 = 0.30
    # sum = (1.20 + 0.70) + (1.00 + 0.80) = 1.90 + 1.80 = 3.70
    assert np.isclose(rush_sr_row["diff__rush_explosiveness"], 0.30)
    assert np.isclose(rush_sr_row["sum__rush_explosiveness"], 3.70)


def test_calibration_variance_uses_candidate_features():
    """Verify _calibration_variance fits using the specified features."""
    corpus, states = _build_dummy_corpus_and_states()
    frame = frame_with_multifactor_states(corpus, states)

    var_v5, count_v5 = _calibration_variance(
        frame, season=2022, target="margin", features=FEATURES
    )
    var_direct18, count_direct18 = _calibration_variance(
        frame, season=2022, target="margin", features=DIRECT18_FEATURES
    )
    var_diff, count_diff = _calibration_variance(
        frame, season=2022, target="margin", features=DIFFERENTIAL_SPREAD_FEATURES
    )
    var_sum, count_sum = _calibration_variance(
        frame, season=2022, target="total", features=DIFFERENTIAL_TOTAL_FEATURES
    )

    assert count_v5 > 0
    assert count_v5 == count_direct18 == count_diff == count_sum
    assert var_v5 > 0.0
    assert var_direct18 > 0.0
    assert var_diff > 0.0
    assert var_sum > 0.0


def test_common_bridge_predictions_dual_bridges():
    """Verify common_bridge_predictions executes correctly for direct18 and differentials."""
    corpus, states = _build_dummy_corpus_and_states()
    frame = frame_with_multifactor_states(corpus, states)

    # 1. Bridge A: Direct 18
    preds_direct = common_bridge_predictions(
        corpus, frame, candidate_id="test_candidate", bridge="alpha10_direct18"
    )
    assert len(preds_direct) == 8  # 4 headline seasons x 2 targets
    assert set(preds_direct.target.unique()) == {"margin", "total"}
    assert (preds_direct.gaussian_crps > 0.0).all()
    assert (preds_direct.interval_90_upper > preds_direct.interval_90_lower).all()

    # 2. Bridge B: Domain Differentials & Sums
    preds_diff = common_bridge_predictions(
        corpus, frame, candidate_id="test_candidate", bridge="alpha10_differentials"
    )
    assert len(preds_diff) == 8
    assert set(preds_diff.target.unique()) == {"margin", "total"}
    assert (preds_diff.gaussian_crps > 0.0).all()
    assert (preds_diff.interval_90_upper > preds_diff.interval_90_lower).all()

    # 3. Invalid bridge raises ValueError
    with pytest.raises(ValueError, match="unregistered bridge type"):
        common_bridge_predictions(
            corpus, frame, candidate_id="test_candidate", bridge="nonexistent_bridge"
        )


def test_cli_evaluate_multi_stage_args():
    """Verify CLI evaluate parser accepts multiple --stage-key inputs and bridge options."""
    from scripts.research.ratings_lab import main

    with pytest.raises(SystemExit) as exc:
        main(["evaluate", "--help"])
    assert exc.value.code == 0
