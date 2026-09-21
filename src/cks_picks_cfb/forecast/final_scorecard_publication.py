"""Contract 12 V5 historical scorecard publication and independent verification.

Publishes a signed Preview-only scorecard artifact and terminal manifest
under the full-v1 scorecard prefix:
artifacts/research/data-first-football-v1/historical-scorecards/full-v1/runs/<run_id>/

The independent verifier re-reads the stored scorecard without trusting any
in-memory derived value.

Permitted use: ``historical_readiness_review_only``.
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
from cks_picks_cfb.forecast.final_historical_scorecard import (
    CLOSED_FINDINGS,
    FROZEN_IDENTITIES,
    MARKET_DIAGNOSTIC_REFERENCE,
    OUTPUT_ROOT,
    PERMITTED_USE,
    PRODUCTION_ACTIVATION_AUTHORIZED,
    READINESS_RECOMMENDATION,
    SCORECARD_MANIFEST_SCHEMA,
    SCORECARD_SCHEMA,
    V4_COMPARISON_DISCLOSURE,
    VERIFICATION_MANIFEST_URI,
    ScorecardError,
    compute_scorecard,
    load_data,
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
            "Existing scorecard manifest is bound to a different run or invalid metadata"
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
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._loop, daemon=True)

    def start(self) -> None:
        self._emit(self.phase, **self.fields)
        self.thread.start()

    def emit(self, phase: str, **fields: Any) -> None:
        self.phase = phase
        self.fields = fields
        self._emit(phase, **fields)

    def _emit(self, phase: str, **fields: Any) -> None:
        payload = {
            "event": "historical_scorecard_progress",
            "run_id": self.run_id,
            "phase": phase,
            "elapsed_seconds": round(time.monotonic() - self.started, 2),
            **fields,
        }
        print(json.dumps(payload, sort_keys=True), flush=True)

    def _loop(self) -> None:
        while not self.stop_event.wait(self.interval):
            self._emit(self.phase, **self.fields)

    def close(self) -> None:
        self.stop_event.set()
        if self.thread.is_alive():
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
    """Validate 11D entry gate and compute full scorecard metrics.

    No writes to Preview R2. Returns the dry-run evidence dict.
    """
    if progress:
        progress.emit("preflight.start", run_id=run_id)

    manifest = validate_verification_manifest(storage)
    if progress:
        progress.emit("preflight.manifest_ok")

    predictions, calibration, window_comparison, head_recipes = load_data(
        storage, manifest
    )
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
        predictions,
        calibration,
        window_comparison,
        head_recipes,
        population_summary=population_summary,
    )
    if progress:
        progress.emit("preflight.metrics_ok")

    evidence = {
        "state": "dry_run",
        "run_id": run_id,
        "verification_manifest_uri": VERIFICATION_MANIFEST_URI,
        "scorecard": scorecard,
        "permitted_use": PERMITTED_USE,
        "production_activation_authorized": PRODUCTION_ACTIVATION_AUTHORIZED,
        "readiness_recommendation": READINESS_RECOMMENDATION,
        "v4_comparison": dict(V4_COMPARISON_DISCLOSURE),
        "market_diagnostic_evidence": dict(MARKET_DIAGNOSTIC_REFERENCE),
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
    """Recompute and publish signed historical scorecard + terminal manifest.

    Requires clean worktree. Idempotent: returns already_applied if exists.
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

    manifest = validate_verification_manifest(storage)
    predictions, calibration, window_comparison, head_recipes = load_data(
        storage, manifest
    )
    population_summary = validate_population(predictions, calibration)
    scorecard = compute_scorecard(
        predictions,
        calibration,
        window_comparison,
        head_recipes,
        population_summary=population_summary,
    )
    if progress:
        progress.emit("apply.recomputed")

    rerun_evidence = {
        "state": "dry_run",
        "run_id": run_id,
        "verification_manifest_uri": VERIFICATION_MANIFEST_URI,
        "scorecard": scorecard,
        "permitted_use": PERMITTED_USE,
        "production_activation_authorized": PRODUCTION_ACTIVATION_AUTHORIZED,
        "readiness_recommendation": READINESS_RECOMMENDATION,
        "v4_comparison": dict(V4_COMPARISON_DISCLOSURE),
        "market_diagnostic_evidence": dict(MARKET_DIAGNOSTIC_REFERENCE),
    }
    rerun_evidence["evidence_sha256"] = sha256(rerun_evidence)

    rerun_normalized = json.loads(json.dumps(rerun_evidence))
    reviewed_normalized = json.loads(json.dumps(dict(reviewed_evidence)))
    if rerun_normalized != reviewed_normalized:
        raise ScorecardPublicationError(
            "Apply recomputation differs from reviewed evidence — do not publish"
        )

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
            "verification_manifest_uri": VERIFICATION_MANIFEST_URI,
            "evidence_sha256": rerun_evidence["evidence_sha256"],
            "code_sha": code_sha,
            "scorecard": scorecard,
            "frozen_identities": dict(FROZEN_IDENTITIES),
            "closed_findings": [dict(f) for f in CLOSED_FINDINGS],
            "permitted_use": PERMITTED_USE,
            "production_activation_authorized": PRODUCTION_ACTIVATION_AUTHORIZED,
            "readiness_recommendation": READINESS_RECOMMENDATION,
            "readiness_rationale": scorecard.get("readiness_rationale"),
            "market_diagnostic_evidence": dict(MARKET_DIAGNOSTIC_REFERENCE),
            "v4_comparison": dict(V4_COMPARISON_DISCLOSURE),
        }
    )
    scorecard_raw_sha256 = hashlib.sha256(
        canonical_bytes(scorecard_payload)
    ).hexdigest()
    scorecard_canonical_sha256 = sha256(scorecard_payload)

    _write_immutable(storage, scorecard_uri, scorecard_payload)
    if progress:
        progress.emit("apply.scorecard_written", uri=scorecard_uri)

    manifest_payload = signed_payload(
        {
            "schema_version": SCORECARD_MANIFEST_SCHEMA,
            "state": "published",
            "run_id": run_id,
            "scorecard_uri": scorecard_uri,
            "scorecard_raw_sha256": scorecard_raw_sha256,
            "scorecard_canonical_sha256": scorecard_canonical_sha256,
            "verification_manifest_uri": VERIFICATION_MANIFEST_URI,
            "evidence_sha256": rerun_evidence["evidence_sha256"],
            "code_sha": code_sha,
            "frozen_identities": dict(FROZEN_IDENTITIES),
            "closed_findings": [dict(f) for f in CLOSED_FINDINGS],
            "permitted_use": PERMITTED_USE,
            "production_activation_authorized": PRODUCTION_ACTIVATION_AUTHORIZED,
            "readiness_recommendation": READINESS_RECOMMENDATION,
            "market_diagnostic_evidence": dict(MARKET_DIAGNOSTIC_REFERENCE),
            "v4_comparison": dict(V4_COMPARISON_DISCLOSURE),
        }
    )
    _write_immutable(storage, manifest_uri, manifest_payload)
    if progress:
        progress.emit("apply.manifest_written", uri=manifest_uri)

    verified = verify_scorecard_publication(storage, manifest_uri=manifest_uri)
    return {"state": "applied", **verified}


