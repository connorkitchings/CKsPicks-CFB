#!/usr/bin/env python3
"""Run and publish Contract 11A conditional forecast verification evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv

from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.forecast.conditional_verification import (
    ConditionalVerificationError,
    conditional_identity,
    publish_conditional_verification,
    publish_failure,
    run_conditional_verification,
    verify_conditional_publication,
)
from cks_picks_cfb.forecast.forecast_verification import VerificationError

ROOT = Path(__file__).resolve().parents[2]


class _Progress:
    """Secret-safe bounded stderr heartbeat for the long reconstruction."""

    def __init__(self, run_id: str, interval: float = 30.0) -> None:
        self.run_id = run_id
        self.interval = interval
        self.started = time.monotonic()
        self.phase = "initializing"
        self.fields: dict[str, Any] = {}
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.thread: threading.Thread | None = None

    def emit(self, event: str, /, **fields: Any) -> None:
        safe = {
            str(key): value
            for key, value in fields.items()
            if not any(
                marker in str(key).casefold()
                for marker in (
                    "credential",
                    "password",
                    "secret",
                    "token",
                    "access_key",
                )
            )
        }
        with self.lock:
            self.phase = event
            self.fields = safe
            self._write(event, safe)

    def _write(self, event: str, fields: dict[str, Any]) -> None:
        print(
            json.dumps(
                {
                    "event": event,
                    "phase": self.phase,
                    "run_id": self.run_id,
                    "elapsed_seconds": round(time.monotonic() - self.started, 3),
                    **fields,
                },
                sort_keys=True,
                default=str,
            ),
            file=sys.stderr,
            flush=True,
        )

    def start(self) -> None:
        def heartbeat() -> None:
            while not self.stop.wait(self.interval):
                with self.lock:
                    self._write("heartbeat", self.fields)

        self.thread = threading.Thread(target=heartbeat, daemon=True)
        self.thread.start()

    def close(self) -> None:
        self.stop.set()
        if self.thread is not None:
            self.thread.join(timeout=1.0)


def _git_sha() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def _clean_worktree() -> bool:
    return not subprocess.check_output(
        ["git", "status", "--porcelain=v1"], cwd=ROOT, text=True
    ).strip()


def _load_evidence(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        raise ConditionalVerificationError("reviewed evidence is unreadable") from exc
    if not isinstance(payload, dict):
        raise ConditionalVerificationError("reviewed evidence must be an object")
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id")
    parser.add_argument("--as-of")
    parser.add_argument("--expected-code-sha")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--preflight-evidence", type=Path)
    parser.add_argument("--verify-manifest-uri")
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = _parser().parse_args(argv)
    storage = get_storage(environment="preview")
    if args.verify_manifest_uri:
        print(
            json.dumps(
                verify_conditional_publication(
                    storage, manifest_uri=args.verify_manifest_uri
                ),
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if not args.run_id or not args.as_of or not args.expected_code_sha:
        raise ConditionalVerificationError(
            "--run-id, --as-of, and --expected-code-sha are required"
        )
    if pd.Timestamp(args.as_of).tzinfo is None:
        raise ConditionalVerificationError("--as-of must be timezone-aware")
    if _git_sha() != args.expected_code_sha:
        raise ConditionalVerificationError("expected code SHA differs from HEAD")
    identity = conditional_identity(
        run_id=args.run_id,
        as_of=args.as_of,
        code_sha=args.expected_code_sha,
    )
    if args.apply and (args.preflight_evidence is None or not _clean_worktree()):
        raise ConditionalVerificationError(
            "--apply requires reviewed evidence and a clean committed worktree"
        )
    progress = _Progress(args.run_id)
    progress.start()
    try:
        if not args.apply:
            result = run_conditional_verification(
                storage, identity=identity, progress=progress.emit
            )
        else:
            evidence = _load_evidence(args.preflight_evidence)
            try:
                result = publish_conditional_verification(
                    storage,
                    identity=identity,
                    reviewed_evidence=evidence,
                    progress=progress.emit,
                )
            except VerificationError as exc:
                result = publish_failure(storage, identity=identity, error=exc)
    finally:
        progress.close()
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result.get("state") != "failed" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ConditionalVerificationError, VerificationError) as exc:
        print(f"conditional verification failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
