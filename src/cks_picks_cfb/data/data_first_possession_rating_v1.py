"""Fail-closed contracts for the Preview-only V5 possession rating tournament."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from cks_picks_cfb.data.data_first_phase2 import DEVELOPMENT_SEASONS, FORBIDDEN_SEASONS
from cks_picks_cfb.data.data_first_phase2d import (
    sha256,
    signed_payload,
    verify_signed_payload,
)
from cks_picks_cfb.data.data_first_phase3_v2 import verify_repair_manifest
from cks_picks_cfb.data.data_first_possession_v1 import POSSESSION_MANIFEST_SCHEMA

POSSESSION_RATING_IDENTITY_SCHEMA = "data_first_possession_rating_identity_v1"
POSSESSION_RATING_MANIFEST_SCHEMA = "data_first_possession_retained_rating_v1"
POSSESSION_RATING_OUTPUT_ROOT = (
    "artifacts/research/data-first-football-v1/possession-v1/ratings/runs"
)
REQUIRED_R9_CERTIFICATION_SHA256 = (
    "fc26a3d03416e688dc437ad863653dfac7df6faad51b478a7b94f466c0d870c3"
)

DEFINITIONS = ("ppp", "epa_per_possession")
PRIOR_FAMILIES = (
    "neutral",
    "rho_0_60",
    "recruiting_ridge",
    "returning_production_ridge",
    "continuity_ridge",
    "all_context_ridge",
)
UPDATERS = ("exposure", "half_life_2", "half_life_4", "half_life_8", "kalman")
OUTER_SEASONS = (2018, 2019, 2021, 2022, 2023, 2024, 2025)
RATING_DATASETS = {
    "rating_registry": (
        "possession_rating_registry",
        "data_first_possession_rating_registry_v1",
    ),
    "priors": ("possession_rating_prior", "data_first_possession_rating_prior_v1"),
    "noise_fits": (
        "possession_rating_noise_fit",
        "data_first_possession_rating_noise_fit_v1",
    ),
    "rating_states": (
        "possession_rating_state",
        "data_first_possession_rating_state_v1",
    ),
    "team_states": ("possession_team_state", "data_first_possession_team_state_v1"),
    "bridge_predictions": (
        "possession_rating_bridge_prediction",
        "data_first_possession_rating_bridge_prediction_v1",
    ),
    "attribution": (
        "possession_rating_attribution",
        "data_first_possession_rating_attribution_v1",
    ),
}

RATING_REGISTRY_COLUMNS = (
    "candidate_id",
    "definition",
    "prior_family",
    "updater",
    "reference_candidate",
    "prior_feature_count",
)
PRIOR_COLUMNS = (
    "candidate_id",
    "season",
    "team",
    "unit_role",
    "prior_mean",
    "prior_variance",
    "prior_source",
    "prior_source_season",
    "annual_decay_steps",
    "fallback_reason",
)
NOISE_FIT_COLUMNS = (
    "candidate_id",
    "season",
    "unit_role",
    "q",
    "r",
    "objective",
    "converged",
    "cold_start",
    "training_seasons",
)
RATING_STATE_COLUMNS = (
    "candidate_id",
    "definition",
    "season",
    "week",
    "game_id",
    "cutoff_utc",
    "team",
    "unit_role",
    "native_mean",
    "rating_mean",
    "rating_variance",
    "prior_mean",
    "prior_variance",
    "evidence_weight",
    "process_variance",
    "usable_exposure",
    "completed_games",
    "fallback_reason",
)
TEAM_STATE_COLUMNS = (
    "candidate_id",
    "definition",
    "season",
    "week",
    "game_id",
    "cutoff_utc",
    "team",
    "offense_rating",
    "offense_variance",
    "defense_rating",
    "defense_variance",
    "overall_rating",
    "overall_variance",
    "fallback_reason",
)
PREDICTION_COLUMNS = (
    "candidate_id",
    "definition",
    "season",
    "week",
    "game_id",
    "target",
    "actual",
    "prediction",
    "absolute_error",
    "training_seasons",
    "venue_unknown",
    "completed_game_stage",
)
ATTRIBUTION_COLUMNS = (
    "candidate_id",
    "definition",
    "prior_family",
    "updater",
    "reference_candidate",
    "pooled_mae",
    "reference_mae",
    "improvement_pct",
    "bootstrap_90_lower",
    "bootstrap_90_upper",
    "full_gate",
    "early_gate",
    "regression_gate",
    "valid",
    "selected",
    "selection_reason",
)


class PossessionRatingContractError(ValueError):
    """Raised when a V5-03 input or artifact escapes its sealed boundary."""


def candidate_id(definition: str, prior_family: str, updater: str) -> str:
    if (
        definition not in DEFINITIONS
        or prior_family not in PRIOR_FAMILIES
        or updater not in UPDATERS
    ):
        raise PossessionRatingContractError("unknown possession rating candidate part")
    return f"{definition}__{prior_family}__{updater}"


def candidate_registry() -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "candidate_id": candidate_id(definition, prior, updater),
            "definition": definition,
            "prior_family": prior,
            "updater": updater,
            "reference_candidate": candidate_id(definition, "rho_0_60", "exposure"),
            "prior_feature_count": 0
            if prior in {"neutral", "rho_0_60"}
            else (3 if prior == "all_context_ridge" else 1),
        }
        for definition in DEFINITIONS
        for prior in PRIOR_FAMILIES
        for updater in UPDATERS
    )


def validate_config(payload: Mapping[str, Any]) -> None:
    expected = [entry["candidate_id"] for entry in candidate_registry()]
    if payload.get("schema_version") != "data_first_possession_rating_config_v1":
        raise PossessionRatingContractError(
            "unexpected possession rating config schema"
        )
    if (
        tuple(payload.get("development_seasons") or ()) != DEVELOPMENT_SEASONS
        or tuple(payload.get("forbidden_seasons") or ()) != FORBIDDEN_SEASONS
    ):
        raise PossessionRatingContractError("rating season policy drifted")
    if payload.get("candidates") != expected:
        raise PossessionRatingContractError("rating candidate registry drifted")
    selection = payload.get("selection") or {}
    if selection != {
        "outer_seasons": list(OUTER_SEASONS),
        "ridge_alpha": 10,
        "minimum_improvement_pct": 0.5,
        "maximum_regression_pct": 5.0,
        "bootstrap_replicates": 2000,
        "bootstrap_seed": 20260908,
        "bootstrap_confidence": 0.90,
    }:
        raise PossessionRatingContractError("rating selection contract drifted")
    if payload.get("production_activation_authorized") is not False:
        raise PossessionRatingContractError(
            "rating config may not authorize production"
        )


def rating_identity(
    *,
    run_id: str,
    as_of: str,
    code_sha: str,
    config_sha: str,
    measurement_manifest_uri: str,
    measurement_manifest_raw_sha256: str,
    repair_manifest_uri: str,
    repair_manifest_raw_sha256: str,
) -> dict[str, Any]:
    if not all(
        (
            run_id,
            as_of,
            code_sha,
            config_sha,
            measurement_manifest_uri,
            measurement_manifest_raw_sha256,
            repair_manifest_uri,
            repair_manifest_raw_sha256,
        )
    ):
        raise PossessionRatingContractError("rating identity is incomplete")
    value = {
        "schema_version": POSSESSION_RATING_IDENTITY_SCHEMA,
        "run_id": run_id,
        "environment": "preview",
        "as_of": as_of,
        "code_sha": code_sha,
        "config_sha": config_sha,
        "measurement_manifest_uri": measurement_manifest_uri,
        "measurement_manifest_raw_sha256": measurement_manifest_raw_sha256,
        "repair_manifest_uri": repair_manifest_uri,
        "repair_manifest_raw_sha256": repair_manifest_raw_sha256,
        "development_seasons": list(DEVELOPMENT_SEASONS),
        "forbidden_seasons": list(FORBIDDEN_SEASONS),
    }
    return value | {"identity_sha256": sha256(value)}


def verify_parents(
    measurement: Mapping[str, Any], repair: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reject historical Phase 4 substitutes and unsafe possession parents."""
    if measurement.get("schema_version") != POSSESSION_MANIFEST_SCHEMA:
        raise PossessionRatingContractError(
            "V5-03 requires a possession measurement manifest"
        )
    try:
        verify_signed_payload(measurement, label="possession measurement manifest")
    except ValueError as exc:
        raise PossessionRatingContractError(str(exc)) from exc
    # The r9 producer manifest is a signed immutable result rather than a
    # mutable lifecycle record; its reviewed certification checksum is the
    # eligibility proof carried forward to V5-11B.
    if (
        measurement.get("certification_sha256") != REQUIRED_R9_CERTIFICATION_SHA256
        or measurement.get("production_activation_authorized") is not False
    ):
        raise PossessionRatingContractError(
            "possession measurements are not an eligible Preview parent"
        )
    identity = measurement.get("identity") or {}
    if (
        identity.get("environment") != "preview"
        or identity.get("run_id") != "possession-v1-measurements-20260921-r9"
    ):
        raise PossessionRatingContractError(
            "V5-11B accepts only independently verified r9 measurements"
        )
    try:
        repair_verified = verify_repair_manifest(repair)
    except ValueError as exc:
        raise PossessionRatingContractError(str(exc)) from exc
    return dict(measurement), repair_verified


def retained_manifest(
    *,
    identity: Mapping[str, Any],
    parents: Mapping[str, Any],
    output_refs: Mapping[str, Any],
    selected_candidate: str,
    selection: Mapping[str, Any],
) -> dict[str, Any]:
    if selected_candidate not in {
        entry["candidate_id"] for entry in candidate_registry()
    }:
        raise PossessionRatingContractError("retained rating has an unsealed candidate")
    return signed_payload(
        {
            "schema_version": POSSESSION_RATING_MANIFEST_SCHEMA,
            "state": "frozen",
            "identity": dict(identity),
            "parents": dict(parents),
            "output_refs": dict(output_refs),
            "selected_candidate": selected_candidate,
            "selection": dict(selection),
            "production_activation_authorized": False,
        }
    )
