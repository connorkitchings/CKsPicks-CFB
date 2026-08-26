"""Tests for the frozen Phase 3 structured prediction baseline."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cks_picks_cfb.ratings.contracts import MeasurementContractError
from cks_picks_cfb.ratings.prediction_evaluation import evaluate_predictions
from cks_picks_cfb.ratings.predictions import (
    expanding_predictions,
    fit_ols,
    load_prediction_config,
    predict,
    prepare_prediction_frame,
)


@pytest.fixture()
def config():
    return load_prediction_config("conf/ratings/prediction_baseline_v1.yaml")


def _training_frame() -> pd.DataFrame:
    rows = []
    game_id = 1
    for season in range(2021, 2026):
        for index in range(12):
            quality = float(index - 5)
            off = float(index % 4 - 1)
            defense = float((index * 2) % 5 - 2)
            pace = float(index % 3 - 1)
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
                    "home_field": float(index % 2),
                    "quality_gap": quality,
                    "offense_sum": off,
                    "defense_sum": defense,
                    "pace_z": pace,
                    "home_overall_sd": 0.2,
                    "away_overall_sd": 0.3,
                    "home_offense_sd": 0.2,
                    "away_offense_sd": 0.2,
                    "home_defense_sd": 0.3,
                    "away_defense_sd": 0.3,
                    "actual_margin": 2.0 * float(index % 2)
                    + 3.0 * quality
                    + (index % 2 - 0.5),
                    "actual_total": 45.0
                    + 4.0 * off
                    - 3.0 * defense
                    + 2.0 * pace
                    + (index % 2 - 0.5),
                }
            )
            game_id += 1
    return pd.DataFrame(rows)


def test_ols_coefficients_chronology_and_uncertainty(config):
    frame = _training_frame()
    model = fit_ols(frame, target="margin", training_seasons=(2021, 2022, 2023))
    assert model.rank == 2
    assert model.coefficients[1] > 0
    values = predict(model, frame[frame.season.eq(2024)], fold_id="expanding_2024")
    assert (values["prediction_sd"] > 0).all()
    assert (values["interval_95_lower"] < values["interval_95_upper"]).all()
    predictions, models = expanding_predictions(frame, config)
    assert set(predictions["season"]) == {2022, 2023, 2024, 2025}
    assert len(models) == 8


def test_ols_rejects_frozen_sign_failure():
    frame = _training_frame()
    frame["actual_margin"] = -frame["quality_gap"]
    with pytest.raises(MeasurementContractError, match="signs"):
        fit_ols(frame, target="margin", training_seasons=(2021, 2022, 2023))


def test_expanding_predictions_exclude_unscorable_historical_games(config):
    frame = _training_frame()
    incomplete_game_id = int(frame.loc[frame.season.eq(2024), "game_id"].iloc[0])
    frame.loc[
        frame.game_id.eq(incomplete_game_id), ["actual_margin", "actual_total"]
    ] = np.nan

    predictions, _ = expanding_predictions(frame, config)

    assert incomplete_game_id not in set(predictions["game_id"])
    assert len(predictions) == (4 * 12 - 1) * 2


def test_prediction_evaluation_preserves_paired_v4_source_kind(config):
    frame = _training_frame()
    predictions, _ = expanding_predictions(frame, config)
    v4 = predictions.copy()
    v4["target"] = v4["target"].replace({"margin": "spread"})
    v4["v4_prediction"] = v4["actual"] + 0.1
    v4["source_kind"] = "native_route_replay"
    # Use deliberately broad local gates so this test exercises the report shape.
    gates = dict(config.gates)
    gates.update(
        {
            "pooled_error_ratio": 10,
            "seasonal_mae_ratio": 10,
            "max_absolute_bias": 10,
            "max_bias_excess": 10,
            "max_abs_standardized_residual_mean": 10,
            "standardized_residual_sd_min": 0,
            "standardized_residual_sd_max": 10,
            "interval_80_min": 0,
            "interval_80_max": 1,
            "interval_95_min": 0,
            "interval_95_max": 1,
            "bootstrap_samples": 10,
        }
    )
    report = evaluate_predictions(predictions=predictions, v4=v4, gates=gates)
    assert report["all_checks_passed"]
    assert report["targets"]["margin"]["v4_source_kind_counts"] == {
        "native_route_replay": len(predictions[predictions.target.eq("margin")])
    }


def test_prepare_rejects_missing_neutral_site(config):
    team_states = pd.DataFrame(
        [
            {
                "state_kind": "pregame",
                "season": 2021,
                "as_of_game_id": 1,
                "team": "A",
                "state_id": "game:2021:1",
                "offense_mean": 1.0,
                "offense_sd": 0.2,
                "defense_mean": 0.3,
                "defense_sd": 0.2,
                "overall_mean": 0.6,
                "overall_sd": 0.2,
                "completed_games": 0,
            },
            {
                "state_kind": "pregame",
                "season": 2021,
                "as_of_game_id": 1,
                "team": "B",
                "state_id": "game:2021:1",
                "offense_mean": 0.1,
                "offense_sd": 0.2,
                "defense_mean": -0.2,
                "defense_sd": 0.2,
                "overall_mean": -0.1,
                "overall_sd": 0.2,
                "completed_games": 0,
            },
        ]
    )
    games = pd.DataFrame(
        [
            {
                "season": 2021,
                "week": 1,
                "game_id": 1,
                "kickoff_utc": "2021-09-01T00:00:00Z",
                "home_team": "A",
                "away_team": "B",
                "neutral_site": np.nan,
            }
        ]
    )
    outcomes = pd.DataFrame(
        [
            {
                "season": 2021,
                "game_id": 1,
                "completed": True,
                "home_points": 20,
                "away_points": 10,
            }
        ]
    )
    with pytest.raises(MeasurementContractError, match="neutral-site"):
        prepare_prediction_frame(
            team_states=team_states,
            snapshots=pd.DataFrame(),
            terminal_snapshots=pd.DataFrame(),
            games=games,
            outcomes=outcomes,
            config=config,
        )


def test_prepare_uses_current_pregame_pace_and_outcome_identity(config):
    team_states = pd.DataFrame(
        [
            {
                "state_kind": "pregame",
                "season": 2021,
                "as_of_game_id": 1,
                "team": "A",
                "state_id": "game:2021:1",
                "offense_mean": 1.0,
                "offense_sd": 0.2,
                "defense_mean": 0.3,
                "defense_sd": 0.2,
                "overall_mean": 0.6,
                "overall_sd": 0.2,
                "completed_games": 0,
            },
            {
                "state_kind": "pregame",
                "season": 2021,
                "as_of_game_id": 1,
                "team": "B",
                "state_id": "game:2021:1",
                "offense_mean": 0.1,
                "offense_sd": 0.2,
                "defense_mean": -0.2,
                "defense_sd": 0.2,
                "overall_mean": -0.1,
                "overall_sd": 0.2,
                "completed_games": 0,
            },
        ]
    )
    snapshots = pd.DataFrame(
        [
            {
                "season": 2021,
                "as_of_game_id": 1,
                "team": "A",
                "measurement_id": "plays_per_drive",
                "unit_role": "offense",
                "coverage_status": "observed",
                "adjusted_value": 6.0,
            },
            {
                "season": 2021,
                "as_of_game_id": 1,
                "team": "B",
                "measurement_id": "plays_per_drive",
                "unit_role": "offense",
                "coverage_status": "observed",
                "adjusted_value": 8.0,
            },
        ]
    )
    games = pd.DataFrame(
        [
            {
                "season": 2021,
                "week": 1,
                "game_id": 1,
                "kickoff_utc": "2021-09-01T00:00:00Z",
                "home_team": "A",
                "away_team": "B",
                "neutral_site": False,
                "completed": False,
                "home_points": 99,
                "away_points": 0,
            }
        ]
    )
    outcomes = pd.DataFrame(
        [
            {
                "season": 2021,
                "game_id": 1,
                "completed": True,
                "home_points": 20,
                "away_points": 10,
            }
        ]
    )
    result = prepare_prediction_frame(
        team_states=team_states,
        snapshots=snapshots,
        terminal_snapshots=pd.DataFrame(columns=snapshots.columns),
        games=games,
        outcomes=outcomes,
        config=config,
    )
    assert result.loc[0, "actual_margin"] == 10.0
    assert result.loc[0, "pace_z"] == 1.0
    assert result.loc[0, "home_pace_source"] == "current_pregame"
