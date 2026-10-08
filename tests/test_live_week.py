"""Which games a live (forward) week can forecast: only those that have not kicked off."""

from __future__ import annotations

import pandas as pd
import pytest

from cks_picks_cfb.rebuild.errors import GateError
from cks_picks_cfb.rebuild.live_week import kicked_off_game_ids

SCHEDULE = pd.DataFrame(
    {
        "week": [6, 6, 6, 5],
        "game_id": [1, 2, 3, 9],
        "kickoff_utc": [
            "2026-10-07T00:00:00Z",
            "2026-10-08T23:00:00Z",
            "2026-10-10T16:00:00Z",
            "2026-10-01T00:00:00Z",
        ],
    }
)


def test_games_at_or_before_as_of_are_listed_and_later_ones_are_not():
    assert kicked_off_game_ids(SCHEDULE, 6, "2026-10-08T23:00:00Z") == [1, 2]
    assert kicked_off_game_ids(SCHEDULE, 6, "2026-10-08T22:59:59Z") == [1]
    assert kicked_off_game_ids(SCHEDULE, 6, "2026-10-06T00:00:00Z") == []


def test_other_weeks_are_never_listed():
    assert 9 not in kicked_off_game_ids(SCHEDULE, 6, "2026-12-31T00:00:00Z")


def test_an_as_of_without_a_timezone_is_refused():
    with pytest.raises(GateError, match="timezone-aware"):
        kicked_off_game_ids(SCHEDULE, 6, "2026-10-08T23:00:00")
