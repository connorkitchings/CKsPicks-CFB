#!/usr/bin/env python3
"""Independently validate the sealed V5-03 rating parent and retained manifest.

The envelope checks confirm the retained manifest is signed, frozen, and bound
to the expected code.  The independent verifier then re-reads the exact R6 and
Repair v2 parents, reconstructs every prior, state, bridge prediction, and the
complete selection without importing any producer module, compares each output
partition by canonical digest, and publishes a signed verifier manifest.
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
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload
from cks_picks_cfb.data.data_first_possession_rating_v1 import (
    POSSESSION_RATING_MANIFEST_SCHEMA,
    RATING_DATASETS,
    candidate_registry,
)
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ratings.possession_rating_verification import (
    IndependentRatingError,
    verify_rating_artifact,
)

ROOT = Path(__file__).resolve().parents[2]


class PossessionRatingVerificationError(ValueError):
    """Raised when a retained V5-03 artifact cannot be independently trusted."""


class _Heartbeat:
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

    def emit(self, event: str, /, **fields: Any) -> None:
        now = time.monotonic()
        safe = {
            str(key): value
            for key, value in fields.items()
            if not any(
                marker in str(key).casefold()
                for marker in ("credential", "password", "secret", "token")
            )
        }
        with self.lock:
            self.phase = str(safe.pop("phase", event))
            self.context = safe
            if now - self.last < self.interval_seconds and event != "heartbeat":
                if event not in {
                    "verifier_parents_started",
                    "tournament_started",
                    "history_audit_started",
                    "verification_complete",
                }:
                    return
            self.last = now
            print(
                json.dumps(
                    {
                        "event": event,
                        "phase": self.phase,
                        "run_id": self.run_id,
                        "elapsed_seconds": round(now - self.started, 3),
                        **safe,
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
                    print(
                        json.dumps(
                            {
                                "event": "heartbeat",
                                "phase": self.phase,
                                "run_id": self.run_id,
                                "elapsed_seconds": round(now - self.started, 3),
                                **self.context,
                            },
                            sort_keys=True,
                            default=str,
                        ),
                        file=sys.stderr,
                        flush=True,
                    )
                    self.last = now

        self.thread = threading.Thread(
            target=heartbeat, name=f"rating-verify-{self.run_id}", daemon=True
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


def verify_manifest(
    payload: dict[str, object], *, expected_code_sha: str
) -> dict[str, object]:
    if payload.get("schema_version") != POSSESSION_RATING_MANIFEST_SCHEMA:
        raise PossessionRatingVerificationError("unexpected retained rating schema")
    verify_signed_payload(payload, label="retained possession rating manifest")
    if (
        payload.get("state") != "frozen"
        or payload.get("production_activation_authorized") is not False
    ):
        raise PossessionRatingVerificationError(
            "retained rating violates research boundary"
        )
    identity = payload.get("identity") or {}
    if (
        identity.get("code_sha") != expected_code_sha
        or identity.get("environment") != "preview"
    ):
        raise PossessionRatingVerificationError(
            "retained rating code or environment mismatch"
        )
    if payload.get("selected_candidate") not in {
        item["candidate_id"] for item in candidate_registry()
    }:
        raise PossessionRatingVerificationError("unsealed selected candidate")
    if set((payload.get("output_refs") or {})) != set(RATING_DATASETS):
        raise PossessionRatingVerificationError(
            "retained rating lacks complete output evidence"
        )
    return payload


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-uri", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--environment", choices=("preview",), required=True)
    parser.add_argument("--measurement-manifest-uri", required=True)
    parser.add_argument("--repair-manifest-uri", required=True)
    args = parser.parse_args(argv)
    storage = get_storage(environment="preview")
    raw = storage.read_bytes(args.manifest_uri)
    verified = verify_manifest(
        json.loads(raw), expected_code_sha=args.expected_code_sha
    )
    run_id = str(((verified.get("identity") or {}).get("run_id")) or "rating-verify")
    progress = _Heartbeat(run_id)
    progress.start()
    atexit.register(progress.close)
    try:
        report = verify_rating_artifact(
            storage=storage,
            manifest=verified,
            manifest_uri=args.manifest_uri,
            measurement_manifest_uri=args.measurement_manifest_uri,
            repair_manifest_uri=args.repair_manifest_uri,
            verifier_code_sha=_git_sha(),
            progress=progress.emit,
        )
    except IndependentRatingError as exc:
        progress.close()
        raise PossessionRatingVerificationError(
            f"independent rating verification failed: {exc}"
        ) from exc
    progress.close()
    report["manifest_raw_sha256"] = hashlib.sha256(raw).hexdigest()
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
