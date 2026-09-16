#!/usr/bin/env python3
"""Preflight the sealed Preview-only V5-03 possession-rating tournament.

This command intentionally defaults to a no-write preflight.  The dry run loads
the exact R6/Repair v2 parents read-only, constructs every chronological prior
and pregame state for the sealed 60-candidate registry, runs the common bridge
and selection tournament, and prints complete deterministic preflight evidence
(part plans, row counts, record digests, and the selected identity).  An
immutable apply is accepted only after the exact committed code SHA is
available; the runner refuses to create a partial ratings prefix while evidence
construction is still incomplete.
"""

from __future__ import annotations

import argparse
import atexit
import hashlib
import json
import subprocess
import sys
import threading
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_possession_rating_v1 import (
    POSSESSION_RATING_OUTPUT_ROOT,
    candidate_registry,
    rating_identity,
    validate_config,
    verify_parents,
)
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ratings.possession_rating_materializer import (
    compute_tournament,
    load_rating_inputs,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "conf/research/data_first_football_v1/possession_rating_v1.yaml"


class PossessionRatingRunError(ValueError):
    """Raised before a V5-03 run can produce immutable output."""


class _Progress:
    """Bounded, secret-safe stderr progress heartbeat for long phases."""

    def __init__(self, run_id: str, interval_seconds: float = 30.0) -> None:
        self.run_id = run_id
        self.interval_seconds = interval_seconds
        self.started = time.monotonic()
        self.last = float("-inf")
        self.phase = "initializing"
        self.context: dict[str, Any] = {}
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.thread: threading.Thread | None = None

    @staticmethod
    def _safe(fields: Mapping[str, Any]) -> dict[str, Any]:
        blocked = ("credential", "password", "secret", "token", "access_key")
        return {
            str(key): value
            for key, value in fields.items()
            if not any(marker in str(key).casefold() for marker in blocked)
        }

    def emit(self, event: str, /, **fields: Any) -> None:
        now = time.monotonic()
        safe = self._safe(fields)
        with self.lock:
            self.phase = str(safe.pop("phase", event))
            self.context = safe
            if now - self.last < self.interval_seconds and event != "heartbeat":
                if event not in {
                    "tournament_started",
                    "r6_stream_started",
                    "history_audit_started",
                }:
                    return
            self.last = now
            self._write(event, self.phase, safe, now)

    def _write(
        self, event: str, phase: str, fields: Mapping[str, Any], now: float
    ) -> None:
        print(
            json.dumps(
                {
                    "event": event,
                    "phase": phase,
                    "run_id": self.run_id,
                    "elapsed_seconds": round(now - self.started, 3),
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
            while not self.stop.wait(self.interval_seconds):
                with self.lock:
                    now = time.monotonic()
                    self._write("heartbeat", self.phase, self.context, now)
                    self.last = now

        self.thread = threading.Thread(
            target=heartbeat,
            name=f"possession-rating-progress-{self.run_id}",
            daemon=True,
        )
        self.thread.start()

    def close(self) -> None:
        self.stop.set()
        if self.thread is not None:
            self.thread.join(timeout=min(self.interval_seconds, 1.0))


def _git_sha() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def _clean_worktree() -> bool:
    return not subprocess.check_output(
        ["git", "status", "--porcelain=v1"], cwd=ROOT, text=True
    ).strip()


def preflight(*, storage: object, args: argparse.Namespace) -> dict[str, object]:
    config_path = Path(args.config)
    config = yaml.safe_load(config_path.read_text())
    validate_config(config)
    measurement_raw = storage.read_bytes(args.measurement_manifest_uri)
    repair_raw = storage.read_bytes(args.repair_manifest_uri)
    measurement, repair = verify_parents(
        json.loads(measurement_raw), json.loads(repair_raw)
    )
    config_sha = hashlib.sha256(config_path.read_bytes()).hexdigest()
    identity = rating_identity(
        run_id=args.run_id,
        as_of=args.as_of,
        code_sha=args.expected_code_sha,
        config_sha=config_sha,
        measurement_manifest_uri=args.measurement_manifest_uri,
        measurement_manifest_raw_sha256=hashlib.sha256(measurement_raw).hexdigest(),
        repair_manifest_uri=args.repair_manifest_uri,
        repair_manifest_raw_sha256=hashlib.sha256(repair_raw).hexdigest(),
    )
    progress = _Progress(args.run_id)
    progress.start()
    atexit.register(progress.close)
    progress.emit("dry_run_started", force=True)
    inputs = load_rating_inputs(
        storage=storage,
        measurement=measurement,
        repair=repair,
        progress=progress.emit,
    )
    computation = compute_tournament(inputs=inputs, progress=progress.emit)
    progress.emit("dry_run_complete", force=True)
    progress.close()
    return {
        "state": "dry_run",
        "identity": identity,
        "candidate_count": len(candidate_registry()),
        "candidates": [item["candidate_id"] for item in candidate_registry()],
        "measurement_parent": measurement["identity"]["run_id"],
        "repair_parent": repair["identity"]["run_id"],
        "output_prefix": f"{POSSESSION_RATING_OUTPUT_ROOT}/{args.run_id}",
        "source_refs": inputs.source_refs,
        "population_sha256": inputs.population_sha256,
        **computation.preflight_evidence(),
        "production_activation_authorized": False,
    }


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--environment", required=True, choices=("preview",))
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--measurement-manifest-uri", required=True)
    parser.add_argument("--repair-manifest-uri", required=True)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    if _git_sha() != args.expected_code_sha:
        raise PossessionRatingRunError(
            "expected code SHA does not match committed HEAD"
        )
    storage = get_storage(environment="preview")
    evidence = preflight(storage=storage, args=args)
    if args.apply:
        if not _clean_worktree():
            raise PossessionRatingRunError(
                "apply requires a completely clean committed worktree"
            )
        # Do not create an immutable prefix until the evidence-bound apply path
        # is supplied by Contract 03B.  This prevents a dry-run prefix from
        # being mistaken for a downstream-eligible rating parent.
        raise PossessionRatingRunError(
            "V5-03 apply is blocked pending the evidence-bound materializer"
        )
    print(json.dumps(evidence, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
