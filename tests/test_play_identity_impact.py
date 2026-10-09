import numpy as np
import pandas as pd
import pytest

from scripts.analysis.play_identity_impact import (
    SEQ,
    classify_collision,
    diff_frames,
    drive_identity_reuse,
    legacy_dedup,
    order_diagnostics,
    remap_source_tokens,
    shadow_retained,
    source_play_ids,
)


def plays(rows):
    columns = [
        "game_id",
        "period",
        "drive_number",
        "play_number",
        "play_id",
        "drive_id",
        "clock_minutes",
        "clock_seconds",
        "offense",
    ]
    return pd.DataFrame(rows, columns=columns)


def test_source_play_ids_are_exact_strings():
    series = pd.Series([-22405, 401762831104868701], dtype="int64")
    assert source_play_ids(series).tolist() == ["-22405", "401762831104868701"]
    as_text = pd.Series(["-22405", " 401762831104868701 "], dtype=object)
    assert source_play_ids(as_text).tolist() == ["-22405", "401762831104868701"]


@pytest.mark.parametrize(
    "values",
    [
        pd.Series([1.0, 2.0]),
        pd.Series([1, None], dtype="Int64"),
        pd.Series([1, 2.5], dtype=object),
    ],
)
def test_source_play_ids_reject_float_and_missing(values):
    with pytest.raises(ValueError):
        source_play_ids(values)


def test_same_second_plays_are_kept_and_reversals_are_only_counted():
    frame = plays(
        [
            # incomplete pass, penalty and spike all at 10:45, then a replay-review reset
            (1, 1, 1, 1, 10, 100, 10, 45, "A"),
            (1, 1, 1, 2, 11, 100, 10, 45, "A"),
            (1, 1, 1, 3, 12, 100, 10, 39, "A"),
            (1, 1, 1, 4, 13, 100, 10, 45, "A"),  # clock restored by 6 seconds
            (1, 1, 2, 1, 14, 101, 9, 0, "B"),
        ]
    )
    report = order_diagnostics(frame)
    assert report["unresolved"] == []
    clock = report["clock"]
    assert clock["pairs_compared"] == 4
    assert clock["same_second_pairs"] == 1
    assert clock["reversals"] == 1
    assert clock["reversals_by_size"] == {"le_10s": 1, "s11_to_60": 0, "gt_60s": 0}
    assert clock["largest_reversals"][0]["seconds_back"] == 6


def test_reversal_sizes_are_bucketed():
    rows = [
        (1, 1, 1, i + 1, 100 + i, 7, m, s, "A")
        for i, (m, s) in enumerate([(10, 0), (10, 30), (10, 0), (12, 0), (11, 0)])
    ]
    sizes = order_diagnostics(plays(rows))["clock"]["reversals_by_size"]
    assert sizes == {"le_10s": 0, "s11_to_60": 1, "gt_60s": 1}


def test_same_period_tie_with_distinct_ids_is_unresolved():
    frame = plays(
        [
            (5, 1, 5, 6, -217, -26, 3, 41, "A"),
            (5, 1, 5, 6, -218, -26, 3, 10, "A"),
            (5, 1, 5, 7, -219, -26, 2, 50, "A"),
        ]
    )
    unresolved = order_diagnostics(frame)["unresolved"]
    assert [u["source_play_id"] for u in unresolved] == ["-217", "-218"]
    assert {u["reason"] for u in unresolved} == {"tied_sequence"}


def test_cross_period_reuse_of_a_sequence_is_not_unresolved():
    frame = plays(
        [
            (9, 4, 18, 1, 401762831104868701, 40176283118, 13, 12, "Buffalo"),
            (9, 5, 18, 1, -22405, -2885, 0, 0, "Eastern Michigan"),
        ]
    )
    report = order_diagnostics(frame)
    assert report["unresolved"] == []
    assert report["clock"]["pairs_compared"] == 0  # overtime has no clock census


