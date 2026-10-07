"""Point-in-time reconciliation: games that kicked off after the cutoff are out of scope."""

from __future__ import annotations

import pandas as pd
import pytest

from cks_picks_cfb.data.reconciliation import (
    ReconciliationError,
    exclude_games_after_cutoff,
    reconcile_completed_games,
    require_reconciled,
)

CUTOFF = "2026-10-05T00:00:00Z"


def _schedule() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "season": 2026,
                "game_id": 1,
                "home_team": "A",
                "away_team": "B",
                "completed": True,
                "start_date": "2026-10-03T23:00:00Z",
            },
            {
                # Provider already reports this later game as completed (Troy, Week 6).
                "season": 2026,
                "game_id": 2,
                "home_team": "C",
                "away_team": "D",
                "completed": True,
                "start_date": "2026-10-07T00:00:00Z",
            },
        ]
    )


def _team_game_for_game_one() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"game_id": 1, "team": "A", "points": 10},
            {"game_id": 1, "team": "B", "points": 7},
        ]
    )


def test_later_games_are_marked_not_completed_without_dropping_rows():
    schedule = _schedule()
    result, excluded = exclude_games_after_cutoff(schedule, CUTOFF)
    assert excluded == [2]
    assert len(result) == len(schedule)
    assert result.set_index("game_id")["completed"].to_dict() == {1: True, 2: False}
    # The input is not mutated.
    assert schedule["completed"].tolist() == [True, True]


def test_the_availability_buffer_decides_a_game_that_started_before_the_cutoff():
    schedule = pd.DataFrame(
        [
            {
                "game_id": 10,
                "completed": True,
                "start_date": "2026-10-04T18:00:00Z",  # exactly six hours before
            },
            {
                "game_id": 11,
                "completed": True,
                "start_date": "2026-10-04T19:00:00Z",  # five hours: not yet available
            },
        ]
    )
    result, excluded = exclude_games_after_cutoff(schedule, CUTOFF)
    assert excluded == [11]
    assert result.set_index("game_id")["completed"].to_dict() == {10: True, 11: False}


def test_missing_kickoffs_and_incomplete_games_are_left_alone():
    schedule = pd.DataFrame(
        [
            {"game_id": 1, "completed": True, "start_date": None},
            {"game_id": 2, "completed": False, "start_date": "2026-10-09T00:00:00Z"},
        ]
    )
    result, excluded = exclude_games_after_cutoff(schedule, CUTOFF)
    assert excluded == []
    assert result["completed"].tolist() == [True, False]
    no_column, none_excluded = exclude_games_after_cutoff(
        schedule.drop(columns=["start_date"]), CUTOFF
    )
    assert none_excluded == [] and len(no_column) == 2


def test_naive_and_aware_cutoffs_agree():
    aware, a = exclude_games_after_cutoff(_schedule(), CUTOFF)
    naive, b = exclude_games_after_cutoff(_schedule(), "2026-10-05T00:00:00")
    assert a == b == [2]
    assert aware["completed"].tolist() == naive["completed"].tolist()


def test_without_the_exclusion_the_reconciliation_blocks_on_the_later_game():
    team_game = _team_game_for_game_one()
    blocked = reconcile_completed_games(_schedule(), team_game)
    with pytest.raises(ReconciliationError, match=r"\[2\]"):
        require_reconciled(blocked)

    adjusted, _ = exclude_games_after_cutoff(_schedule(), CUTOFF)
    reconciled = reconcile_completed_games(adjusted, team_game)
    require_reconciled(reconciled)
    assert reconciled["game_id"].tolist() == [1]


def test_a_missing_game_that_is_inside_the_cutoff_still_blocks():
    adjusted, _ = exclude_games_after_cutoff(_schedule(), CUTOFF)
    empty = _team_game_for_game_one().iloc[0:0]
    with pytest.raises(ReconciliationError, match=r"\[1\]"):
        require_reconciled(reconcile_completed_games(adjusted, empty))
