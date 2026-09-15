"""Bounded, machine-readable progress reporting for sealed research jobs."""

from __future__ import annotations

import json
import sys
import threading
import time
from collections.abc import Mapping
from typing import Any


class ResearchProgress:
    """Write flushed JSONL heartbeats to stderr without contaminating stdout."""

    def __init__(self, *, run_id: str, interval_seconds: float = 30.0) -> None:
        self.run_id = run_id
        self.interval_seconds = interval_seconds
        self.started = time.monotonic()
        self._last = 0.0
        self._phase = "initializing"
        self._context: dict[str, Any] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @staticmethod
    def _safe(fields: Mapping[str, Any]) -> dict[str, Any]:
        blocked = ("credential", "password", "secret", "token", "access_key")
        return {
            str(key): value
            for key, value in fields.items()
            if not any(marker in str(key).casefold() for marker in blocked)
        }

    def emit(self, event: str, /, *, force: bool = False, **fields: Any) -> None:
        now = time.monotonic()
        safe = self._safe(fields)
        with self._lock:
            self._phase = str(safe.pop("phase", event))
            self._context = safe
            if not force and now - self._last < self.interval_seconds:
                return
            payload: Mapping[str, Any] = {
                "event": event,
                "phase": self._phase,
                "run_id": self.run_id,
                "elapsed_seconds": round(now - self.started, 3),
                **safe,
            }
            print(
                json.dumps(payload, sort_keys=True, default=str),
                file=sys.stderr,
                flush=True,
            )
            self._last = now

    def start(self) -> None:
        """Start a daemon heartbeat for long blocking storage or compute calls."""
        if self._thread is not None:
            return

        def heartbeat() -> None:
            while not self._stop.wait(self.interval_seconds):
                with self._lock:
                    payload: Mapping[str, Any] = {
                        "event": "heartbeat",
                        "phase": self._phase,
                        "run_id": self.run_id,
                        "elapsed_seconds": round(time.monotonic() - self.started, 3),
                        **self._context,
                    }
                    print(
                        json.dumps(payload, sort_keys=True, default=str),
                        file=sys.stderr,
                        flush=True,
                    )
                    self._last = time.monotonic()

        self._thread = threading.Thread(
            target=heartbeat,
            name=f"research-progress-{self.run_id}",
            daemon=True,
        )
        self._thread.start()

    def close(self) -> None:
        """Stop the background heartbeat without delaying process exit."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=min(self.interval_seconds, 1.0))
