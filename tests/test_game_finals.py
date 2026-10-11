import pandas as pd
import pytest

from cks_picks_cfb.ops.game_finals import (
    GameFinalsError,
    apply_finals,
    plan_finals,
)


def _outcomes(rows):
    return pd.DataFrame(
        rows,
        columns=["season", "game_id", "completed", "home_points", "away_points"],
    )


def _stored(game_id, home=None, away=None):
    return {
        "game_id": game_id,
        "home_points": home,
        "away_points": away,
        "completion_state": None if home is None else "completed",
    }


class _Cursor:
    def __init__(self, rowcount=1):
        self.calls = []
        self.rowcount = rowcount

    def execute(self, sql, params=None):
        self.calls.append((sql, params))


def test_inserts_only_final_games_without_a_stored_result():
    outcomes = _outcomes(
        [
            (2026, 1, True, 24, 17),
            (2026, 2, False, None, None),
            (2026, 3, True, 10, 31),
        ]
    )
    plan = plan_finals(
        outcomes,
        [_stored(1), _stored(2), _stored(3, 10, 31), _stored(4)],
        season=2026,
        week=6,
    )
    assert plan.inserts == [{"game_id": 1, "home_points": 24, "away_points": 17}]
    assert plan.unchanged == [3]
    assert plan.not_final == [2]
    assert plan.missing_outcome == [4]
    assert not plan.conflicts


def test_a_different_stored_score_is_a_conflict_that_blocks_apply():
    plan = plan_finals(
        _outcomes([(2026, 1, True, 24, 17), (2026, 2, True, 3, 0)]),
        [_stored(1, 21, 17), _stored(2)],
        season=2026,
        week=6,
    )
    assert plan.conflicts == [{"game_id": 1, "stored": [21, 17], "certified": [24, 17]}]
    cursor = _Cursor()
    with pytest.raises(GameFinalsError):
        apply_finals(cursor, plan)
    assert cursor.calls == []


def test_apply_is_insert_only_and_idempotent_on_conflict_do_nothing():
    plan = plan_finals(
        _outcomes([(2026, 1, True, 24, 17)]), [_stored(1)], season=2026, week=6
    )
    cursor = _Cursor()
    assert apply_finals(cursor, plan) == 1
    sql, params = cursor.calls[0]
    assert "ON CONFLICT (game_id) DO NOTHING" in sql
    assert "spread_result" not in sql and "total_result" not in sql
    assert params == {"game_id": 1, "home_points": 24, "away_points": 17}
    # A rerun sees the stored row and plans nothing.
    rerun = plan_finals(
        _outcomes([(2026, 1, True, 24, 17)]),
        [_stored(1, 24, 17)],
        season=2026,
        week=6,
    )
    assert rerun.inserts == [] and rerun.unchanged == [1]


def test_other_seasons_are_ignored_and_duplicates_rejected():
    plan = plan_finals(
        _outcomes([(2025, 1, True, 7, 3)]), [_stored(1)], season=2026, week=6
    )
    assert plan.missing_outcome == [1]
    with pytest.raises(GameFinalsError):
        plan_finals(
            _outcomes([(2026, 1, True, 7, 3), (2026, 1, True, 7, 3)]),
            [_stored(1)],
            season=2026,
            week=6,
        )


def test_missing_columns_fail_closed():
    with pytest.raises(GameFinalsError):
        plan_finals(pd.DataFrame({"game_id": [1]}), [], season=2026, week=6)
