import pandas as pd

from cks_picks_cfb.features.point_in_time import build_temporal_matchup_inputs
from cks_picks_cfb.models.baselines import generate_baselines


def test_temporal_inputs_use_only_prior_games_and_keep_2019_prior():
    schedule = pd.DataFrame(
        [
            {
                "season": 2021,
                "week": 0,
                "game_id": 1,
                "kickoff_utc": "2021-08-20T16:00:00Z",
                "home_team": "A",
                "away_team": "B",
                "completed": True,
                "home_points": 20,
                "away_points": 10,
            },
            {
                "season": 2021,
                "week": 0,
                "game_id": 2,
                "kickoff_utc": "2021-08-21T16:00:00Z",
                "home_team": "A",
                "away_team": "B",
                "completed": True,
                "home_points": 24,
                "away_points": 21,
            },
        ]
    )
    team_game = pd.DataFrame(
        [
            {
                "season": 2021,
                "week": 0,
                "game_id": 1,
                "team": "A",
                "off_epa": 2.0,
                "def_epa": -1.0,
            },
            {
                "season": 2021,
                "week": 0,
                "game_id": 1,
                "team": "B",
                "off_epa": 1.0,
                "def_epa": 0.5,
            },
            {
                "season": 2021,
                "week": 0,
                "game_id": 2,
                "team": "A",
                "off_epa": 99.0,
                "def_epa": 99.0,
            },
            {
                "season": 2021,
                "week": 0,
                "game_id": 2,
                "team": "B",
                "off_epa": 99.0,
                "def_epa": 99.0,
            },
        ]
    )
    prior = pd.DataFrame(
        [
            {"season": 2019, "team": "A", "off_epa": 0.2, "def_epa": -0.2},
            {"season": 2019, "team": "B", "off_epa": 0.1, "def_epa": -0.1},
        ]
    )
    result = build_temporal_matchup_inputs(schedule, team_game, prior_2019=prior)
    first = result[result["game_id"] == 1].iloc[0]
    second = result[result["game_id"] == 2].iloc[0]
    assert pd.isna(first["home_current_off_epa"])
    assert second["home_current_off_epa"] == 2.0
    assert second["home_prior_off_epa"] == 0.2
    assert second["home_current_adj_off_epa"] == 1.5


def test_temporal_inputs_overlay_outcomes_and_exclude_cancelled_training_games():
    schedule = pd.DataFrame(
        [
            {
                "season": 2025,
                "week": 4,
                "game_id": 1,
                "kickoff_utc": "2025-09-20T16:00:00Z",
                "home_team": "A",
                "away_team": "B",
                "completed": False,
                "home_points": None,
                "away_points": None,
            },
            {
                "season": 2025,
                "week": 5,
                "game_id": 2,
                "kickoff_utc": "2025-09-27T16:00:00Z",
                "home_team": "A",
                "away_team": "B",
                "completed": False,
                "home_points": None,
                "away_points": None,
            },
            {
                "season": 2026,
                "week": 0,
                "game_id": 3,
                "kickoff_utc": "2026-08-29T16:00:00Z",
                "home_team": "A",
                "away_team": "B",
                "completed": False,
                "home_points": None,
                "away_points": None,
            },
        ]
    )
    team_game = pd.DataFrame(
        [
            {"season": 2025, "week": 4, "game_id": 1, "team": "A", "off_epa": 1.0},
            {"season": 2025, "week": 4, "game_id": 1, "team": "B", "off_epa": 1.0},
            {"season": 2025, "week": 5, "game_id": 2, "team": "A", "off_epa": 1.0},
            {"season": 2025, "week": 5, "game_id": 2, "team": "B", "off_epa": 1.0},
        ]
    )
    outcomes = pd.DataFrame(
        [
            {
                "season": 2025,
                "game_id": 1,
                "completed": True,
                "home_points": 17,
                "away_points": 16,
            },
            {
                "season": 2025,
                "game_id": 2,
                "completed": False,
                "home_points": None,
                "away_points": None,
            },
        ]
    )
    result = build_temporal_matchup_inputs(
        schedule,
        team_game,
        prior_2019=pd.DataFrame(),
        outcomes=outcomes,
        inference_seasons=frozenset({2026}),
    )
    assert result["game_id"].tolist() == [1, 3]
    assert result.loc[result["game_id"] == 1, "spread_target"].item() == 1


def test_baselines_are_strictly_temporal_and_2025_is_guarded():
    rows = []
    for season in range(2021, 2026):
        for index, regime in enumerate(("preseason", "established")):
            rows.append(
                {
                    "season": season,
                    "game_id": season * 10 + index,
                    "prediction_regime": regime,
                    "spread_target": float(index),
                    "total_target": 40.0 + index,
                    "home_prior_rating": float(season),
                    "away_prior_rating": float(season - 1),
                    "home_adj_rating": float(index),
                    "away_adj_rating": float(index + 1),
                }
            )
    frame = pd.DataFrame(rows)
    selection = generate_baselines(frame, include_locked_2025=False)
    assert set(selection["season"]) == {2022, 2023, 2024}
    assert (selection["training_max_year"] < selection["season"]).all()

    locked = generate_baselines(frame, include_locked_2025=True)
    assert 2025 in set(locked["season"])
    assert locked.loc[locked["season"] == 2025, "training_max_year"].eq(2024).all()
