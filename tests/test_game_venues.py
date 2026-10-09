"""Unit tests for the game_venues transform (no database or R2 required)."""

from __future__ import annotations

import pandas as pd
import pytest

from cks_picks_cfb.data.game_venues import (
    UPSERT_GAME_VENUE_SQL,
    MissingVenueColumnsError,
    apply_venue_supplement,
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


def test_required_city_gate_allows_international_city_without_state():
    from cks_picks_cfb.data.game_venues import require_venue_cities

    assert (
        require_venue_cities([{"game_id": 1, "city": "Dublin", "state": None}], [1])[
            "missing_game_ids"
        ]
        == []
    )
    with pytest.raises(ValueError, match="2"):
        require_venue_cities([{"game_id": 1, "city": "Dublin"}], [1, 2])
    with pytest.raises(ValueError, match="1"):
        require_venue_cities([{"game_id": 1, "city": "  "}], [1])


def test_latest_silver_ref_pins_an_exact_version():
    from scripts.pipeline import publish_game_venues as pgv

    class Cur:
        def execute(self, query, params):
            self.query, self.params = query, params

        def fetchone(self):
            return ("venues", "v-pinned", "venues_v1", "sha", "uri")

    cur = Cur()
    ref = pgv._latest_silver_ref(cur, "venues", None, "v-pinned")
    assert ref.version_id == "v-pinned"
    assert "AND version_id = %s" in cur.query and "v-pinned" in cur.params
    pgv._latest_silver_ref(cur, "venues", None)
    assert "version_id = %s" not in cur.query


@pytest.mark.parametrize("version", ["games-pinned", None])
def test_games_catalog_lookup_keeps_season_and_validation_scope(version):
    from scripts.pipeline import publish_game_venues as pgv

    class Cur:
        def execute(self, query, params):
            self.query, self.params = query, params

        def fetchone(self):
            return ("games", "games-pinned", "games_v2", "sha", "uri")

    cur = Cur()
    ref = pgv._latest_silver_ref(cur, "games", 2026, version)
    assert ref.version_id == "games-pinned"
    assert "state = 'validated'" in cur.query
    assert "partitions @> %s::jsonb" in cur.query
    assert cur.params == [
        "games",
        *([version] if version else []),
        '{"seasons": [2026]}',
    ]
    assert ("AND version_id = %s" in cur.query) == (version is not None)


def test_missing_pinned_games_version_fails_closed():
    from scripts.pipeline import publish_game_venues as pgv

    class Cur:
        def execute(self, query, params):
            assert "version_id = %s" in query
            assert "missing" in params

        def fetchone(self):
            return None

    with pytest.raises(LookupError, match="No validated Silver games"):
        pgv._latest_silver_ref(Cur(), "games", 2026, "missing")


@pytest.mark.parametrize(
    "problem",
    [
        "missing_game",
        "unknown_venue",
        "missing_city",
        "duplicate_game",
        "duplicate_venue",
    ],
)
def test_pinned_publication_rejects_incomplete_or_ambiguous_sources_before_write(
    monkeypatch, problem
):
    _run_pinned_publisher(monkeypatch, problem)


def test_pinned_dry_run_reports_exact_versions_and_hashes(monkeypatch, capsys):
    _run_pinned_publisher(monkeypatch)
    output = capsys.readouterr().out
    assert '"games": "games-pinned"' in output
    assert '"venues": "venues-pinned"' in output
    assert '"games": "games-sha"' in output
    assert '"venues": "venues-sha"' in output
    assert "Dry run: nothing written" in output


def _run_pinned_publisher(monkeypatch, problem=None):
    import sys
    from contextlib import nullcontext
    from types import SimpleNamespace

    from scripts.pipeline import publish_game_venues as pgv

    frame = games([{"game_id": 1, "venue_id": 12}])
    venues = VENUES.copy()
    if problem == "missing_game":
        frame["game_id"] = 2
    elif problem == "unknown_venue":
        frame["venue_id"] = 999
    elif problem == "missing_city":
        venues.loc[venues.venue_id == 12, "city"] = " "
    elif problem == "duplicate_game":
        frame = pd.concat([frame, frame])
    elif problem == "duplicate_venue":
        venues = pd.concat([venues, venues[venues.venue_id == 12]])

    class Cur:
        def execute(self, query, params):
            assert query.startswith("SELECT game_id FROM games")

        def fetchall(self):
            return [(1,)]

        def executemany(self, *args):
            pytest.fail("publication must not reach writes")

    conn = SimpleNamespace(
        cursor=lambda: nullcontext(Cur()),
        commit=lambda: pytest.fail("unexpected commit"),
    )
    monkeypatch.setattr(pgv.psycopg, "connect", lambda url: nullcontext(conn))
    monkeypatch.setattr(pgv, "load_dotenv", lambda: None)
    monkeypatch.setattr(pgv, "get_storage", lambda **kwargs: object())
    monkeypatch.setenv("DATABASE_URL", "test-only")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "publisher",
            "--environment",
            "production",
            "--games-version",
            "games-pinned",
            "--venues-version",
            "venues-pinned",
            "--require-city",
            *(["--dry-run"] if problem is None else []),
        ],
    )

    def lookup(cur, dataset, season, version):
        assert version == f"{dataset}-pinned"
        assert season == (2026 if dataset == "games" else None)
        return pgv.DatasetRef(dataset, version, "schema", f"{dataset}-sha", "uri")

    monkeypatch.setattr(pgv, "_latest_silver_ref", lookup)
    monkeypatch.setattr(
        pgv,
        "read_dataset",
        lambda storage, ref: frame if ref.dataset == "games" else venues,
    )
    monkeypatch.setattr(
        pgv, "finalize_quality", lambda run, identity: _quality_identity(identity)
    )
    if problem:
        with pytest.raises(ValueError):
            pgv.main()
    else:
        assert pgv.main() == 0


def _quality_identity(identity):
    assert identity["games_version"] == "games-pinned"
    assert identity["venues_version"] == "venues-pinned"
    assert identity["games_content_sha"] == "games-sha"
    assert identity["venues_content_sha"] == "venues-sha"
    return {"_path": "test-only"}


def test_supplement_fills_only_absent_venue_ids():
    extra = [
        {"venue_id": 10, "name": "Not Rose Bowl", "city": "Elsewhere", "state": "ZZ"},
        {"venue_id": 99, "name": "Ryan Field", "city": "Evanston", "state": "IL"},
    ]
    out, added = apply_venue_supplement(VENUES, extra)
    assert added == [99]
    assert out.loc[out["venue_id"] == 10, "city"].tolist() == ["Pasadena"]
    assert out.loc[out["venue_id"] == 99, "city"].tolist() == ["Evanston"]
    same, none = apply_venue_supplement(VENUES, [])
    assert none == [] and same is VENUES
