"""Shared play order and the unresolved-play rule (contract 2026-10-09/01, Task 3)."""

import pandas as pd
import pytest

from cks_picks_cfb.data.play_order import (
    FLAG_COLUMN,
    PLAY_ORDER_KEYS,
    REASON_COLUMN,
    PlayOrderError,
    flag_unresolved_plays,
    order_plays,
    tie_groups,
    unresolved_play_keys,
)


def frame(rows):
    columns = [
        "season",
        "game_id",
        "quarter",
        "drive_number",
        "play_number",
        "source_play_id",
    ]
    return pd.DataFrame(rows, columns=columns)


def test_order_is_period_then_drive_then_play_and_ignores_provider_ids():
    plays = frame(
        [
            (2025, 9, 5, 18, 1, "-22405"),  # overtime restarts the drive number
            (2025, 9, 4, 18, 2, "900"),
            (2025, 9, 4, 18, 1, "800"),
            (2025, 9, 4, 3, 1, "999999999999999999"),
        ]
    )
    assert order_plays(plays)["source_play_id"].tolist() == [
        "999999999999999999",
        "800",
        "900",
        "-22405",
    ]
    assert PLAY_ORDER_KEYS == (
        "season",
        "game_id",
        "quarter",
        "drive_number",
        "play_number",
    )


def test_order_does_not_convert_or_reorder_equal_keys():
    plays = frame(
        [(2025, 9, 1, 5, 6, "b"), (2025, 9, 1, 5, 6, "a"), (2025, 9, 1, 5, 5, "c")]
    )
    assert order_plays(plays)["source_play_id"].tolist() == ["c", "b", "a"]  # stable
    assert plays["source_play_id"].tolist() == ["b", "a", "c"]  # input untouched


def test_requires_the_ordering_columns():
    with pytest.raises(PlayOrderError, match="ordering columns"):
        order_plays(pd.DataFrame({"game_id": [1]}))


def test_same_second_plays_and_clock_reversals_are_never_flagged():
    """The clock is not an input: only the sequence and provider IDs are looked at."""
    plays = frame([(2025, 9, 1, 5, n, str(n)) for n in range(1, 6)]).assign(
        clock_seconds=[45, 45, 39, 45, 0]  # same second, then a replay-review reset
    )
    assert not flag_unresolved_plays(plays)[FLAG_COLUMN].any()


def test_a_cross_period_collision_is_resolved_by_the_period():
    plays = frame(
        [(2025, 9, 4, 18, 1, "401762831104868701"), (2025, 9, 5, 18, 1, "-22405")]
    )
    flags = flag_unresolved_plays(plays)
    assert not flags[FLAG_COLUMN].any() and flags[REASON_COLUMN].isna().all()
    assert tie_groups(plays) == []


def test_distinct_ids_tied_in_one_period_are_unresolved():
    plays = frame(
        [
            (2021, 1, 1, 5, 5, "-216"),
            (2021, 1, 1, 5, 6, "-217"),
            (2021, 1, 1, 5, 6, "-218"),
            (2021, 1, 1, 5, 7, "-219"),
        ]
    )
    flags = flag_unresolved_plays(plays)
    assert flags[FLAG_COLUMN].tolist() == [False, True, True, False]
    assert flags[REASON_COLUMN].tolist() == [
        None,
        "tied_sequence",
        "tied_sequence",
        None,
    ]
    groups = tie_groups(plays)
    assert len(groups) == 1 and list(groups[0]) == [1, 2]


def test_a_missing_period_is_unresolved_and_wins_over_a_tie():
    plays = frame(
        [
            (2025, 9, 0, 9, 1, "1"),  # byplay encodes a missing quarter as 0
            (
                2025,
                9,
                0,
                9,
                1,
                "2",
            ),  # also a tie, but the missing period takes precedence
            (2025, 9, 2, 9, 1, "3"),
        ]
    )
    plays.loc[2, "quarter"] = None
    flags = flag_unresolved_plays(plays)
    assert flags[FLAG_COLUMN].tolist() == [True, True, True]
    assert set(flags[REASON_COLUMN]) == {"missing_period"}


def test_frames_without_provider_ids_can_only_have_a_missing_period():
    v1 = frame([(2025, 9, 1, 1, 1, "x"), (2025, 9, 0, 1, 2, "y")]).drop(
        columns="source_play_id"
    )
    flags = flag_unresolved_plays(v1)
    assert flags[REASON_COLUMN].tolist() == [None, "missing_period"]
    duplicated = pd.concat([v1.iloc[:1], v1.iloc[:1]], ignore_index=True)
    with pytest.raises(PlayOrderError, match="unique on its sequence"):
        flag_unresolved_plays(duplicated)


def test_unresolved_keys_are_disclosed_sorted_with_group_size():
    plays = frame(
        [
            (2025, 9, 5, 24, 1, "401756916105000001"),
            (2025, 9, 5, 24, 1, "-22421"),
            (2025, 9, 5, 23, 1, "-22415"),
            (2025, 9, 5, 23, 1, "401756916105000002"),
            (2025, 9, 1, 1, 1, "ok"),
        ]
    )
    keys = unresolved_play_keys(plays)
    assert [(k["drive_number"], k["source_play_id"]) for k in keys] == [
        (23, "-22415"),
        (23, "401756916105000002"),
        (24, "-22421"),
        (24, "401756916105000001"),
    ]
    assert {k["reason"] for k in keys} == {"tied_sequence"}
    assert {k["group_size"] for k in keys} == {2}
    assert all(isinstance(k["game_id"], int) for k in keys)
    assert unresolved_play_keys(plays.iloc[4:]) == []


def test_score_stream_check_is_period_first_only_for_v2_frames():
    """Drive numbers restart in period 2, so a drive-first order sees the score fall."""
    from cks_picks_cfb.quality.silver import score_stream_regressions

    rows = [
        # period 1: drive 8 ends 14-0, then period 2 restarts the drive number at 2
        dict(
            game_id=1,
            quarter=1,
            drive_number=8,
            play_number=1,
            offense="A",
            defense="B",
            offense_score=7,
            defense_score=0,
        ),
        dict(
            game_id=1,
            quarter=1,
            drive_number=8,
            play_number=2,
            offense="A",
            defense="B",
            offense_score=14,
            defense_score=0,
        ),
        dict(
            game_id=1,
            quarter=2,
            drive_number=2,
            play_number=1,
            offense="B",
            defense="A",
            offense_score=0,
            defense_score=14,
        ),
        dict(
            game_id=1,
            quarter=2,
            drive_number=2,
            play_number=2,
            offense="B",
            defense="A",
            offense_score=3,
            defense_score=14,
        ),
    ]
    v1 = pd.DataFrame(rows)
    v2 = v1.assign(source_play_id=["1", "2", "3", "4"])
    assert (
        score_stream_regressions(v1)["regressed"] == 2
    )  # drive-first: a false regression
    assert score_stream_regressions(v2)["regressed"] == 0  # period-first: coherent
