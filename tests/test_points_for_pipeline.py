"""Tests for points-for prediction helpers."""

from __future__ import annotations

import pandas as pd
from sklearn.linear_model import LinearRegression

from src.scripts.generate_weekly_bets_clean import predict_with_points_for


def _fit_model(features: list[str], y_values: list[float]) -> LinearRegression:
    model = LinearRegression()
    model.fit(pd.DataFrame([range(len(features))], columns=features), [y_values[0]])
    model.feature_names_in_ = features  # type: ignore[attr-defined]
    return model


def test_predict_with_points_for_generates_expected_columns() -> None:
    df = pd.DataFrame(
        {
            "home_adj_off_epa_pp": [0.2, 0.5],
            "home_adj_def_epa_pp": [0.1, -0.2],
            "home_games_played": [5, 6],
            "away_adj_off_epa_pp": [0.3, 0.4],
            "away_adj_def_epa_pp": [0.2, 0.1],
            "away_games_played": [5, 5],
        }
    )

    home_features = ["home_adj_off_epa_pp", "home_adj_def_epa_pp", "home_games_played"]
    away_features = ["away_adj_off_epa_pp", "away_adj_def_epa_pp", "away_games_played"]
    home_model = LinearRegression()
    home_model.fit(df[home_features], [28.0, 31.0])
    away_model = LinearRegression()
    away_model.fit(df[away_features], [24.0, 21.0])

    result = predict_with_points_for(
        df,
        home_model,
        away_model,
        spread_std=18.0,
        total_std=17.0,
    )

    assert not result.empty
    assert set(
        [
            "predicted_spread",
            "predicted_total",
            "predicted_spread_std_dev",
            "predicted_total_std_dev",
        ]
    ).issubset(result.columns)
    assert (result["predicted_spread_std_dev"] == 18.0).all()
    assert (result["predicted_total_std_dev"] == 17.0).all()
