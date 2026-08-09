import pandas as pd

from cks_picks_cfb.models.training_policy import policy_from_mapping
from cks_picks_cfb.ops.data_audit import audit_feature_frame


def _policy():
    return policy_from_mapping(
        {
            "schema_version": "training_policy_2026_v1",
            "labeled_years": [2021, 2022, 2023, 2024, 2025],
            "selection_folds": [
                {"train_years": [2021], "validation_year": 2022},
                {"train_years": [2021, 2022], "validation_year": 2023},
                {"train_years": [2021, 2022, 2023], "validation_year": 2024},
            ],
            "locked_test": {
                "train_years": [2021, 2022, 2023, 2024],
                "test_year": 2025,
            },
            "production_refit_years": [2021, 2022, 2023, 2024, 2025],
            "prior_source_overrides": {2021: 2019},
            "excluded_years": [2020],
        }
    )


def test_data_audit_reports_all_years_and_regimes():
    regimes = ["preseason", "one_game", "two_games", "three_games", "established"]
    rows = []
    for season in range(2021, 2026):
        for index, regime in enumerate(regimes):
            prior = 2019 if season == 2021 else season - 1
            rows.append(
                {
                    "season": season,
                    "game_id": season * 10 + index,
                    "spread_target": 1.0,
                    "total_target": 50.0,
                    "prior_source_season": prior,
                    "prior_season_gap": season - prior,
                    "home_completed_games": index,
                    "away_completed_games": index,
                    "prediction_regime": regime,
                    "home_team_spread_line": None,
                    "total_line": None,
                    "baseline_spread_prediction": 0.0,
                    "baseline_total_prediction": 50.0,
                    "home_prior_adj_off_epa_pp": 0.1,
                    "away_prior_adj_off_epa_pp": 0.1,
                    "home_adj_off_epa_pp": 0.2,
                    "away_adj_off_epa_pp": 0.2,
                }
            )
    result = audit_feature_frame(pd.DataFrame(rows), _policy())
    assert result.passed
    assert result.coverage["market_coverage"] == 0.0


def test_data_audit_fails_for_2020_lineage_and_duplicate_game():
    frame = pd.DataFrame(
        [
            {
                "season": 2021,
                "game_id": 1,
                "spread_target": 1.0,
                "total_target": 50.0,
                "prior_source_season": 2020,
                "prior_season_gap": 1,
                "home_completed_games": 0,
                "away_completed_games": 0,
                "prediction_regime": "preseason",
            },
            {
                "season": 2021,
                "game_id": 1,
                "spread_target": 1.0,
                "total_target": 50.0,
                "prior_source_season": 2020,
                "prior_season_gap": 1,
                "home_completed_games": 0,
                "away_completed_games": 0,
                "prediction_regime": "preseason",
            },
        ]
    )
    result = audit_feature_frame(frame, _policy())
    assert not result.passed
    assert not result.checks["temporal_lineage"]
    assert not result.checks["unique_game_keys"]
