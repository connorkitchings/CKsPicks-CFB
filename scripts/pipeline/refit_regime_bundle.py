#!/usr/bin/env python3
"""Refit a frozen regime design on 2021-2025 and publish model_bundle_v2."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
from dataclasses import asdict
from pathlib import Path

import joblib
from dotenv import load_dotenv
from omegaconf import OmegaConf

from cks_picks_cfb.data.lake import DatasetRef, read_dataset
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.model_bundle import load_model_bundle_v2
from cks_picks_cfb.models.regime_training import (
    TARGET_COLUMNS,
    fit_candidate_model,
)
from cks_picks_cfb.models.training_policy import (
    policy_from_mapping,
    validate_feature_lineage,
)


def _load_ref(storage, uri: str) -> DatasetRef:
    raw = json.loads(storage.read_bytes(uri).decode("utf-8"))
    return DatasetRef(
        dataset=str(raw["dataset"]),
        version_id=str(raw["version_id"]),
        schema_version=str(raw["schema_version"]),
        content_sha=str(raw["content_sha"]),
        uri=str(raw["uri"]),
    )


def _write_model(storage, model, uri: str) -> dict:
    buffer = io.BytesIO()
    joblib.dump(model, buffer)
    payload = buffer.getvalue()
    sha256 = hashlib.sha256(payload).hexdigest()
    if storage.exists(uri):
        if storage.read_bytes(uri) != payload:
            raise FileExistsError(f"Immutable model collision: {uri}")
    else:
        storage.write_bytes(payload, uri)
    return {"artifact_uri": uri, "sha256": sha256}


def _code_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-ref-uri", required=True)
    parser.add_argument("--routing-report-uri", required=True)
    parser.add_argument("--bundle-id", required=True)
    parser.add_argument(
        "--environment", choices=("preview", "production"), required=True
    )
    parser.add_argument(
        "--experiment",
        type=Path,
        default=Path("conf/experiment/week0_regimes.yaml"),
    )
    args = parser.parse_args()
    os.environ["CFB_ARTIFACT_ENV"] = args.environment
    storage = get_storage()
    feature_ref = _load_ref(storage, args.feature_ref_uri)
    frame = read_dataset(storage, feature_ref)
    experiment = OmegaConf.load(args.experiment)
    policy = policy_from_mapping(
        OmegaConf.to_container(
            OmegaConf.load(str(experiment.training_policy)), resolve=True
        )
    )
    validate_feature_lineage(frame, policy)
    if tuple(sorted(frame["season"].astype(int).unique())) != policy.labeled_years:
        raise ValueError("Production refit dataset must contain exactly 2021-2025")
    report = json.loads(storage.read_bytes(args.routing_report_uri).decode("utf-8"))
    if report.get("training_policy") != policy.schema_version:
        raise ValueError("Routing report uses a different training policy")
    prior_features = tuple(str(value) for value in experiment.prior_features)
    current_features = tuple(str(value) for value in experiment.current_features)
    hybrid_features = tuple(dict.fromkeys([*prior_features, *current_features]))
    prefix = f"artifacts/{args.environment}/models/{args.bundle_id}"
    blend_components: dict[str, tuple[dict, dict]] = {}
    for target, target_column in TARGET_COLUMNS.items():
        prior_model = fit_candidate_model(
            frame,
            features=prior_features,
            target_column=target_column,
            kind="direct_ridge",
        )
        current_model = fit_candidate_model(
            frame[frame["prediction_regime"] == "established"],
            features=current_features,
            target_column=target_column,
            kind="direct_ridge",
        )
        prior_ref = _write_model(
            storage, prior_model, f"{prefix}/components/{target}-preseason.joblib"
        )
        current_ref = _write_model(
            storage, current_model, f"{prefix}/components/{target}-current.joblib"
        )
        blend_components[target] = (
            {**prior_ref, "features": list(prior_features)},
            {**current_ref, "features": list(current_features)},
        )

    routes = []
    regimes = ("preseason", "one_game", "two_games", "three_games", "established")
    for target, target_column in TARGET_COLUMNS.items():
        for games, regime in enumerate(regimes):
            selected = str(report["routing"][target][regime])
            fallback = selected == "display_fallback"
            candidate = "direct_ridge" if fallback else selected
            common = {
                "target": target,
                "regime": regime,
                "model_version": f"{args.bundle_id}-{target}-{regime}",
                "feature_version": feature_ref.version_id,
                "display_fallback": fallback,
                "high_confidence_eligible": not fallback,
            }
            if candidate == "blend":
                prior_ref, current_ref = blend_components[target]
                routes.append(
                    {
                        **common,
                        "strategy": "blend",
                        "preseason": prior_ref,
                        "current": current_ref,
                        "prior_weight": float(
                            report["blend_weights"][target][str(games)]
                        ),
                    }
                )
                continue
            kind = (
                candidate
                if candidate in {"direct_ridge", "direct_catboost"}
                else "direct_ridge"
            )
            features = (
                prior_features
                if regime == "preseason"
                else current_features
                if regime == "established"
                else hybrid_features
            )
            model = fit_candidate_model(
                frame[frame["prediction_regime"] == regime],
                features=features,
                target_column=target_column,
                kind=kind,
            )
            artifact = _write_model(
                storage, model, f"{prefix}/routes/{target}-{regime}.joblib"
            )
            routes.append(
                {
                    **common,
                    "strategy": "direct",
                    "direct": {**artifact, "features": list(features)},
                }
            )

    manifest = {
        "schema_version": "model_bundle_v2",
        "bundle_id": args.bundle_id,
        "code_sha": _code_sha(),
        "training_years": list(policy.production_refit_years),
        "feature_dataset_refs": [asdict(feature_ref)],
        "prior_source_policy": {"2021": 2019, "excluded_years": [2020]},
        "blend_weights": report["blend_weights"],
        "promotion_reports": {"regime_routing": args.routing_report_uri},
        "routes": routes,
    }
    payload = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")
    manifest_uri = f"{prefix}/manifest.json"
    if storage.exists(manifest_uri):
        if storage.read_bytes(manifest_uri) != payload:
            raise FileExistsError(f"Immutable bundle exists: {manifest_uri}")
    else:
        storage.write_bytes(payload, manifest_uri)
    sha256 = hashlib.sha256(payload).hexdigest()
    bundle = load_model_bundle_v2(
        {"artifact_uri": manifest_uri, "sha256": sha256}, storage=storage
    )
    print(
        json.dumps(
            {
                "artifact_uri": manifest_uri,
                "sha256": sha256,
                "bundle_id": bundle.bundle_id,
                "route_count": len(bundle.routes),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
