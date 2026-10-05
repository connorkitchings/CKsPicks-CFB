"""Bounded retries for transient object-store read failures.

A single R2 read timeout aborted a multi-minute stage once. Reads are idempotent, so they
are retried a few times with backoff; any non-transient error, and the last transient one,
still propagates unchanged. Writes are never retried here.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

TRANSIENT_NAMES = frozenset(
    {
        "ReadTimeoutError",
        "ConnectTimeoutError",
        "ConnectionClosedError",
        "EndpointConnectionError",
        "IncompleteReadError",
        "ResponseStreamingError",
        "ProtocolError",
    }
)
RETRIED_METHODS = frozenset({"read_bytes", "read_parquet", "read_csv"})


def is_transient(error: BaseException) -> bool:
    if isinstance(error, (TimeoutError, ConnectionError)):
        return True
    return any(cls.__name__ in TRANSIENT_NAMES for cls in type(error).__mro__)


def with_retries(
    call: Callable[[], Any],
    *,
    attempts: int = 4,
    delay: float = 2.0,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    for attempt in range(1, attempts + 1):
        try:
            return call()
        except BaseException as error:  # noqa: BLE001 - re-raised unless transient
            if attempt == attempts or not is_transient(error):
                raise
            sleep(delay * attempt)
    raise AssertionError("unreachable")


class RetryingStorage:
    """Proxy that retries only the idempotent read methods of a storage backend."""

    def __init__(
        self, inner: Any, *, attempts: int = 4, delay: float = 2.0, sleep=time.sleep
    ):
        self._inner = inner
        self._attempts = attempts
        self._delay = delay
        self._sleep = sleep

    def __getattr__(self, name: str) -> Any:
        attribute = getattr(self._inner, name)
        if name not in RETRIED_METHODS or not callable(attribute):
            return attribute

        def retried(*args: Any, **kwargs: Any) -> Any:
            return with_retries(
                lambda: attribute(*args, **kwargs),
                attempts=self._attempts,
                delay=self._delay,
                sleep=self._sleep,
            )

        return retried
