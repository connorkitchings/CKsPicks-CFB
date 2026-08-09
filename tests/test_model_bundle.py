import hashlib
import json

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.dummy import DummyRegressor

from cks_picks_cfb.data.storage import LocalStorage
from cks_picks_cfb.model_bundle import (
    REGIMES,
    TARGETS,
    load_model_artifact,
    load_model_bundle_v2,
    predict_with_model_bundle_v2,
    validate_model_feature_allowlist,
)


def test_loads_checksummed_durable_model(tmp_path):
    model_path = tmp_path / "model.joblib"
    joblib.dump(DummyRegressor(), model_path)
    payload = model_path.read_bytes()
    storage_root = tmp_path / "storage"
    storage_root.mkdir()
    storage = LocalStorage(storage_root)
    storage.write_bytes(payload, "models/test.joblib")

    model, checksum = load_model_artifact(
        {
            "artifact_uri": "models/test.joblib",
            "sha256": hashlib.sha256(payload).hexdigest(),
        },
        storage=storage,
        require_durable=True,
    )
    assert isinstance(model, DummyRegressor)
    assert checksum == hashlib.sha256(payload).hexdigest()


def test_rejects_bad_checksum_and_missing_durable_uri(tmp_path):
    storage = LocalStorage(tmp_path)
    storage.write_bytes(b"not-a-model", "models/test.joblib")
    with pytest.raises(ValueError, match="checksum mismatch"):
        load_model_artifact(
            {"artifact_uri": "models/test.joblib", "sha256": "bad"},
            storage=storage,
        )
    with pytest.raises(ValueError, match="Durable"):
        load_model_artifact({"path": "models/local.joblib"}, require_durable=True)


def _bundle_payload():
    return {
        "schema_version": "model_bundle_v2",
        "bundle_id": "bundle-1",
        "code_sha": "abc",
        "training_years": [2021, 2022, 2023, 2024, 2025],
        "feature_dataset_refs": [
            {
                "dataset": "point_in_time_matchups",
                "version_id": "features-1",
                "schema_version": "2",
                "content_sha": "b" * 64,
                "uri": "lake/gold/features-1/data.parquet",
            }
        ],
        "prior_source_policy": {"2021": 2019, "excluded_years": [2020]},
        "blend_weights": {
            "spread": {"0": 1, "1": 0.75, "2": 0.5, "3": 0.25, "4": 0},
            "total": {"0": 1, "1": 0.8, "2": 0.55, "3": 0.2, "4": 0},
        },
        "promotion_reports": {},
        "routes": [
            {
                "target": target,
                "regime": regime,
                "strategy": "direct",
                "artifact_uri": f"models/{target}-{regime}.joblib",
                "sha256": "a" * 64,
                "model_version": f"{target}-{regime}-v1",
                "feature_version": "features-v1",
                "features": ["home_off_success_rate"],
                "display_fallback": False,
                "high_confidence_eligible": True,
            }
            for target in TARGETS
            for regime in REGIMES
        ],
    }


def test_loads_complete_ten_cell_routing_manifest(tmp_path):
    storage = LocalStorage(tmp_path)
    payload = json.dumps(_bundle_payload()).encode()
    storage.write_bytes(payload, "models/bundle.json")
    bundle = load_model_bundle_v2(
        {
            "artifact_uri": "models/bundle.json",
            "sha256": hashlib.sha256(payload).hexdigest(),
        },
        storage=storage,
    )
    assert len(bundle.routes) == 10
    assert bundle.route("spread", "one_game").high_confidence_eligible is True
    assert bundle.route("spread", "one_game").strategy == "direct"


def test_bundle_rejects_missing_route_and_bookmaker_feature(tmp_path):
    storage = LocalStorage(tmp_path)
    raw = _bundle_payload()
    raw["routes"].pop()
    payload = json.dumps(raw).encode()
    storage.write_bytes(payload, "models/incomplete.json")
    with pytest.raises(ValueError, match="ten cells"):
        load_model_bundle_v2(
            {
                "artifact_uri": "models/incomplete.json",
                "sha256": hashlib.sha256(payload).hexdigest(),
            },
            storage=storage,
        )
    with pytest.raises(ValueError, match="Bookmaker-derived"):
        validate_model_feature_allowlist(["home_off_success_rate", "total_line"])


def test_blend_route_executes_both_checksummed_components(tmp_path):
    storage = LocalStorage(tmp_path)
    refs = {}
    for name, constant in (("prior", 10.0), ("current", 2.0)):
        model = DummyRegressor(strategy="constant", constant=constant).fit(
            np.array([[0.0]]), np.array([constant])
        )
        path = tmp_path / f"{name}.joblib"
        joblib.dump(model, path)
        payload = path.read_bytes()
        uri = f"models/{name}.joblib"
        storage.write_bytes(payload, uri)
        refs[name] = {
            "artifact_uri": uri,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "features": [f"{name}_feature"],
        }
    raw = _bundle_payload()
    for route in raw["routes"]:
        if route["regime"] == "one_game":
            target = route["target"]
            route.clear()
            route.update(
                {
                    "target": target,
                    "regime": "one_game",
                    "strategy": "blend",
                    "model_version": f"{target}-blend-v1",
                    "feature_version": "features-v1",
                    "preseason": refs["prior"],
                    "current": refs["current"],
                    "prior_weight": raw["blend_weights"][target]["1"],
                    "display_fallback": False,
                    "high_confidence_eligible": True,
                }
            )
    payload = json.dumps(raw).encode()
    storage.write_bytes(payload, "models/blend-bundle.json")
    bundle = load_model_bundle_v2(
        {
            "artifact_uri": "models/blend-bundle.json",
            "sha256": hashlib.sha256(payload).hexdigest(),
        },
        storage=storage,
    )
    frame = pd.DataFrame(
        {
            "prediction_regime": ["one_game"],
            "prior_feature": [1.0],
            "current_feature": [1.0],
        }
    )
    result = predict_with_model_bundle_v2(bundle, frame, storage=storage)
    assert result.loc[0, "predicted_spread"] == pytest.approx(8.0)
    assert result.loc[0, "predicted_total"] == pytest.approx(8.4)
