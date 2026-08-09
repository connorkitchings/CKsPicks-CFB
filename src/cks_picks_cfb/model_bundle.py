"""Portable, checksummed model artifact loading for production inference."""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import joblib
import numpy as np
import pandas as pd

from cks_picks_cfb.data.storage import StorageBackend, get_storage

TARGETS = ("spread", "total")
REGIMES = ("preseason", "one_game", "two_games", "three_games", "established")
BOOKMAKER_FEATURE_TOKENS = (
    "spread_line",
    "total_line",
    "moneyline",
    "market_",
    "bookmaker",
    "provider_count",
)


@dataclass(frozen=True)
class ModelArtifactRef:
    artifact_uri: str
    sha256: str
    features: tuple[str, ...]


@dataclass(frozen=True)
class RouteSpec:
    target: str
    regime: str
    strategy: str
    model_version: str
    feature_version: str
    direct: ModelArtifactRef | None
    preseason: ModelArtifactRef | None
    current: ModelArtifactRef | None
    prior_weight: float | None
    display_fallback: bool
    high_confidence_eligible: bool


@dataclass(frozen=True)
class ModelBundleV2:
    bundle_id: str
    schema_version: str
    code_sha: str
    training_years: tuple[int, ...]
    routes: dict[tuple[str, str], RouteSpec]
    blend_weights: dict[str, dict[int, float]]
    promotion_reports: dict[str, str]
    feature_dataset_refs: tuple[Mapping[str, Any], ...]
    prior_source_policy: Mapping[str, Any]
    manifest_sha256: str

    def route(self, target: str, regime: str) -> RouteSpec:
        try:
            return self.routes[(target, regime)]
        except KeyError as exc:
            raise KeyError(f"No frozen route for {target}/{regime}") from exc


def validate_model_feature_allowlist(features: list[str] | tuple[str, ...]) -> None:
    """Reject market-derived model inputs by contract, not convention."""
    violations = [
        feature
        for feature in features
        if any(token in feature.casefold() for token in BOOKMAKER_FEATURE_TOKENS)
    ]
    if violations:
        raise ValueError(f"Bookmaker-derived features are forbidden: {violations}")


def _validate_monotone_weights(weights: dict[int, float], target: str) -> None:
    expected = set(range(5))
    if set(weights) != expected:
        raise ValueError(f"{target} blend weights must define completed games 0-4")
    ordered = [weights[count] for count in range(5)]
    if ordered[0] != 1.0 or ordered[-1] != 0.0:
        raise ValueError(f"{target} weights must start at 1.0 and end at 0.0")
    if any(left < right for left, right in zip(ordered, ordered[1:])):
        raise ValueError(f"{target} prior weights must decrease monotonically")


def _artifact_ref(raw: Mapping[str, Any], label: str) -> ModelArtifactRef:
    uri = str(raw.get("artifact_uri") or "")
    sha256 = str(raw.get("sha256") or "")
    features = tuple(str(value) for value in raw.get("features", []))
    if not uri or len(sha256) != 64 or not features:
        raise ValueError(f"{label} requires artifact_uri, sha256, and features")
    validate_model_feature_allowlist(features)
    return ModelArtifactRef(uri, sha256, features)


