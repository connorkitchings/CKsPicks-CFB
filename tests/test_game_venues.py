"""Unit tests for the game_venues transform (no database or R2 required)."""

from __future__ import annotations

import pandas as pd
import pytest

from cks_picks_cfb.data.game_venues import (
    UPSERT_GAME_VENUE_SQL,
    MissingVenueColumnsError,
    build_game_venue_rows,
)

VENUES = pd.DataFrame(
    [
        {
            "venue_id": 10,
            "name": "Rose Bowl",
            "city": "Pasadena",
            "state": "CA",
            "country_code": "US",
            "timezone": "America/Los_Angeles",
        },
        {
            "venue_id": 11,
            "name": "  Michigan Stadium ",
            "city": "Ann Arbor",
            "state": "MI",
            "country_code": "US",
            "timezone": "America/Detroit",
        },
        {
            "venue_id": 12,
            "name": "Aviva Stadium",
            "city": "Dublin",
            "state": None,
            "country_code": "IE",
            "timezone": "Europe/Dublin",
        },
        {
            "venue_id": 13,
            "name": "Blank City Field",
            "city": "  ",
            "state": "",
            "country_code": "US",
            "timezone": None,
        },
    ]
)


def games(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def test_joins_city_and_state_and_keeps_neutral_site():
    frame = games(
        [
            {"game_id": 1, "venue_id": 10, "venue": "Rose Bowl", "neutral_site": True},
            {
                "game_id": 2,
                "venue_id": 11,
                "venue": "Michigan Stadium",
                "neutral_site": False,
            },
        ]
    )
    rows, report = build_game_venue_rows(frame, VENUES, [1, 2])
    by_id = {r["game_id"]: r for r in rows}
    assert by_id[1]["city"] == "Pasadena" and by_id[1]["state"] == "CA"
    assert by_id[1]["neutral_site"] is True
    assert by_id[2]["venue_name"] == "Michigan Stadium"  # trimmed, from venues
    assert by_id[2]["neutral_site"] is False
    assert report["rows"] == 2 and report["with_city_and_state"] == 2


def test_only_games_that_exist_in_neon_are_returned():
    frame = games([{"game_id": 1, "venue_id": 10}, {"game_id": 2, "venue_id": 11}])
    rows, report = build_game_venue_rows(frame, VENUES, [2, 999])
    assert [r["game_id"] for r in rows] == [2]
    assert report["games_absent_from_silver"] == 1
    assert report["games_absent_sample"] == [999]


def test_missing_venue_id_still_yields_a_row_with_the_silver_name():
    frame = games(
        [
            {
                "game_id": 3,
                "venue_id": None,
                "venue": "Somewhere Field",
                "neutral_site": None,
            }
        ]
    )
    rows, report = build_game_venue_rows(frame, VENUES, [3])
    assert rows[0]["venue_id"] is None
    assert rows[0]["venue_name"] == "Somewhere Field"
    assert rows[0]["city"] is None and rows[0]["state"] is None
    assert report["missing_venue_id"] == 1


def test_unknown_venue_id_is_counted_and_has_no_location():
    rows, report = build_game_venue_rows(
        games([{"game_id": 4, "venue_id": 777}]), VENUES, [4]
    )
    assert rows[0]["venue_id"] == 777 and rows[0]["city"] is None
    assert report["venue_not_found"] == 1


def test_non_us_venue_has_city_but_no_state_and_blank_fields_become_none():
    rows, _ = build_game_venue_rows(
        games([{"game_id": 5, "venue_id": 12}, {"game_id": 6, "venue_id": 13}]),
        VENUES,
        [5, 6],
    )
    by_id = {r["game_id"]: r for r in rows}
    assert by_id[5]["city"] == "Dublin" and by_id[5]["state"] is None
    assert by_id[5]["country_code"] == "IE"
    assert by_id[6]["city"] is None and by_id[6]["state"] is None
    assert by_id[6]["timezone"] is None


def test_duplicate_game_records_keep_the_last_and_alternate_spellings_work():
    frame = pd.DataFrame(
        [
            {"id": 7, "venueId": 10, "neutralSite": False},
            {"id": 7, "venueId": 11, "neutralSite": True},
        ]
    )
    venues = VENUES.rename(columns={"venue_id": "id"})
    rows, report = build_game_venue_rows(frame, venues, [7])
    assert len(rows) == 1
    assert rows[0]["city"] == "Ann Arbor" and rows[0]["neutral_site"] is True
    assert report["rows"] == 1


def test_missing_required_columns_fail_loudly_with_the_column_list():
    with pytest.raises(MissingVenueColumnsError, match="no venue id column"):
        build_game_venue_rows(pd.DataFrame([{"game_id": 1}]), VENUES, [1])
    with pytest.raises(MissingVenueColumnsError, match="no game id column"):
        build_game_venue_rows(pd.DataFrame([{"venue_id": 1}]), VENUES, [1])
    with pytest.raises(MissingVenueColumnsError, match="venues has no id column"):
        build_game_venue_rows(
            pd.DataFrame([{"game_id": 1, "venue_id": 1}]),
            pd.DataFrame([{"name": "x"}]),
            [1],
        )


def test_upsert_sql_covers_every_column_and_is_idempotent():
    for column in (
        "venue_id",
        "venue_name",
        "city",
        "state",
        "country_code",
        "timezone",
        "neutral_site",
    ):
        assert f"{column} = EXCLUDED.{column}" in UPSERT_GAME_VENUE_SQL
    assert "ON CONFLICT (game_id) DO UPDATE" in UPSERT_GAME_VENUE_SQL
