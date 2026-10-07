"""Extending the 2026 rebuild source lock by one completed week."""

from __future__ import annotations

import copy

import pandas as pd
import pytest

from cks_picks_cfb.rebuild import lock_extension as le

COLUMNS = [
    "week",
    "game_id",
    "start_date",
    "home_team",
    "away_team",
    "home_points",
    "away_points",
]
BASE = {
    "schema_version": "v5_intended_update_2026_source_lock_v1",
    "game_rows_sha256": "f" * 64,
    "games": {
        "columns": COLUMNS,
        "rows": [
            [0, 1, "2026-08-29T16:00:00Z", "A", "B", 10, 7],
            [1, 2, "2026-09-05T16:00:00Z", "C", "D", 21, 14],
            [2, 3, "2026-10-03T16:00:00Z", "E", "F", None, None],
            [2, 4, "2026-10-03T23:00:00Z", "G", "H", None, None],
        ],
    },
    "post_week_cutoffs": {"0": "2026-09-03T04:00:00Z", "1": "2026-09-13T04:00:00Z"},
    "research_2026_prediction_keys": {"completed_games": 2, "week2_games": 2},
}
OUTCOMES = {"dataset": "game_outcomes", "version_id": "v-new", "content_sha": "c" * 64}
CUTOFF = "2026-10-05T00:00:00Z"


def _finals(*rows):
    return pd.DataFrame(rows, columns=["game_id", "home_points", "away_points"])


def _extend(finals, cutoff=CUTOFF, base=BASE):
    return le.extend_lock(
        base,
        base_sha256="a" * 64,
        finals=finals,
        new_cutoff=cutoff,
        outcomes_ref=OUTCOMES,
    )


def test_adds_the_next_cutoff_and_the_new_finals_without_touching_earlier_rows():
    result = _extend(_finals((1, 10, 7), (2, 21, 14), (3, 30, 3), (4, 17, 20)))
    assert result["post_week_cutoffs"]["2"] == CUTOFF
    assert list(result["post_week_cutoffs"]) == ["0", "1", "2"]
    rows = {row[1]: row for row in result["games"]["rows"]}
    assert rows[3][5:] == [30, 3] and rows[4][5:] == [17, 20]
    assert rows[1][5:] == [10, 7] and rows[2][5:] == [21, 14]
    assert result["research_2026_prediction_keys"]["completed_games"] == 4
    ext = result["extends"]
    assert ext["added_post_week"] == 2 and ext["newly_final_game_ids"] == [3, 4]
    assert ext["completed_games_before"] == 2 and ext["completed_games_after"] == 4
    assert ext["base_game_rows_sha256"] == "f" * 64
    assert ext["game_rows_sha256"] == le.rows_sha256(result["games"]["rows"])
    assert (
        result["game_rows_sha256"] == "f" * 64
    )  # the base's own field stays untouched


def test_the_base_lock_is_not_mutated_and_the_result_is_deterministic():
    snapshot = copy.deepcopy(BASE)
    finals = _finals((3, 30, 3), (4, 17, 20))
    first, second = _extend(finals), _extend(finals)
    assert BASE == snapshot
    assert first == second


def test_a_changed_final_score_is_refused_not_overwritten():
    with pytest.raises(le.LockExtensionError, match="game 1"):
        _extend(_finals((1, 11, 7), (3, 30, 3)))


def test_a_final_that_is_not_yet_available_at_the_cutoff_is_refused():
    # Game 4 kicks off 2026-10-03T23:00Z; with a six-hour buffer it is available from 2026-10-04T05:00Z.
    with pytest.raises(le.LockExtensionError, match="not available"):
        _extend(_finals((3, 30, 3), (4, 17, 20)), cutoff="2026-10-04T04:00:00Z")


def test_the_new_cutoff_must_follow_the_last_one_and_there_must_be_something_new():
    with pytest.raises(le.LockExtensionError, match="after the last"):
        _extend(_finals((3, 30, 3)), cutoff="2026-09-13T04:00:00Z")
    with pytest.raises(le.LockExtensionError, match="nothing to extend"):
        _extend(_finals((1, 10, 7)))


def test_non_contiguous_cutoffs_and_repeated_extension_are_refused():
    gap = copy.deepcopy(BASE)
    gap["post_week_cutoffs"] = {
        "0": "2026-09-03T04:00:00Z",
        "2": "2026-09-13T04:00:00Z",
    }
    with pytest.raises(le.LockExtensionError, match="contiguous"):
        _extend(_finals((3, 30, 3)), base=gap)
    once = _extend(_finals((3, 30, 3), (4, 17, 20)))
    with pytest.raises(le.LockExtensionError, match="already an extension"):
        _extend(_finals((3, 30, 3)), base=once, cutoff="2026-10-12T00:00:00Z")


def test_games_without_a_final_stay_unrecorded():
    result = _extend(_finals((3, 30, 3)))
    rows = {row[1]: row for row in result["games"]["rows"]}
    assert rows[4][5:] == [None, None]
    assert result["research_2026_prediction_keys"]["completed_games"] == 3
