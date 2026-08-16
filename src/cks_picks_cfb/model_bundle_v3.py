"""Canonical first-three-game model bundles with points-derived routes."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np
import pandas as pd

from cks_picks_cfb.data.storage import StorageBackend, get_storage
from cks_picks_cfb.model_bundle import (
    ModelArtifactRef,
    _artifact_ref,
    load_model_artifact,
)

TARGETS = ("spread", "total")
REGIMES = ("game_1", "game_2", "game_3", "established")


@dataclass(frozen=True)
class RouteSpecV3:
    target: str
    regime: str
    strategy: str
    model_version: str
    feature_version: str
    direct: ModelArtifactRef | None
    home_points: ModelArtifactRef | None
    away_points: ModelArtifactRef | None
    prior: ModelArtifactRef | None
    current: ModelArtifactRef | None
    prior_weight: float | None
    prior_strengths: Mapping[str, float] | None
    display_fallback: bool
    high_confidence_eligible: bool


@dataclass(frozen=True)
class ModelBundleV3:
    bundle_id: str
    code_sha: str
    training_years: tuple[int, ...]
    routes: dict[tuple[str, str], RouteSpecV3]
    feature_dataset_refs: tuple[Mapping[str, Any], ...]
    prior_source_policy: Mapping[str, Any]
    selection_basis: str
    betting_validation_status: str
    manifest_sha256: str

    def route(self, target: str, regime: str) -> RouteSpecV3:
        return self.routes[(target, regime)]


def load_model_bundle_v3(
    spec: Mapping[str, Any], *, storage: StorageBackend | None = None
) -> ModelBundleV3:
    """Load a checksummed eight-route canonical early-season bundle."""
    uri = str(spec.get("artifact_uri") or "")
    expected_sha = str(spec.get("sha256") or "")
    if not uri or len(expected_sha) != 64:
        raise ValueError("model_bundle_v3 requires artifact_uri and sha256")
    store = storage or get_storage()
    payload = store.read_bytes(uri)
    actual_sha = hashlib.sha256(payload).hexdigest()
    if actual_sha != expected_sha:
        raise ValueError("model_bundle_v3 checksum mismatch")
    raw = json.loads(payload.decode("utf-8"))
    if raw.get("schema_version") != "model_bundle_v3":
        raise ValueError("Unsupported model bundle schema")
    routes: dict[tuple[str, str], RouteSpecV3] = {}
    for item in raw.get("routes") or ():
        target, regime = str(item["target"]), str(item["regime"])
        key = (target, regime)
        if key in routes:
            raise ValueError(f"Duplicate model route: {target}/{regime}")
        strategy = str(item.get("strategy") or "direct")
        if strategy not in {"direct", "points_derived", "blend"}:
            raise ValueError(f"Unsupported v3 route strategy: {strategy}")
        direct = home_points = away_points = prior = current = None
        prior_weight: float | None = None
        prior_strengths: Mapping[str, float] | None = None
        if strategy == "direct":
            direct = _artifact_ref(item.get("direct") or item, f"{target}/{regime}")
        elif strategy == "points_derived":
            home_points = _artifact_ref(
                item.get("home_points") or {}, f"{target}/{regime} home points"
            )
            away_points = _artifact_ref(
                item.get("away_points") or {}, f"{target}/{regime} away points"
            )
        if strategy == "blend":
            prior = _artifact_ref(item.get("prior") or {}, f"{target}/{regime} prior")
            current = _artifact_ref(
                item.get("current") or {}, f"{target}/{regime} current"
            )
            prior_weight = float(item.get("prior_weight"))
            if not 0.0 <= prior_weight <= 1.0:
                raise ValueError(f"Invalid prior weight for {target}/{regime}")
        if item.get("prior_strengths") is not None:
            prior_strengths = {
                str(key): float(value)
                for key, value in dict(item["prior_strengths"]).items()
            }
        routes[key] = RouteSpecV3(
            target=target,
            regime=regime,
            strategy=strategy,
            model_version=str(item["model_version"]),
            feature_version=str(item["feature_version"]),
            direct=direct,
            home_points=home_points,
            away_points=away_points,
            prior=prior,
            current=current,
            prior_weight=prior_weight,
            prior_strengths=prior_strengths,
            display_fallback=bool(item.get("display_fallback", False)),
            high_confidence_eligible=bool(item.get("high_confidence_eligible", False)),
        )
    expected = {(target, regime) for target in TARGETS for regime in REGIMES}
    if set(routes) != expected:
        raise ValueError(
            f"model_bundle_v3 requires eight routes; missing={sorted(expected - set(routes))}"
        )
    years = tuple(int(year) for year in raw.get("training_years") or ())
    if years != (2021, 2022, 2023, 2024, 2025):
        raise ValueError("v3 production bundle training years must be 2021-2025")
    refs = tuple(raw.get("feature_dataset_refs") or ())
    if not refs:
        raise ValueError("v3 bundle requires feature_dataset_refs")
    policy = dict(raw.get("prior_source_policy") or {})
    if policy.get("2021") != 2019 or policy.get("excluded_years") != [2020]:
        raise ValueError("v3 bundle has invalid prior source policy")
    selection_basis = str(raw.get("selection_basis") or "")
    if selection_basis not in {"predictive_results_only", "predictive_and_betting"}:
        raise ValueError("v3 bundle must declare a supported selection_basis")
    betting_validation_status = str(raw.get("betting_validation_status") or "")
    if betting_validation_status not in {"not_evaluated", "validated"}:
        raise ValueError("v3 bundle must declare betting_validation_status")
    return ModelBundleV3(
        bundle_id=str(raw["bundle_id"]),
        code_sha=str(raw["code_sha"]),
        training_years=years,
        routes=routes,
        feature_dataset_refs=refs,
        prior_source_policy=policy,
        selection_basis=selection_basis,
        betting_validation_status=betting_validation_status,
        manifest_sha256=actual_sha,
    )


def _predict_ref(
    ref: ModelArtifactRef, frame: pd.DataFrame, storage: StorageBackend
) -> np.ndarray:
    missing = set(ref.features) - set(frame.columns)
    if missing:
        raise ValueError(f"Bundle feature frame is missing: {sorted(missing)}")
    model, _ = load_model_artifact(
        {"artifact_uri": ref.artifact_uri, "sha256": ref.sha256},
        storage=storage,
        require_durable=True,
    )
    from cks_picks_cfb.models.regime_training import _model_values

    values = _model_values(frame, ref.features)
    prediction = np.asarray(model.predict(values), dtype=float)
    if not np.isfinite(prediction).all():
        raise ValueError(
            f"Model artifact {ref.artifact_uri} produced non-finite predictions"
        )
    return prediction


def _prepare_route_frame(route: RouteSpecV3, frame: pd.DataFrame) -> pd.DataFrame:
    """Materialize route-specific shrinkage only when an artifact needs it."""
    needs_shrinkage = any(
        "_shrunk_" in feature
        for ref in (route.direct, route.home_points, route.away_points)
        if ref is not None
        for feature in ref.features
    )
    if not needs_shrinkage:
        return frame
    if not route.prior_strengths:
        raise ValueError(f"{route.target}/{route.regime} lacks shrinkage provenance")
    from cks_picks_cfb.models.early_season import add_ordinal_shrinkage_features

    values, _ = add_ordinal_shrinkage_features(
        frame, prior_strengths=route.prior_strengths
    )
    return values


def predict_with_model_bundle_v3(
    bundle: ModelBundleV3,
    frame: pd.DataFrame,
    *,
    storage: StorageBackend | None = None,
) -> pd.DataFrame:
    """Route canonical ordinal rows and derive direct or point-score outputs."""
    if "prediction_regime" not in frame:
        raise ValueError("Inference frame is missing prediction_regime")
    unknown = set(frame["prediction_regime"].dropna().astype(str)) - set(REGIMES)
    if unknown:
        raise ValueError(f"Unsupported canonical regimes: {sorted(unknown)}")
    store = storage or get_storage()
    result = frame.copy()
    for target in TARGETS:
        predictions = pd.Series(np.nan, index=frame.index, dtype=float)
        versions = pd.Series("", index=frame.index, dtype=object)
        eligible = pd.Series(False, index=frame.index, dtype=bool)
        for regime in REGIMES:
            mask = frame["prediction_regime"].eq(regime)
            if not mask.any():
                continue
            route = bundle.route(target, regime)
            subset = _prepare_route_frame(route, frame.loc[mask])
            if route.strategy == "direct":
                assert route.direct is not None
                prediction = _predict_ref(route.direct, subset, store)
            elif route.strategy == "points_derived":
                assert route.home_points is not None and route.away_points is not None
                home = np.clip(_predict_ref(route.home_points, subset, store), 0, None)
                away = np.clip(_predict_ref(route.away_points, subset, store), 0, None)
                prediction = home - away if target == "spread" else home + away
            else:
                assert route.prior is not None and route.current is not None
                assert route.prior_weight is not None
                prior = _predict_ref(route.prior, subset, store)
                current = _predict_ref(route.current, subset, store)
                prediction = (
                    route.prior_weight * prior + (1.0 - route.prior_weight) * current
                )
            predictions.loc[mask] = prediction
            versions.loc[mask] = route.model_version
            eligible.loc[mask] = route.high_confidence_eligible
        result[f"predicted_{target}"] = predictions
        result[f"{target}_model_version"] = versions
        result[f"{target}_high_confidence_eligible"] = eligible
    return result
