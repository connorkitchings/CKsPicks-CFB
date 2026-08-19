"""The Odds API historical NCAAF adapter with no implicit paid requests."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd

from cks_picks_cfb.data.sources import (
    FailureCategory,
    SourceError,
    SourceResponse,
)

HISTORICAL_NCAAF_ENDPOINT = (
    "https://api.the-odds-api.com/v4/historical/sports/americanfootball_ncaaf/odds"
)
HISTORICAL_CREDITS_PER_SNAPSHOT = 20  # US region × spreads + totals.


def estimate_historical_snapshot_requests(
    schedule: pd.DataFrame,
    *,
    credits_per_snapshot: int = HISTORICAL_CREDITS_PER_SNAPSHOT,
) -> dict[str, int]:
    """Return the paid-call estimate without contacting the provider."""
    if "start_date" not in schedule:
        raise ValueError("Schedule requires start_date for historical quote estimate")
    starts = pd.to_datetime(schedule["start_date"], utc=True, errors="raise")
    request_count = int(starts.drop_duplicates().size)
    return {
        "snapshot_requests": request_count,
        "estimated_credits": request_count * int(credits_per_snapshot),
    }


def match_odds_events_to_schedule(
    events: Sequence[Mapping[str, Any]],
    schedule: pd.DataFrame,
    *,
    kickoff_tolerance_minutes: int = 5,
) -> dict[str, int]:
    """Return only unambiguous provider-event to canonical-game matches."""
    required = {"game_id", "home_team", "away_team", "start_date"}
    missing = sorted(required - set(schedule.columns))
    if missing:
        raise ValueError(f"Schedule is missing event-matching columns: {missing}")

    def normalized(value: object) -> str:
        return re.sub(r"[^a-z0-9]", "", str(value).casefold())

    schedule_rows = schedule.copy()
    schedule_rows["start_date"] = pd.to_datetime(
        schedule_rows["start_date"], utc=True, errors="raise"
    )
    result: dict[str, int] = {}
    tolerance = pd.Timedelta(minutes=kickoff_tolerance_minutes)
    for event in events:
        event_id = str(event.get("id") or event.get("source_event_id") or "")
        kickoff = pd.to_datetime(
            event.get("commence_time", event.get("kickoff_utc")),
            utc=True,
            errors="coerce",
        )
        if not event_id or pd.isna(kickoff):
            continue
        matched = schedule_rows[
            (
                schedule_rows["home_team"].map(normalized)
                == normalized(event.get("home_team"))
            )
            & (
                schedule_rows["away_team"].map(normalized)
                == normalized(event.get("away_team"))
            )
            & ((schedule_rows["start_date"] - kickoff).abs() <= tolerance)
        ]
        if len(matched) > 1:
            raise ValueError(f"Ambiguous The Odds API event match: {event_id}")
        if len(matched) == 1:
            result[event_id] = int(matched.iloc[0]["game_id"])
    return result


class TheOddsAPIAdapter:
    """Provider-native historical quote source.

    ``fetch`` is deliberately explicit: callers must pass ``snapshot_at`` and
    the adapter refuses to issue an unauthenticated request.  Production
    backfills should first call :func:`estimate_historical_snapshot_requests`
    and receive user approval for the quoted spend.
    """

    provider = "the_odds_api"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        http_get: Callable[[str], Mapping[str, Any]] | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.api_key = api_key or os.getenv("THE_ODDS_API_KEY")
        self._http_get = http_get or self._default_http_get
        self._now = now

    @staticmethod
    def _default_http_get(url: str) -> Mapping[str, Any]:
        with urlopen(url, timeout=30) as response:  # noqa: S310 - fixed HTTPS host
            return json.loads(response.read().decode("utf-8"))

    def fetch(self, entity: str, request: Mapping[str, Any]) -> SourceResponse:
        if entity != "market_quotes":
            raise SourceError(
                f"Unsupported The Odds API entity: {entity}",
                FailureCategory.CONTRACT,
                retryable=False,
            )
        if not self.api_key:
            raise SourceError(
                "THE_ODDS_API_KEY is required for historical odds requests",
                FailureCategory.AUTHENTICATION,
                retryable=False,
            )
        snapshot_at = pd.Timestamp(request.get("snapshot_at"), tz="UTC")
        parameters = {
            "apiKey": self.api_key,
            "regions": str(request.get("regions", "us")),
            "markets": "spreads,totals",
            "oddsFormat": "american",
            "dateFormat": "iso",
            "date": snapshot_at.isoformat().replace("+00:00", "Z"),
        }
        url = f"{HISTORICAL_NCAAF_ENDPOINT}?{urlencode(parameters)}"
        try:
            payload = self._http_get(url)
        except Exception as exc:  # Classification happens in fetch_with_retry.
            raise exc
        response_timestamp = pd.Timestamp(payload.get("timestamp"), tz="UTC")
        if response_timestamp >= snapshot_at + pd.Timedelta(seconds=1):
            raise SourceError(
                "Historical response timestamp is after requested pre-kick cutoff",
                FailureCategory.CONTRACT,
                retryable=False,
            )
        event_game_ids = {
            str(key): int(value)
            for key, value in dict(request.get("event_game_ids") or {}).items()
        }
        records = tuple(
            self._flatten(payload.get("data") or (), response_timestamp, event_game_ids)
        )
        if not records:
            raise SourceError(
                "The Odds API returned no historical NCAAF quotes",
                FailureCategory.DATA_UNAVAILABLE,
                retryable=False,
            )
        return SourceResponse(
            provider=self.provider,
            entity=entity,
            records=records,
            request={
                key: value for key, value in parameters.items() if key != "apiKey"
            },
            captured_at=self._now(),
            effective_at=response_timestamp.to_pydatetime(),
            provider_api_version="v4",
            response_metadata={
                "snapshot_timestamp": response_timestamp.isoformat(),
                "previous_timestamp": payload.get("previous_timestamp"),
                "next_timestamp": payload.get("next_timestamp"),
            },
        )

    @staticmethod
    def _flatten(
        events: Sequence[Mapping[str, Any]],
        snapshot_at: pd.Timestamp,
        event_game_ids: Mapping[str, int],
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for event in events:
            for bookmaker in event.get("bookmakers") or ():
                lines: dict[str, Any] = {}
                latest_update: pd.Timestamp | None = None
                for market in bookmaker.get("markets") or ():
                    update = market.get("last_update") or bookmaker.get("last_update")
                    if update:
                        updated_at = pd.Timestamp(update, tz="UTC")
                        latest_update = (
                            max(latest_update, updated_at)
                            if latest_update
                            else updated_at
                        )
                    outcomes = {
                        item.get("name"): item for item in market.get("outcomes") or ()
                    }
                    if market.get("key") == "spreads":
                        home = outcomes.get(event.get("home_team"))
                        away = outcomes.get(event.get("away_team"))
                        if home:
                            lines["spread"] = home.get("point")
                            lines["home_spread_price"] = home.get("price")
                        if away:
                            lines["away_spread"] = away.get("point")
                            lines["away_spread_price"] = away.get("price")
                    if market.get("key") == "totals":
                        over = outcomes.get("Over")
                        under = outcomes.get("Under")
                        if over:
                            lines["total"] = over.get("point")
                            lines["over_price"] = over.get("price")
                        if under:
                            lines["under_price"] = under.get("price")
                if not lines:
                    continue
                records.append(
                    {
                        "source_event_id": event.get("id"),
                        "game_id": event_game_ids.get(str(event.get("id"))),
                        "home_team": event.get("home_team"),
                        "away_team": event.get("away_team"),
                        "kickoff_utc": event.get("commence_time"),
                        "provider": bookmaker.get("key"),
                        "captured_at": snapshot_at.isoformat(),
                        "quote_updated_at": (
                            latest_update.isoformat()
                            if latest_update
                            else snapshot_at.isoformat()
                        ),
                        **lines,
                    }
                )
        return records
