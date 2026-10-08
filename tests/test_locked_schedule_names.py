"""Serving keeps the provider's team names; ratings use the canonical ones."""

from __future__ import annotations

import pandas as pd

from cks_picks_cfb.rebuild.states_2026 import locked_schedule

GAMES = pd.DataFrame(
    {
        "game_id": [1, 2],
        "week": [6, 6],
        "kickoff_utc": ["2026-10-10T16:00:00Z", "2026-10-10T19:00:00Z"],
        "home_team": ["UTSA", "San José State"],
        "away_team": ["UConn", "Hawai'i"],
        "completed": [False, False],
    }
)
LOCK = {
    "games": {
        "columns": [
            "week",
            "game_id",
            "start_date",
            "home_team",
            "away_team",
            "home_points",
            "away_points",
        ],
        "rows": [
            [6, 1, "2026-10-10T16:00:00Z", "UTSA", "UConn", None, None],
            [6, 2, "2026-10-10T19:00:00Z", "San José State", "Hawai'i", None, None],
        ],
    }
}


def test_the_default_schedule_uses_canonical_names_for_ratings():
    schedule = locked_schedule(GAMES, LOCK)
    assert schedule["home_team"].tolist() == ["UT San Antonio", "San Jose State"]
    assert schedule["away_team"].tolist() == ["Connecticut", "Hawai_i"]


def test_the_serving_schedule_keeps_the_provider_names():
    schedule = locked_schedule(GAMES, LOCK, canonical=False)
    assert schedule["home_team"].tolist() == ["UTSA", "San José State"]
    assert schedule["away_team"].tolist() == ["UConn", "Hawai'i"]
