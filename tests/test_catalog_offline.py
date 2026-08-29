"""Offline catalog registration and point-in-time lookup tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cks_picks_cfb.data import catalog
from cks_picks_cfb.data.lake import DatasetManifest, DatasetRef, SourceCapture


class _Cursor:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params=()):
        self.executed.append((sql, params))
        return self

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def fetchall(self):
        return self.rows.pop(0) if self.rows else []


class _Connection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self):
        return self._cursor

    def execute(self, sql, params=()):
        return self._cursor.execute(sql, params)

    def commit(self):
        self.commits += 1


def _capture(capture_id="capture"):
    return SourceCapture(
        capture_id=capture_id,
        provider="fixture",
        entity="games",
        captured_at=datetime(2026, 8, 23, tzinfo=timezone.utc),
        effective_at=None,
        request={"week": 1},
        content_sha="content",
        object_sha="object",
        uri="lake/bronze/fixture",
        row_count=2,
        response_metadata={"status": 200},
    )


def _connect(monkeypatch, cursor):
    connection = _Connection(cursor)
    monkeypatch.setattr(catalog.psycopg, "connect", lambda _url: connection)
    return connection


def test_ingestion_and_capture_registration_are_immutable_offline(monkeypatch):
    cursor = _Cursor([None, None])
    connection = _connect(monkeypatch, cursor)
    catalog.begin_ingestion_run(
        "postgresql://fixture",
        ingestion_run_id="run",
        provider="fixture",
        entity="games",
        request={"week": 1},
    )
    catalog.finish_ingestion_run(
        "postgresql://fixture", "run", succeeded=False, error_detail="x" * 5000
    )
    assert connection.commits == 2
    assert cursor.executed[-1][1][2] == "x" * 4000

    cursor = _Cursor([None])
    _connect(monkeypatch, cursor)
    catalog.register_source_capture(
        "postgresql://fixture", _capture(), ingestion_run_id="run"
    )
    assert any("source_captures" in sql for sql, _ in cursor.executed)

    conflict = _Cursor(
        [
            (
                "other",
                "games",
                datetime.now(timezone.utc),
                None,
                {},
                "x",
                "y",
                "z",
                1,
                None,
                {},
            )
        ]
    )
    with pytest.raises(ValueError, match="Immutable source capture conflict"):
        catalog._register_source_capture_cursor(conflict, _capture(), None)


def test_request_set_identity_ignores_observation_time_and_rejects_duplicates():
    base = {
        "provider": "cfbd",
        "entity": "plays",
        "endpoint": "PlaysApi.get_plays",
        "parameters": {"year": 2015, "week": 1, "expected_game_ids": [1, 2]},
    }
    first = {**base, "requested_at": "2026-08-27T00:00:00Z"}
    retry = {**base, "requested_at": "2026-08-28T00:00:00Z"}
    assert catalog.source_request_sha(first) == catalog.source_request_sha(retry)
    assert catalog.canonical_request_plan([first]) == catalog.canonical_request_plan(
        [retry]
    )
    with pytest.raises(ValueError, match="duplicate semantic request"):
        catalog.canonical_request_plan([first, retry])


def test_request_set_resume_rejects_changed_successor_code_or_configuration(
    monkeypatch,
):
    request = {
        "provider": "cfbd",
        "entity": "plays",
        "endpoint": "PlaysApi.get_plays",
        "parameters": {"year": 2015, "week": 1},
    }
    header = {
        "contract_version": "play_capture_set_v2",
        "policy": {"version": "history_play_capture_v2"},
        "identity": {"code_sha": "old", "configuration_sha256": "old-config"},
        "requests": [request],
    }
    _connect(monkeypatch, _Cursor([("cfbd", "successor_history_2015_plays", header)]))
    with pytest.raises(ValueError, match="Immutable request-set conflict"):
        catalog.begin_or_resume_request_set(
            "postgresql://fixture",
            ingestion_run_id="r1:successor_history_2015_plays",
            provider="cfbd",
            entity="successor_history_2015_plays",
            requests=[request],
            policy={"version": "history_play_capture_v2"},
            contract_version="play_capture_set_v2",
            identity={"code_sha": "new", "configuration_sha256": "new-config"},
        )


def test_completed_request_capture_rejects_duplicate_or_mismatched_requests(
    monkeypatch,
):
    request = {
        "provider": "cfbd",
        "entity": "plays",
        "endpoint": "PlaysApi.get_plays",
        "parameters": {"year": 2015, "week": 1},
    }
    request_sha = catalog.source_request_sha(request)
    _connect(monkeypatch, _Cursor([[(request_sha, "capture-1", request)]]))
    assert catalog.completed_request_capture_ids("postgresql://fixture", "run") == {
        request_sha: "capture-1"
    }

    _connect(
        monkeypatch,
        _Cursor(
            [[(request_sha, "capture-1", request), (request_sha, "capture-2", request)]]
        ),
    )
    with pytest.raises(ValueError, match="duplicate"):
        catalog.completed_request_capture_ids("postgresql://fixture", "run")


def test_catalog_point_in_time_lookups_and_missing_results(monkeypatch):
    cursor = _Cursor(
        [
            ("v1", "1", "sha", "lake/v1"),
            ("v2", "1", "sha2", "lake/v2"),
            (
                "fixture",
                "games",
                datetime(2026, 8, 23, tzinfo=timezone.utc),
                None,
                {"week": 1},
                "content",
                "object",
                "lake/bronze/fixture",
                2,
                None,
                {"status": 200},
                "registered",
            ),
        ]
    )
    _connect(monkeypatch, cursor)
    assert catalog.dataset_ref_as_of("url", "games", "2026-08-23").version_id == "v1"
    assert (
        catalog.dataset_ref_for_partition_as_of(
            "url", "games", "2026-08-23", partitions={"season": 2026}
        ).version_id
        == "v2"
    )
    assert catalog.source_capture_by_id("url", "capture").state == "registered"

    _connect(monkeypatch, _Cursor([None]))
    with pytest.raises(LookupError, match="No validated games"):
        catalog.dataset_ref_as_of("url", "games", "2026-08-23")


def test_legacy_comparison_ref_selection_rejects_successor_and_ambiguous_rows(
    monkeypatch,
):
    rows = [
        (
            "legacy",
            "v1",
            "legacy-sha",
            "artifacts/preview/history/games-2019",
            {"seasons": [2019]},
            "2026-08-20T00:00:00Z",
            "2026-08-20T01:00:00Z",
            "v1",
        ),
        (
            "successor",
            "v1",
            "successor-sha",
            "artifacts/research/rating-successor-v2/r1/run/games-2019",
            {"seasons": [2019]},
            "2026-08-27T00:00:00Z",
            "2026-08-27T01:00:00Z",
            "v1",
        ),
    ]
    cursor = _Cursor([rows])
    _connect(monkeypatch, cursor)
    selected = catalog.legacy_dataset_ref_for_season(
        "postgresql://fixture", "games", "2026-08-27T12:00:00Z", season=2019
    )
    assert selected.version_id == "legacy"
    # Successor-v2 research writes dataset_identity_v2 rows whose lake/silver
    # URIs evade the research-prefix exclusion; the selection must pin the
    # pre-successor v1 registration lineage in SQL.
    selection_sql = " ".join(sql for sql, _ in cursor.executed)
    assert "identity_version = 'v1'" in selection_sql

    ambiguous = [
        (
            f"legacy-{index}",
            "v1",
            f"sha-{index}",
            f"artifacts/preview/history/games-2019-{index}",
            {"season": 2019},
            "2026-08-20T00:00:00Z",
            "2026-08-20T01:00:00Z",
            "v1",
        )
        for index in (1, 2)
    ]
    _connect(monkeypatch, _Cursor([ambiguous]))
    with pytest.raises(ValueError, match="Ambiguous"):
        catalog.legacy_dataset_ref_for_season(
            "postgresql://fixture", "games", "2026-08-27T12:00:00Z", season=2019
        )


def test_manifest_conversion_identity_checks_and_json_are_deterministic():
    ref = DatasetRef("games", "v1", "1", "sha", "lake/v1/ref.json")
    manifest = DatasetManifest(
        dataset="games",
        version_id="v1",
        tier="silver",
        schema_version="1",
        content_sha="sha",
        uri="lake/v1/ref.json",
        row_count=1,
        partitions={"season": 2026},
        created_at="2026-08-23T00:00:00Z",
        as_of="2026-08-23T00:00:00Z",
    )
    catalog._verify_ref_manifest(ref, manifest, "fixture-ref")
    assert catalog.ref_json(ref)["version_id"] == "v1"
    assert catalog._catalog_timestamp("2026-08-23T00:00:00Z").tzinfo is not None
    with pytest.raises(ValueError, match="disagree"):
        catalog._verify_ref_manifest(
            DatasetRef("games", "other", "1", "sha", "lake/v1/ref.json"),
            manifest,
            "fixture-ref",
        )


def test_dataset_registration_records_dependency_and_quality_surfaces(monkeypatch):
    class RegistrationCursor(_Cursor):
        def fetchone(self):
            return None

        def fetchall(self):
            return []

    cursor = RegistrationCursor()
    connection = _connect(monkeypatch, cursor)
    ref = DatasetRef("games", "v-register", "1", "sha", "lake/v-register/ref.json")
    manifest = DatasetManifest(
        dataset="games",
        version_id="v-register",
        tier="silver",
        schema_version="1",
        content_sha="sha",
        uri="lake/v-register/ref.json",
        row_count=1,
        partitions={"season": 2026},
        created_at="2026-08-23T00:00:00Z",
        as_of="2026-08-23T00:00:00Z",
        parent_versions=("parent",),
        source_capture_ids=("capture",),
        validation={"schema": True, "row_count": 1},
    )
    catalog.register_dataset_version("postgresql://fixture", ref, manifest)
    assert connection.commits == 1
    statements = "\n".join(sql for sql, _ in cursor.executed)
    assert "dataset_versions" in statements
    assert "dataset_dependencies" in statements
    assert "dataset_capture_dependencies" in statements
    assert "quality_results" in statements

    import pandas as pd

    cursor = RegistrationCursor()
    _connect(monkeypatch, cursor)
    catalog.register_reconciliation_results(
        "postgresql://fixture",
        pd.DataFrame(
            [
                {
                    "reconciliation_id": "r1",
                    "season": 2026,
                    "game_id": 1,
                    "classification": "matched",
                    "blocking": False,
                    "details": {"score": "ok"},
                }
            ]
        ),
        source_dataset_versions=["v-register"],
    )
    assert any("source_reconciliations" in sql for sql, _ in cursor.executed)
