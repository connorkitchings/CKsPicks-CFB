"""Manifest-scoped non-play capture planning tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pandas as pd

from cks_picks_cfb.data.history_source_capture import (
    HistorySourceCapturePolicy,
    HistorySourceCaptureSet,
    transform_capture_records,
)
from cks_picks_cfb.data.lake import SourceCapture


class _Storage:
    def __init__(self, objects: dict[str, bytes]):
        self.objects = objects

    def read_bytes(self, uri: str) -> bytes:
        return self.objects[uri]


def test_source_worker_uses_canonical_transform_without_projection_writes():
    class _Ingester:
        def __init__(self):
            self.received = None

        def transform_data(self, raw_records):
            self.received = raw_records
            return [
                {
                    "id": 10,
                    "home_team": "Home",
                    "away_team": "Away",
                    "kickoff_utc": "2016-09-01T00:00:00+00:00",
                }
            ]

    raw = [SimpleNamespace(id=10)]
    ingester = _Ingester()

    records = transform_capture_records(ingester, raw)

    assert ingester.received == raw
    assert records[0]["home_team"] == "Home"
    assert records[0]["id"] == 10


def test_successor_venue_request_uses_exact_games_capture_manifest(monkeypatch):
    games_manifest_uri = "r1/captures/2016/games.json"
    storage = _Storage(
        {
            games_manifest_uri: json.dumps(
                {
                    "contract_version": "source-capture-entity-set-v2",
                    "state": "complete",
                    "season": 2016,
                    "entity": "games",
                    "requests": [{"capture_id": "games-capture"}],
                }
            ).encode()
        }
    )
    capture = SourceCapture(
        capture_id="games-capture",
        provider="cfbd",
        entity="games",
        captured_at=datetime(2026, 8, 28, tzinfo=timezone.utc),
        effective_at=None,
        request={},
        content_sha="content",
        object_sha="object",
        uri="lake/bronze/games",
        row_count=2,
        state="registered",
    )
    monkeypatch.setattr(
        "cks_picks_cfb.data.history_source_capture.source_capture_by_id",
        lambda *_: capture,
    )
    monkeypatch.setattr(
        "cks_picks_cfb.data.history_source_capture.read_source_capture",
        lambda *_: pd.DataFrame([{"venueId": 12}, {"venueId": 34}]),
    )
    policy = HistorySourceCapturePolicy(
        version="fixture",
        provider="cfbd",
        max_concurrency=1,
        sdk_request_timeout_seconds=1,
        worker_timeout_seconds=1,
        max_attempts=1,
        retry={"base_delay_seconds": 0, "max_delay_seconds": 0},
    )
    capture_set = HistorySourceCaptureSet(
        conn_url="postgresql://fixture",
        storage=storage,
        pipeline_run_id="r1",
        season=2016,
        entity="venues",
        manifest_uri="r1/captures/2016/venues.json",
        identity={},
        games_manifest_uri=games_manifest_uri,
        policy=policy,
    )

    requests = capture_set._planned_requests()

    assert len(requests) == 1
    assert requests[0]["parameters"]["expected_venue_ids"] == [12, 34]
    assert "raw/games" not in json.dumps(requests)


def test_successor_game_stats_requests_use_exact_games_capture_manifest(monkeypatch):
    games_manifest_uri = "r1/captures/2016/games.json"
    storage = _Storage(
        {
            games_manifest_uri: json.dumps(
                {
                    "contract_version": "source-capture-entity-set-v2",
                    "state": "complete",
                    "season": 2016,
                    "entity": "games",
                    "requests": [{"capture_id": "games-capture"}],
                }
            ).encode()
        }
    )
    capture = SourceCapture(
        capture_id="games-capture",
        provider="cfbd",
        entity="games",
        captured_at=datetime(2026, 8, 28, tzinfo=timezone.utc),
        effective_at=None,
        request={},
        content_sha="content",
        object_sha="object",
        uri="lake/bronze/games",
        row_count=3,
        state="registered",
    )
    monkeypatch.setattr(
        "cks_picks_cfb.data.history_source_capture.source_capture_by_id",
        lambda *_: capture,
    )
    monkeypatch.setattr(
        "cks_picks_cfb.data.history_source_capture.read_source_capture",
        lambda *_: pd.DataFrame(
            [
                {"id": 10, "week": 1, "seasonType": "regular"},
                {"id": 11, "week": 1, "seasonType": "regular"},
                {"id": 12, "week": 16, "seasonType": "postseason"},
            ]
        ),
    )
    policy = HistorySourceCapturePolicy(
        version="fixture",
        provider="cfbd",
        max_concurrency=1,
        sdk_request_timeout_seconds=1,
        worker_timeout_seconds=1,
        max_attempts=1,
        retry={"base_delay_seconds": 0, "max_delay_seconds": 0},
    )
    capture_set = HistorySourceCaptureSet(
        conn_url="postgresql://fixture",
        storage=storage,
        pipeline_run_id="r1",
        season=2016,
        entity="game_stats",
        manifest_uri="r1/captures/2016/game_stats.json",
        identity={},
        games_manifest_uri=games_manifest_uri,
        policy=policy,
    )

    requests = capture_set._planned_requests()

    assert len(requests) == 1
    assert requests[0]["parameters"]["expected_game_ids"] == [10, 11]
    assert "raw/games" not in json.dumps(requests)
