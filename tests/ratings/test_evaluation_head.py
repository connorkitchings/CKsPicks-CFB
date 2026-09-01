"""Unit tests for the fixed Gaussian evaluation head (R2 fold evaluator)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cks_picks_cfb.ratings.evaluation_head import (
    EvaluationHeadError,
    fit_gaussian_head,
    fold_metrics,
    predict_gaussian_head,
)


def _team_states(season: int, game_ids: list[int], teams: list[tuple[str, float, float]]) -> pd.DataFrame:
    """Build synthetic pregame team states."""
    rows = []
    for gid in game_ids:
        for team, off, deff in teams:
            rows.append(
                {
                    "season": season,
                    "game_id": gid,
                    "team": team,
                    "offense_mean": off,
                    "defense_mean": deff,
                    "state_kind": "pregame",
                    "completed_games": 0,
                }
            )
    return pd.DataFrame(rows)


def _outcomes(season: int, games: list[dict]) -> pd.DataFrame:
    rows = []
    for g in games:
        rows.append({"season": season, **g})
    return pd.DataFrame(rows)


TRAIN_STATES = _team_states(
    2017,
    game_ids=list(range(50)),
    teams=[("Home", 0.5, 0.3), ("Away", 0.2, 0.4)],
)
TRAIN_OUTCOMES = _outcomes(
    2017,
    [
        {
            "game_id": i,
            "home_team": "Home",
            "away_team": "Away",
            "home_points": 28.0 + i * 0.1,
            "away_points": 21.0 + i * 0.05,
        }
        for i in range(50)
    ],
)


def test_fit_gaussian_head_basic():
    head = fit_gaussian_head(
        team_states=TRAIN_STATES,
        game_outcomes=TRAIN_OUTCOMES,
        train_seasons=(2017,),
    )
    assert head.n_train_games > 0
    assert np.isfinite(head.margin_coef).all()
    assert np.isfinite(head.total_coef).all()
    assert head.train_seasons == (2017,)


def test_fit_gaussian_head_rejects_forbidden_seasons():
    with pytest.raises(EvaluationHeadError, match="Forbidden"):
        fit_gaussian_head(
            team_states=TRAIN_STATES,
            game_outcomes=TRAIN_OUTCOMES,
            train_seasons=(2020,),
        )
    with pytest.raises(EvaluationHeadError, match="Forbidden"):
        fit_gaussian_head(
            team_states=TRAIN_STATES,
            game_outcomes=TRAIN_OUTCOMES,
            train_seasons=(2025,),
        )


def test_fit_gaussian_head_missing_columns_raises():
    bad_states = TRAIN_STATES.drop(columns=["offense_mean"])
    with pytest.raises(EvaluationHeadError, match="missing columns"):
        fit_gaussian_head(
            team_states=bad_states,
            game_outcomes=TRAIN_OUTCOMES,
            train_seasons=(2017,),
        )


def test_predict_gaussian_head_basic():
    head = fit_gaussian_head(
        team_states=TRAIN_STATES,
        game_outcomes=TRAIN_OUTCOMES,
        train_seasons=(2017,),
    )
    target_states = _team_states(
        2018,
        game_ids=[100, 101],
        teams=[("Home", 0.5, 0.3), ("Away", 0.2, 0.4)],
    )
    target_outcomes = _outcomes(
        2018,
        [
            {
                "game_id": 100,
                "home_team": "Home",
                "away_team": "Away",
                "home_points": 30.0,
                "away_points": 24.0,
            },
            {
                "game_id": 101,
                "home_team": "Home",
                "away_team": "Away",
                "home_points": 17.0,
                "away_points": 14.0,
            },
        ],
    )
    preds = predict_gaussian_head(
        head=head,
        team_states=target_states,
        game_outcomes=target_outcomes,
        target_season=2018,
    )
    assert len(preds) == 2
    assert "predicted_margin" in preds.columns
    assert "predicted_total" in preds.columns
    assert "actual_margin" in preds.columns
    assert np.isfinite(preds["predicted_margin"]).all()


def test_predict_gaussian_head_rejects_target_in_training():
    head = fit_gaussian_head(
        team_states=TRAIN_STATES,
        game_outcomes=TRAIN_OUTCOMES,
        train_seasons=(2017,),
    )
    with pytest.raises(EvaluationHeadError, match="data leakage"):
        predict_gaussian_head(
            head=head,
            team_states=TRAIN_STATES,
            game_outcomes=TRAIN_OUTCOMES,
            target_season=2017,
        )


def test_predict_gaussian_head_rejects_forbidden_season():
    head = fit_gaussian_head(
        team_states=TRAIN_STATES,
        game_outcomes=TRAIN_OUTCOMES,
        train_seasons=(2017,),
    )
    with pytest.raises(EvaluationHeadError, match="Forbidden"):
        predict_gaussian_head(
            head=head,
            team_states=TRAIN_STATES,
            game_outcomes=TRAIN_OUTCOMES,
            target_season=2025,
        )


def test_fold_metrics_early_full_separation():
    preds = pd.DataFrame(
        [
            {
                "game_id": i,
                "season": 2018,
                "predicted_margin": 7.0,
                "predicted_total": 50.0,
                "actual_margin": 10.0,
                "actual_total": 55.0,
                "completed_games": (i % 5) + 1,
            }
            for i in range(20)
        ]
    )
    metrics = fold_metrics(preds, "fixed_rho_0_60", 2018)
    assert "early_margin_mae" in metrics
    assert "full_margin_mae" in metrics
    assert np.isfinite(metrics["early_margin_mae"])
    assert np.isfinite(metrics["full_margin_mae"])
    # Early is games 1-3 only; full is games 1+
    assert metrics["early_n"] < metrics["full_n"]


def test_fold_metrics_rejects_forbidden_season():
    preds = pd.DataFrame(
        [
            {
                "game_id": 1,
                "season": 2025,
                "predicted_margin": 7.0,
                "predicted_total": 50.0,
                "actual_margin": 10.0,
                "actual_total": 55.0,
                "completed_games": 2,
            }
        ]
    )
    with pytest.raises(EvaluationHeadError, match="Forbidden season"):
        fold_metrics(preds, "fixed_rho_0_60", 2025)


def test_fold_metrics_empty_raises():
    with pytest.raises(EvaluationHeadError, match="No predictions"):
        fold_metrics(pd.DataFrame(), "fixed_rho_0_60", 2018)
