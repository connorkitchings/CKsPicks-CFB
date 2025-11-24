# Unit tests for Kelly sizing and confidence filters in weekly betting policy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from src.models.betting import apply_betting_policy


def test_apply_betting_policy_kelly_basic():
    # Construct a minimal DataFrame with strong edges and reasonable std-devs
    df = pd.DataFrame(
        [
            {
                "season": 2024,
                "week": 5,
                "id": 1,
                "home_team": "A",
                "away_team": "B",
                # Lines
                "home_team_spread_line": -3.0,  # home -3
                "total_line": 50.0,
                # Predictions
                "predicted_spread": 10.0,  # strong lean to home
                "predicted_total": 60.0,  # strong lean to over
                # Ensemble uncertainty
                "predicted_spread_std_dev": 2.0,
                "predicted_total_std_dev": 1.0,
                # Eligibility
                "home_games_played": 6,
                "away_games_played": 6,
            }
        ]
    )

    out = apply_betting_policy(
        df,
        spread_edge_threshold=5.0,
        total_edge_threshold=5.0,
        spread_std_dev_threshold=3.0,
        total_std_dev_threshold=1.5,
        min_games_played=4,
        fractional_kelly=0.25,
        kelly_cap=0.25,
        base_unit_fraction=0.02,
        single_bet_cap=0.05,
        bankroll=10000,
        max_weekly_exposure_fraction=0.15,
        max_weekly_bets=12,
    )

    row = out.iloc[0]
    # Bets should be selected
    assert row["bet_spread"] == "home"
    assert row["bet_total"] == "over"
    # Kelly fractions should be positive and capped
    assert 0 < row["kelly_fraction_spread"] <= 0.25 * 0.25
    assert 0 < row["kelly_fraction_total"] <= 0.25 * 0.25
    # Units should be positive numbers and respect the 5% single-bet cap (2.5u)
    assert 0 < row["bet_units_spread"] <= 2.5
    assert 0 < row["bet_units_total"] <= 2.5


def test_apply_betting_policy_confidence_filter_blocks():
    # Same scenario but extreme std-dev to fail confidence filter
    df = pd.DataFrame(
        [
            {
                "season": 2024,
                "week": 5,
                "id": 1,
                "home_team": "A",
                "away_team": "B",
                "home_team_spread_line": -3.0,
                "total_line": 50.0,
                "predicted_spread": 10.0,
                "predicted_total": 60.0,
                # Very large std devs
                "predicted_spread_std_dev": 20.0,
                "predicted_total_std_dev": 20.0,
                "home_games_played": 6,
                "away_games_played": 6,
            }
        ]
    )

    out = apply_betting_policy(
        df,
        spread_edge_threshold=5.0,
        total_edge_threshold=5.0,
        spread_std_dev_threshold=3.0,
        total_std_dev_threshold=1.5,
        min_games_played=4,
        bankroll=10000,
    )

    row = out.iloc[0]
    # No bets should be taken due to confidence filter
    assert row["bet_spread"] == "none"
    assert row["bet_total"] == "none"
    assert row.get("kelly_fraction_spread", 0) in (0, 0.0)
    assert row.get("kelly_fraction_total", 0) in (0, 0.0)
