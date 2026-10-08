"""Corrected live serving: the display-only partition and the publication window."""

from __future__ import annotations

import pandas as pd
import pytest

from scripts.pipeline.build_v5_corrected_live_serving import (
    apply_window_open,
    live_week,
    receipt_uri,
    run_uris,
    serving_slate,
)

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
CUTOFF = pd.Timestamp("2026-10-08T12:00:00Z")


def test_without_display_only_any_kicked_off_game_is_an_error():
    with pytest.raises(ValueError, match="display-only run is required"):
        serving_slate(SCHEDULE, 6, CUTOFF, display_only=False)


def test_a_week_with_no_kickoffs_yet_is_served_whole_either_way():
    early = pd.Timestamp("2026-10-06T00:00:00Z")
    slate, kicked = serving_slate(SCHEDULE, 6, early, display_only=False)
    assert kicked == [] and slate["game_id"].tolist() == [1, 2, 3]


def test_display_only_serves_exactly_the_games_ahead_of_the_cutoff():
    slate, kicked = serving_slate(SCHEDULE, 6, CUTOFF, display_only=True)
    assert kicked == [1]
    assert slate["game_id"].tolist() == [2, 3]
    # A game exactly at the cutoff counts as kicked off.
    slate, kicked = serving_slate(
        SCHEDULE, 6, pd.Timestamp("2026-10-08T23:00:00Z"), display_only=True
    )
    assert kicked == [1, 2] and slate["game_id"].tolist() == [3]


def test_a_prospective_manifest_is_publishable_only_before_its_first_kickoff():
    manifest = {
        "data_as_of": "2026-10-08T12:00:00+00:00",
        "first_included_kickoff_utc": "2026-10-08T23:00:00+00:00",
    }
    before = pd.Timestamp("2026-10-08T22:59:00Z")
    after = pd.Timestamp("2026-10-08T23:00:00Z")
    assert apply_window_open(manifest, now=before, display_only=False)
    assert not apply_window_open(manifest, now=after, display_only=False)


def test_a_display_only_manifest_must_be_recent_and_not_from_the_future():
    manifest = {
        "data_as_of": "2026-10-08T12:00:00+00:00",
        "first_included_kickoff_utc": "2026-10-08T23:00:00+00:00",
    }
    assert apply_window_open(
        manifest, now=pd.Timestamp("2026-10-08T17:59:00Z"), display_only=True
    )
    assert not apply_window_open(
        manifest, now=pd.Timestamp("2026-10-08T18:01:00Z"), display_only=True
    )
    assert not apply_window_open(
        manifest, now=pd.Timestamp("2026-10-08T11:00:00Z"), display_only=True
    )


def test_the_week_and_uris_come_from_the_lock():
    lock = {
        "active_week": {"week": 6},
        "corrected_lineage": {"kind": "corrected_rebuild", "live_week": {"week": 6}},
    }
    assert live_week(lock) == 6
    run_id, forecast, serving = run_uris(6, "20261008-d1")
    assert run_id == "2026w6-v5repair-20261008-d1"
    assert forecast.endswith("/20261008-d1/week=6/forecast-manifest.json")
    assert receipt_uri(6, "20261008-d1").endswith(
        f"{run_id}/verification/verifier-manifest.json"
    )
    with pytest.raises(ValueError, match="no live week"):
        live_week(
            {
                "active_week": {"week": 6},
                "corrected_lineage": {"kind": "corrected_rebuild"},
            }
        )
    with pytest.raises(ValueError, match="differs from its active week"):
        live_week({**lock, "active_week": {"week": 7}})
    with pytest.raises(ValueError, match="invalid live release tag"):
        run_uris(6, "Bad Tag")
