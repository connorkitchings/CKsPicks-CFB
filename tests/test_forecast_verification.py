"""Focused V5-04B forecast verification tests."""

from __future__ import annotations

import json

import pytest

from cks_picks_cfb.data.data_first_forecast_v1 import (
    FORECAST_MANIFEST_SCHEMA,
    REQUIRED_RATING_MANIFEST_URI,
)
from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.forecast.forecast_verification import (
    VerificationError,
    verify_forecast_artifact,
)


def _forecast_manifest(
    *, code_sha: str = "a" * 40, selected_horizon: str = "expanding"
) -> dict:
    return signed_payload(
        {
            "schema_version": FORECAST_MANIFEST_SCHEMA,
            "state": "frozen",
            "identity": {
                "environment": "preview",
                "run_id": "forecast-v1-test",
                "code_sha": code_sha,
            },
            "parents": {
                "rating_manifest_uri": REQUIRED_RATING_MANIFEST_URI,
                "measurement_manifest_uri": "measurement/uri",
                "repair_manifest_uri": "repair/uri",
            },
            "output_refs": {
                "forecast_registry": {
                    "dataset": "forecast_registry",
                    "schema_version": "data_first_forecast_registry_v1",
                },
                "forecast_model": {
                    "dataset": "forecast_model",
                    "schema_version": "data_first_forecast_model_v1",
                },
                "forecast_prediction": {
                    "dataset": "forecast_prediction",
                    "schema_version": "data_first_forecast_prediction_v1",
                },
                "forecast_calibration": {
                    "dataset": "forecast_calibration",
                    "schema_version": "data_first_forecast_calibration_v1",
                },
                "window_comparison": {
                    "dataset": "window_comparison",
                    "schema_version": "data_first_window_comparison_v1",
                },
                "forecast_selection": {
                    "dataset": "forecast_selection",
                    "schema_version": "data_first_forecast_selection_v1",
                },
            },
            "selected_horizon": selected_horizon,
            "head_recipes": {},
            "calibration_summary": {},
            "preflight_sha256": "b" * 64,
            "horizon_sha256": "c" * 64,
            "production_activation_authorized": False,
        }
    )


class _FakeStorage:
    def __init__(self, manifest: dict) -> None:
        self.manifest = manifest
        self.uri = "forecast/manifest.json"

    def read_bytes(self, uri: str) -> bytes:
        if uri != self.uri:
            raise FileNotFoundError(uri)
        return json.dumps(self.manifest, sort_keys=True).encode()

    def exists(self, uri: str) -> bool:
        return uri == self.uri


def test_verifier_accepts_valid_manifest():
    manifest = _forecast_manifest()
    storage = _FakeStorage(manifest)
    result = verify_forecast_artifact(
        storage,
        manifest_uri=storage.uri,
        expected_code_sha="a" * 40,
        environment="preview",
        rating_manifest_uri=REQUIRED_RATING_MANIFEST_URI,
        measurement_manifest_uri="measurement/uri",
        repair_manifest_uri="repair/uri",
    )
    assert result["verified"] is True
    assert result["selected_horizon"] == "expanding"
    assert result["output_count"] == 6


def test_verifier_rejects_wrong_code_sha():
    manifest = _forecast_manifest(code_sha="b" * 40)
    storage = _FakeStorage(manifest)
    with pytest.raises(VerificationError, match="code SHA"):
        verify_forecast_artifact(
            storage,
            manifest_uri=storage.uri,
            expected_code_sha="a" * 40,
            environment="preview",
            rating_manifest_uri=REQUIRED_RATING_MANIFEST_URI,
            measurement_manifest_uri="measurement/uri",
            repair_manifest_uri="repair/uri",
        )


def test_verifier_rejects_wrong_environment():
    manifest = _forecast_manifest()
    storage = _FakeStorage(manifest)
    with pytest.raises(VerificationError, match="preview"):
        verify_forecast_artifact(
            storage,
            manifest_uri=storage.uri,
            expected_code_sha="a" * 40,
            environment="production",
            rating_manifest_uri=REQUIRED_RATING_MANIFEST_URI,
            measurement_manifest_uri="measurement/uri",
            repair_manifest_uri="repair/uri",
        )


def test_verifier_rejects_wrong_rating_parent_uri():
    manifest = _forecast_manifest()
    storage = _FakeStorage(manifest)
    with pytest.raises(VerificationError, match="rating parent URI"):
        verify_forecast_artifact(
            storage,
            manifest_uri=storage.uri,
            expected_code_sha="a" * 40,
            environment="preview",
            rating_manifest_uri="wrong/rating/uri",
            measurement_manifest_uri="measurement/uri",
            repair_manifest_uri="repair/uri",
        )


def test_verifier_rejects_unknown_horizon():
    manifest = _forecast_manifest(selected_horizon="unknown")
    storage = _FakeStorage(manifest)
    with pytest.raises(VerificationError, match="horizon"):
        verify_forecast_artifact(
            storage,
            manifest_uri=storage.uri,
            expected_code_sha="a" * 40,
            environment="preview",
            rating_manifest_uri=REQUIRED_RATING_MANIFEST_URI,
            measurement_manifest_uri="measurement/uri",
            repair_manifest_uri="repair/uri",
        )


def test_verifier_rejects_production_authorized():
    manifest = _forecast_manifest()
    manifest["production_activation_authorized"] = True
    manifest = signed_payload(
        {k: v for k, v in manifest.items() if k != "signature"}
        | {"production_activation_authorized": True}
    )
    storage = _FakeStorage(manifest)
    with pytest.raises(VerificationError, match="production"):
        verify_forecast_artifact(
            storage,
            manifest_uri=storage.uri,
            expected_code_sha="a" * 40,
            environment="preview",
            rating_manifest_uri=REQUIRED_RATING_MANIFEST_URI,
            measurement_manifest_uri="measurement/uri",
            repair_manifest_uri="repair/uri",
        )
