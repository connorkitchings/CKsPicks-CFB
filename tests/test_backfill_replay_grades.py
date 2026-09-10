"""Tests for the replay grade backfill (frozen-line lean grading)."""

from scripts.pipeline.backfill_replay_grades import spread_result, total_result


def test_spread_result_home_cover():
    assert spread_result(31, 7, -14.0, "home") == "win"
    assert spread_result(31, 7, -14.0, "away") == "loss"


def test_spread_result_away_cover():
    assert spread_result(21, 24, -3.0, "home") == "loss"
    assert spread_result(21, 24, -3.0, "away") == "win"


def test_spread_result_push_and_ungradable():
    assert spread_result(24, 21, -3.0, "home") == "push"
    assert spread_result(24, 21, -3.0, None) is None
    assert spread_result(24, 21, None, "home") is None
    assert spread_result(None, 21, -3.0, "home") is None


def test_spread_result_texas_san_jose_state():
    # Texas 38, San Jose State 7, line Texas -36.75, lean away.
    assert spread_result(38, 7, -36.75, "away") == "win"


def test_total_result_over_under():
    assert total_result(21, 24, 51.0, "under") == "win"
    assert total_result(21, 24, 51.0, "over") == "loss"
    assert total_result(31, 30, 50.5, "over") == "win"
    assert total_result(24, 21, 45.0, "under") == "push"


def test_total_result_ungradable():
    assert total_result(21, 24, 51.0, None) is None
    assert total_result(21, 24, None, "over") is None
    assert total_result(None, 24, 51.0, "over") is None


def test_total_result_texas_san_jose_state():
    # Actual total 45 vs line 52.5, lean over.
    assert total_result(38, 7, 52.5, "over") == "loss"
