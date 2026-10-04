from datetime import datetime, timezone

import pytest

from cks_picks_cfb.data.market_integrity import (
    SNAPSHOT_FIELDS,
    SNAPSHOT_POLICY,
    snapshot_identity,
    snapshot_payload,
    verify_snapshot,
)


def record():
    return {
        "market_snapshot_id": "snapshot",
        "game_id": 1,
        "market_captured_at": datetime(2026, 10, 1, tzinfo=timezone.utc),
        "home_team_spread_line": -4.0,
        "total_line": 51.0,
        "canonical_spread_line": -3.0,
        "canonical_total_line": 50.0,
        "spread_selection_rule": "median",
        "total_selection_rule": "median",
        "spread_provider_count": 2,
        "total_provider_count": 2,
        "source_quote_ids": '["b", "a"]',
        "market_policy_version": SNAPSHOT_POLICY,
    }


class Cursor:
    def __init__(self, payload):
        self.payload = payload

    def execute(self, *_):
        pass

    def fetchone(self):
        return tuple(self.payload[key] for key in SNAPSHOT_FIELDS)


def test_identity_is_canonical_and_run_independent():
    original = record()
    altered = {
        **original,
        "run_id": "new",
        "home_team_spread_line": -5.0,
        "source_quote_ids": '["a", "b"]',
    }
    assert snapshot_identity(original) == snapshot_identity(altered)
    assert snapshot_identity(original) != snapshot_identity(
        {**original, "canonical_spread_line": -2.0}
    )
    assert snapshot_payload(original)["spread"] == -3.0


def test_identical_retry_accepts_but_conflicting_identity_fails():
    value = record()
    verify_snapshot(Cursor(snapshot_payload(value)), value)
    conflicting = {**snapshot_payload(value), "spread": -5.0}
    with pytest.raises(ValueError, match="conflicting immutable"):
        verify_snapshot(Cursor(conflicting), value)