def load_model_bundle_v2(
    spec: Mapping[str, Any], *, storage: StorageBackend | None = None
) -> ModelBundleV2:
    """Load and validate the frozen ten-cell production routing manifest."""
    uri = str(spec.get("artifact_uri") or "")
    expected_sha = str(spec.get("sha256") or "")
    if not uri or len(expected_sha) != 64:
        raise ValueError("model_bundle_v2 requires artifact_uri and sha256")
    store = storage or get_storage()
    payload = store.read_bytes(uri)
    actual_sha = hashlib.sha256(payload).hexdigest()
    if actual_sha != expected_sha:
        raise ValueError(
            f"Model bundle checksum mismatch: {actual_sha} != {expected_sha}"
        )
    raw = json.loads(payload.decode("utf-8"))
    if raw.get("schema_version") != "model_bundle_v2":
        raise ValueError("Unsupported model bundle schema")
    routes: dict[tuple[str, str], RouteSpec] = {}
    for item in raw.get("routes", []):
        target = str(item["target"])
        regime = str(item["regime"])
        key = (target, regime)
        if key in routes:
            raise ValueError(f"Duplicate model route: {target}/{regime}")
        strategy = str(item.get("strategy") or "direct")
        if strategy not in {"direct", "blend"}:
            raise ValueError(f"Unsupported route strategy: {strategy}")
        if strategy == "blend" and regime not in {
            "one_game",
            "two_games",
            "three_games",
        }:
            raise ValueError("Blend routes are allowed only for 1-3 games")
        direct = None
        preseason = None
        current = None
        prior_weight = None
        if strategy == "direct":
            direct_raw = item.get("direct") or item
            direct = _artifact_ref(direct_raw, f"{target}/{regime} direct model")
        else:
            preseason = _artifact_ref(
                item.get("preseason") or {}, f"{target}/{regime} preseason model"
            )
            current = _artifact_ref(
                item.get("current") or {}, f"{target}/{regime} current model"
            )
            prior_weight = float(item["prior_weight"])
            if not 0.0 <= prior_weight <= 1.0:
                raise ValueError("Blend prior_weight must be between zero and one")
        routes[key] = RouteSpec(
            target=target,
            regime=regime,
            strategy=strategy,
            model_version=str(item["model_version"]),
            feature_version=str(item["feature_version"]),
            direct=direct,
            preseason=preseason,
            current=current,
            prior_weight=prior_weight,
            display_fallback=bool(item.get("display_fallback", False)),
            high_confidence_eligible=bool(item.get("high_confidence_eligible", False)),
        )
    expected_routes = {(target, regime) for target in TARGETS for regime in REGIMES}
    if set(routes) != expected_routes:
        missing = sorted(expected_routes - set(routes))
        extra = sorted(set(routes) - expected_routes)
        raise ValueError(
            f"Routing manifest must contain ten cells; missing={missing}, extra={extra}"
        )
    blend_weights: dict[str, dict[int, float]] = {}
    for target in TARGETS:
        weights = {
            int(count): float(weight)
            for count, weight in raw.get("blend_weights", {}).get(target, {}).items()
        }
        _validate_monotone_weights(weights, target)
        blend_weights[target] = weights
    training_years = tuple(int(year) for year in raw.get("training_years", []))
    if training_years != (2021, 2022, 2023, 2024, 2025):
        raise ValueError("Production model bundle training years must be 2021-2025")
    feature_dataset_refs = tuple(raw.get("feature_dataset_refs") or ())
    if not feature_dataset_refs:
        raise ValueError("Production model bundle requires feature_dataset_refs")
    for ref in feature_dataset_refs:
        required = {"dataset", "version_id", "schema_version", "content_sha", "uri"}
        if required - set(ref):
            raise ValueError("Feature dataset reference is incomplete")
    prior_source_policy = dict(raw.get("prior_source_policy") or {})
    if prior_source_policy.get("2021") != 2019:
        raise ValueError("Model bundle must record the 2021 -> 2019 prior override")
    if prior_source_policy.get("excluded_years") != [2020]:
        raise ValueError("Model bundle must exclude 2020 lineage")
    for target in TARGETS:
        for games, regime in enumerate(REGIMES[:4]):
            route = routes[(target, regime)]
            if (
                route.strategy == "blend"
                and route.prior_weight != blend_weights[target][games]
            ):
                raise ValueError(
                    f"{target}/{regime} route weight does not match bundle weights"
                )
    return ModelBundleV2(
        bundle_id=str(raw["bundle_id"]),
        schema_version="model_bundle_v2",
        code_sha=str(raw["code_sha"]),
        training_years=training_years,
        routes=routes,
        blend_weights=blend_weights,
        promotion_reports={
            str(key): str(value)
            for key, value in raw.get("promotion_reports", {}).items()
        },
        feature_dataset_refs=feature_dataset_refs,
        prior_source_policy=prior_source_policy,
        manifest_sha256=actual_sha,
    )


