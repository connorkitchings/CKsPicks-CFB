"""Tests for the sealed Phase 3 v2 team-score tournament."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

import cks_picks_cfb.ratings.score_models as score_models
from cks_picks_cfb.ratings.score_models import (
    MeasurementContractError,
    ScoreModel,
    expanding_score_predictions,
    fit_score_model,
    load_score_tournament_config,
    locked_score_predictions,
    predict_score_model,
    tournament_selection,
)
from scripts.pipeline import build_rating_score_tournament as tournament_cli


def _score_frame() -> pd.DataFrame:
    rows = []
    game_id = 1
    for season in range(2021, 2026):
        for index in range(24):
            home_field = float(index % 2)
            home_offense = float((index % 7) - 3) / 2
            away_offense = float(((index + 3) % 7) - 3) / 2
            home_defense = float(((index + 1) % 5) - 2) / 2
            away_defense = float(((index + 2) % 5) - 2) / 2
            pace = float((index % 5) - 2) / 2
            home_points = (
                30
                + 2 * home_field
                + 4 * home_offense
                - 3 * away_defense
                + pace
                + (index % 3)
            )
            away_points = (
                30 + 4 * away_offense - 3 * home_defense + pace + ((index + 1) % 3)
            )
            rows.append(
                {
                    "season": season,
                    "week": 1,
                    "game_id": game_id,
                    "kickoff_utc": f"{season}-09-01T00:00:00Z",
                    "home_state_id": f"game:{season}:{game_id}",
                    "away_state_id": f"game:{season}:{game_id}",
                    "home_completed_games": index,
                    "away_completed_games": index,
                    "home_pace_source": "current_pregame",
                    "away_pace_source": "current_pregame",
                    "home_field": home_field,
                    "home_offense_mean": home_offense,
                    "away_offense_mean": away_offense,
                    "home_defense_mean": home_defense,
                    "away_defense_mean": away_defense,
                    "pace_z": pace,
                    "actual_home_points": home_points,
                    "actual_away_points": away_points,
                    "actual_margin": home_points - away_points,
                    "actual_total": home_points + away_points,
                }
            )
            game_id += 1
    return pd.DataFrame(rows)


def _broad_config():
    config = load_score_tournament_config("conf/ratings/score_model_tournament_v2.yaml")
    gates = dict(config.gates)
    gates.update(
        {
            "pooled_error_ratio": 100,
            "seasonal_mae_ratio": 100,
            "max_absolute_bias": 100,
            "max_bias_excess": 100,
            "max_abs_standardized_residual_mean": 100,
            "standardized_residual_sd_min": 0,
            "standardized_residual_sd_max": 100,
            "interval_80_min": 0,
            "interval_80_max": 1,
            "interval_95_min": 0,
            "interval_95_max": 1,
            "bootstrap_samples": 10,
        }
    )
    return replace(config, gates=gates)


def test_score_predictions_derive_margin_total_and_valid_intervals():
    frame = _score_frame()
    config = _broad_config()
    for family in config.candidates:
        model = fit_score_model(
            family, frame, training_seasons=(2021, 2022, 2023), config=config
        )
        values = predict_score_model(
            model, frame[frame.season.eq(2024)], fold_id="test"
        )
        margin = values[values.target.eq("margin")].reset_index(drop=True)
        total = values[values.target.eq("total")].reset_index(drop=True)
        assert np.allclose(
            margin.prediction_mean,
            margin.predicted_home_score - margin.predicted_away_score,
        )
        assert np.allclose(
            total.prediction_mean,
            total.predicted_home_score + total.predicted_away_score,
        )
        assert (values.prediction_sd > 0).all()
        assert (values.interval_95_lower < values.interval_95_upper).all()
        covariance = np.array(
            [
                [
                    [
                        row.home_score_sd**2,
                        row.score_covariance,
                    ],
                    [
                        row.score_covariance,
                        row.away_score_sd**2,
                    ],
                ]
                for row in margin.itertuples()
            ]
        )
        assert (np.linalg.eigvalsh(covariance) >= 0).all()


def test_neutral_side_swap_flips_margin_and_preserves_total():
    frame = _score_frame().iloc[[0]].copy()
    frame["home_field"] = 0.0
    model = ScoreModel(
        family="linear_scores",
        coefficients=np.array([30.0, 2.0, 4.0, -3.0, 1.0]),
        residual_covariance=np.array([[16.0, 4.0], [4.0, 16.0]]),
        dispersion=None,
        training_seasons=(2021,),
    )
    original = predict_score_model(model, frame, fold_id="test")
    swapped = frame.rename(
        columns={
            "home_offense_mean": "away_offense_mean",
            "away_offense_mean": "home_offense_mean",
            "home_defense_mean": "away_defense_mean",
            "away_defense_mean": "home_defense_mean",
        }
    )
    values = predict_score_model(model, swapped, fold_id="test")
    original_margin = original[original.target.eq("margin")].prediction_mean.iloc[0]
    swapped_margin = values[values.target.eq("margin")].prediction_mean.iloc[0]
    original_total = original[original.target.eq("total")].prediction_mean.iloc[0]
    swapped_total = values[values.target.eq("total")].prediction_mean.iloc[0]
    assert swapped_margin == -original_margin
    assert swapped_total == original_total


def test_sealed_tournament_is_deterministic_and_selects_one_family():
    frame = _score_frame()
    config = _broad_config()
    v4_rows = []
    for target, actual in (("spread", "actual_margin"), ("total", "actual_total")):
        for row in frame[frame.season.isin(config.selection_seasons)].itertuples():
            v4_rows.append(
                {
                    "season": row.season,
                    "game_id": row.game_id,
                    "target": target,
                    "v4_prediction": getattr(row, actual) + 1.0,
                    "source_kind": "native_route_replay",
                }
            )
    v4 = pd.DataFrame(v4_rows)
    winner, report, first_models = tournament_selection(
        frame=frame, v4=v4, config=config
    )
    repeated_winner, repeated_report, _ = tournament_selection(
        frame=frame, v4=v4, config=config
    )
    assert winner in config.candidates
    assert repeated_winner == winner
    assert repeated_report == report
    assert report["all_selection_checks_passed"] is True
    predictions, models = expanding_score_predictions(winner, frame, config=config)
    assert set(predictions.season) == set(config.selection_seasons)
    assert len(models) == len(config.selection_seasons)
    assert [model.training_seasons for model in first_models[winner]] == [
        (2021,),
        (2021, 2022),
        (2021, 2022, 2023),
    ]


def test_locked_confirmation_keeps_the_selected_family_and_2025_sealed():
    frame = _score_frame()
    config = _broad_config()
    predictions, model = locked_score_predictions("linear_scores", frame, config=config)
    assert model.training_seasons == (2021, 2022, 2023, 2024)
    assert set(predictions.season) == {2025}


def test_tie_break_selects_linear_family_for_both_targets(monkeypatch):
    frame = _score_frame()
    config = _broad_config()

    def fake_predictions(family, frame, *, config):
        return pd.DataFrame({"family": [family]}), []

    def fake_evaluation(*, predictions, v4, gates):
        ratio = 1.000 if predictions.family.iloc[0] == "linear_scores" else 0.995
        return {
            "all_checks_passed": True,
            "targets": {
                target: {
                    "candidate": {"mae": ratio},
                    "v4": {"mae": 1.0},
                }
                for target in ("margin", "total")
            },
        }

    monkeypatch.setattr(score_models, "expanding_score_predictions", fake_predictions)
    monkeypatch.setattr(score_models, "evaluate_predictions", fake_evaluation)
    winner, report, _ = tournament_selection(
        frame=frame, v4=pd.DataFrame(), config=config
    )
    assert winner == "linear_scores"
    assert report["winner"] == "linear_scores"


def test_rejects_invalid_score_direction_and_nonpositive_predictions():
    frame = _score_frame()
    config = _broad_config()
    bad_direction = frame.copy()
    bad_direction["actual_home_points"] = 30 - bad_direction["home_offense_mean"]
    bad_direction["actual_away_points"] = 30 - bad_direction["away_offense_mean"]
    with pytest.raises(MeasurementContractError, match="directions"):
        fit_score_model(
            "linear_scores",
            bad_direction,
            training_seasons=(2021, 2022, 2023),
            config=config,
        )
    nonpositive = ScoreModel(
        family="linear_scores",
        coefficients=np.array([-100.0, 2.0, 4.0, -3.0, 1.0]),
        residual_covariance=np.eye(2),
        dispersion=None,
        training_seasons=(2021,),
    )
    with pytest.raises(MeasurementContractError, match="non-positive"):
        predict_score_model(nonpositive, frame.iloc[[0]], fold_id="test")


def _cli_argv(*, environment: str, prefix: str) -> list[str]:
    return [
        "--environment",
        environment,
        "--as-of",
        "2026-08-25T00:00:00Z",
        "--run-id",
        "test",
        "--games-ref-uri",
        "unused-games",
        "--outcomes-ref-uri",
        "unused-outcomes",
        "--v4-ref-uri",
        "unused-v4",
        "--tournament-uri",
        f"{prefix}/tournament.json",
        "--models-ref-uri",
        f"{prefix}/models-ref.json",
        "--predictions-ref-uri",
        f"{prefix}/predictions-ref.json",
        "--candidate-manifest-uri",
        f"{prefix}/candidate.json",
    ]


def test_cli_rejects_production_and_paths_outside_the_research_prefix():
    with pytest.raises(ValueError, match="only in preview"):
        tournament_cli.main(_cli_argv(environment="production", prefix="unused"))
    with pytest.raises(ValueError, match="run-stamped research prefix"):
        tournament_cli.main(
            _cli_argv(environment="preview", prefix="artifacts/production/ratings")
        )
