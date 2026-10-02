"""Play filters: the V5 legacy filter vs the scrimmage filter team stats uses."""

from __future__ import annotations

import pandas as pd
import pytest

from cks_picks_cfb.data.play_filters import (
    eligible_possession_play_mask,
    kicking_play_mask,
    scrimmage_play_mask,
)
from cks_picks_cfb.ratings import possession_measurements as v5


def frame(*play_types, **overrides):
    base = {"quarter": 1, "st": 0, "penalty": 0, "twopoint": 0, "garbage": 0}
    base.update(overrides)
    return pd.DataFrame([{**base, "play_type": t} for t in play_types])


def test_scrimmage_mask_drops_returned_punts_the_legacy_mask_keeps():
    df = frame("Rush", "Pass Reception", "Punt Return", "Sack")
    assert eligible_possession_play_mask(df).tolist() == [True] * 4
    assert scrimmage_play_mask(df).tolist() == [True, True, False, True]


@pytest.mark.parametrize(
    "play_type",
    [
        "Punt Return",
        "Punt",
        "Punt Return Touchdown",
        "Kickoff",
        "Field Goal Good",
        "Extra Point Good",
    ],
)
def test_kicking_plays_are_recognised(play_type):
    assert kicking_play_mask(pd.Series([play_type])).tolist() == [True]


@pytest.mark.parametrize(
    "play_type",
    [
        "Rush",
        "Pass Reception",
        "Pass Incompletion",
        "Sack",
        "Interception",
        "Fumble Recovery (Own)",
        "Safety",
    ],
)
def test_scrimmage_plays_are_not_kicking_plays(play_type):
    assert kicking_play_mask(pd.Series([play_type])).tolist() == [False]


def test_scrimmage_mask_keeps_every_legacy_exclusion():
    for overrides in (
        {"quarter": 5},
        {"st": 1},
        {"penalty": 1},
        {"twopoint": 1},
        {"garbage": 1},
    ):
        assert scrimmage_play_mask(frame("Rush", **overrides)).tolist() == [False], (
            overrides
        )
    assert scrimmage_play_mask(frame("Timeout")).tolist() == [False]


def test_v5_measurements_still_use_the_legacy_definition():
    df = frame("Rush", "Punt Return", "Timeout")
    assert v5.eligible_possession_play_mask(df).tolist() == [True, True, False]
    assert v5.eligible_possession_play is v5._eligible_play