def predict_with_model_bundle_v2(
    bundle: ModelBundleV2,
    frame: pd.DataFrame,
    *,
    storage: StorageBackend | None = None,
) -> pd.DataFrame:
    """Route every row through the frozen target/regime manifest.

    The input must carry ``prediction_regime``. Models are loaded from their
    checksummed durable artifacts; no registry or local fallback is consulted.
    """
    if "prediction_regime" not in frame:
        raise ValueError("Inference frame is missing prediction_regime")
    unknown = set(frame["prediction_regime"].dropna().astype(str)) - set(REGIMES)
    if unknown:
        raise ValueError(f"Unsupported prediction regimes: {sorted(unknown)}")
    store = storage or get_storage()
    output = frame.copy()
    for target in TARGETS:
        values = pd.Series(np.nan, index=frame.index, dtype=float)
        versions = pd.Series("", index=frame.index, dtype=object)
        eligible = pd.Series(False, index=frame.index, dtype=bool)
        for regime in REGIMES:
            mask = frame["prediction_regime"] == regime
            if not mask.any():
                continue
            route = bundle.route(target, regime)
            if route.strategy == "direct":
                assert route.direct is not None
                missing = set(route.direct.features) - set(frame.columns)
                if missing:
                    raise ValueError(
                        f"{target}/{regime} is missing features: {sorted(missing)}"
                    )
                model, _ = load_model_artifact(
                    {
                        "artifact_uri": route.direct.artifact_uri,
                        "sha256": route.direct.sha256,
                    },
                    storage=store,
                    require_durable=True,
                )
                values.loc[mask] = model.predict(
                    frame.loc[mask, list(route.direct.features)]
                )
            else:
                assert route.preseason is not None
                assert route.current is not None
                assert route.prior_weight is not None
                required = set(route.preseason.features) | set(route.current.features)
                missing = required - set(frame.columns)
                if missing:
                    raise ValueError(
                        f"{target}/{regime} is missing features: {sorted(missing)}"
                    )
                preseason_model, _ = load_model_artifact(
                    {
                        "artifact_uri": route.preseason.artifact_uri,
                        "sha256": route.preseason.sha256,
                    },
                    storage=store,
                    require_durable=True,
                )
                current_model, _ = load_model_artifact(
                    {
                        "artifact_uri": route.current.artifact_uri,
                        "sha256": route.current.sha256,
                    },
                    storage=store,
                    require_durable=True,
                )
                prior = preseason_model.predict(
                    frame.loc[mask, list(route.preseason.features)]
                )
                current = current_model.predict(
                    frame.loc[mask, list(route.current.features)]
                )
                values.loc[mask] = (
                    route.prior_weight * prior + (1.0 - route.prior_weight) * current
                )
            versions.loc[mask] = route.model_version
            eligible.loc[mask] = route.high_confidence_eligible
        output[f"predicted_{target}"] = values
        output[f"{target}_model_version"] = versions
        output[f"{target}_high_confidence_eligible"] = eligible
    return output


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_model_artifact(
    spec: Mapping[str, Any],
    *,
    storage: StorageBackend | None = None,
    require_durable: bool = False,
) -> tuple[Any, str]:
    """Load a model from durable storage first, with verified legacy fallback."""
    artifact_uri = spec.get("artifact_uri")
    expected = spec.get("sha256")
    if artifact_uri:
        if not expected:
            raise ValueError(f"Model artifact {artifact_uri} has no sha256")
        store = storage or get_storage()
        payload = store.read_bytes(str(artifact_uri))
        actual = hashlib.sha256(payload).hexdigest()
        if actual != expected:
            raise ValueError(
                f"Model checksum mismatch for {artifact_uri}: {actual} != {expected}"
            )
        return joblib.load(io.BytesIO(payload)), actual

    if require_durable:
        raise ValueError("Durable model artifact_uri and sha256 are required")
    local_path = Path(str(spec.get("path", "")))
    if not local_path.is_file():
        raise FileNotFoundError(f"Model artifact not found: {local_path}")
    actual = sha256_file(local_path)
    if expected and actual != expected:
        raise ValueError(
            f"Model checksum mismatch for {local_path}: {actual} != {expected}"
        )
    return joblib.load(local_path), actual
