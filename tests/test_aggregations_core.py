import pandas as pd

from features.core import (
    aggregate_team_game,
    aggregate_team_season,
    apply_iterative_opponent_adjustment,
)


def test_aggregate_team_season_recency_weighting():
    """
    Tests that the recency weighting in aggregate_team_season is applied correctly.
    The last four games are weighted 4, 3, 2, 1 (most recent lowest index gets 1).
    Any earlier games retain a weight of 1.
    """
    team_game_data = {
        "season": [2024, 2024, 2024, 2024],
        "week": [1, 2, 3, 4],
        "team": ["A", "A", "A", "A"],
        "off_sr": [0.1, 0.2, 0.3, 0.4],  # Metric to be averaged
    }
    team_game_df = pd.DataFrame(team_game_data)

    # Expected calculation (based on current implementation):
    # Weights for weeks 1, 2, 3, 4 are [4.0, 3.0, 2.0, 1.0]
    # Weighted sum = (0.1 * 4.0) + (0.2 * 3.0) + (0.3 * 2.0) + (0.4 * 1.0) = 2.0
    # Sum of weights = 10
    # Expected mean = 0.2
    expected_off_sr = 0.2

    team_season_df = aggregate_team_season(team_game_df)

    assert len(team_season_df) == 1
    actual_off_sr = team_season_df.iloc[0]["off_sr"]
    assert abs(actual_off_sr - expected_off_sr) < 1e-6, (
        "Recency weighting calculation is incorrect."
    )


def test_aggregate_team_season_empty_input():
    """Tests that aggregate_team_season handles empty input gracefully."""
    team_game_df = pd.DataFrame(columns=["season", "week", "team", "off_sr"])
    team_season_df = aggregate_team_season(team_game_df)
    assert team_season_df.empty


def test_aggregate_team_season_missing_metric_cols():
    """Tests that aggregate_team_season runs without error if a metric column is missing."""
    team_game_data = {
        "season": [2024],
        "week": [1],
        "team": ["A"],
        # off_sr is missing
    }
    team_game_df = pd.DataFrame(team_game_data)
    team_season_df = aggregate_team_season(team_game_df)
    assert len(team_season_df) == 1
    assert "off_sr" not in team_season_df.columns


def test_aggregate_team_season_fills_special_teams_missingness():
    """
    Special-teams metrics (e.g., net punt yards) can be missing for teams with no punts.
    Ensure the aggregation fills NaNs and still produces finite momentum features.
    """
    team_game_df = pd.DataFrame(
        {
            "season": [2024, 2024],
            "week": [1, 2],
            "team": ["A", "A"],
            "off_avg_net_punt_yards": [pd.NA, 40.0],
        }
    )

    team_season_df = aggregate_team_season(team_game_df)
    row = team_season_df.iloc[0]

    assert not pd.isna(row["off_avg_net_punt_yards"])
    assert not pd.isna(row["off_avg_net_punt_yards_last_1"])
    assert abs(row["off_avg_net_punt_yards_last_1"] - 40.0) < 1e-6
    assert abs(row["off_avg_net_punt_yards_last_2"] - 20.0) < 1e-6


def test_apply_iterative_opponent_adjustment_simple():
    """
    Tests the opponent adjustment logic with a simple 2-team, 1-game scenario.
    """
    team_season_df = pd.DataFrame(
        {
            "season": [2024, 2024],
            "team": ["A", "B"],
            "games_played": [1, 1],
            "off_sr": [0.6, 0.4],
            "def_sr": [0.3, 0.5],
        }
    )
    team_game_df = pd.DataFrame(
        {
            "season": [2024, 2024],
            "week": [1, 1],
            "game_id": [1, 1],
            "team": ["A", "B"],
        }
    )

    # With one game, opponent is clear.
    # Team A played B, Team B played A.
    # League mean off_sr = 0.5, def_sr = 0.4
    #
    # Iteration 1 for Team A offense:
    # adj_off_sr(A) = base_off_sr(A) - (adj_def_sr(B) - league_mean_def_sr)
    # adj_off_sr(A) = 0.6 - (0.5 - 0.4) = 0.6 - 0.1 = 0.5
    #
    # Iteration 1 for Team A defense:
    # adj_def_sr(A) = base_def_sr(A) - (adj_off_sr(B) - league_mean_off_sr)
    # adj_def_sr(A) = 0.3 - (0.4 - 0.5) = 0.3 - (-0.1) = 0.4

    adjusted_df = apply_iterative_opponent_adjustment(
        team_season_df, team_game_df, iterations=1
    )

    # Filter for the final iteration (iteration=1)
    final_iteration_df = adjusted_df[adjusted_df["iteration"] == 1]
    team_a_adj = final_iteration_df[final_iteration_df["team"] == "A"].iloc[0]

    assert "adj_off_sr" in team_a_adj
    assert "adj_def_sr" in team_a_adj
    assert abs(team_a_adj["adj_off_sr"] - 0.5) < 1e-6
    assert abs(team_a_adj["adj_def_sr"] - 0.4) < 1e-6


