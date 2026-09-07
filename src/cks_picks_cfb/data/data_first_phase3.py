"""Fail-closed contracts for data-first Phase 3 research."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd

from cks_picks_cfb.data.data_first_phase2 import DEVELOPMENT_SEASONS, FORBIDDEN_SEASONS
from cks_picks_cfb.data.data_first_phase2d import (
    PHASE3_DATASETS,
    REPLACEMENT_ELIGIBILITY_SCHEMA,
    Phase2dError,
    canonical_bytes,
    sha256,
    verify_signed_payload,
)

PHASE3_IDENTITY_SCHEMA = "data_first_phase3_run_identity_v1"
PHASE3_RETAINED_CORE_SCHEMA = "data_first_phase3_retained_core_v1"
CORE_CANDIDATES = (
    "epa_only",
    "quality_core_equal",
    "without_success_rate",
    "without_explosive_rate_20",
    "without_points_per_scoring_opportunity",
    "without_epa_per_play",
    "epa_pass_rush",
    "quality_core_epa_split",
)
QUALITY_COMPONENTS = (
    "epa_per_play",
    "success_rate",
    "explosive_rate_20",
    "points_per_scoring_opportunity",
)


class Phase3Error(ValueError):
    """Raised when Phase 3 inputs or decisions violate the sealed contract."""


def _ref_key(ref: Mapping[str, Any]) -> tuple[str, str, str, str, str]:
    fields = ("dataset", "version_id", "schema_version", "content_sha", "uri")
    if missing := [field for field in fields if not ref.get(field)]:
        raise Phase3Error(f"Phase 3 parent ref is missing fields: {missing}")
    return tuple(str(ref[field]) for field in fields)


def verify_core_eligibility(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return the exact sorted 70-ref Phase 3 parent set or fail closed."""
    if payload.get("schema_version") != REPLACEMENT_ELIGIBILITY_SCHEMA:
        raise Phase3Error("Phase 3 requires the replacement Phase 2d eligibility schema")
    if payload.get("state") != "eligible":
        raise Phase3Error("Phase 2d eligibility handoff is not eligible")
    try:
        verify_signed_payload(payload, label="Phase 2d eligibility")
    except Phase2dError as exc:
        raise Phase3Error(str(exc)) from exc
    if payload.get("production_activation_authorized") is not False:
        raise Phase3Error("Phase 3 parent must forbid production activation")
    if tuple(payload.get("development_seasons") or ()) != DEVELOPMENT_SEASONS:
        raise Phase3Error("Phase 3 parent has the wrong development seasons")
    if tuple(payload.get("forbidden_seasons") or ()) != FORBIDDEN_SEASONS:
        raise Phase3Error("Phase 3 parent has the wrong forbidden seasons")

    refs = [dict(ref) for ref in payload.get("phase3_input_refs") or []]
    expected = {(season, dataset) for season in DEVELOPMENT_SEASONS for dataset in PHASE3_DATASETS}
    seen: set[tuple[int, str]] = set()
    immutable: set[tuple[str, str, str, str, str]] = set()
    for ref in refs:
        key = (int(ref.get("season", -1)), str(ref.get("dataset")))
        if key in seen:
            raise Phase3Error(f"duplicate Phase 3 parent: {key}")
        seen.add(key)
        identity = _ref_key(ref)
        if identity in immutable:
            raise Phase3Error(f"repeated immutable Phase 3 parent: {identity[1]}")
        immutable.add(identity)
        if ref.get("eligible") is not True:
            raise Phase3Error(f"ineligible Phase 3 parent: {key}")
        if list(ref.get("permitted_uses") or []) != ["phase3_measurement_validation"]:
            raise Phase3Error(f"unexpected Phase 3 parent use: {key}")
    if seen != expected or len(refs) != len(expected):
        raise Phase3Error("Phase 3 parent membership must be exactly 70 refs")
    return sorted(refs, key=lambda ref: (int(ref["season"]), str(ref["dataset"])))


def phase3_identity(*, run_id: str, environment: str, code_sha: str, config_sha: str, core_eligibility_uri: str, core_eligibility_sha256: str) -> dict[str, Any]:
    """Construct a deterministic Preview-only Phase 3 run identity."""
    if environment != "preview":
        raise Phase3Error("Phase 3 is Preview-only")
    if not run_id or not code_sha or not config_sha:
        raise Phase3Error("Phase 3 identity requires run ID, code SHA, and config SHA")
    payload = {
        "schema_version": PHASE3_IDENTITY_SCHEMA,
        "run_id": run_id,
        "environment": environment,
        "code_sha": code_sha,
        "config_sha": config_sha,
        "core_eligibility_uri": core_eligibility_uri,
        "core_eligibility_sha256": core_eligibility_sha256,
        "development_seasons": list(DEVELOPMENT_SEASONS),
        "forbidden_seasons": list(FORBIDDEN_SEASONS),
        "auxiliary_context_permitted": False,
        "production_activation_authorized": False,
    }
    payload["identity_sha256"] = sha256(payload)
    return payload


