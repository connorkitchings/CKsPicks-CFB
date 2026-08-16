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
    response = adapter.fetch(
        "market_quotes", {"snapshot_at": "2024-09-01T15:59:59Z"}
    )
    assert response.provider == "the_odds_api"
    assert response.effective_at == datetime(2024, 9, 1, 15, 55, tzinfo=timezone.utc)
    assert response.records[0]["spread"] == -3.5
    assert response.records[0]["total"] == 48.5
    assert response.records[0]["under_price"] == -115


def test_adapter_requires_key_without_making_a_request():
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
