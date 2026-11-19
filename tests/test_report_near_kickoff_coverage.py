from datetime import datetime

import pandas as pd

from scripts.research.report_near_kickoff_coverage import slot_coverage


def test_slot_coverage_uses_future_games_on_eastern_capture_day():
    schedule = pd.DataFrame(
        {
            "game_id": [1, 2, 3, 4, 5, 6],
            "home_team": ["Home"] * 6,
            "away_team": ["Away"] * 6,
            "kickoff_utc": [
                "2026-11-18T22:30:00Z",
                "2026-11-19T00:30:00Z",
                "2026-11-19T01:30:00Z",
                "2026-11-19T02:30:00Z",
                "2026-11-19T03:30:00Z",
                "2026-11-19T23:30:00Z",
            ],
        }
    )
    quotes = pd.DataFrame(
        {
            "game_id": [1, 2, 2, 3, 5, 6],
            "spread": [-2.0, 0.0, None, -5.0, None, -1.5],
            "total": [52.0, None, 45.0, None, 54.0, 51.0],
        }
    )
    report = slot_coverage(
        schedule, quotes, datetime.fromisoformat("2026-11-18T22:30:00+00:00")
    )
    assert report["eligible_games"] == 4
    assert report["spread_games"] == 2
    assert report["total_games"] == 2
    assert report["both_targets_games"] == 1
    assert report["unmatched_game_ids"] == [4]
    assert [game["minutes_to_kickoff"] for game in report["games"]] == [
        120,
        180,
        240,
        300,
    ]


def test_slot_coverage_handles_missing_target_column():
    schedule = pd.DataFrame(
        {
            "game_id": [1],
            "home_team": ["Home"],
            "away_team": ["Away"],
            "kickoff_utc": ["2026-11-18T23:30:00Z"],
        }
    )
    quotes = pd.DataFrame({"game_id": [1], "spread": [1.0]})
    report = slot_coverage(
        schedule, quotes, datetime.fromisoformat("2026-11-18T22:30:00+00:00")
    )
    assert report["spread_games"] == 1
    assert report["total_games"] == 0
    assert report["unmatched_game_ids"] == []