def validate_candidate_losses(losses: pd.DataFrame) -> None:
    """Require identical complete candidate/target/game loss populations."""
    required = {"candidate", "target", "season", "week", "game_id", "absolute_error"}
    if missing := sorted(required - set(losses.columns)):
        raise Phase3Error(f"candidate losses missing columns: {missing}")
    if losses.empty:
        raise Phase3Error("candidate losses are empty")
    if losses["season"].isin(FORBIDDEN_SEASONS).any():
        raise Phase3Error("candidate losses include 2020")
    if set(losses["candidate"]) != set(CORE_CANDIDATES):
        raise Phase3Error("candidate registry differs from the sealed Phase 3 set")
    if set(losses["target"]) != {"margin", "total"}:
        raise Phase3Error("candidate losses must include margin and total")
    key_columns = ["candidate", "target", "season", "week", "game_id"]
    if losses.duplicated(key_columns).any():
        raise Phase3Error("candidate losses contain duplicate target-game rows")
    errors = pd.to_numeric(losses["absolute_error"], errors="coerce")
    if errors.isna().any() or not errors.map(float).map(__import__("math").isfinite).all():
        raise Phase3Error("candidate losses contain non-finite errors")
    expected: set[tuple[str, int, int, int]] | None = None
    for candidate in CORE_CANDIDATES:
        for target in ("margin", "total"):
            subset = losses[(losses["candidate"] == candidate) & (losses["target"] == target)]
            keys = set(subset[["season", "week", "game_id"]].itertuples(index=False, name=None))
            if expected is None:
                expected = keys
            elif keys != expected:
                raise Phase3Error("candidate populations are not identical")


def retained_core(losses: pd.DataFrame) -> dict[str, Any]:
    """Apply sealed primary score and simplicity tie-breaking to losses.

    Bootstrap and seasonal gates are supplied by the runner as explicit columns;
    this pure decision rule refuses a candidate without every required gate.
    """
    validate_candidate_losses(losses)
    required = {"bootstrap_excludes_zero", "coverage_equal", "seasonal_gate_passed"}
    if missing := sorted(required - set(losses.columns)):
        raise Phase3Error(f"candidate losses missing gate columns: {missing}")
    summary = (
        losses.groupby("candidate", sort=False)
        .agg(
            pooled_mae=("absolute_error", "mean"),
            bootstrap_excludes_zero=("bootstrap_excludes_zero", "all"),
            coverage_equal=("coverage_equal", "all"),
            seasonal_gate_passed=("seasonal_gate_passed", "all"),
        )
        .reset_index()
    )
    baseline = float(summary.loc[summary["candidate"] == "epa_only", "pooled_mae"].iloc[0])
    summary["improvement_pct"] = (baseline - summary["pooled_mae"]) / baseline * 100
    passing = summary[
        (summary["candidate"] != "epa_only")
        & (summary["improvement_pct"] >= 0.5)
        & summary["bootstrap_excludes_zero"]
        & summary["coverage_equal"]
        & summary["seasonal_gate_passed"]
    ].copy()
    if passing.empty:
        selected = "epa_only"
    else:
        complexity = {"epa_only": 1, "epa_pass_rush": 2, "quality_core_equal": 4, "quality_core_epa_split": 5,
                      "without_success_rate": 3, "without_explosive_rate_20": 3,
                      "without_points_per_scoring_opportunity": 3, "without_epa_per_play": 3}
        best = float(passing["pooled_mae"].min())
        selected = min(
            passing.loc[passing["pooled_mae"] <= best * 1.005, "candidate"],
            key=lambda candidate: (complexity[candidate], candidate),
        )
    return {
        "schema_version": PHASE3_RETAINED_CORE_SCHEMA,
        "selected_candidate": selected,
        "baseline_candidate": "epa_only",
        "candidate_summary": summary.sort_values("candidate").to_dict("records"),
        "manifest_sha256": sha256({"selected_candidate": selected, "summary": summary.sort_values("candidate").to_dict("records")}),
    }


def canonical_payload(value: Mapping[str, Any]) -> bytes:
    """Expose canonical serialization for immutable Phase 3 JSON artifacts."""
    return canonical_bytes(value)
