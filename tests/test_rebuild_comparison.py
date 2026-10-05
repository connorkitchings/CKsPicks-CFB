"""Step 5 comparison helpers: keyed differences and the bounded punt-flag effect."""

from __future__ import annotations

import pandas as pd

from cks_picks_cfb.rebuild import comparison

KEYS = comparison.POSSESSION_KEYS


def _possessions(eligible, ineligible, mixed=None, **extra):
    n = len(eligible)
    frame = pd.DataFrame(
        {
            "season": [2025] * n,
            "game_id": [1] * n,
            "drive_number": list(range(n)),
            "offense": ["A"] * n,
            "eligible_play_count": eligible,
            "ineligible_play_count": ineligible,
            "mixed_eligibility": mixed or [False] * n,
            "possession_eligible": [True] * n,
        }
    )
    for key, value in extra.items():
        frame[key] = value
    return frame


EVENTS = pd.DataFrame({"season": [2025], "game_id": [1], "score_increment": [7]})


def _effect(new, old, events_new=EVENTS, events_old=EVENTS):
    return comparison.punt_flag_effect(new, old, {"e": events_new}, {"e": events_old})


def test_keyed_differences_ignore_row_order():
    a = _possessions([3, 4], [0, 1])
    b = a.iloc[::-1].reset_index(drop=True)
    assert comparison.keyed_differences(a, b, KEYS)["differing_columns"] == {}


def test_punt_effect_accepts_bookkeeping_moves_only():
    old = _possessions([3, 4], [0, 0])
    new = _possessions([2, 4], [1, 0], mixed=[True, False])
    result = _effect(new, old)
    assert result["bounded"] and result["eligible_plays_moved"] == 1


def test_punt_effect_rejects_eligibility_or_event_changes():
    old = _possessions([3, 4], [0, 0])
    assert not _effect(
        _possessions([2, 4], [1, 0], possession_eligible=[False, True]), old
    )["bounded"]
    changed_events = EVENTS.assign(score_increment=[3])
    assert not _effect(old, old, changed_events, EVENTS)["bounded"]


def test_punt_effect_rejects_unconserved_or_increased_counts():
    old = _possessions([3, 4], [0, 0])
    assert not _effect(_possessions([2, 4], [0, 0]), old)["bounded"]
    assert not _effect(_possessions([4, 4], [0, 0]), old)["bounded"]


def test_punt_effect_rejects_different_possession_keys():
    old = _possessions([3, 4], [0, 0])
    assert not _effect(_possessions([3], [0]), old)["bounded"]
