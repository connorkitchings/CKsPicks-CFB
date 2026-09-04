from datetime import datetime, timezone

import pandas as pd
import pytest

from cks_picks_cfb.data.sources import FailureCategory, SourceError
from cks_picks_cfb.data.the_odds_api import (
    TheOddsAPIAdapter,
    estimate_historical_snapshot_requests,
    match_odds_events_to_schedule,
)


def test_historical_request_estimate_groups_identical_kickoff_slots():
    estimate = estimate_historical_snapshot_requests(
        pd.DataFrame(
            {
                "start_date": [
                    "2024-09-01T16:00:00Z",
                    "2024-09-01T16:00:00Z",
                    "2024-09-01T19:00:00Z",
                ]
            }
        )
    )
    assert estimate == {"snapshot_requests": 2, "estimated_credits": 40}


def test_adapter_flattens_pre_kick_spread_total_and_prices():
    payload = {
        "timestamp": "2024-09-01T15:55:00Z",
        "data": [
            {
                "id": "event-1",
                "home_team": "Home",
                "away_team": "Away",
                "commence_time": "2024-09-01T16:00:00Z",
                "bookmakers": [
                    {
                        "key": "book",
                        "markets": [
                            {
                                "key": "spreads",
                                "last_update": "2024-09-01T15:54:00Z",
                                "outcomes": [
                                    {"name": "Home", "point": -3.5, "price": -110},
                                    {"name": "Away", "point": 3.5, "price": -110},
                                ],
                            },
                            {
                                "key": "totals",
                                "last_update": "2024-09-01T15:55:00Z",
                                "outcomes": [
                                    {"name": "Over", "point": 48.5, "price": -105},
                                    {"name": "Under", "point": 48.5, "price": -115},
                                ],
                            },
                        ],
                    }
                ],
            }
        ],
    }
    adapter = TheOddsAPIAdapter(
        api_key="test-key",
        http_get=lambda _: payload,
        now=lambda: datetime(2026, 8, 15, tzinfo=timezone.utc),
    )
    response = adapter.fetch("market_quotes", {"snapshot_at": "2024-09-01T15:59:59Z"})
    assert response.provider == "the_odds_api"
    assert response.effective_at == datetime(2024, 9, 1, 15, 55, tzinfo=timezone.utc)
    assert response.records[0]["spread"] == -3.5
    assert response.records[0]["total"] == 48.5
    assert response.records[0]["under_price"] == -115


def test_adapter_requires_key_without_making_a_request(monkeypatch):
    monkeypatch.delenv("THE_ODDS_API_KEY", raising=False)
    adapter = TheOddsAPIAdapter(api_key="", http_get=lambda _: pytest.fail("called"))
    with pytest.raises(SourceError) as exc:
        adapter.fetch("market_quotes", {"snapshot_at": "2024-09-01T15:59:59Z"})
    assert exc.value.category == FailureCategory.AUTHENTICATION


def test_event_matching_requires_teams_kickoff_and_unambiguous_game():
    schedule = pd.DataFrame(
        [
            {
                "game_id": 1,
                "home_team": "Miami (OH)",
                "away_team": "Ohio State",
                "start_date": "2024-09-01T16:00:00Z",
            }
        ]
    )
    matches = match_odds_events_to_schedule(
        [
            {
                "id": "odds-1",
                "home_team": "Miami OH",
                "away_team": "Ohio State",
                "commence_time": "2024-09-01T16:03:00Z",
            }
        ],
        schedule,
    )
    assert matches == {"odds-1": 1}


def test_prefix_matching_accepts_mascot_names():
    schedule = pd.DataFrame(
        [
            {
                "game_id": 7,
                "home_team": "Texas Tech",
                "away_team": "Abilene Christian",
                "start_date": "2026-09-12T20:00:00Z",
            },
            {
                "game_id": 8,
                "home_team": "App State",
                "away_team": "East Carolina",
                "start_date": "2026-09-12T16:00:00Z",
            },
        ]
    )
    events = [
        {
            "id": "e-1",
            "home_team": "Texas Tech Red Raiders",
            "away_team": "Abilene Christian Wildcats",
            "commence_time": "2026-09-12T20:00:00Z",
        },
        {
            "id": "e-2",
            "home_team": "Appalachian State Mountaineers",
            "away_team": "East Carolina Pirates",
            "commence_time": "2026-09-12T16:00:00Z",
        },
    ]
    # Exact-only mode (default) must not match mascot names.
    assert match_odds_events_to_schedule(events, schedule) == {}
    matches = match_odds_events_to_schedule(events, schedule, allow_prefix=True)
    assert matches == {"e-1": 7, "e-2": 8}


