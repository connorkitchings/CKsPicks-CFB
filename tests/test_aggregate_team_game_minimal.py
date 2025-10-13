# Unit test for aggregate_team_game using tiny synthetic inputs

import pandas as pd

from cfb_model.data.aggregations.core import aggregate_team_game


def test_aggregate_team_game_minimal():
    # two plays and a minimal drives mapping including season/week
    plays = pd.DataFrame(
        [
            {
                "season": 2024,
                "week": 1,
                "game_id": 1,
                "offense": "A",
                "defense": "B",
                "play_number": 1,
                "rush_attempt": 1,
                "pass_attempt": 0,
                "success": 1,
                "yards_gained": 5,
                "ppa": 0.2,
                "st": 0,
                "thirddown_conversion": 1,
            },
            {
                "season": 2024,
                "week": 1,
                "game_id": 1,
                "offense": "B",
                "defense": "A",
                "play_number": 1,
                "rush_attempt": 0,
                "pass_attempt": 1,
                "success": 0,
                "yards_gained": 10,
                "st": 0,
                "thirddown_conversion": 0,
            },
            {
                "season": 2024,
                "week": 1,
                "game_id": 1,
                "offense": "A",
                "defense": "B",
                "play_number": 2,
                "rush_attempt": 0,
                "pass_attempt": 1,
                "success": 1,
                "yards_gained": 0,
                "ppa": 0.0,
                "havoc": 0,
                "line_yards": 0.0,
                "second_level_yards": 0.0,
                "open_field_yards": 0.0,
                "is_power_situation": 0,
                "power_success_converted": 0,
                "st": 0,
                "thirddown_conversion": None,
            },
        ]
    )

    drives = pd.DataFrame(
        [
            {
                "game_id": 1,
                "drive_number": 1,
                "season": 2024,
                "week": 1,
                "offense": "A",
                "defense": "B",
                "is_eckel_drive": 1,
                "is_successful_drive": 1,
                "is_busted_drive": 0,
                "is_explosive_drive": 0,
                "points_on_opps": 7,
                "had_scoring_opportunity": 1,
                "start_yards_to_goal": 75,
            }
        ]
    )

    team_game = aggregate_team_game(plays, drives)
    # Expect two rows (one per team)
    assert set(team_game["team"]) == {"A", "B"}
    # Check some derived columns exist
    for col in ["off_sr", "off_ypp", "off_epa_pp"]:
        assert col in team_game.columns