def test_aggregate_team_game_field_position_and_drive_metrics():
    season = 2024
    week = 1
    game_id = 111

    def _play(**overrides):
        base = {
            "season": season,
            "week": week,
            "game_id": game_id,
            "play_number": overrides.get("play_number", 1),
            "offense": overrides.get("offense", "TeamA"),
            "defense": overrides.get("defense", "TeamB"),
            "rush_attempt": overrides.get("rush_attempt", 1),
            "pass_attempt": overrides.get("pass_attempt", 0),
            "success": overrides.get("success", 1),
            "yards_gained": overrides.get("yards_gained", 5),
            "ppa": overrides.get("ppa", 0.1),
            "havoc": overrides.get("havoc", 0),
            "line_yards": overrides.get("line_yards", 2.0),
            "second_level_yards": overrides.get("second_level_yards", 1.0),
            "open_field_yards": overrides.get("open_field_yards", 0.5),
            "is_power_situation": overrides.get("is_power_situation", 0),
            "power_success_converted": overrides.get("power_success_converted", 0),
            "thirddown_conversion": overrides.get("thirddown_conversion", 0),
            "play_type": overrides.get("play_type", "Rush"),
            "st": 0,
            "penalty": 0,
            "twopoint": 0,
            "quarter": 1,
            "eckel": 0,
            "yards_to_goal": overrides.get("yards_to_goal", 65),
            "drive_number": overrides.get("drive_number", 1),
            "scoring": overrides.get("scoring", 0),
            "turnover": overrides.get("turnover", 0),
            "st_fg": 0,
            "st_punt": 0,
            "kick_distance": 0,
            "is_fg_made": 0,
        }
        base.update(overrides)
        return base

    plays = [
        _play(
            play_number=1,
            drive_number=1,
            offense="TeamA",
            defense="TeamB",
            yards_gained=7,
        ),
        _play(
            play_number=2,
            drive_number=2,
            offense="TeamA",
            defense="TeamB",
            yards_gained=3,
            success=0,
        ),
        _play(
            play_number=3,
            drive_number=1,
            offense="TeamB",
            defense="TeamA",
            yards_gained=4,
        ),
        _play(
            play_number=4,
            drive_number=2,
            offense="TeamB",
            defense="TeamA",
            yards_gained=6,
        ),
        _play(
            play_number=5,
            drive_number=3,
            offense="TeamB",
            defense="TeamA",
            yards_gained=8,
        ),
    ]
    plays_df = pd.DataFrame(plays)

    drives = [
        {
            "season": season,
            "week": week,
            "game_id": game_id,
            "drive_number": 1,
            "offense": "TeamA",
            "defense": "TeamB",
            "is_eckel_drive": 1,
            "is_successful_drive": 1,
            "is_busted_drive": 0,
            "is_explosive_drive": 0,
            "points_on_opps": 7,
            "had_scoring_opportunity": 1,
            "start_yards_to_goal": 70,
            "points": 7,
            "turnover": 0,
        },
        {
            "season": season,
            "week": week,
            "game_id": game_id,
            "drive_number": 2,
            "offense": "TeamA",
            "defense": "TeamB",
            "is_eckel_drive": 0,
            "is_successful_drive": 1,
            "is_busted_drive": 0,
            "is_explosive_drive": 0,
            "points_on_opps": 3,
            "had_scoring_opportunity": 1,
            "start_yards_to_goal": 60,
            "points": 3,
            "turnover": 0,
        },
        # Opponent drives against TeamA defense
        {
            "season": season,
            "week": week,
            "game_id": game_id,
            "drive_number": 1,
            "offense": "TeamB",
            "defense": "TeamA",
            "is_eckel_drive": 0,
            "is_successful_drive": 1,
            "is_busted_drive": 0,
            "is_explosive_drive": 0,
            "points_on_opps": 3,
            "had_scoring_opportunity": 1,
            "start_yards_to_goal": 80,
            "points": 3,
            "turnover": 0,
        },
        {
            "season": season,
            "week": week,
            "game_id": game_id,
            "drive_number": 2,
            "offense": "TeamB",
            "defense": "TeamA",
            "is_eckel_drive": 0,
            "is_successful_drive": 1,
            "is_busted_drive": 0,
            "is_explosive_drive": 0,
            "points_on_opps": 3,
            "had_scoring_opportunity": 1,
            "start_yards_to_goal": 75,
            "points": 3,
            "turnover": 0,
        },
        {
            "season": season,
            "week": week,
            "game_id": game_id,
            "drive_number": 3,
            "offense": "TeamB",
            "defense": "TeamA",
            "is_eckel_drive": 0,
            "is_successful_drive": 0,
            "is_busted_drive": 0,
            "is_explosive_drive": 0,
            "points_on_opps": 2,
            "had_scoring_opportunity": 1,
            "start_yards_to_goal": 70,
            "points": 2,
            "turnover": 0,
        },
    ]
    drives_df = pd.DataFrame(drives)

    team_game = aggregate_team_game(plays_df, drives_df)
    team_a_row = team_game[team_game["team"] == "TeamA"].iloc[0]

    assert abs(team_a_row["off_points_per_drive"] - 5.0) < 1e-6
    expected_def_ppd = 8.0 / 3.0
    assert abs(team_a_row["def_points_per_drive_allowed"] - expected_def_ppd) < 1e-6
    assert abs(team_a_row["net_field_position_delta"] - 10.0) < 1e-6
