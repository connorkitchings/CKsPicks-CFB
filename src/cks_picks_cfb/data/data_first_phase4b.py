"""Fail-closed contracts for Preview-only data-first Phase 4B research."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
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
from cks_picks_cfb.data.data_first_phase4a import (
    PHASE4A_RETAINED_RATING_SCHEMA,
    Phase4AError,
    verify_retained_rating_manifest,
)

PHASE4B_IDENTITY_SCHEMA = "data_first_phase4b_run_identity_v1"
PHASE4B_RETAINED_BASELINE_SCHEMA = "data_first_phase4b_retained_baseline_v1"
PHASE4B_PREDICTION_DATASET = "phase4b_context_predictions"
PHASE4B_PREDICTION_SCHEMA = "phase4b_context_predictions_v1"
PHASE4B_ATTRIBUTION_DATASET = "phase4b_context_attribution"
PHASE4B_ATTRIBUTION_SCHEMA = "phase4b_context_attribution_v1"
PHASE4B_COVERAGE_DATASET = "phase4b_context_coverage"
PHASE4B_COVERAGE_SCHEMA = "phase4b_context_coverage_v1"

REQUIRED_PHASE4A_RETAINED_SHA256 = (
    "af9e66af67f26155ab74d1acd1947f72add7307203ae09bf1853856696e27612"
)
REQUIRED_PHASE3_RETAINED_SHA256 = (
    "c8bc1ebd8a369c59cf298844dfdb2167baaa17dc72a3b29ceebd119eeacaf234"
)
REQUIRED_PHASE2E_ELIGIBILITY_SHA256 = (
    "d06ed3968a7bb6ec7ba97212aa2063068c253f26202e810c921b044006ab13ad"
)

CONTEXT_FAMILIES = (
    "field_position",
    "pace",
    "turnovers",
    "recruiting",
    "returning_production",
    "coaching",
    "roster_continuity",
    "lagged_rankings",
)
NO_CONTEXT_FAMILY = "no_context"
ALL_CONTEXT_CANDIDATES = (NO_CONTEXT_FAMILY, *CONTEXT_FAMILIES)
TARGETS = ("margin", "total")

CONTEXT_FAMILY_FEATURES: dict[str, tuple[str, ...]] = {
    "field_position": (
        "average_start_field_position_offense",
        "average_start_field_position_defense",
    ),
    "pace": ("plays_per_drive_offense",),
    "turnovers": (
        "turnover_rate_offense",
        "turnover_rate_defense",
    ),
    "recruiting": (
        "recruiting_4yr",
        "recruiting_current",
        "recruiting_trend",
    ),
    "returning_production": (
        "return_total_ppa",
        "return_passing_ppa",
        "return_rushing_ppa",
        "return_receiving_ppa",
        "return_percent_ppa",
        "return_passing_usage",
        "return_rushing_usage",
    ),
    "coaching": (
        "coach_tenure",
        "coach_new",
    ),
    "roster_continuity": (
        "roster_size",
        "roster_returning_share",
        "roster_returning_qb_count",
    ),
    "lagged_rankings": (
        "lagged_ap_rank",
        "lagged_coaches_rank",
        "lagged_ranked_either",
    ),
}

RATING_FEATURES = (
    "home_offense",
    "home_defense",
    "away_offense",
    "away_defense",
)

PREDICTION_COLUMNS = (
    "family",
    "target",
    "season",
    "week",
    "game_id",
    "kickoff_utc",
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
    "target",
    "family",
    "feature_count",
    "validation_rows",
    "validation_games",
    "pooled_mae",
    "baseline_mae",
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

COVERAGE_COLUMNS = (
    "family",
    "target",
    "season",
    "total_rows",
    "complete_rows",
    "imputed_rows",
    "coverage_fraction",
    "fallback_reason",
)


class Phase4BError(ValueError):
    """Raised when a Phase 4B input or result escapes its sealed boundary."""


def verify_phase4a_parent(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Accept only the signed Phase 4A retained rating."""
    try:
        manifest = verify_retained_rating_manifest(payload)
    except Phase4AError as exc:
        raise Phase4BError(str(exc)) from exc
    if manifest.get("schema_version") != PHASE4A_RETAINED_RATING_SCHEMA:
        raise Phase4BError("Phase 4B parent has the wrong Phase 4A schema")
    if manifest.get("selected_candidate") != "rho_0_60__exposure":
        raise Phase4BError("Phase 4B requires the certified rho_0_60__exposure rating")
    if manifest.get("auxiliary_context_consumed") is not False:
        raise Phase4BError("Phase 4A parent consumed auxiliary context")
    return dict(manifest)


