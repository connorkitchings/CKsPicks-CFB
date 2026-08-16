import hashlib
import json

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor

from cks_picks_cfb.data.storage import LocalStorage
from cks_picks_cfb.model_bundle_v3 import (
    REGIMES,
    TARGETS,
    load_model_bundle_v3,
    predict_with_model_bundle_v3,
)


def _ref(storage, tmp_path, name, value):
    model = DummyRegressor(strategy="constant", constant=value).fit(
        np.array([[0.0]]), np.array([value])
    )
    path = tmp_path / f"{name}.joblib"
    joblib.dump(model, path)
    payload = path.read_bytes()
    uri = f"models/{name}.joblib"
    storage.write_bytes(payload, uri)
    return {
        "artifact_uri": uri,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "features": ["x"],
    }


def test_v3_bundle_derives_spread_and_total_from_team_point_models(tmp_path):
    storage_root = tmp_path / "storage"
    storage_root.mkdir()
    storage = LocalStorage(storage_root)
    home = _ref(storage, tmp_path, "home", 28.0)
    away = _ref(storage, tmp_path, "away", 21.0)
    direct = _ref(storage, tmp_path, "direct", 44.0)
    routes = []
    for target in TARGETS:
        for regime in REGIMES:
            common = {
                "target": target,
                "regime": regime,
                "model_version": f"{target}-{regime}",
                "feature_version": "features-v3",
                "display_fallback": False,
                "high_confidence_eligible": True,
            }
            if regime == "game_1":
                routes.append(
                    {
                        **common,
                        "strategy": "points_derived",
                        "home_points": home,
                        "away_points": away,
                    }
                )
            else:
                routes.append({**common, "strategy": "direct", "direct": direct})
    raw = {
        "schema_version": "model_bundle_v3",
        "bundle_id": "v3-test",
        "code_sha": "abc",
        "training_years": [2021, 2022, 2023, 2024, 2025],
        "feature_dataset_refs": [
            {
                "dataset": "features",
                "version_id": "v1",
                "schema_version": "v1",
                "content_sha": "a" * 64,
                "uri": "lake/features",
            }
        ],
        "prior_source_policy": {"2021": 2019, "excluded_years": [2020]},
        "selection_basis": "predictive_results_only",
        "betting_validation_status": "not_evaluated",
        "routes": routes,
    }
    payload = json.dumps(raw).encode()
    storage.write_bytes(payload, "models/v3.json")
    bundle = load_model_bundle_v3(
        {
            "artifact_uri": "models/v3.json",
            "sha256": hashlib.sha256(payload).hexdigest(),
        },
        storage=storage,
    )
    result = predict_with_model_bundle_v3(
        bundle,
        pd.DataFrame({"prediction_regime": ["game_1"], "x": [1.0]}),
        storage=storage,
    )
    assert result.loc[0, "predicted_spread"] == 7.0
    assert result.loc[0, "predicted_total"] == 49.0
    assert bundle.selection_basis == "predictive_results_only"


def test_v3_bundle_executes_a_frozen_blend_route(tmp_path):
    storage_root = tmp_path / "storage"
    storage_root.mkdir()
    storage = LocalStorage(storage_root)
    prior = _ref(storage, tmp_path, "prior", 30.0)
    current = _ref(storage, tmp_path, "current", 10.0)
    routes = []
    for target in TARGETS:
        for regime in REGIMES:
            common = {
                "target": target,
                "regime": regime,
                "model_version": f"{target}-{regime}",
                "feature_version": "v3",
                "display_fallback": False,
                "high_confidence_eligible": True,
            }
            if regime == "game_2":
                routes.append(
                    {
                        **common,
                        "strategy": "blend",
                        "prior_weight": 0.25,
                        "prior": prior,
                        "current": current,
                    }
                )
            else:
                routes.append({**common, "strategy": "direct", "direct": current})
    raw = {
        "schema_version": "model_bundle_v3",
        "bundle_id": "blend-test",
        "code_sha": "abc",
        "training_years": [2021, 2022, 2023, 2024, 2025],
        "feature_dataset_refs": [
            {
                "dataset": "features",
                "version_id": "v1",
                "schema_version": "v1",
                "content_sha": "b" * 64,
                "uri": "lake/features",
            }
        ],
        "prior_source_policy": {"2021": 2019, "excluded_years": [2020]},
        "selection_basis": "predictive_results_only",
        "betting_validation_status": "not_evaluated",
        "routes": routes,
    }
    payload = json.dumps(raw).encode()
    storage.write_bytes(payload, "models/blend.json")
    bundle = load_model_bundle_v3(
        {
            "artifact_uri": "models/blend.json",
            "sha256": hashlib.sha256(payload).hexdigest(),
        },
        storage=storage,
    )
    result = predict_with_model_bundle_v3(
        bundle,
        pd.DataFrame({"prediction_regime": ["game_2"], "x": [1.0]}),
        storage=storage,
    )
    assert result.loc[0, "predicted_spread"] == 15.0
