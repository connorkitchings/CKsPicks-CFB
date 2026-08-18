"""Completed-game routing and prior/current shrinkage tests."""

import pandas as pd

from cks_picks_cfb.features.v2_recency import (
    _merge_seeded_prediction_rows,
    canonical_prediction_regime,
    completed_game_regime,
    upcoming_game_regime,
)


def test_completed_game_regimes_cover_zero_through_established():
    assert [completed_game_regime(value) for value in range(6)] == [
        "preseason",
        "one_game",
        "two_games",
        "three_games",
        "established",
        "established",
    ]


def test_upcoming_game_routes_cover_the_first_four_scheduled_games():
    assert [upcoming_game_regime(value) for value in range(6)] == [
        "game_1",
        "game_2",
        "game_3",
        "game_4",
        "established",
        "established",
    ]
    assert canonical_prediction_regime("preseason") == "game_1"
    assert canonical_prediction_regime("one_game") == "game_2"
    assert canonical_prediction_regime("two_games") == "game_3"
    assert canonical_prediction_regime("three_games") == "game_4"


def test_current_and_prior_features_remain_separate():
    games = pd.DataFrame(
        [
            {
                "game_id": 99,
                "season": 2026,
                "week": 3,
                "home_team": "A",
                "away_team": "B",
                "start_date": "2026-09-12T12:00:00Z",
            }
        ]
    )
    prior_games = pd.DataFrame(
        [
            {"game_id": 1, "week": 1, "team": "A"},
            {"game_id": 2, "week": 2, "team": "A"},
            {"game_id": 3, "week": 1, "team": "B"},
            {"game_id": 4, "week": 2, "team": "B"},
        ]
    )
    current = pd.DataFrame(
        [
            {"game_id": 99, "team": "A", "adj_off_epa_pp": 100.0},
            {"game_id": 99, "team": "B", "adj_off_epa_pp": 200.0},
        ]
    )

    def read_entity(entity, year):
        assert entity == "team_week_adj"
        assert year == 2025
        return [
            {"team": "A", "week": 15, "adj_off_epa_pp": 20.0},
            {"team": "B", "week": 15, "adj_off_epa_pp": 40.0},
        ]

    result = _merge_seeded_prediction_rows(
        current,
        games,
        prior_games,
        read_entity,
        2026,
    ).set_index("team")

    assert result.loc["A", "adj_off_epa_pp"] == 100.0
    assert result.loc["B", "adj_off_epa_pp"] == 200.0
    assert result.loc["A", "prior_adj_off_epa_pp"] == 20.0
    assert result.loc["B", "prior_adj_off_epa_pp"] == 40.0
    assert result.loc["A", "prediction_regime"] == "two_games"


def test_2021_seed_uses_2019_not_2020():
    games = pd.DataFrame(
        [
            {
                "game_id": 1,
                "season": 2021,
                "week": 0,
                "home_team": "A",
                "away_team": "B",
                "start_date": "2021-08-28T12:00:00Z",
            }
        ]
    )
    requested = []

    def read_entity(entity, year):
        requested.append((entity, year))
        return [
            {"team": "A", "week": 15, "adj_off_epa_pp": 1.0},
            {"team": "B", "week": 15, "adj_off_epa_pp": 2.0},
        ]

    result = _merge_seeded_prediction_rows(
        pd.DataFrame(), games, pd.DataFrame(), read_entity, 2021
    )
    assert requested == [("team_week_adj", 2019)]
    assert set(result["prior_source_season"]) == {2019}
    assert set(result["prior_season_gap"]) == {2}
    assert result["adj_off_epa_pp"].isna().all()
    assert set(result["prior_adj_off_epa_pp"]) == {1.0, 2.0}
