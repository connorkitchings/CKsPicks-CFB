from __future__ import annotations

import json
import subprocess

import pytest

from cks_picks_cfb.data.history_play_capture import (
    HistoryPlayCaptureError,
    load_history_play_capture_policy,
    manifest_capture_ids,
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
    assert policy.version == "history_play_capture_v1"
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
        manifest_capture_ids(_MemoryStorage({uri: json.dumps(incomplete).encode()}), uri)

    duplicate = {**complete, "requests": [{"capture_id": "one"}, {"capture_id": "one"}]}
    with pytest.raises(HistoryPlayCaptureError, match="invalid capture IDs"):
        manifest_capture_ids(_MemoryStorage({uri: json.dumps(duplicate).encode()}), uri)


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
    policy = type(policy)(
        **{**policy.__dict__, "worker_timeout_seconds": 0.001}
    )
    request = {
        "provider": "cfbd",
        "entity": "plays",
        "endpoint": "PlaysApi.get_plays",
        "parameters": {"year": 2015, "week": 1, "season_type": "regular", "classification": "fbs", "expected_game_ids": [1]},
    }
    with pytest.raises(subprocess.TimeoutExpired):
        run_isolated_play_worker(request, policy=policy)
    assert signals == [(123, 15)]