def test_prefix_matching_raises_on_ambiguity():
    schedule = pd.DataFrame(
        [
            {
                "game_id": 1,
                "home_team": "Texas",
                "away_team": "Oklahoma",
                "start_date": "2026-10-10T19:30:00Z",
            },
            {
                "game_id": 2,
                "home_team": "Texas Long",
                "away_team": "Oklahoma",
                "start_date": "2026-10-10T19:30:00Z",
            },
        ]
    )
    with pytest.raises(ValueError, match="Ambiguous"):
        match_odds_events_to_schedule(
            [
                {
                    "id": "e-1",
                    "home_team": "Texas Longhorns",
                    "away_team": "Oklahoma Sooners",
                    "commence_time": "2026-10-10T19:30:00Z",
                }
            ],
            schedule,
            allow_prefix=True,
        )


def test_abbreviation_expansions_apply_to_schedule_names():
    schedule = pd.DataFrame(
        [
            {
                "game_id": 9,
                "home_team": "FIU",
                "away_team": "Troy",
                "start_date": "2026-09-12T19:00:00Z",
            }
        ]
    )
    matches = match_odds_events_to_schedule(
        [
            {
                "id": "e-1",
                "home_team": "Florida International Panthers",
                "away_team": "Troy Trojans",
                "commence_time": "2026-09-12T19:00:00Z",
            }
        ],
        schedule,
        allow_prefix=True,
    )
    assert matches == {"e-1": 9}


LIVE_PAYLOAD = [
    {
        "id": "event-1",
        "home_team": "Home",
        "away_team": "Away",
        "commence_time": "2026-09-05T16:00:00Z",
        "bookmakers": [
            {
                "key": "book",
                "markets": [
                    {
                        "key": "spreads",
                        "last_update": "2026-09-03T14:20:00Z",
                        "outcomes": [
                            {"name": "Home", "point": -10.5, "price": -105},
                            {"name": "Away", "point": 10.5, "price": -115},
                        ],
                    },
                    {
                        "key": "totals",
                        "last_update": "2026-09-03T14:21:00Z",
                        "outcomes": [
                            {"name": "Over", "point": 58.5, "price": -110},
                            {"name": "Under", "point": 58.5, "price": -110},
                        ],
                    },
                ],
            }
        ],
    }
]


def test_fetch_live_flattens_board_with_fetch_time_capture():
    adapter = TheOddsAPIAdapter(
        api_key="test-key",
        http_get=lambda _: LIVE_PAYLOAD,
        now=lambda: datetime(2026, 9, 3, 14, 22, tzinfo=timezone.utc),
    )
    response = adapter.fetch_live("market_quotes", {"event_game_ids": {"event-1": 42}})
    assert response.provider == "the_odds_api"
    assert response.captured_at == datetime(2026, 9, 3, 14, 22, tzinfo=timezone.utc)
    assert response.effective_at == response.captured_at
    record = response.records[0]
    assert record["game_id"] == 42
    assert record["source_event_id"] == "event-1"
    assert record["spread"] == -10.5
    assert record["home_spread_price"] == -105
    assert record["total"] == 58.5
    assert record["over_price"] == -110
    assert record["quote_updated_at"] == "2026-09-03T14:21:00+00:00"
    assert response.response_metadata["mode"] == "live"
    assert response.response_metadata["estimated_credits"] == 2


def test_fetch_live_requires_key_without_making_a_request(monkeypatch):
    monkeypatch.delenv("THE_ODDS_API_KEY", raising=False)
    adapter = TheOddsAPIAdapter(api_key="", http_get=lambda _: pytest.fail("called"))
    with pytest.raises(SourceError) as exc:
        adapter.fetch_live("market_quotes", {})
    assert exc.value.category == FailureCategory.AUTHENTICATION


def test_fetch_live_rejects_empty_board():
    adapter = TheOddsAPIAdapter(api_key="test-key", http_get=lambda _: [])
    with pytest.raises(SourceError) as exc:
        adapter.fetch_live("market_quotes", {})
    assert exc.value.category == FailureCategory.DATA_UNAVAILABLE


def test_fetch_live_accepts_wrapped_payload_shape():
    adapter = TheOddsAPIAdapter(
        api_key="test-key",
        http_get=lambda _: {"data": LIVE_PAYLOAD},
        now=lambda: datetime(2026, 9, 3, 14, 22, tzinfo=timezone.utc),
    )
    response = adapter.fetch_live("market_quotes", {})
    assert len(response.records) == 1
