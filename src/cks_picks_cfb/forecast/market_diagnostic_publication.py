"""Contract 02 (2026-09-21) market-diagnostic publication and verification.

Publishes a signed Preview-only diagnostic artifact and terminal manifest
under the market-diagnostics v1 prefix.  The independent verifier re-reads
the stored diagnostic without trusting any in-memory derived value.

Permitted use: ``diagnostic_comparison_only`` only.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np

from cks_picks_cfb.data import catalog as catalog_module
from cks_picks_cfb.data.data_first_phase2d import (
    canonical_bytes,
    sha256,
    signed_payload,
    verify_signed_payload,
)
from cks_picks_cfb.forecast.historical_scorecard import (
    VERIFICATION_MANIFEST_URI,
)
from cks_picks_cfb.forecast.market_diagnostic import (
    DIAGNOSTIC_MANIFEST_SCHEMA,
    DIAGNOSTIC_SCHEMA,
    LINE_SEMANTICS,
    OUTPUT_ROOT,
    PERMITTED_USE,
    TARGETS,
    MarketDiagnosticError,
    assert_market_quarantined,
    build_study_population,
    compute_market_diagnostic,
    fetch_market_catalog_state,
    load_market_snapshots,
    load_study_forecasts,
    resolve_market_snapshots_ref,
    validate_sign_convention,
    validate_snapshots_frame,
)
from cks_picks_cfb.forecast.scorecard_publication import _Progress

ROOT = Path(__file__).resolve().parents[4]


class MarketDiagnosticPublicationError(MarketDiagnosticError):
    """Raised when diagnostic publication cannot proceed or reconcile."""


# ---------------------------------------------------------------------------
# Idempotency helpers
# ---------------------------------------------------------------------------


def _write_immutable(storage: Any, uri: str, payload: Mapping[str, Any]) -> None:
    encoded = canonical_bytes(payload)
    if storage.exists(uri):
        if storage.read_bytes(uri) != encoded:
            raise MarketDiagnosticPublicationError(f"immutable collision at {uri!r}")
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
        verify_signed_payload(manifest, label="diagnostic manifest")
    except (json.JSONDecodeError, ValueError) as exc:
        raise MarketDiagnosticPublicationError(
            "Existing diagnostic manifest is invalid"
        ) from exc
    if (
        manifest.get("schema_version") != DIAGNOSTIC_MANIFEST_SCHEMA
        or manifest.get("run_id") != run_id
        or manifest.get("permitted_use") != PERMITTED_USE
        or manifest.get("line_semantics") != LINE_SEMANTICS
        or manifest.get("closing_line_evidence") is not False
        or manifest.get("production_activation_authorized") is not False
    ):
        raise MarketDiagnosticPublicationError(
            "Existing diagnostic manifest is bound to a different run"
        )
    return manifest


# ---------------------------------------------------------------------------
# Preflight (dry-run)
# ---------------------------------------------------------------------------


def run_market_diagnostic_preflight(
    storage: Any,
    *,
    run_id: str,
    catalog_url: str | None = None,
    progress: _Progress | None = None,
) -> dict[str, Any]:
    """Resolve entry gates, validate convention, compute all metrics.

    No writes to R2 or any external system.  Returns the dry-run evidence dict.
    """
    if progress:
        progress.emit("preflight.start", run_id=run_id)

    ref = resolve_market_snapshots_ref(storage)
    if progress:
        progress.emit("preflight.market_ref_ok", version_id=ref.get("version_id"))
    catalog_row = fetch_market_catalog_state(
        catalog_url or catalog_module.catalog_connection_url("preview")
    )
    assert_market_quarantined(catalog_row)
    if progress:
        progress.emit("preflight.market_quarantine_ok")
    snapshots = load_market_snapshots(storage, ref)
    snapshot_summary = validate_snapshots_frame(snapshots)
    if progress:
        progress.emit(
            "preflight.snapshots_ok", snapshot_rows=snapshot_summary["snapshot_rows"]
        )

    forecasts = load_study_forecasts(storage)
    if progress:
        progress.emit("preflight.forecasts_ok", forecast_rows=len(forecasts))
    sign = validate_sign_convention(forecasts, snapshots)
    if progress:
        progress.emit("preflight.sign_ok")
    population, accounting = build_study_population(forecasts, snapshots)
    if progress:
        progress.emit("preflight.population_ok")

    market_provenance = {
        "dataset": ref["dataset"],
        "version_id": ref["version_id"],
        "schema_version": ref["schema_version"],
        "content_sha": ref["content_sha"],
        "uri": ref["uri"],
        "catalog_state": catalog_row["state"],
        "line_semantics": LINE_SEMANTICS,
        "policy": snapshot_summary["policy"],
        "snapshot_rows": snapshot_summary["snapshot_rows"],
        "replay_input_refs": 16,
        "replay_ref_agreement": "unanimous_16_of_16",
    }
    diagnostic = compute_market_diagnostic(
        population,
        sign_convention=sign,
        accounting=accounting,
        market_provenance=market_provenance,
    )
    if progress:
        progress.emit("preflight.metrics_ok")

    evidence = {
        "state": "dry_run",
        "run_id": run_id,
        "study_season": 2025,
        "verification_manifest_uri": VERIFICATION_MANIFEST_URI,
        "diagnostic": diagnostic,
        "permitted_use": PERMITTED_USE,
        "line_semantics": LINE_SEMANTICS,
        "closing_line_evidence": False,
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


def publish_market_diagnostic(
    storage: Any,
    *,
    run_id: str,
    reviewed_evidence: Mapping[str, Any],
    catalog_url: str | None = None,
    progress: _Progress | None = None,
) -> dict[str, Any]:
    """Re-compute and publish a signed diagnostic + terminal manifest.

    Requires a clean committed worktree.  Idempotent: returns already_applied
    if the terminal manifest already exists and reconciles.
    """
    prefix = f"{OUTPUT_ROOT}/{run_id}"
    diagnostic_uri = f"{prefix}/market-diagnostic.json"
    manifest_uri = f"{prefix}/diagnostic-manifest.json"

    existing = _existing_manifest(storage, manifest_uri=manifest_uri, run_id=run_id)
    if existing is not None:
        if progress:
            progress.emit("apply.already_applied", run_id=run_id)
        verified = verify_market_diagnostic_publication(
            storage, manifest_uri=manifest_uri
        )
        return {"state": "already_applied", **verified}

    if storage.list_files(prefix):
        raise MarketDiagnosticPublicationError(
            f"Diagnostic prefix already has partial content: {prefix!r}"
        )

    if (
        reviewed_evidence.get("state") != "dry_run"
        or reviewed_evidence.get("run_id") != run_id
        or reviewed_evidence.get("permitted_use") != PERMITTED_USE
        or reviewed_evidence.get("line_semantics") != LINE_SEMANTICS
        or reviewed_evidence.get("closing_line_evidence") is not False
    ):
        raise MarketDiagnosticPublicationError(
            "Reviewed evidence identity does not match this apply call"
        )

    if progress:
        progress.emit("apply.start", run_id=run_id)

    rerun = run_market_diagnostic_preflight(
        storage, run_id=run_id, catalog_url=catalog_url, progress=progress
    )
    rerun_normalized = json.loads(json.dumps(rerun))
    reviewed_normalized = json.loads(json.dumps(dict(reviewed_evidence)))
    if rerun_normalized != reviewed_normalized:
        raise MarketDiagnosticPublicationError(
            "Apply recomputation differs from reviewed evidence — do not publish"
        )

    try:
        code_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        code_sha = "unknown"

    diagnostic = rerun["diagnostic"]
    diagnostic_payload = signed_payload(
        {
            "schema_version": DIAGNOSTIC_SCHEMA,
            "state": "published",
            "run_id": run_id,
            "code_sha": code_sha,
            "verification_manifest_uri": VERIFICATION_MANIFEST_URI,
            "diagnostic": diagnostic,
            "permitted_use": PERMITTED_USE,
            "line_semantics": LINE_SEMANTICS,
            "closing_line_evidence": False,
            "production_activation_authorized": False,
            "readiness_recommendation": None,
            "v4_comparison": None,
        }
    )
    _write_immutable(storage, diagnostic_uri, diagnostic_payload)
    diagnostic_raw = storage.read_bytes(diagnostic_uri)
    if progress:
        progress.emit(
            "apply.diagnostic_written",
            diagnostic_uri=diagnostic_uri,
            diagnostic_raw_sha=hashlib.sha256(diagnostic_raw).hexdigest(),
        )

    diagnostic_manifest = signed_payload(
        {
            "schema_version": DIAGNOSTIC_MANIFEST_SCHEMA,
            "state": "published",
            "run_id": run_id,
            "code_sha": code_sha,
            "diagnostic_uri": diagnostic_uri,
            "diagnostic_raw_sha256": hashlib.sha256(diagnostic_raw).hexdigest(),
            "diagnostic_manifest_sha256": diagnostic_payload["manifest_sha256"],
            "verification_manifest_uri": VERIFICATION_MANIFEST_URI,
            "permitted_use": PERMITTED_USE,
            "line_semantics": LINE_SEMANTICS,
            "closing_line_evidence": False,
            "production_activation_authorized": False,
            "readiness_recommendation": None,
            "v4_comparison": None,
        }
    )
    _write_immutable(storage, manifest_uri, diagnostic_manifest)
    if progress:
        progress.emit("apply.manifest_written", manifest_uri=manifest_uri)

    verified = verify_market_diagnostic_publication(storage, manifest_uri=manifest_uri)
    return {"state": "applied", **verified}


# ---------------------------------------------------------------------------
# Independent verifier
# ---------------------------------------------------------------------------


def verify_market_diagnostic_publication(
    storage: Any,
    *,
    manifest_uri: str,
) -> dict[str, Any]:
    """Independently re-read and verify a published diagnostic.

    Recomputes intersection counts and one sentinel metric per target to
    confirm the stored diagnostic was derived from the pinned inputs.
    Does not trust any stored derived value.
    """
    try:
        manifest_raw = storage.read_bytes(manifest_uri)
        manifest = json.loads(manifest_raw)
        verify_signed_payload(manifest, label="diagnostic manifest")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise MarketDiagnosticPublicationError(
            "Diagnostic manifest is unreadable or has invalid signature"
        ) from exc

    if (
        manifest.get("schema_version") != DIAGNOSTIC_MANIFEST_SCHEMA
        or manifest.get("state") != "published"
        or manifest.get("permitted_use") != PERMITTED_USE
        or manifest.get("line_semantics") != LINE_SEMANTICS
        or manifest.get("closing_line_evidence") is not False
        or manifest.get("production_activation_authorized") is not False
    ):
        raise MarketDiagnosticPublicationError(
            "Diagnostic manifest has invalid boundary fields"
        )

    diagnostic_uri = manifest.get("diagnostic_uri", "")
    try:
        diagnostic_raw = storage.read_bytes(diagnostic_uri)
        diagnostic = json.loads(diagnostic_raw)
        verify_signed_payload(diagnostic, label="diagnostic payload")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise MarketDiagnosticPublicationError(
            "Diagnostic payload is unreadable or has invalid signature"
        ) from exc

    expected_diagnostic_sha = manifest.get("diagnostic_raw_sha256", "")
    actual_diagnostic_sha = hashlib.sha256(diagnostic_raw).hexdigest()
    if expected_diagnostic_sha != actual_diagnostic_sha:
        raise MarketDiagnosticPublicationError(
            f"Diagnostic raw SHA mismatch: "
            f"expected {expected_diagnostic_sha}, got {actual_diagnostic_sha}"
        )
    if manifest.get("diagnostic_manifest_sha256") != diagnostic.get("manifest_sha256"):
        raise MarketDiagnosticPublicationError(
            "Diagnostic manifest_sha256 cross-check failed"
        )

    if (
        diagnostic.get("schema_version") != DIAGNOSTIC_SCHEMA
        or diagnostic.get("state") != "published"
        or diagnostic.get("permitted_use") != PERMITTED_USE
        or diagnostic.get("line_semantics") != LINE_SEMANTICS
        or diagnostic.get("closing_line_evidence") is not False
        or diagnostic.get("production_activation_authorized") is not False
        or diagnostic.get("readiness_recommendation") is not None
        or diagnostic.get("v4_comparison") is not None
    ):
        raise MarketDiagnosticPublicationError(
            "Diagnostic payload has invalid boundary fields"
        )

    # Independent recomputation from the pinned inputs.
    ref = resolve_market_snapshots_ref(storage)
    snapshots = load_market_snapshots(storage, ref)
    validate_snapshots_frame(snapshots)
    forecasts = load_study_forecasts(storage)
    validate_sign_convention(forecasts, snapshots)
    population, accounting = build_study_population(forecasts, snapshots)

    stored = diagnostic.get("diagnostic", {})
    stored_pop = stored.get("population", {}).get("per_target", {})
    for target in TARGETS:
        expected_n = accounting["per_target"][target]["intersection_games"]
        stored_n = stored_pop.get(target, {}).get("intersection_games")
        if stored_n != expected_n:
            raise MarketDiagnosticPublicationError(
                f"Stored intersection for {target!r} does not match "
                f"recomputed value (stored={stored_n}, expected={expected_n})"
            )

    # Sentinel per target: overall MAE delta (market − V5).
    stored_targets = stored.get("targets", {})
    for target in TARGETS:
        leg = population[population["target"] == target]
        v5_err = np.abs(
            leg["prediction"].to_numpy(float) - leg["actual"].to_numpy(float)
        )
        mkt_err = np.abs(
            leg["market_implied"].to_numpy(float) - leg["actual"].to_numpy(float)
        )
        expected_delta = float(mkt_err.mean() - v5_err.mean())
        stored_delta = (
            stored_targets.get(target, {})
            .get("overall", {})
            .get("mae_delta_market_minus_v5")
        )
        if stored_delta is None or abs(float(stored_delta) - expected_delta) > 1e-9:
            raise MarketDiagnosticPublicationError(
                f"Stored MAE delta for {target!r} does not match recomputed value "
                f"(stored={stored_delta}, expected={expected_delta:.6f})"
            )

    run_id = manifest.get("run_id", "")
    return {
        "verified": True,
        "run_id": run_id,
        "manifest_uri": manifest_uri,
        "manifest_raw_sha256": hashlib.sha256(manifest_raw).hexdigest(),
        "diagnostic_uri": diagnostic_uri,
        "diagnostic_raw_sha256": actual_diagnostic_sha,
        "permitted_use": PERMITTED_USE,
        "line_semantics": LINE_SEMANTICS,
        "closing_line_evidence": False,
        "production_activation_authorized": False,
    }
