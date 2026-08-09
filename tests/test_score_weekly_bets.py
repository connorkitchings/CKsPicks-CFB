"""Unit tests for score_weekly_bets storage-backed score loading."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts" / "pipeline"
sys.path.insert(0, str(SCRIPTS_DIR))

import score_weekly_bets  # noqa: E402


class FakeStorage:
    def read_index(self, entity, filters):
        assert entity == "raw/games"
        assert filters == {"year": 2025}
        return [
            {
                "id": 1,
                "week": 15,
                "home_points": 28,
                "away_points": 24,
            },
            {
                "id": 2,
                "week": 15,
                "home_points": None,
                "away_points": None,
            },
            {
                "id": 3,
                "week": 16,
                "home_points": 31,
                "away_points": 30,
            },
        ]


def test_load_week_scores_uses_configured_storage(monkeypatch):
    monkeypatch.setattr(score_weekly_bets, "get_storage", lambda: FakeStorage())

    scores = score_weekly_bets.load_week_scores(2025, 15)

    expected = pd.DataFrame([{"id": 1, "home_points": 28.0, "away_points": 24.0}])
    pd.testing.assert_frame_equal(scores.reset_index(drop=True), expected)


def test_same_game_can_grade_differently_for_two_frozen_lines():
    scores = pd.DataFrame([{"id": 1, "home_points": 24, "away_points": 21}])
    common = {
        "game_id": 1,
        "Spread Bet": "Home",
        "Total Bet": "Under",
        "total_line": 50.0,
    }
    early = score_weekly_bets.score_bets(
        pd.DataFrame([{**common, "run_id": "early", "home_team_spread_line": -2.5}]),
        scores,
    )
    late = score_weekly_bets.score_bets(
        pd.DataFrame([{**common, "run_id": "late", "home_team_spread_line": -3.5}]),
        scores,
    )
    assert early.iloc[0]["Spread Bet Result"] == "Win"
    assert late.iloc[0]["Spread Bet Result"] == "Loss"
