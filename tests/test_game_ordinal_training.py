import pandas as pd

from cks_picks_cfb.models.game_ordinal_training import (
    generate_game_ordinal_candidate_predictions,
)
from cks_picks_cfb.models.training_policy import policy_from_mapping


def test_ordinal_candidates_are_temporal_and_include_both_formulations():
    rows = []
    for season in (2021, 2022, 2023, 2024, 2025):
        for route_index, regime in enumerate(("game_1", "game_2", "game_3"), start=1):
            for sample in range(4):
                rows.append(
                    {
                        "season": season,
                        "game_id": season * 100 + route_index * 10 + sample,
                        "prediction_regime": regime,
                        "prior_source_season": 2019 if season == 2021 else season - 1,
                        "prior_season_gap": 2 if season == 2021 else 1,
                        "feature": float(route_index + sample + season % 3),
                        "home_points": 20.0 + route_index + sample + season % 3,
                        "away_points": 14.0 + route_index + sample + season % 2,
                        "spread_target": float(6 + season % 2 + sample),
                        "total_target": 34.0 + route_index * 2 + sample,
                        "baseline_spread_prediction": 5.0,
                        "baseline_total_prediction": 35.0,
                    }
                )
    policy = policy_from_mapping(
        {
            "schema_version": "training_policy_2026_v1",
            "labeled_years": [2021, 2022, 2023, 2024, 2025],
            "selection_folds": [
                {"train_years": [2021], "validation_year": 2022},
                {"train_years": [2021, 2022], "validation_year": 2023},
                {"train_years": [2021, 2022, 2023], "validation_year": 2024},
            ],
            "locked_test": {"train_years": [2021, 2022, 2023, 2024], "test_year": 2025},
            "production_refit_years": [2021, 2022, 2023, 2024, 2025],
            "prior_source_overrides": {"2021": 2019},
            "excluded_years": [2020],
        }
    )
    result = generate_game_ordinal_candidate_predictions(
        pd.DataFrame(rows),
        policy=policy,
        features=["feature"],
        baseline_columns={
            "spread": "baseline_spread_prediction",
            "total": "baseline_total_prediction",
        },
    )
    assert {
        "direct_ridge_prediction",
        "direct_catboost_prediction",
        "points_ridge_prediction",
        "points_catboost_prediction",
    }.issubset(result.columns)
    assert (result["training_max_year"] == result["season"] - 1).all()
    assert set(result["season"].astype(int)) == {2022, 2023, 2024}
    assert set(result["candidate_stage"]) == {"selection"}
