"""A forecast covers the locked games; only a display-only live week may omit kicked-off ones."""

from __future__ import annotations

import pytest

from scripts.pipeline.build_v5_intended_update_forecasts import forecast_population


def test_the_whole_population_must_be_covered_exactly_once():
    assert forecast_population({1, 2, 3}, {1, 2}, {3}, set(), display_only=False) == {
        1,
        2,
        3,
    }
    with pytest.raises(ValueError, match="differ"):
        forecast_population({1, 2, 3}, {1, 2}, set(), set(), display_only=False)
    with pytest.raises(ValueError, match="differ"):
        forecast_population({1, 2}, {1, 2}, {2}, set(), display_only=False)


def test_kicked_off_games_may_be_omitted_only_in_display_only_mode():
    with pytest.raises(ValueError, match="display-only"):
        forecast_population({1, 2, 3}, {1}, {2}, {3}, display_only=False)
    assert forecast_population({1, 2, 3}, {1}, {2}, {3}, display_only=True) == {1, 2}


def test_the_omitted_set_must_be_exactly_the_games_without_a_feature_row():
    with pytest.raises(ValueError, match="differ"):
        forecast_population({1, 2, 3}, {1}, set(), {3}, display_only=True)
    with pytest.raises(ValueError, match="not in the locked"):
        forecast_population({1, 2}, {1, 2}, set(), {9}, display_only=True)
