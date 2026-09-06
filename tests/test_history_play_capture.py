from __future__ import annotations

import json
import subprocess

import pandas as pd
import pytest

from cks_picks_cfb.data.history_play_capture import (
    HistoryPlayCaptureError,
    HistoryPlayCapturePolicy,
    HistoryPlayCaptureSet,
    load_history_play_capture_policy,
    manifest_capture_ids,
    manifest_declared_missing_game_ids,
    run_isolated_play_worker,
)


class _MemoryStorage:
    def __init__(self, objects: dict[str, bytes]):
        self.objects = objects

    def exists(self, uri: str) -> bool:
        return uri in self.objects

    def read_bytes(self, uri: str) -> bytes:
        return self.objects[uri]


def test_history_play_policy_is_sequential_and_hashed():
    policy = load_history_play_capture_policy()
    assert policy.version == "history_play_capture_v2"
    assert policy.max_concurrency == 1
    assert policy.sdk_request_timeout_seconds == 120
    assert policy.worker_timeout_seconds == 300
    assert policy.max_attempts == 4
    assert len(policy.sha256) == 64


def test_manifest_capture_ids_requires_one_complete_ordered_set():
    uri = "artifacts/research/rating-successor-v2/r1/run/plays-2015-capture-set.json"
    complete = {
        "contract_version": "play-capture-set-v1",
        "state": "complete",
        "requests": [{"capture_id": "one"}, {"capture_id": "two"}],
    }
    storage = _MemoryStorage({uri: json.dumps(complete).encode()})
    assert manifest_capture_ids(storage, uri) == ["one", "two"]

    incomplete = {**complete, "state": "failed"}
    with pytest.raises(HistoryPlayCaptureError, match="not complete"):
        manifest_capture_ids(
            _MemoryStorage({uri: json.dumps(incomplete).encode()}), uri
        )

    duplicate = {**complete, "requests": [{"capture_id": "one"}, {"capture_id": "one"}]}
    with pytest.raises(HistoryPlayCaptureError, match="invalid capture IDs"):
        manifest_capture_ids(_MemoryStorage({uri: json.dumps(duplicate).encode()}), uri)


def test_manifest_declared_missing_game_ids_requires_complete_exact_coverage():
    uri = "artifacts/research/rating-successor-v2/r1/run/captures/2015/plays.json"
    manifest = {
        "contract_version": "play-capture-set-v2",
        "state": "complete",
        "season": 2015,
        "requests": [
            {
                "capture_id": "one",
                "request": {"parameters": {"year": 2015, "expected_game_ids": [1, 2]}},
                "returned_game_ids": [1],
                "missing_game_ids": [2],
                "extra_game_ids": [],
            },
            {
                "capture_id": "two",
                "request": {"parameters": {"year": 2015, "expected_game_ids": [3]}},
                "returned_game_ids": [3],
                "missing_game_ids": [],
                "extra_game_ids": [],
            },
        ],
    }
    storage = _MemoryStorage({uri: json.dumps(manifest).encode()})
    assert manifest_declared_missing_game_ids(storage, uri, season=2015) == {2}

    malformed = {
        **manifest,
        "requests": [
            {
                **manifest["requests"][0],
                "returned_game_ids": [1],
                "missing_game_ids": [],
            }
        ],
    }
    with pytest.raises(HistoryPlayCaptureError, match="coverage mismatches"):
        manifest_declared_missing_game_ids(
            _MemoryStorage({uri: json.dumps(malformed).encode()}), uri, season=2015
        )

    wrong_season = {**manifest, "season": 2016}
    with pytest.raises(HistoryPlayCaptureError, match="incomplete or mismatched"):
        manifest_declared_missing_game_ids(
            _MemoryStorage({uri: json.dumps(wrong_season).encode()}), uri, season=2015
        )


def test_successor_play_requests_use_exact_games_capture_manifest(monkeypatch):
    games_manifest_uri = "r1/captures/2016/games.json"
    storage = _MemoryStorage(
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
    monkeypatch.setattr(
        "cks_picks_cfb.data.history_play_capture.source_capture_by_id",
        lambda *_: object(),
    )
    monkeypatch.setattr(
        "cks_picks_cfb.data.history_play_capture.read_source_capture",
        lambda *_: pd.DataFrame(
            [
                {"id": 10, "week": 1, "seasonType": "regular"},
                {"id": 11, "week": 1, "seasonType": "regular"},
                {"id": 12, "week": 16, "seasonType": "postseason"},
            ]
        ),
    )
    policy = HistoryPlayCapturePolicy(
        version="fixture",
        provider="cfbd",
        entity="plays",
        max_concurrency=1,
        sdk_request_timeout_seconds=1,
        worker_timeout_seconds=1,
        max_attempts=1,
        retry={"base_delay_seconds": 0, "max_delay_seconds": 0},
    )
    capture_set = HistoryPlayCaptureSet(
        conn_url="postgresql://fixture",
        storage=storage,
        pipeline_run_id="r1",
        season=2016,
        manifest_uri="r1/captures/2016/plays.json",
        games_manifest_uri=games_manifest_uri,
        policy=policy,
    )

    requests = capture_set._planned_requests()

    assert len(requests) == 1
    assert requests[0]["parameters"]["expected_game_ids"] == [10, 11]
    assert "raw/games" not in json.dumps(requests)


def test_stalled_worker_terminates_its_process_group(monkeypatch):
    class StalledProcess:
        pid = 123
        returncode = None
        terminated = False

        def wait(self, timeout):
            if self.terminated:
                self.returncode = -15
                return self.returncode
            raise subprocess.TimeoutExpired(["worker"], timeout)

        def poll(self):
            return self.returncode

    process = StalledProcess()
    signals = []
    monkeypatch.setattr(
        "cks_picks_cfb.data.history_play_capture.subprocess.Popen",
        lambda *_args, **_kwargs: process,
    )

    def killpg(pid, signal):
        signals.append((pid, signal))
        process.terminated = True

    monkeypatch.setattr("cks_picks_cfb.data.history_play_capture.os.killpg", killpg)
    policy = load_history_play_capture_policy()
    policy = type(policy)(**{**policy.__dict__, "worker_timeout_seconds": 0.001})
    request = {
        "provider": "cfbd",
        "entity": "plays",
        "endpoint": "PlaysApi.get_plays",
        "parameters": {
            "year": 2015,
            "week": 1,
            "season_type": "regular",
            "classification": "fbs",
            "expected_game_ids": [1],
        },
    }
    with pytest.raises(subprocess.TimeoutExpired):
        run_isolated_play_worker(request, policy=policy)
    assert signals == [(123, 15)]
