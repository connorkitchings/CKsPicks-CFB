"""
Tests for the bet settling and scoring utilities in src/cfb_model/analysis/scoring.py.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import pytest

from scoring import settle_spread_bets, settle_total_bets


@pytest.fixture
def sample_bets_df() -> pd.DataFrame:
    """Provides a sample DataFrame containing bets and game outcomes."""
    data = {
        # Game 1: Home bet wins
        "game_id": [1, 2, 3, 4, 5, 6],
        "home_team_spread_line": [-3.5, 7.0, -10.0, -7.0, -3.0, 0.0],
        "total_line": [50.5, 48.0, 55.0, 52.0, 45.0, 0.0],
        "bet_spread": ["home", "away", "home", "away", "home", "none"],
        "bet_total": ["over", "under", "over", "under", "none", "over"],
        "home_points": [30, 20, 40, 21, 20, 30],
        "away_points": [20, 24, 30, 30, 23, 20],
    }
    return pd.DataFrame(data)


@pytest.fixture
def pending_bets_df() -> pd.DataFrame:
    """Provides a sample DataFrame with a game outcome missing."""
    data = {
        "game_id": [1],
        "home_team_spread_line": [-3.5],
        "total_line": [50.5],
        "bet_spread": ["home"],
        "bet_total": ["over"],
        "home_points": [None],  # Missing score
        "away_points": [None],
    }
    return pd.DataFrame(data)


# --- Tests for settle_spread_bets --- #


def test_settle_spread_home_win(sample_bets_df):
    result_df = settle_spread_bets(sample_bets_df)
    assert result_df.loc[0, "spread_bet_result"] == "Win"


def test_settle_spread_away_win(sample_bets_df):
    result_df = settle_spread_bets(sample_bets_df)
    assert result_df.loc[1, "spread_bet_result"] == "Loss"


def test_settle_spread_push(sample_bets_df):
    result_df = settle_spread_bets(sample_bets_df)
    assert result_df.loc[2, "spread_bet_result"] == "Push"


def test_settle_spread_loss(sample_bets_df):
    result_df = settle_spread_bets(sample_bets_df)
    assert result_df.loc[3, "spread_bet_result"] == "Win"


def test_settle_spread_no_bet(sample_bets_df):
    result_df = settle_spread_bets(sample_bets_df)
    assert result_df.loc[5, "spread_bet_result"] == "No Bet"


def test_settle_spread_pending(pending_bets_df):
    result_df = settle_spread_bets(pending_bets_df)
    assert result_df.loc[0, "spread_bet_result"] == "Pending"


# --- Tests for settle_total_bets --- #


def test_settle_total_over_win(sample_bets_df):
    result_df = settle_total_bets(sample_bets_df)
    assert result_df.loc[0, "total_bet_result"] == "Loss"


def test_settle_total_under_win(sample_bets_df):
    result_df = settle_total_bets(sample_bets_df)
    assert result_df.loc[1, "total_bet_result"] == "Win"


def test_settle_total_push(sample_bets_df):
    # Game with total 50 vs line 50
    df = sample_bets_df.copy()
    df.loc[1, "total_line"] = 44.0
    result_df = settle_total_bets(df)
    assert result_df.loc[1, "total_bet_result"] == "Push"


def test_settle_total_loss(sample_bets_df):
    result_df = settle_total_bets(sample_bets_df)
    assert result_df.loc[2, "total_bet_result"] == "Win"


def test_settle_total_no_bet(sample_bets_df):
    result_df = settle_total_bets(sample_bets_df)
    assert result_df.loc[4, "total_bet_result"] == "No Bet"


def test_settle_total_pending(pending_bets_df):
    result_df = settle_total_bets(pending_bets_df)
    assert result_df.loc[0, "total_bet_result"] == "Pending"