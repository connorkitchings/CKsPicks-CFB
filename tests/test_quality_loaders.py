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


def test_silver_context_reads_games_previous_and_capture_index():
    class Cur(FakeCursor):
        def execute(self, query, params=()):
            self.queries.append((query, tuple(params)))
            if "FROM catalog.source_captures" in query:
                self._rows = [("c1", "sha", "osha", "uri", "t")]
            elif "version_id <> %s" in query:
                self._rows = [("games", "g25", "s1", "sha-g25", "uri/g25")]
            elif "AND version_id = %s" in query or "partitions @>" in query:
                dataset = params[0]
                self._rows = [(dataset, f"{dataset}-v", "s1", f"sha-{dataset}", "uri")]
            else:
                self._rows = []

    cur = Cur([], [])
    seen = []
    ctx = loaders.build_silver_context(
        cur,
        lambda row: seen.append(row[1]) or pd.DataFrame({"game_id": [1]}),
        year=2026,
    )
    assert {
        "byplay",
        "drives",
        "games",
        "source_reconciliation",
        "games_previous",
    } <= set(ctx)
    assert "g25" in seen and ctx["inputs"]["games_previous"]["version_id"] == "g25"
    assert list(ctx["capture_index"]["capture_id"]) == ["c1"]


class RunsCursor:
    """Answers the ingestion-run and odds-capture queries only."""

    def __init__(self, runs=(), odds=None):
        self.runs, self.odds = list(runs), odds
        self._rows: list = []

    def execute(self, query, params=()):
        if "FROM catalog.ingestion_runs" in query:
            self._rows = self.runs
        elif "FROM catalog.source_captures" in query:
            self._rows = [self.odds] if self.odds else []
        else:
            self._rows = []

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


def _request(entity, **parameters):
    return {"requests": [{"entity": entity, "parameters": parameters}]}


def test_a_request_that_only_failed_is_a_capture_gap_and_a_retry_clears_it():
    runs = [
        ("succeeded", _request("games", year=2026, week=1)),
        ("failed", _request("plays", year=2026, week=1)),
    ]
    expected, completed = loaders.capture_requests(RunsCursor(runs), 2026)
    assert expected - completed == {
        loaders.request_key("plays", {"year": 2026, "week": 1})
    }
    retried = [*runs, ("succeeded", _request("plays", week=1, year=2026))]
    expected, completed = loaders.capture_requests(RunsCursor(retried), 2026)
    assert expected == completed


def test_the_capture_check_runs_on_loaded_requests_instead_of_skipping():
    runs = [("failed", _request("plays", year=2026, week=2))]
    expected, completed = loaders.capture_requests(RunsCursor(runs), 2026)
    ctx = {"expected_requests": expected, "completed_requests": completed}
    result = {r.check_id: r for r in q.run_stage("ingest", ctx).results}[
        "ingest.capture_completeness"
    ]
    assert not result.skipped and result.passed is False


def test_odds_capture_reports_the_unmatched_events_of_the_latest_capture():
    cursor = RunsCursor(odds=("cap-1", {"unmatched_events": 3, "matched_events": 40}))
    assert loaders.latest_odds_capture(cursor, 2026) == {
        "capture_id": "cap-1",
        "unmatched_events": 3,
        "matched_events": 40,
    }
    assert loaders.latest_odds_capture(RunsCursor(), 2026) is None
    ctx = {"odds_capture": loaders.latest_odds_capture(cursor, 2026)}
    result = {r.check_id: r for r in q.run_stage("ingest", ctx).results}[
        "ingest.odds_unmatched_events"
    ]
    assert not result.skipped and result.passed is False


def test_loaded_datasets_come_with_their_contract_so_the_schema_check_runs():
    cur = FakeCursor(CATALOG, [(2026, 1, 101)])
    ctx = loaders.build_ingest_context(
        cur, lambda row: pd.DataFrame({"game_id": [101]}), year=2026
    )
    assert set(ctx["schemas"]) == {"games"}
    results = [
        r
        for r in q.run_stage("ingest", ctx).results
        if r.check_id == "ingest.schema_contract"
    ]
    assert results and not any(r.skipped for r in results)


def test_a_version_with_no_active_contract_is_a_finding_not_a_crash():
    # The fake catalog stamps every version "s1"; drives only accepts "drives_v1".
    cur = FakeCursor([("drives", "d26", T, {"seasons": [2026]})], [(2026, 1, 101)])
    ctx = loaders.build_ingest_context(
        cur, lambda row: pd.DataFrame({"game_id": [101]}), year=2026
    )
    assert "drives" in ctx["schema_errors"] and "drives" not in ctx["schemas"]
    outcome = {r.check_id: r for r in q.run_stage("ingest", ctx).results}
    assert outcome["ingest.schema_contract"].passed is False
