"""Bounded read retries and staged-leftover cleanup."""

from __future__ import annotations

import pytest

from cks_picks_cfb.rebuild.retry import RetryingStorage, is_transient, with_retries
from cks_picks_cfb.rebuild.targets import InMemoryStore


class ReadTimeoutError(Exception):  # name matches the botocore/urllib3 transient set
    pass


class Flaky:
    def __init__(self, failures, error=ReadTimeoutError("t")):
        self.failures, self.error, self.calls = failures, error, 0

    def read_bytes(self, uri):
        self.calls += 1
        if self.calls <= self.failures:
            raise self.error
        return b"ok"

    def write_bytes(self, data, uri):
        self.calls += 1
        raise self.error


def test_transient_errors_are_retried_then_succeed():
    inner = Flaky(2)
    storage = RetryingStorage(inner, sleep=lambda _: None)
    assert storage.read_bytes("x") == b"ok" and inner.calls == 3


def test_last_transient_and_non_transient_errors_propagate():
    exhausted = Flaky(10)
    with pytest.raises(ReadTimeoutError):
        RetryingStorage(exhausted, attempts=3, sleep=lambda _: None).read_bytes("x")
    assert exhausted.calls == 3
    permanent = Flaky(1, error=ValueError("bad"))
    with pytest.raises(ValueError):
        RetryingStorage(permanent, sleep=lambda _: None).read_bytes("x")
    assert permanent.calls == 1


def test_writes_are_never_retried():
    inner = Flaky(0)
    with pytest.raises(ReadTimeoutError):
        RetryingStorage(inner, sleep=lambda _: None).write_bytes(b"d", "x")
    assert inner.calls == 1


def test_is_transient_classification():
    assert is_transient(TimeoutError()) and is_transient(ConnectionResetError())
    assert not is_transient(ValueError()) and not is_transient(KeyError("k"))
    assert with_retries(lambda: 5) == 5


def test_discard_prefix_removes_only_that_stage():
    store = InMemoryStore()
    for key in ("stages/a/x", "stages/a/y", "stages/b/x"):
        store.put_if_absent(key, b"1")
    store.discard_prefix("stages/a/")
    assert sorted(store.objects) == ["stages/b/x"]
