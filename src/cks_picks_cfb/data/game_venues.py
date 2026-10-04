"""Venue, city and state per game, for the ``game_venues`` table.

Pure transformation of the Silver ``games`` and ``venues`` datasets into rows
for Neon (migration 0019). CFBD games carry ``venue_id``, a venue name and a
``neutral_site`` flag; city and state live on the venue record, so the two are
joined on ``venue_id``. Column names are matched against a few spellings so a
Silver naming difference is reported rather than silently producing no rows.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pandas as pd

GAME_ID = ("game_id", "id")
GAME_VENUE_ID = ("venue_id", "venueId")
GAME_VENUE_NAME = ("venue", "venue_name")
GAME_NEUTRAL = ("neutral_site", "neutralSite")

VENUE_ID = ("venue_id", "id")
VENUE_NAME = ("name", "venue_name", "venue")
VENUE_CITY = ("city",)
VENUE_STATE = ("state",)
VENUE_COUNTRY = ("country_code", "countryCode")
VENUE_TIMEZONE = ("timezone",)

UPSERT_GAME_VENUE_SQL = """
INSERT INTO game_venues (
    game_id, venue_id, venue_name, city, state, country_code, timezone,
    neutral_site, source, updated_at
) VALUES (
    %(game_id)s, %(venue_id)s, %(venue_name)s, %(city)s, %(state)s,
    %(country_code)s, %(timezone)s, %(neutral_site)s, 'cfbd', NOW()
)
ON CONFLICT (game_id) DO UPDATE SET
    venue_id = EXCLUDED.venue_id,
    venue_name = EXCLUDED.venue_name,
    city = EXCLUDED.city,
    state = EXCLUDED.state,
    country_code = EXCLUDED.country_code,
    timezone = EXCLUDED.timezone,
    neutral_site = EXCLUDED.neutral_site,
    updated_at = NOW()
"""


class MissingVenueColumnsError(ValueError):
    """Raised when Silver does not carry a column the join cannot work without."""


def _column(frame: pd.DataFrame, names: tuple[str, ...]) -> str | None:
    return next((name for name in names if name in frame.columns), None)


def _text(value: Any) -> str | None:
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


def _int(value: Any) -> int | None:
    if value is None or pd.isna(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _bool(value: Any) -> bool | None:
    if value is None or pd.isna(value):
        return None
    return bool(value)


def build_game_venue_rows(
    games: pd.DataFrame,
    venues: pd.DataFrame,
    game_ids: Iterable[int],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return ``(rows, report)`` for the games that exist in Neon.

    Only ``game_ids`` present in Silver ``games`` produce a row. A game without
    a venue id still gets a row (venue name and neutral-site flag when Silver
    has them) so coverage gaps are visible rather than dropped.
    """
    wanted = {int(g) for g in game_ids}
    game_id_col = _column(games, GAME_ID)
    if game_id_col is None:
        raise MissingVenueColumnsError(
            f"Silver games has no game id column; columns: {sorted(games.columns)}"
        )
    venue_id_col = _column(games, GAME_VENUE_ID)
    if venue_id_col is None:
        raise MissingVenueColumnsError(
            "Silver games has no venue id column "
            f"({', '.join(GAME_VENUE_ID)}); columns: {sorted(games.columns)}"
        )
    name_col = _column(games, GAME_VENUE_NAME)
    neutral_col = _column(games, GAME_NEUTRAL)

    v_id = _column(venues, VENUE_ID)
    if v_id is None:
        raise MissingVenueColumnsError(
            f"Silver venues has no id column; columns: {sorted(venues.columns)}"
        )
    v_name = _column(venues, VENUE_NAME)
    v_city = _column(venues, VENUE_CITY)
    v_state = _column(venues, VENUE_STATE)
    v_country = _column(venues, VENUE_COUNTRY)
    v_tz = _column(venues, VENUE_TIMEZONE)

    by_venue: dict[int, pd.Series] = {}
    for _, row in venues.iterrows():
        vid = _int(row[v_id])
        if vid is not None:
            by_venue[vid] = row

    # One row per game; if Silver repeats a game, the last record wins.
    ordered = games.drop_duplicates(subset=[game_id_col], keep="last")

    rows: list[dict[str, Any]] = []
    seen: set[int] = set()
    missing_venue_id = 0
    venue_not_found = 0
    for _, game in ordered.iterrows():
        gid = _int(game[game_id_col])
        if gid is None or gid not in wanted:
            continue
        seen.add(gid)
        vid = _int(game[venue_id_col])
        venue = by_venue.get(vid) if vid is not None else None
        if vid is None:
            missing_venue_id += 1
        elif venue is None:
            venue_not_found += 1
        rows.append(
            {
                "game_id": gid,
                "venue_id": vid,
                "venue_name": _text(venue[v_name])
                if venue is not None and v_name
                else (_text(game[name_col]) if name_col else None),
                "city": _text(venue[v_city]) if venue is not None and v_city else None,
                "state": _text(venue[v_state])
                if venue is not None and v_state
                else None,
                "country_code": _text(venue[v_country])
                if venue is not None and v_country
                else None,
                "timezone": _text(venue[v_tz]) if venue is not None and v_tz else None,
                "neutral_site": _bool(game[neutral_col]) if neutral_col else None,
            }
        )

    absent = sorted(wanted - seen)
    report = {
        "games_in_neon": len(wanted),
        "rows": len(rows),
        "with_city": sum(1 for r in rows if r["city"]),
        "with_city_and_state": sum(1 for r in rows if r["city"] and r["state"]),
        "missing_venue_id": missing_venue_id,
        "venue_not_found": venue_not_found,
        "games_absent_from_silver": len(absent),
        "games_absent_sample": absent[:10],
    }
    return rows, report


def require_venue_cities(rows: list[dict[str, Any]], game_ids: list[int]) -> dict:
    """Require city coverage for the exact published slate; state is optional."""
    cities = {int(row["game_id"]): _text(row.get("city")) for row in rows}
    missing = sorted(
        {int(game_id) for game_id in game_ids if not cities.get(int(game_id))}
    )
    if missing:
        raise ValueError(f"required venue city missing for game IDs: {missing}")
    return {"required_games": len(set(game_ids)), "missing_game_ids": missing}
