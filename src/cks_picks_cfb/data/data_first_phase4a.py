"""Fail-closed contracts for Preview-only data-first Phase 4A research."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd

from cks_picks_cfb.data.data_first_phase2d import (
    canonical_bytes,
    sha256,
    verify_signed_payload,
)
from cks_picks_cfb.data.data_first_phase3 import (
    PHASE3_RETAINED_CORE_SCHEMA,
    Phase3Error,
    verify_retained_core_manifest,
)

PHASE4A_IDENTITY_SCHEMA = "data_first_phase4a_run_identity_v1"
PHASE4A_RETAINED_RATING_SCHEMA = "data_first_phase4a_retained_rating_v1"
PHASE4A_RATING_STATE_DATASET = "phase4a_rating_states"
PHASE4A_RATING_STATE_SCHEMA = "phase4a_rating_states_v1"
PHASE4A_TEAM_STATE_DATASET = "phase4a_team_states"
PHASE4A_TEAM_STATE_SCHEMA = "phase4a_team_states_v1"
PHASE4A_PREDICTION_DATASET = "phase4a_fold_predictions"
PHASE4A_PREDICTION_SCHEMA = "phase4a_fold_predictions_v1"
PHASE4A_ATTRIBUTION_DATASET = "phase4a_attribution_coverage"
PHASE4A_ATTRIBUTION_SCHEMA = "phase4a_attribution_coverage_v1"
REQUIRED_PHASE3_RETAINED_SHA256 = (
    "c8bc1ebd8a369c59cf298844dfdb2167baaa17dc72a3b29ceebd119eeacaf234"
)

RATING_CANDIDATES = (
    "neutral__exposure",
    "neutral__half_life_2",
    "neutral__half_life_4",
    "neutral__half_life_8",
    "rho_0_60__exposure",
    "rho_0_60__half_life_2",
    "rho_0_60__half_life_4",
    "rho_0_60__half_life_8",
)
REFERENCE_CANDIDATE = "rho_0_60__exposure"
RATING_STATE_COLUMNS = (
    "candidate",
    "season",
    "week",
    "game_id",
    "kickoff_utc",
    "team",
    "unit_role",
    "prior_source",
    "prior_source_season",
    "annual_decay_steps",
    "standardization_center",
    "standardization_scale",
    "observed_adjusted_value",
    "observed_z",
    "effective_exposure",
    "completed_games",
    "prior_mean",
    "prior_variance",
    "prior_precision",
    "observed_precision",
    "posterior_mean",
    "posterior_variance",
    "posterior_sd",
    "movement",
    "fallback_used",
    "fallback_reason",
    "fallback_cohort",
    "parent_identity_sha",
    "code_sha",
    "config_sha",
)
TEAM_STATE_COLUMNS = (
    "candidate",
    "season",
    "week",
    "game_id",
    "kickoff_utc",
    "team",
    "offense_rating",
    "offense_sd",
    "defense_rating",
    "defense_sd",
    "overall_rating",
    "overall_sd",
    "offense_fallback",
    "defense_fallback",
    "parent_identity_sha",
    "code_sha",
    "config_sha",
)
PREDICTION_COLUMNS = (
    "candidate",
    "season",
    "week",
    "game_id",
    "kickoff_utc",
    "target",
    "actual",
    "prediction",
    "absolute_error",
    "fold_id",
    "training_seasons",
    "feature_names",
    "standardization_center",
    "standardization_scale",
    "ridge_coefficients",
    "ridge_intercept",
    "feature_fallback",
    "fallback_count",
)
ATTRIBUTION_COLUMNS = (
    "candidate",
    "prior_family",
    "updater",
    "mechanism_count",
    "validation_rows",
    "validation_games",
    "pooled_mae",
    "reference_mae",
    "improvement_pct",
    "bootstrap_mean_improvement",
    "bootstrap_90_lower",
    "bootstrap_90_upper",
    "bootstrap_excludes_zero",
    "coverage_equal",
    "maximum_seasonal_regression_pct",
    "seasonal_gate_passed",
    "primary_gate_passed",
    "selected",
)


class Phase4AError(ValueError):
    """Raised when a Phase 4A input or result escapes its sealed boundary."""


def candidate_parts(candidate: str) -> tuple[str, str]:
    """Return the explicitly permitted prior/updater pair."""
    if candidate not in RATING_CANDIDATES:
        raise Phase4AError(f"unknown Phase 4A candidate: {candidate}")
    prior, updater = candidate.split("__", 1)
    return prior, updater


def validate_phase4a_config(payload: Mapping[str, Any]) -> None:
    """Reject drift in the closed Phase 4A candidate and selection registry."""
    if tuple(payload.get("candidates") or ()) != RATING_CANDIDATES:
        raise Phase4AError("config candidate registry differs from Phase 4A contract")
    selection = payload.get("selection") or {}
    expected = {
        "reference_candidate": REFERENCE_CANDIDATE,
        "rho": 0.60,
        "equivalent_exposure": 100.0,
        "ridge_alpha": 10,
        "validation_seasons": [2018, 2019, 2021, 2022, 2023, 2024, 2025],
        "minimum_pooled_improvement_pct": 0.5,
        "maximum_seasonal_regression_pct": 5.0,
        "bootstrap_confidence": 0.90,
        "bootstrap_replicates": 2000,
        "bootstrap_seed": 20260908,
    }
    if {key: selection.get(key) for key in expected} != expected:
        raise Phase4AError("config selection scaffold differs from Phase 4A contract")


def verify_phase3_parent(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Accept only the signed EPA-only, Preview-only retained core."""
    try:
        manifest = verify_retained_core_manifest(payload)
    except Phase3Error as exc:
        raise Phase4AError(str(exc)) from exc
    if manifest.get("schema_version") != PHASE3_RETAINED_CORE_SCHEMA:
        raise Phase4AError("Phase 4A parent has the wrong schema")
    if manifest.get("selected_candidate") != "epa_only":
        raise Phase4AError("Phase 4A requires the certified EPA-only core")
    if manifest.get("auxiliary_context_consumed") is not False:
        raise Phase4AError("Phase 4A parent consumed auxiliary context")
    return manifest