# ---------------------------------------------------------------------------
# Independent verifier (storage-only)
# ---------------------------------------------------------------------------


def verify_scorecard_publication(storage: Any, *, manifest_uri: str) -> dict[str, Any]:
    """Independently re-read the published manifest and scorecard from storage."""
    if not storage.exists(manifest_uri):
        raise ScorecardPublicationError(
            f"Scorecard manifest not found at {manifest_uri!r}"
        )

    manifest_raw = storage.read_bytes(manifest_uri)
    manifest_raw_sha256 = hashlib.sha256(manifest_raw).hexdigest()

    try:
        manifest = json.loads(manifest_raw)
        verify_signed_payload(manifest, label="scorecard manifest")
    except Exception as exc:
        raise ScorecardPublicationError(
            "Manifest signature verification failed"
        ) from exc

    if manifest.get("schema_version") != SCORECARD_MANIFEST_SCHEMA:
        raise ScorecardPublicationError("Unexpected manifest schema_version")
    if manifest.get("state") != "published":
        raise ScorecardPublicationError("Manifest state is not 'published'")
    if manifest.get("permitted_use") != PERMITTED_USE:
        raise ScorecardPublicationError("Manifest permitted_use mismatch")
    if manifest.get("production_activation_authorized") is not False:
        raise ScorecardPublicationError(
            "Manifest production_activation_authorized is not False"
        )
    if manifest.get("readiness_recommendation") != READINESS_RECOMMENDATION:
        raise ScorecardPublicationError("Manifest readiness recommendation mismatch")

    scorecard_uri = manifest.get("scorecard_uri", "")
    if not scorecard_uri or not storage.exists(scorecard_uri):
        raise ScorecardPublicationError(
            f"Scorecard artifact missing at {scorecard_uri!r}"
        )

    scorecard_raw = storage.read_bytes(scorecard_uri)
    computed_raw_sha = hashlib.sha256(scorecard_raw).hexdigest()
    if computed_raw_sha != manifest.get("scorecard_raw_sha256"):
        raise ScorecardPublicationError("Scorecard raw SHA-256 mismatch")

    try:
        scorecard = json.loads(scorecard_raw)
        verify_signed_payload(scorecard, label="historical scorecard")
    except Exception as exc:
        raise ScorecardPublicationError(
            "Scorecard signature verification failed"
        ) from exc

    if scorecard.get("schema_version") != SCORECARD_SCHEMA:
        raise ScorecardPublicationError("Unexpected scorecard schema_version")
    if scorecard.get("state") != "published":
        raise ScorecardPublicationError("Scorecard state is not 'published'")
    if scorecard.get("permitted_use") != PERMITTED_USE:
        raise ScorecardPublicationError("Scorecard permitted_use mismatch")
    if scorecard.get("production_activation_authorized") is not False:
        raise ScorecardPublicationError(
            "Scorecard production_activation_authorized is not False"
        )
    if scorecard.get("readiness_recommendation") != READINESS_RECOMMENDATION:
        raise ScorecardPublicationError("Scorecard readiness recommendation mismatch")

    return {
        "verified": True,
        "run_id": manifest.get("run_id"),
        "manifest_uri": manifest_uri,
        "manifest_raw_sha256": manifest_raw_sha256,
        "manifest_canonical_sha256": manifest.get("manifest_sha256"),
        "scorecard_uri": scorecard_uri,
        "scorecard_raw_sha256": computed_raw_sha,
        "scorecard_canonical_sha256": manifest.get("scorecard_canonical_sha256"),
        "permitted_use": manifest.get("permitted_use"),
        "production_activation_authorized": manifest.get(
            "production_activation_authorized"
        ),
        "readiness_recommendation": manifest.get("readiness_recommendation"),
    }
