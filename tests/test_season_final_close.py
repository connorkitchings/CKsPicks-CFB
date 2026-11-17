"""A final close (no next-week slate) passes the real prepare and verification."""

from __future__ import annotations

import pytest

from tests.season_fixtures import THROUGH_WEEK, build_season


@pytest.fixture(scope="module")
def final_close(tmp_path_factory):
    return build_season(tmp_path_factory.mktemp("final"), next_week=None)


def test_final_close_active_week_equals_through_week(final_close):
    identity = final_close["identity"]
    assert identity["active_week"] == identity["through_week"] == THROUGH_WEEK


def test_final_close_has_no_live_week_and_every_game_graded(final_close):
    predictions = final_close["frames"]["predictions"]
    grades = final_close["frames"]["grades"]
    assert set(predictions.week) == set(range(THROUGH_WEEK + 1))
    assert set(predictions.timing_class) == {"replay"}
    assert set(grades.game_id) == set(predictions.game_id)