def phase4a_identity(
    *,
    run_id: str,
    environment: str,
    as_of: str,
    code_sha: str,
    config_sha: str,
    phase3_retained_uri: str,
    phase3_retained_sha256: str,
) -> dict[str, Any]:
    """Create a deterministic Preview-only immutable run identity."""
    if environment != "preview":
        raise Phase4AError("Phase 4A is Preview-only")
    if not all(
        (
            run_id,
            as_of,
            code_sha,
            config_sha,
            phase3_retained_uri,
            phase3_retained_sha256,
        )
    ):
        raise Phase4AError("Phase 4A identity is incomplete")
    payload = {
        "schema_version": PHASE4A_IDENTITY_SCHEMA,
        "run_id": run_id,
        "environment": environment,
        "as_of": as_of,
        "code_sha": code_sha,
        "config_sha": config_sha,
        "phase3_retained_uri": phase3_retained_uri,
        "phase3_retained_sha256": phase3_retained_sha256,
    }
    return payload | {"identity_sha256": sha256(payload)}


def select_rating(
    attribution: pd.DataFrame,
    *,
    minimum_improvement_pct: float = 0.5,
) -> str:
    """Apply the predeclared gates and deterministic simplicity tie-break."""
    if set(attribution["candidate"].astype(str)) != set(RATING_CANDIDATES):
        raise Phase4AError("rating attribution lacks the complete candidate grid")
    reference = attribution.loc[
        attribution["candidate"].eq(REFERENCE_CANDIDATE), "pooled_mae"
    ]
    if len(reference) != 1:
        raise Phase4AError("rating attribution lacks exactly one reference row")
    candidates = attribution.copy()
    candidates["improvement_pct"] = (
        (float(reference.iloc[0]) - candidates["pooled_mae"].astype(float))
        / float(reference.iloc[0])
        * 100
    )
    challengers = candidates[candidates["candidate"] != REFERENCE_CANDIDATE]
    passing = challengers[
        (challengers["improvement_pct"] >= minimum_improvement_pct)
        & challengers["bootstrap_excludes_zero"].astype(bool)
        & challengers["coverage_equal"].astype(bool)
        & challengers["seasonal_gate_passed"].astype(bool)
    ]
    if passing.empty:
        return REFERENCE_CANDIDATE
    best = float(passing["pooled_mae"].min())

    def order(row: pd.Series) -> tuple[int, int, str]:
        prior, updater = candidate_parts(str(row["candidate"]))
        return (
            0 if prior == "neutral" else 1,
            0 if updater == "exposure" else 1,
            str(row["candidate"]),
        )

    eligible = passing[passing["pooled_mae"] <= best * 1.005]
    return str(min((row for _, row in eligible.iterrows()), key=order)["candidate"])