def test_missing_period_is_unresolved():
    frame = plays([(9, np.nan, 1, 1, 5, 1, 10, 0, "A"), (9, 1, 1, 2, 6, 1, 9, 0, "A")])
    unresolved = order_diagnostics(frame)["unresolved"]
    assert [(u["source_play_id"], u["reason"]) for u in unresolved] == [
        ("5", "missing_period")
    ]


def test_classify_collision_cross_and_same_period():
    key = {"season": 2025, "game_id": 9, "drive_number": 18, "play_number": 1}
    cross = plays(
        [
            (9, 4, 18, 1, 401762831104868701, 40176283118, 13, 12, "Buffalo"),
            (9, 5, 18, 1, -22405, -2885, 0, 0, "Eastern Michigan"),
        ]
    )
    result = classify_collision(cross, key)
    assert result["class"] == "cross_period"
    assert result["unresolved_under_rule"] is False
    assert result["distinct_provider_drives"] is True
    assert result["source_play_ids"] == ["401762831104868701", "-22405"]

    same = plays(
        [(9, 1, 5, 6, -217, -26, 3, 41, "A"), (9, 1, 5, 6, -218, -26, 3, 10, "A")]
    )
    result = classify_collision(same, {**key, "drive_number": 5, "play_number": 6})
    assert result["class"] == "same_period"
    assert result["unresolved_under_rule"] is True
    assert result["clock_distinguishes"] is True
    assert result["clock_order_matches_row_order"] is True


def test_legacy_dedup_keeps_first_row_at_a_sequence():
    frame = plays(
        [
            (9, 5, 18, 1, -22405, -2885, 0, 0, "EMU"),
            (9, 4, 18, 1, 401762831104868701, 40176283118, 13, 12, "Buffalo"),
        ]
    )
    kept = legacy_dedup(frame)
    assert kept["play_id"].tolist() == [-22405]


def test_shadow_retained_keeps_every_play_with_unique_sequences():
    frame = plays(
        [
            (9, 4, 18, 1, 401762831104868701, 40176283118, 13, 12, "Buffalo"),
            (9, 4, 18, 2, 401762831104874702, 40176283118, 12, 52, "Buffalo"),
            (9, 5, 18, 1, -22405, -2885, 0, 0, "EMU"),
            (9, 5, 18, 2, -22406, -2885, 0, 0, "EMU"),
            (9, 5, 19, 1, -22407, -2886, 0, 0, "Buffalo"),
        ]
    )
    shadow = shadow_retained(frame)
    assert len(shadow) == len(frame)
    assert not shadow.duplicated(SEQ).any()
    assert sorted(shadow["play_id"]) == sorted(frame["play_id"])
    # the regulation drive keeps its number; the overtime drive is moved above the maximum
    by_id = shadow.set_index("play_id")["drive_number"]
    assert by_id[401762831104868701] == 18
    assert by_id[-22405] > 19
    assert by_id[-22405] == by_id[-22406]
    # inputs are not modified
    assert frame["drive_number"].tolist() == [18, 18, 18, 18, 19]


def test_shadow_retained_renumbers_a_drive_with_repeated_play_numbers():
    frame = plays(
        [
            (2, 1, 5, 5, -216, -26, 4, 0, "A"),
            (2, 1, 5, 6, -217, -26, 3, 41, "A"),
            (2, 1, 5, 6, -218, -26, 3, 10, "A"),
        ]
    )
    shadow = shadow_retained(frame)
    assert shadow.sort_values("play_number")["play_id"].tolist() == [-216, -217, -218]
    assert shadow["play_number"].tolist() == [1, 2, 3]


def test_drive_identity_reuse_counts_games_without_a_known_collision():
    frame = plays(
        [
            (1, 4, 3, 1, 10, 301, 5, 0, "A"),
            (1, 5, 3, 1, 11, -9, 0, 0, "B"),
            (2, 4, 3, 1, 12, 401, 5, 0, "A"),
            (2, 5, 4, 1, 13, -10, 0, 0, "B"),
        ]
    )
    report = drive_identity_reuse(frame, collision_games={1})
    assert report["reused_drive_numbers"] == 1
    assert report["games_without_known_collision"] == []
    report = drive_identity_reuse(frame, collision_games=set())
    assert report["games_without_known_collision"] == [1]


