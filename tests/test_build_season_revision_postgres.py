"""Season market-capture union against a disposable Postgres catalog table.

Uses ``tests/pg_harness.py`` (socket-only cluster); skips without PostgreSQL binaries.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from scripts.pipeline.build_season_revision import season_market_capture_ids
from tests.pg_harness import PgCluster, find_pg_bin

PG_BIN = find_pg_bin()
if PG_BIN is None:
    pytest.skip(
        "PostgreSQL server binaries (initdb, pg_ctl, postgres) not found",
        allow_module_level=True,
    )

CAPTURES = [
    # capture_id, provider, entity, captured_at, request year, state
    ("w1", "cfbd", "betting_lines", "2026-09-02T18:00:00Z", 2026, "registered"),
    ("w7a", "cfbd", "betting_lines", "2026-10-13T21:28:00Z", 2026, "registered"),
    ("w7b", "cfbd", "betting_lines", "2026-10-14T14:41:28Z", 2026, "registered"),
    (
        "odds",
        "the_odds_api",
        "market_quotes",
        "2026-10-13T21:26:30Z",
        None,
        "registered",
    ),
    (
        "prior-season",
        "cfbd",
        "betting_lines",
        "2026-09-06T18:11:00Z",
        2025,
        "registered",
    ),
    ("staged", "cfbd", "betting_lines", "2026-10-01T00:00:00Z", 2026, "staged"),
    (
        "legacy",
        "legacy_cfbd_export",
        "betting_lines",
        "2026-08-04T00:00:00Z",
        2026,
        "registered",
    ),
    ("plays", "cfbd", "plays", "2026-10-11T15:33:00Z", 2026, "registered"),
    (
        "old-odds",
        "the_odds_api",
        "market_quotes",
        "2025-11-01T00:00:00Z",
        None,
        "registered",
    ),
    ("future", "cfbd", "betting_lines", "2026-10-20T00:00:00Z", 2026, "registered"),
]


@pytest.fixture(scope="module")
def catalog_url(tmp_path_factory):
    cluster = PgCluster(PG_BIN, tmp_path_factory.mktemp("season_revision_pg"))
    try:
        cluster.start()
        with cluster.connect(autocommit=True) as conn:
            conn.execute("CREATE SCHEMA catalog")
            conn.execute(
                "CREATE TABLE catalog.source_captures (capture_id text PRIMARY KEY, "
                "provider text, entity text, captured_at timestamptz, "
                "request jsonb, state text)"
            )
            for capture_id, provider, entity, at, year, state in CAPTURES:
                request = {"parameters": {"year": year}} if year else {}
                conn.execute(
                    "INSERT INTO catalog.source_captures VALUES (%s, %s, %s, %s, %s, %s)",
                    (capture_id, provider, entity, at, json.dumps(request), state),
                )
        yield cluster.conninfo()
    finally:
        cluster.stop()


def test_season_market_capture_ids_registered_season_markets_by_cutoff(catalog_url):
    cutoff = datetime(2026, 10, 15, tzinfo=timezone.utc)

    capture_ids = season_market_capture_ids(catalog_url, 2026, cutoff)

    assert capture_ids == ["w1", "odds", "w7a", "w7b"]


def test_season_market_capture_ids_earlier_cutoff_is_cumulative_prefix(catalog_url):
    cutoff = datetime(2026, 10, 13, 21, 27, tzinfo=timezone.utc)

    capture_ids = season_market_capture_ids(catalog_url, 2026, cutoff)

    assert capture_ids == ["w1", "odds"]