def retained_rating_manifest(
    *,
    identity: Mapping[str, Any],
    phase3_parent: Mapping[str, Any],
    attribution: pd.DataFrame,
    output_refs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the signed, activation-ineligible Phase 4A handoff."""
    selected = select_rating(attribution)
    rows = attribution.sort_values("candidate").to_dict("records")
    payload: dict[str, Any] = {
        "schema_version": PHASE4A_RETAINED_RATING_SCHEMA,
        "state": "frozen",
        "identity": dict(identity),
        "selected_candidate": selected,
        "reference_candidate": REFERENCE_CANDIDATE,
        "candidate_summary": rows,
        "phase3_parent_identity": dict(phase3_parent["identity"]),
        "phase3_parent_manifest_sha256": phase3_parent.get("manifest_sha256"),
        "auxiliary_context_consumed": False,
        "production_activation_authorized": False,
        "neon_activation_authorized": False,
        "publication_authorized": False,
    }
    if output_refs is not None:
        payload["output_refs"] = dict(output_refs)
    from cks_picks_cfb.data.data_first_phase2d import signed_payload

    return signed_payload(payload)


def canonical_payload(value: Mapping[str, Any]) -> bytes:
    return canonical_bytes(value)


def verify_retained_rating_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a frozen Phase 4A handoff before a later phase consumes it."""
    if payload.get("schema_version") != PHASE4A_RETAINED_RATING_SCHEMA:
        raise Phase4AError("unexpected Phase 4A retained-rating schema")
    if payload.get("state") != "frozen":
        raise Phase4AError("Phase 4A retained rating is not frozen")
    try:
        verify_signed_payload(payload, label="Phase 4A retained rating")
    except Exception as exc:  # Phase2d exposes a domain-specific verifier error.
        raise Phase4AError(str(exc)) from exc
    if payload.get("selected_candidate") not in RATING_CANDIDATES:
        raise Phase4AError("Phase 4A selected an unknown candidate")
    if any(
        payload.get(key) is not False
        for key in (
            "auxiliary_context_consumed",
            "production_activation_authorized",
            "neon_activation_authorized",
            "publication_authorized",
        )
    ):
        raise Phase4AError("Phase 4A retained rating violates its isolation boundary")
    identity = payload.get("identity") or {}
    if (
        identity.get("schema_version") != PHASE4A_IDENTITY_SCHEMA
        or identity.get("environment") != "preview"
    ):
        raise Phase4AError("Phase 4A retained rating lacks a Preview identity")
    if (
        not isinstance(identity.get("identity_sha256"), str)
        or not identity["identity_sha256"]
    ):
        raise Phase4AError("Phase 4A identity is malformed")
    return dict(payload)
