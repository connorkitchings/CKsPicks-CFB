"""The provider's "kickoff time not announced" placeholder detector."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from scripts.ops.weekly_automation import is_placeholder_kickoff

UTC = timezone.utc


@pytest.mark.parametrize(
    "start",
    [
        datetime(2026, 11, 14, 5, 0, tzinfo=UTC),  # midnight EST (UTC-5)
        datetime(2026, 9, 12, 4, 0, tzinfo=UTC),  # midnight EDT (UTC-4)
    ],
)
def test_midnight_eastern_is_a_placeholder_in_standard_and_daylight_time(start):
    assert is_placeholder_kickoff(start) is True


@pytest.mark.parametrize(
    "start",
    [
        datetime(2026, 11, 14, 4, 0, tzinfo=UTC),  # 11 PM EST the night before
        datetime(2026, 9, 12, 5, 0, tzinfo=UTC),  # 1 AM EDT
        datetime(2026, 11, 14, 5, 30, tzinfo=UTC),  # 12:30 AM EST, a real late game
        datetime(2026, 11, 14, 17, 0, tzinfo=UTC),
    ],
)
def test_other_kickoff_times_are_not_placeholders(start):
    assert is_placeholder_kickoff(start) is False


def test_provider_flag_overrides_the_midnight_rule_in_both_directions():
    midnight = datetime(2026, 11, 14, 5, 0, tzinfo=UTC)
    afternoon = datetime(2026, 11, 14, 17, 0, tzinfo=UTC)

    assert is_placeholder_kickoff(midnight, tbd_flag=False) is False
    assert is_placeholder_kickoff(afternoon, tbd_flag=True) is True
