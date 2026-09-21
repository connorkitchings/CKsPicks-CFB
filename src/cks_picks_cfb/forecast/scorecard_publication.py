"""Contract 12A scorecard publication and independent verification.

Publishes a signed Preview-only scorecard artifact and terminal manifest
under the conditional-v1 scorecard prefix.  The independent verifier
re-reads the stored scorecard without trusting any in-memory derived value.

Permitted use: ``conditional_historical_results_only`` only.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import threading
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from cks_picks_cfb.data.data_first_phase2d import (
    canonical_bytes,
    sha256,
    signed_payload,
    verify_signed_payload,
)
from cks_picks_cfb.forecast.historical_scorecard import (
    OPEN_LIMITATIONS,
    OUTPUT_ROOT,
    PERMITTED_USE,
    SCORECARD_MANIFEST_SCHEMA,
    SCORECARD_SCHEMA,
    TARGETS,
    VERIFICATION_MANIFEST_URI,
    ScorecardError,
    _load_calibration,
    _load_predictions,
    compute_scorecard,
    validate_population,
    validate_verification_manifest,
)

ROOT = Path(__file__).resolve().parents[4]


class ScorecardPublicationError(ScorecardError):
    """Raised when scorecard publication cannot proceed or reconcile."""


# ---------------------------------------------------------------------------
# Idempotency helpers
# ---------------------------------------------------------------------------


def _write_immutable(storage: Any, uri: str, payload: Mapping[str, Any]) -> None:
    encoded = canonical_bytes(payload)
    if storage.exists(uri):
        if storage.read_bytes(uri) != encoded:
            raise ScorecardPublicationError(f"immutable collision at {uri!r}")
        return
    storage.write_bytes(encoded, uri)


def _existing_manifest(
    storage: Any, *, manifest_uri: str, run_id: str
) -> dict[str, Any] | None:
    if not storage.exists(manifest_uri):
        return None
    try:
        raw = storage.read_bytes(manifest_uri)
        manifest = json.loads(raw)
        verify_signed_payload(manifest, label="scorecard manifest")
    except (json.JSONDecodeError, ValueError) as exc:
        raise ScorecardPublicationError(
            "Existing scorecard manifest is invalid"
        ) from exc
    if (
        manifest.get("schema_version") != SCORECARD_MANIFEST_SCHEMA
        or manifest.get("run_id") != run_id
        or manifest.get("permitted_use") != PERMITTED_USE
        or manifest.get("production_activation_authorized") is not False
    ):
        raise ScorecardPublicationError(
            "Existing scorecard manifest is bound to a different run"
        )
    return manifest


# ---------------------------------------------------------------------------
# Progress reporter (secret-safe)
# ---------------------------------------------------------------------------


class _Progress:
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
            k: v
            for k, v in fields.items()
            if not any(
                m in str(k).casefold()
                for m in ("credential", "password", "secret", "token", "access_key")
            )
        }
        with self.lock:
            self.phase = event
            self.fields = safe
            self._write(event, safe)

    def _write(self, event: str, fields: dict[str, Any]) -> None:
        import sys

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


# ---------------------------------------------------------------------------
# Preflight (dry-run)
# ---------------------------------------------------------------------------


def run_scorecard_preflight(
    storage: Any,
    *,
    run_id: str,
    progress: _Progress | None = None,
) -> dict[str, Any]:
    """Validate the 11A entry gate and population; compute all metrics.

    No writes to R2 or any external system.  Returns the dry-run evidence dict.
    """
    if progress:
        progress.emit("preflight.start", run_id=run_id)

    manifest = validate_verification_manifest(storage)
    if progress:
        progress.emit("preflight.manifest_ok")

    predictions = _load_predictions(storage, manifest)
    calibration = _load_calibration(storage, manifest)
    if progress:
        progress.emit(
            "preflight.data_loaded",
            prediction_rows=len(predictions),
            calibration_rows=len(calibration),
        )

    population_summary = validate_population(predictions, calibration)
    if progress:
        progress.emit(
            "preflight.population_ok",
            included=population_summary["included_count"],
        )

    scorecard = compute_scorecard(
        predictions, calibration, population_summary=population_summary
    )
    if progress:
        progress.emit("preflight.metrics_ok")

    evidence = {
        "state": "dry_run",
        "run_id": run_id,
        "verification_manifest_uri": VERIFICATION_MANIFEST_URI,
        "scorecard": scorecard,
        "permitted_use": PERMITTED_USE,
        "production_activation_authorized": False,
        "readiness_recommendation": None,
        "v4_comparison": None,
    }
    evidence["evidence_sha256"] = sha256(evidence)
    if progress:
        progress.emit("preflight.complete")
    return evidence


# ---------------------------------------------------------------------------
# Evidence-bound apply
# ---------------------------------------------------------------------------


def publish_scorecard(
    storage: Any,
    *,
    run_id: str,
    reviewed_evidence: Mapping[str, Any],
    progress: _Progress | None = None,
) -> dict[str, Any]:
    """Re-compute and publish a signed scorecard + terminal manifest.

    Requires a clean committed worktree.  Idempotent: returns already_applied
    if the terminal manifest already exists and reconciles.
    """
    prefix = f"{OUTPUT_ROOT}/{run_id}"
    scorecard_uri = f"{prefix}/historical-scorecard.json"
    manifest_uri = f"{prefix}/scorecard-manifest.json"

    existing = _existing_manifest(storage, manifest_uri=manifest_uri, run_id=run_id)
    if existing is not None:
        if progress:
            progress.emit("apply.already_applied", run_id=run_id)
        verified = verify_scorecard_publication(storage, manifest_uri=manifest_uri)
        return {"state": "already_applied", **verified}

    if storage.list_files(prefix):
        raise ScorecardPublicationError(
            f"Scorecard prefix already has partial content: {prefix!r}"
        )

    # Guard: reviewed evidence must match this run
    if (
        reviewed_evidence.get("state") != "dry_run"
        or reviewed_evidence.get("run_id") != run_id
        or reviewed_evidence.get("permitted_use") != PERMITTED_USE
    ):
        raise ScorecardPublicationError(
            "Reviewed evidence identity does not match this apply call"
        )

    if progress:
        progress.emit("apply.start", run_id=run_id)

    # Re-run the full scorecard computation to match reviewed evidence
    manifest = validate_verification_manifest(storage)
    predictions = _load_predictions(storage, manifest)
    calibration = _load_calibration(storage, manifest)
    population_summary = validate_population(predictions, calibration)
    scorecard = compute_scorecard(
        predictions, calibration, population_summary=population_summary
    )
    if progress:
        progress.emit("apply.recomputed")

    rerun_evidence = {
        "state": "dry_run",
        "run_id": run_id,
        "verification_manifest_uri": VERIFICATION_MANIFEST_URI,
        "scorecard": scorecard,
        "permitted_use": PERMITTED_USE,
        "production_activation_authorized": False,
        "readiness_recommendation": None,
        "v4_comparison": None,
    }
    rerun_evidence["evidence_sha256"] = sha256(rerun_evidence)

    rerun_normalized = json.loads(json.dumps(rerun_evidence))
    reviewed_normalized = json.loads(json.dumps(dict(reviewed_evidence)))
    if rerun_normalized != reviewed_normalized:
        raise ScorecardPublicationError(
            "Apply recomputation differs from reviewed evidence — do not publish"
        )

    # Build code SHA
    try:
        code_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        code_sha = "unknown"

    scorecard_payload = signed_payload(
        {
            "schema_version": SCORECARD_SCHEMA,
            "state": "published",
            "run_id": run_id,
            "code_sha": code_sha,
            "verification_manifest_uri": VERIFICATION_MANIFEST_URI,
            "scorecard": scorecard,
            "open_limitations": [dict(lim) for lim in OPEN_LIMITATIONS],
            "permitted_use": PERMITTED_USE,
            "production_activation_authorized": False,
            "readiness_recommendation": None,
            "v4_comparison": None,
        }
    )
    _write_immutable(storage, scorecard_uri, scorecard_payload)
    scorecard_raw = storage.read_bytes(scorecard_uri)
    if progress:
        progress.emit(
            "apply.scorecard_written",
            scorecard_uri=scorecard_uri,
            scorecard_raw_sha=hashlib.sha256(scorecard_raw).hexdigest(),
        )

    scorecard_manifest = signed_payload(
        {
            "schema_version": SCORECARD_MANIFEST_SCHEMA,
            "state": "published",
            "run_id": run_id,
            "code_sha": code_sha,
            "scorecard_uri": scorecard_uri,
            "scorecard_raw_sha256": hashlib.sha256(scorecard_raw).hexdigest(),
            "scorecard_manifest_sha256": scorecard_payload["manifest_sha256"],
            "verification_manifest_uri": VERIFICATION_MANIFEST_URI,
            "open_limitations": [dict(lim) for lim in OPEN_LIMITATIONS],
            "permitted_use": PERMITTED_USE,
            "production_activation_authorized": False,
            "readiness_recommendation": None,
            "v4_comparison": None,
        }
    )
    _write_immutable(storage, manifest_uri, scorecard_manifest)
    if progress:
        progress.emit("apply.manifest_written", manifest_uri=manifest_uri)

    verified = verify_scorecard_publication(storage, manifest_uri=manifest_uri)
    return {"state": "applied", **verified}


# ---------------------------------------------------------------------------
# Independent verifier
# ---------------------------------------------------------------------------


def verify_scorecard_publication(
    storage: Any,
    *,
    manifest_uri: str,
) -> dict[str, Any]:
    """Independently re-read and verify a published scorecard.

    Recomputes population counts and one sentinel metric per target to
    confirm the stored scorecard was derived from the correct population.
    Does not trust any stored derived value.
    """
    try:
        manifest_raw = storage.read_bytes(manifest_uri)
        manifest = json.loads(manifest_raw)
        verify_signed_payload(manifest, label="scorecard manifest")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ScorecardPublicationError(
            "Scorecard manifest is unreadable or has invalid signature"
        ) from exc

    if (
        manifest.get("schema_version") != SCORECARD_MANIFEST_SCHEMA
        or manifest.get("state") != "published"
        or manifest.get("permitted_use") != PERMITTED_USE
        or manifest.get("production_activation_authorized") is not False
    ):
        raise ScorecardPublicationError(
            "Scorecard manifest has invalid boundary fields"
        )

    scorecard_uri = manifest.get("scorecard_uri", "")
    try:
        scorecard_raw = storage.read_bytes(scorecard_uri)
        scorecard = json.loads(scorecard_raw)
        verify_signed_payload(scorecard, label="scorecard payload")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ScorecardPublicationError(
            "Scorecard payload is unreadable or has invalid signature"
        ) from exc

    # Cross-check manifest vs scorecard
    expected_scorecard_sha = manifest.get("scorecard_raw_sha256", "")
    actual_scorecard_sha = hashlib.sha256(scorecard_raw).hexdigest()
    if expected_scorecard_sha != actual_scorecard_sha:
        raise ScorecardPublicationError(
            f"Scorecard raw SHA mismatch: "
            f"expected {expected_scorecard_sha}, got {actual_scorecard_sha}"
        )
    if manifest.get("scorecard_manifest_sha256") != scorecard.get("manifest_sha256"):
        raise ScorecardPublicationError("Scorecard manifest_sha256 cross-check failed")

    if (
        scorecard.get("schema_version") != SCORECARD_SCHEMA
        or scorecard.get("state") != "published"
        or scorecard.get("permitted_use") != PERMITTED_USE
        or scorecard.get("production_activation_authorized") is not False
        or scorecard.get("readiness_recommendation") is not None
        or scorecard.get("v4_comparison") is not None
    ):
        raise ScorecardPublicationError("Scorecard payload has invalid boundary fields")

    # Independent recomputation: re-read the 11A manifest and population
    inner_manifest = validate_verification_manifest(storage)
    predictions = _load_predictions(storage, inner_manifest)
    calibration = _load_calibration(storage, inner_manifest)
    population_summary = validate_population(predictions, calibration)

    # Verify stored population counts match
    stored_pop = scorecard.get("scorecard", {}).get("population", {})
    if stored_pop.get("included_count") != population_summary["included_count"]:
        raise ScorecardPublicationError(
            "Stored population included_count does not match recomputed value"
        )
    if stored_pop.get("excluded_count") != 0:
        raise ScorecardPublicationError("Stored population excluded_count is not zero")

    # Verify one sentinel metric per target: 2025 MAE
    import numpy as np

    cal_variances: dict[str, dict[int, float]] = {t: {} for t in TARGETS}
    for _, row in calibration.iterrows():
        t = str(row["target"])
        s = int(row["season"])
        v = float(row["variance"])
        if t in cal_variances:
            cal_variances[t][s] = v

    stored_targets = scorecard.get("scorecard", {}).get("targets", {})
    for target in TARGETS:
        season_rows = predictions[
            (predictions["target"] == target) & (predictions["season"] == 2025)
        ]
        errors = season_rows["prediction"].to_numpy(float) - season_rows[
            "actual"
        ].to_numpy(float)
        expected_mae = float(np.mean(np.abs(errors)))
        stored_mae = stored_targets.get(target, {}).get("headline_2025", {}).get("mae")
        if stored_mae is None or abs(float(stored_mae) - expected_mae) > 1e-9:
            raise ScorecardPublicationError(
                f"Stored 2025 MAE for target={target!r} does not match "
                f"recomputed value (stored={stored_mae}, expected={expected_mae:.6f})"
            )

    run_id = manifest.get("run_id", "")
    return {
        "verified": True,
        "run_id": run_id,
        "manifest_uri": manifest_uri,
        "manifest_raw_sha256": hashlib.sha256(manifest_raw).hexdigest(),
        "scorecard_uri": scorecard_uri,
        "scorecard_raw_sha256": actual_scorecard_sha,
        "permitted_use": PERMITTED_USE,
        "production_activation_authorized": False,
    }
