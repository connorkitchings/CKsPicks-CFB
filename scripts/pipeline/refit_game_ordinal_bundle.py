#!/usr/bin/env python3
"""Refit sealed Games 1–4 routes and compatibility-refit established Ridge."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from omegaconf import OmegaConf

from cks_picks_cfb.data.lake import DatasetRef, read_dataset
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.features.v2_recency import canonical_prediction_regime
from cks_picks_cfb.models.early_season import add_ordinal_shrinkage_features
from cks_picks_cfb.models.regime_training import fit_candidate_model
from cks_picks_cfb.models.training_policy import (
    labeled_training_frame,
    policy_from_mapping,
)
from cks_picks_cfb.models.v4_feature_variants import selected_variant_features

EARLY_REGIMES = ("game_1", "game_2", "game_3", "game_4")
TARGET_COLUMNS = {"spread": "spread_target", "total": "total_target"}


def _code_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _write_model(storage, model, uri: str) -> dict[str, Any]:
    buffer = io.BytesIO()
    joblib.dump(model, buffer)
    payload = buffer.getvalue()
    digest = hashlib.sha256(payload).hexdigest()
    if storage.exists(uri):
        if storage.read_bytes(uri) != payload:
            raise FileExistsError(f"Immutable model collision: {uri}")
    else:
        storage.write_bytes(payload, uri)
    return {"artifact_uri": uri, "sha256": digest}


def _prior_features(frame) -> list[str]:
    features = [
        column
        for column in frame
        if column.startswith(("home_prior_", "away_prior_"))
        and frame[column].dtype.kind in "biufc"
    ]
    if not features:
        raise ValueError("Prior-only fallback has no numeric prior features")
    return features


def _current_features(frame) -> list[str]:
    features = [
        column
        for column in frame
        if column.startswith(
            ("home_current_", "away_current_", "home_adj_", "away_adj_")
        )
        and frame[column].dtype.kind in "biufc"
    ]
    if not features:
        raise ValueError("Blend has no numeric current features")
    return features


def _selection_report(report: dict[str, Any]) -> dict[str, Any]:
    selection = report.get("selection_report")
    if not isinstance(selection, dict):
        raise ValueError("Final routing report must embed its frozen selection report")
    if selection.get("stage") != "selection" or not selection.get(
        "selection_design_sha"
    ):
        raise ValueError("Routing report has no sealed selection design")
    if report.get("selection_report_sha") != selection["selection_design_sha"]:
        raise ValueError("Routing report selection SHA mismatch")
    return selection


def _weights(
    selection: dict[str, Any], target: str, regime: str, candidate: str
) -> float:
    raw_weights = selection.get("blend_weights", {})
    if target in raw_weights and regime in raw_weights[target]:
        # Legacy flat shape: blend_weights[target][regime].
        return float(raw_weights[target][regime])
    # V4 shape: blend_weights[feature_variant][target][regime], resolved
    # through the frozen variant of this route's blend candidate.
    variant = _variant(selection, target, regime, candidate)
    weights = raw_weights.get(variant, {}).get(target, {})
    if regime not in weights:
        raise ValueError(f"Frozen blend weight missing for {target}/{regime}")
    return float(weights[regime])


def _strengths(
    selection: dict[str, Any], target: str, regime: str, candidate: str
) -> dict[str, float]:
    try:
        raw = selection["reports"][target][regime][candidate][
            "selected_prior_strengths"
        ]
    except KeyError as exc:
        raise ValueError(
            f"Frozen strengths missing for {target}/{regime}/{candidate}"
        ) from exc
    if not raw:
        raise ValueError(f"Candidate {candidate} has no frozen shrinkage design")
    return {key: float(value) for key, value in raw.items()}


def _variant(
    selection: dict[str, Any], target: str, regime: str, candidate: str
) -> str:
    try:
        return str(
            selection["reports"][target][regime][candidate][
                "selected_feature_variant"
            ]
        )
    except KeyError as exc:
        raise ValueError(
            f"Frozen V4 feature variant missing for {target}/{regime}/{candidate}"
        ) from exc


def _compatibility_features(
    spec, source: dict[str, Any] | None, target: str
) -> list[str]:
    features = list(spec.established_features)
    if source is None:
        return features
    matches = [
        route
        for route in source.get("routes", [])
        if route.get("target") == target and route.get("regime") == "established"
    ]
    if len(matches) != 1:
        raise ValueError(f"Established source bundle lacks one {target} route")
    route = matches[0]
    if route.get("strategy") != "direct":
        raise ValueError("Established source route must be direct Ridge")
    source_features = list((route.get("direct") or route).get("features") or [])
    if source_features != features:
        raise ValueError("Established feature order differs from the v2 source bundle")
    return features


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-ref-uri", required=True)
    parser.add_argument("--routing-report-uri", required=True)
    parser.add_argument("--bundle-id", required=True)
    parser.add_argument(
        "--environment", choices=("preview", "production"), required=True
    )
    parser.add_argument(
        "--experiment", type=Path, default=Path("conf/experiment/week0_regimes.yaml")
    )
    parser.add_argument("--established-source-bundle-uri")
    args = parser.parse_args()
    storage = get_storage(environment=args.environment)
    ref = DatasetRef(**json.loads(storage.read_bytes(args.feature_ref_uri).decode()))
    spec = OmegaConf.load(args.experiment)
    policy = policy_from_mapping(
        OmegaConf.to_container(OmegaConf.load(spec.training_policy), resolve=True)
    )
    report = json.loads(storage.read_bytes(args.routing_report_uri).decode())
    if (
        report.get("stage") != "finalized"
        or report.get("selection_basis") != "predictive_results_only"
    ):
        raise ValueError("Refit requires a finalized result-only routing report")
    if report.get("feature_track", "strict") != "strict":
        raise ValueError("Reconstructed research reports cannot refit a V4 bundle")
    selection = _selection_report(report)
    source = (
        json.loads(storage.read_bytes(args.established_source_bundle_uri).decode())
        if args.established_source_bundle_uri
        else None
    )
    raw = read_dataset(storage, ref).assign(
        prediction_regime=lambda values: values["prediction_regime"].map(
            canonical_prediction_regime
        )
    )
    tracks = set(raw.get("v4_feature_track", pd.Series("legacy")).dropna().astype(str))
    if tracks == {"reconstructed"}:
        raise ValueError("Reconstructed V4 feature references cannot refit a bundle")
    if tracks == {"strict"} and not bool(raw["v4_activation_eligible"].all()):
        raise ValueError("Strict V4 feature reference is not activation eligible")
    frame = labeled_training_frame(raw, policy)
    frame = frame[frame["season"].isin(policy.production_refit_years)].copy()
    if {"home_points", "away_points"} - set(frame.columns):
        frame["home_points"] = (
            frame["total_target"] + frame["spread_target"]
        ) / 2.0
        frame["away_points"] = (
            frame["total_target"] - frame["spread_target"]
        ) / 2.0
    prior_features = _prior_features(frame)
    current_features = _current_features(frame)
    prefix = f"artifacts/{args.environment}/models/{args.bundle_id}"
    existing = storage.list_files(prefix)
    if existing:
        raise FileExistsError(
            f"Refit bundle prefix is not empty; choose a new immutable bundle id: {prefix}"
        )
    routes = []
    shrunk_cache: dict[str, tuple[Any, list[str]]] = {}
    for target, target_column in TARGET_COLUMNS.items():
        for regime in EARLY_REGIMES:
            candidate = report["routing"][target][regime]
            subset = frame[frame["prediction_regime"] == regime]
            common = {
                "target": target,
                "regime": regime,
                "model_version": f"{args.bundle_id}-{target}-{regime}",
                "feature_version": ref.version_id,
                "display_fallback": candidate == "baseline",
                "high_confidence_eligible": candidate != "baseline",
            }
            if candidate == "baseline":
                artifact = _write_model(
                    storage,
                    fit_candidate_model(
                        subset,
                        features=prior_features,
                        target_column=target_column,
                        kind="direct_ridge",
                    ),
                    f"{prefix}/routes/{target}-{regime}-baseline.joblib",
                )
                routes.append(
                    {
                        **common,
                        "strategy": "direct",
                        "direct": {**artifact, "features": prior_features},
                    }
                )
                continue
            if candidate == "blend":
                prior = _write_model(
                    storage,
                    fit_candidate_model(
                        frame,
                        features=prior_features,
                        target_column=target_column,
                        kind="direct_ridge",
                    ),
                    f"{prefix}/routes/{target}-{regime}-prior.joblib",
                )
                established = frame[frame["prediction_regime"] == "established"]
                current = _write_model(
                    storage,
                    fit_candidate_model(
                        established,
                        features=current_features,
                        target_column=target_column,
                        kind="direct_ridge",
                    ),
                    f"{prefix}/routes/{target}-{regime}-current.joblib",
                )
                routes.append(
                    {
                        **common,
                        "strategy": "blend",
                        "prior_weight": _weights(selection, target, regime, candidate),
                        "prior": {**prior, "features": prior_features},
                        "current": {**current, "features": current_features},
                    }
                )
                continue
            if candidate == "established":
                features = _compatibility_features(spec, source, target)
                artifact = _write_model(
                    storage,
                    fit_candidate_model(
                        frame[frame["prediction_regime"] == "established"],
                        features=features,
                        target_column=target_column,
                        kind="direct_ridge",
                    ),
                    f"{prefix}/routes/{target}-{regime}-established.joblib",
                )
                routes.append(
                    {
                        **common,
                        "strategy": "direct",
                        "direct": {**artifact, "features": features},
                        "handoff_source": "established",
                    }
                )
                continue
            strengths = _strengths(selection, target, regime, candidate)
            variant = _variant(selection, target, regime, candidate)
            cache_key = json.dumps({"strengths": strengths, "variant": variant}, sort_keys=True)
            if cache_key not in shrunk_cache:
                values, features = add_ordinal_shrinkage_features(
                    frame, prior_strengths=strengths
                )
                shrunk_cache[cache_key] = (
                    values,
                    [
                        *features,
                        *selected_variant_features(
                            frame,
                            family_order=list(spec.preseason_feature_variants),
                            context_features=list(spec.context_features),
                            variant=variant,
                        ),
                    ],
                )
            shrunk, features = shrunk_cache[cache_key]
            route_frame = shrunk[shrunk["prediction_regime"] == regime]
            kind = (
                "direct_catboost" if candidate.endswith("catboost") else "direct_ridge"
            )
            if candidate.startswith("points_"):
                home = _write_model(
                    storage,
                    fit_candidate_model(
                        route_frame,
                        features=features,
                        target_column="home_points",
                        kind=kind,
                    ),
                    f"{prefix}/routes/{target}-{regime}-home.joblib",
                )
                away = _write_model(
                    storage,
                    fit_candidate_model(
                        route_frame,
                        features=features,
                        target_column="away_points",
                        kind=kind,
                    ),
                    f"{prefix}/routes/{target}-{regime}-away.joblib",
                )
                routes.append(
                    {
                        **common,
                        "strategy": "points_derived",
                        "home_points": {**home, "features": features},
                        "away_points": {**away, "features": features},
                        "prior_strengths": strengths,
                        "feature_variant": variant,
                    }
                )
            else:
                artifact = _write_model(
                    storage,
                    fit_candidate_model(
                        route_frame,
                        features=features,
                        target_column=target_column,
                        kind=kind,
                    ),
                    f"{prefix}/routes/{target}-{regime}.joblib",
                )
                routes.append(
                    {
                        **common,
                        "strategy": "direct",
                        "direct": {**artifact, "features": features},
                        "prior_strengths": strengths,
                        "feature_variant": variant,
                    }
                )
        features = _compatibility_features(spec, source, target)
        established = fit_candidate_model(
            frame[frame["prediction_regime"] == "established"],
            features=features,
            target_column=target_column,
            kind="direct_ridge",
        )
        artifact = _write_model(
            storage, established, f"{prefix}/routes/{target}-established.joblib"
        )
        routes.append(
            {
                "target": target,
                "regime": "established",
                "strategy": "direct",
                "model_version": f"{args.bundle_id}-{target}-established",
                "feature_version": ref.version_id,
                "display_fallback": True,
                "high_confidence_eligible": False,
                "direct": {**artifact, "features": features},
                "compatibility_refit": {
                    "source_bundle_uri": args.established_source_bundle_uri,
                    "estimator": "Ridge(alpha=10.0)",
                },
            }
        )
    manifest = {
        "schema_version": "model_bundle_v3",
        "bundle_id": args.bundle_id,
        "code_sha": _code_sha(),
        "training_years": list(policy.production_refit_years),
        "feature_dataset_refs": [asdict(ref)],
        "prior_source_policy": {"2021": 2019, "excluded_years": [2020]},
        "selection_basis": "predictive_results_only",
        "feature_track": "strict",
        "activation_eligible": True,
        "betting_validation_status": "not_evaluated",
        "promotion_reports": {
            "game_ordinal_predictive_routing": args.routing_report_uri,
            "selection_design_sha": selection["selection_design_sha"],
        },
        "routes": routes,
    }
    payload = json.dumps(manifest, indent=2, sort_keys=True).encode()
    uri = f"{prefix}/manifest.json"
    if storage.exists(uri):
        if storage.read_bytes(uri) != payload:
            raise FileExistsError(f"Immutable bundle exists: {uri}")
    else:
        storage.write_bytes(payload, uri)
    print(
        json.dumps(
            {"artifact_uri": uri, "sha256": hashlib.sha256(payload).hexdigest()},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
