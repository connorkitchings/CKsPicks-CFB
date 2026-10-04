"""Context loaders: fake cursor and reader, no database or storage access."""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from cks_picks_cfb.quality import checks as q
from cks_picks_cfb.quality import loaders


class FakeCursor:
    def __init__(self, catalog, schedule):
        self.catalog, self.schedule = catalog, schedule
        self.queries: list[tuple[str, tuple]] = []
        self._rows: list = []

    def execute(self, query, params=()):
        self.queries.append((query, tuple(params)))
        if "SELECT dataset, version_id, as_of, partitions" in query:
            self._rows = self.catalog
        elif "FROM market_quotes" in query:
            self._rows = []
        elif "FROM games" in query:
            self._rows = self.schedule
        else:
            dataset = params[0]
            pin = params[1] if "version_id = %s" in query else None
            rows = [
                (d, v, "s1", f"sha-{v}", f"uri/{v}")
                for d, v, _a, parts in self.catalog
                if d == dataset and (pin is None or v == pin)
            ]
            self._rows = rows[:1]

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


T = dt.datetime(2026, 9, 1)
CATALOG = [
    ("games", "g26", T, {"seasons": [2026]}),
    ("venues", "v24", T, {"seasons": []}),
    ("venues", "v25", T, {"seasons": []}),
]


def test_parse_pins():
    assert loaders.parse_pins(["venues=v25", "games=g26"]) == {
        "venues": "v25",
        "games": "g26",
    }
    assert loaders.parse_pins(None) == {}
    with pytest.raises(ValueError, match="dataset=version_id"):
        loaders.parse_pins(["venues"])


def test_context_includes_found_datasets_and_omits_missing_ones():
    cur = FakeCursor(CATALOG, [(2026, 1, 101), (2026, 1, 102)])
    read = lambda row: pd.DataFrame({"game_id": [101], "src": [row[1]]})  # noqa: E731
    ctx = loaders.build_ingest_context(cur, read, year=2026)
    assert list(ctx["games"]["src"]) == ["g26"]
    assert "plays" not in ctx and "drives" not in ctx
    assert ctx["inputs"] == {"games": {"version_id": "g26", "content_sha": "sha-g26"}}
    assert list(ctx["schedule"]["game_id"]) == [101, 102]
    assert set(ctx["catalog_versions"].columns) == {
        "dataset",
        "version_id",
        "as_of",
        "seasons",
    }


def test_missing_datasets_make_their_checks_skip_not_pass():
    cur = FakeCursor(CATALOG, [(2026, 1, 101)])
    ctx = loaders.build_ingest_context(cur, lambda row: pd.DataFrame(), year=2026)
    results = {r.check_id: r for r in q.run_stage("ingest", ctx).results}
    assert results["ingest.plays_and_drives_per_completed_game"].skipped
    assert results["ingest.versions_pinned"].passed is False  # venues unpinned
    assert not results["ingest.versions_pinned"].skipped


def test_a_pin_is_passed_to_the_catalog_query_and_clears_the_check():
    cur = FakeCursor(CATALOG, [])
    ctx = loaders.build_ingest_context(
        cur, lambda row: pd.DataFrame(), year=2026, pins={"venues": "v25"}
    )
    results = {r.check_id: r for r in q.run_stage("ingest", ctx).results}
    assert results["ingest.versions_pinned"].passed
