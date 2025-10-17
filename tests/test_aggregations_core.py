import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from features.core import (
    aggregate_team_season,
    apply_iterative_opponent_adjustment,
)


def test_aggregate_team_season_recency_weighting():
    """
    Tests that the recency weighting in aggregate_team_season is applied correctly.
    The last 3 games should be weighted 3, 2, 1. All others are 1.
    """
    team_game_data = {
        "season": [2024, 2024, 2024, 2024],
        "week": [1, 2, 3, 4],
        "team": ["A", "A", "A", "A"],
        "off_sr": [0.1, 0.2, 0.3, 0.4],  # Metric to be averaged
    }
    team_game_df = pd.DataFrame(team_game_data)

    # Expected calculation (based on current implementation):
    # Weights for weeks 1, 2, 3, 4 are [1.0, 3.0, 2.0, 1.0]
    # Weighted sum = (0.1 * 1.0) + (0.2 * 3.0) + (0.3 * 2.0) + (0.4 * 1.0) = 0.1 + 0.6 + 0.6 + 0.4 = 1.7
    # Sum of weights = 1 + 3 + 2 + 1 = 7
    # Expected mean = 1.7 / 7
    expected_off_sr = 1.7 / 7.0

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

    team_a_adj = adjusted_df[adjusted_df["team"] == "A"].iloc[0]

    assert "adj_off_sr" in team_a_adj
    assert "adj_def_sr" in team_a_adj
    assert abs(team_a_adj["adj_off_sr"] - 0.5) < 1e-6
    assert abs(team_a_adj["adj_def_sr"] - 0.4) < 1e-6