def test_diff_frames_reports_one_sided_keys_and_changed_cells():
    left = pd.DataFrame({"k": [1, 2, 3], "v": [1.0, 2.0, np.nan], "s": ["a", "b", "c"]})
    right = pd.DataFrame(
        {"k": [2, 3, 4], "v": [2.5, np.nan, 9.0], "s": ["b", "c", "d"]}
    )
    diff = diff_frames(left, right, ["k"])
    assert diff["only_historical"] == [[1]]
    assert diff["only_retained"] == [[4]]
    assert [(c["key"], c["column"]) for c in diff["changed_cells"]] == [([2], "v")]


def test_remap_source_tokens_rewrites_ids_in_source_columns_only():
    frame = pd.DataFrame(
        {
            "source_play_ids": ['["2025:9:18:1", "2025:9:18:2"]'],
            "note": ["2025:9:18:1"],
        }
    )
    lookup = {"2025:9:18:1": "401762831104868701", "2025:9:18:2": "-22405"}
    out = remap_source_tokens(frame, lookup)
    assert out.loc[0, "source_play_ids"] == '["401762831104868701", "-22405"]'
    assert out.loc[0, "note"] == "2025:9:18:1"


def test_reversal_census_reports_negative_id_involvement_and_games():
    rows = [
        (1, 1, 1, 1, -5, 7, 10, 0, "A"),
        (1, 1, 1, 2, -6, 7, 12, 0, "A"),  # 120 s back, negative IDs
        (2, 1, 1, 1, 500, 8, 10, 0, "A"),
        (2, 1, 1, 2, 501, 8, 10, 5, "A"),  # 5 s back, positive IDs
    ]
    clock = order_diagnostics(plays(rows))["clock"]
    assert clock["reversals"] == 2
    assert clock["reversals_involving_negative_id"] == 1
    assert clock["reversals_over_60s_involving_negative_id"] == 1
    assert clock["games_with_reversal"] == 2


def test_impossible_clock_values_are_split_from_valid_reversals():
    rows = [
        (1, 1, 1, 1, 10, 7, 10, 0, "A"),
        (1, 1, 1, 2, 11, 7, 58, 0, "A"),  # 58:00 cannot occur in a 15-minute period
        (1, 1, 1, 3, 12, 7, 9, 0, "A"),
        (1, 1, 1, 4, 13, 7, 9, 30, "A"),  # a real 30-second reversal
    ]
    clock = order_diagnostics(plays(rows))["clock"]
    assert clock["impossible_clock_rows"] == 1
    assert clock["reversals"] == 2  # 10:00 -> 58:00 and 9:00 -> 9:30
    assert clock["reversals_with_impossible_clock"] == 1
    assert clock["valid_clock_reversals"] == 1
    assert clock["valid_clock_reversals_by_size"]["s11_to_60"] == 1


def test_reversal_to_a_full_period_clock_is_counted_separately():
    rows = [
        (1, 1, 3, 10, 20, 7, 0, 30, "A"),
        (1, 1, 3, 11, 21, 7, 0, 0, "A"),
        (
            1,
            1,
            4,
            1,
            22,
            8,
            15,
            0,
            "A",
        ),  # next period's kickoff under this period's label
        (1, 1, 4, 2, 23, 8, 14, 0, "A"),
        (1, 1, 4, 3, 24, 8, 14, 50, "A"),  # 50 s back, not a period reset
    ]
    clock = order_diagnostics(plays(rows))["clock"]
    assert clock["valid_reversals_to_full_period_clock"] == 1
    assert clock["valid_reversals_over_60s_not_to_full_period_clock"] == 0
    assert clock["valid_clock_reversals_by_size"]["s11_to_60"] == 1