def verify_phase2e_parent(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Accept only the signed Phase 2e reconstructed-only eligibility manifest."""
    if payload.get("schema_version") != "data_first_phase2e_eligibility_v1":
        raise Phase4BError("Phase 2e parent has the wrong schema")
    if payload.get("state") != "eligible_reconstructed_only":
        raise Phase4BError(
            "Phase 2e parent is not in the eligible_reconstructed_only state"
        )
    try:
        verify_signed_payload(payload, label="Phase 2e auxiliary eligibility")
    except Exception as exc:
        raise Phase4BError(str(exc)) from exc
    permitted = payload.get("permitted_uses") or {}
    if permitted.get("market_references") != ["post_phase5_diagnostic_only"]:
        raise Phase4BError("Phase 2e market references have unexpected permitted use")
    if any(
        payload.get(key) is not False
        for key in (
            "activation_eligible",
            "production_activation_authorized",
            "model_selection_authorized",
        )
    ):
        raise Phase4BError(
            "Phase 2e parent violates its activation-ineligible boundary"
        )
    return dict(payload)


def verify_phase3_parent(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Accept only the signed Phase 3 EPA-only retained core."""
    try:
        manifest = verify_retained_core_manifest(payload)
    except Phase3Error as exc:
        raise Phase4BError(str(exc)) from exc
    if manifest.get("schema_version") != PHASE3_RETAINED_CORE_SCHEMA:
        raise Phase4BError("Phase 4B parent has the wrong Phase 3 schema")
    if manifest.get("selected_candidate") != "epa_only":
        raise Phase4BError("Phase 4B requires the certified EPA-only core")
    if manifest.get("auxiliary_context_consumed") is not False:
        raise Phase4BError("Phase 3 parent consumed auxiliary context")
    return dict(manifest)


def phase4b_identity(
    *,
    run_id: str,
    environment: str,
    as_of: str,
    code_sha: str,
    config_sha: str,
    phase4a_retained_uri: str,
    phase4a_retained_sha256: str,
    phase3_retained_uri: str,
    phase3_retained_sha256: str,
    phase2e_eligibility_uri: str,
    phase2e_eligibility_sha256: str,
) -> dict[str, Any]:
    """Create a deterministic Preview-only immutable run identity."""
    if environment != "preview":
        raise Phase4BError("Phase 4B is Preview-only")
    if not all(
        (
            run_id,
            as_of,
            code_sha,
            config_sha,
            phase4a_retained_uri,
            phase4a_retained_sha256,
            phase3_retained_uri,
            phase3_retained_sha256,
            phase2e_eligibility_uri,
            phase2e_eligibility_sha256,
        )
    ):
        raise Phase4BError("Phase 4B identity is incomplete")
    payload = {
        "schema_version": PHASE4B_IDENTITY_SCHEMA,
        "run_id": run_id,
        "environment": environment,
        "as_of": as_of,
        "code_sha": code_sha,
        "config_sha": config_sha,
        "phase4a_retained_uri": phase4a_retained_uri,
        "phase4a_retained_sha256": phase4a_retained_sha256,
        "phase3_retained_uri": phase3_retained_uri,
        "phase3_retained_sha256": phase3_retained_sha256,
        "phase2e_eligibility_uri": phase2e_eligibility_uri,
        "phase2e_eligibility_sha256": phase2e_eligibility_sha256,
    }
    return payload | {"identity_sha256": sha256(payload)}


def validate_phase4b_config(payload: Mapping[str, Any]) -> None:
    """Reject drift in the closed Phase 4B context family and selection registry."""
    if tuple(payload.get("context_families") or ()) != CONTEXT_FAMILIES:
        raise Phase4BError(
            "config context family registry differs from Phase 4B contract"
        )
    family_features = payload.get("family_features") or {}
    if {k: tuple(v) for k, v in family_features.items()} != CONTEXT_FAMILY_FEATURES:
        raise Phase4BError("config family features differ from Phase 4B contract")
    selection = payload.get("selection") or {}
    expected = {
        "baseline_family": NO_CONTEXT_FAMILY,
        "ridge_alpha": 10,
        "validation_seasons": [2018, 2019, 2021, 2022, 2023, 2024, 2025],
        "minimum_pooled_improvement_pct": 0.5,
        "maximum_seasonal_regression_pct": 5.0,
        "bootstrap_confidence": 0.90,
        "bootstrap_replicates": 2000,
        "bootstrap_seed": 20260908,
    }
    if {key: selection.get(key) for key in expected} != expected:
        raise Phase4BError("config selection scaffold differs from Phase 4B contract")


def select_context(
    attribution: pd.DataFrame,
    *,
    target: str,
    minimum_improvement_pct: float = 0.5,
) -> str:
    """Apply the predeclared gates and deterministic simplicity tie-break for one target."""
    if target not in TARGETS:
        raise Phase4BError(f"unknown Phase 4B target: {target}")
    target_attribution = attribution[attribution["target"] == target]
    families = set(target_attribution["family"].astype(str))
    if families != set(ALL_CONTEXT_CANDIDATES):
        raise Phase4BError(
            f"context attribution for {target} lacks the complete candidate set"
        )
    baseline = target_attribution.loc[
        target_attribution["family"] == NO_CONTEXT_FAMILY, "pooled_mae"
    ]
    if len(baseline) != 1:
        raise Phase4BError(
            f"context attribution for {target} lacks exactly one baseline row"
        )
    baseline_mae = float(baseline.iloc[0])
    if not np.isfinite(baseline_mae) or baseline_mae <= 0:
        raise Phase4BError(
            f"context attribution for {target} has an invalid baseline MAE"
        )
    candidates = target_attribution.copy()
    candidates["improvement_pct"] = (
        (baseline_mae - candidates["pooled_mae"].astype(float)) / baseline_mae * 100
    )
    challengers = candidates[candidates["family"] != NO_CONTEXT_FAMILY]
    passing = challengers[
        (challengers["improvement_pct"] >= minimum_improvement_pct)
        & challengers["bootstrap_excludes_zero"].astype(bool)
        & challengers["coverage_equal"].astype(bool)
        & challengers["seasonal_gate_passed"].astype(bool)
    ]
    if passing.empty:
        return NO_CONTEXT_FAMILY
    best = float(passing["pooled_mae"].min())
    eligible = passing[passing["pooled_mae"] <= best * 1.005]
    return str(
        min(
            eligible.iterrows(),
            key=lambda item: (int(item[1]["feature_count"]), str(item[1]["family"])),
        )[1]["family"]
    )


def retained_baseline_manifest(
    *,
    identity: Mapping[str, Any],
    phase4a_parent: Mapping[str, Any],
    phase3_parent: Mapping[str, Any],
    phase2e_parent: Mapping[str, Any],
    margin_attribution: pd.DataFrame,
    total_attribution: pd.DataFrame,
    output_refs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the signed, activation-ineligible Phase 4B handoff."""
    margin_selected = select_context(margin_attribution, target="margin")
    total_selected = select_context(total_attribution, target="total")
    margin_rows = margin_attribution.sort_values("family").to_dict("records")
    total_rows = total_attribution.sort_values("family").to_dict("records")
    payload: dict[str, Any] = {
        "schema_version": PHASE4B_RETAINED_BASELINE_SCHEMA,
        "state": "frozen",
        "identity": dict(identity),
        "margin_context_selected": margin_selected,
        "total_context_selected": total_selected,
        "baseline_family": NO_CONTEXT_FAMILY,
        "margin_candidate_summary": margin_rows,
        "total_candidate_summary": total_rows,
        "phase4a_parent_identity": dict(phase4a_parent["identity"]),
        "phase4a_parent_manifest_sha256": phase4a_parent.get("manifest_sha256"),
        "phase3_parent_identity": dict(phase3_parent["identity"]),
        "phase3_parent_manifest_sha256": phase3_parent.get("manifest_sha256"),
        "phase2e_parent_manifest_sha256": phase2e_parent.get("manifest_sha256"),
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


def verify_retained_baseline_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a frozen Phase 4B handoff before a later phase consumes it."""
    if payload.get("schema_version") != PHASE4B_RETAINED_BASELINE_SCHEMA:
        raise Phase4BError("unexpected Phase 4B retained-baseline schema")
    if payload.get("state") != "frozen":
        raise Phase4BError("Phase 4B retained baseline is not frozen")
    try:
        verify_signed_payload(payload, label="Phase 4B retained baseline")
    except Exception as exc:
        raise Phase4BError(str(exc)) from exc
    if payload.get("margin_context_selected") not in ALL_CONTEXT_CANDIDATES:
        raise Phase4BError("Phase 4B selected an unknown margin context family")
    if payload.get("total_context_selected") not in ALL_CONTEXT_CANDIDATES:
        raise Phase4BError("Phase 4B selected an unknown total context family")
    if any(
        payload.get(key) is not False
        for key in (
            "auxiliary_context_consumed",
            "production_activation_authorized",
            "neon_activation_authorized",
            "publication_authorized",
        )
    ):
        raise Phase4BError("Phase 4B retained baseline violates its isolation boundary")
    identity = payload.get("identity") or {}
    if (
        identity.get("schema_version") != PHASE4B_IDENTITY_SCHEMA
        or identity.get("environment") != "preview"
    ):
        raise Phase4BError("Phase 4B retained baseline lacks a Preview identity")
    if (
        not isinstance(identity.get("identity_sha256"), str)
        or not identity["identity_sha256"]
    ):
        raise Phase4BError("Phase 4B identity is malformed")
    return dict(payload)
