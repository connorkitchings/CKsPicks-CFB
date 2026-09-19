"""Focused independent and conditional forecast verification tests."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from cks_picks_cfb.data.data_first_forecast_v1 import (
    FORECAST_CALIBRATION_COLUMNS,
    FORECAST_DATASETS,
    FORECAST_MANIFEST_SCHEMA,
    FORECAST_PREDICTION_COLUMNS,
    REQUIRED_RATING_MANIFEST_URI,
)
from cks_picks_cfb.data.data_first_phase2 import (
    DEVELOPMENT_SEASONS,
    FORBIDDEN_SEASONS,
)
from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.data.lake import canonical_frame_digest
from cks_picks_cfb.forecast import forecast_verification as fv
from cks_picks_cfb.forecast.conditional_verification import (
    FORECAST_CANONICAL_SHA256,
    FROZEN_OUTPUT_HASHES,
    FROZEN_RAW_SHA256,
    PERMITTED_USE,
    ConditionalVerificationError,
    conditional_identity,
    publish_conditional_verification,
    publish_failure,
    run_conditional_verification,
    verify_conditional_publication,
)


class _MemoryStorage:
    def __init__(self, objects: dict[str, bytes] | None = None) -> None:
        self.objects = dict(objects or {})

    def read_bytes(self, uri: str) -> bytes:
        if uri not in self.objects:
            raise FileNotFoundError(uri)
        return self.objects[uri]

    def write_bytes(self, data: bytes, uri: str) -> None:
        self.objects[uri] = data

    def exists(self, uri: str) -> bool:
        return uri in self.objects

    def list_files(self, prefix: str) -> list[str]:
        return sorted(uri for uri in self.objects if uri.startswith(prefix))


def _calibration() -> pd.DataFrame:
    return pd.DataFrame.from_records(
        [
            {
                "target": target,
                "season": season,
                "residual_count": 10,
                "variance": float(season),
                "fallback_reason": "",
            }
            for target in ("margin", "total")
            for season in (2022, 2023, 2024, 2025)
        ],
        columns=FORECAST_CALIBRATION_COLUMNS,
    )


def _models() -> pd.DataFrame:
    return pd.DataFrame.from_records(
        [
            {
                "target": target,
                "head": "reference",
                "retained": True,
                "alpha": 10.0,
            }
            for target in ("margin", "total")
        ]
    )


def _output_refs() -> dict[str, dict]:
    return {
        name: {
            "dataset": dataset,
            "schema_version": schema,
            "records_sha": hashlib.sha256(name.encode()).hexdigest(),
            "row_count": 1,
        }
        for name, (dataset, schema) in FORECAST_DATASETS.items()
        if name != "candidate_manifest"
    }


def _forecast_manifest(
    *, code_sha: str = "a" * 40, selected_horizon: str = "expanding"
) -> dict:
    output_refs = _output_refs()
    calibration = _calibration()
    preflight_sha = hashlib.sha256(
        json.dumps(
            {name: value["records_sha"] for name, value in output_refs.items()},
            sort_keys=True,
        ).encode()
    ).hexdigest()
    return signed_payload(
        {
            "schema_version": FORECAST_MANIFEST_SCHEMA,
            "state": "frozen",
            "identity": {
                "environment": "preview",
                "run_id": "forecast-v1-test",
                "code_sha": code_sha,
                "development_seasons": list(DEVELOPMENT_SEASONS),
                "forbidden_seasons": list(FORBIDDEN_SEASONS),
            },
            "parents": {
                "rating_manifest_uri": REQUIRED_RATING_MANIFEST_URI,
                "measurement_manifest_uri": "measurement/uri",
                "repair_manifest_uri": "repair/uri",
            },
            "output_refs": output_refs,
            "selected_horizon": selected_horizon,
            "head_recipes": {
                "margin": {"head": "reference", "alpha": 10.0},
                "total": {"head": "reference", "alpha": 10.0},
            },
            "calibration_summary": {
                "records_sha": canonical_frame_digest(
                    calibration, columns=FORECAST_CALIBRATION_COLUMNS
                ),
                "row_count": 8,
                "by_target": {
                    target: {str(season): float(season) for season in range(2022, 2026)}
                    for target in ("margin", "total")
                },
            },
            "preflight_sha256": preflight_sha,
            "horizon_sha256": "c" * 64,
            "production_activation_authorized": False,
        }
    )


def _patch_reconstruction(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        fv,
        "_verify_parent_manifests",
        lambda *_args, **_kwargs: (
            {},
            {},
            {},
            {"rating": "r", "measurement": "m", "repair": "p"},
        ),
    )
    monkeypatch.setattr(
        fv,
        "_read_output",
        lambda *_args, **kwargs: fv.StoredOutput(
            ref={"row_count": 1, "records_sha": kwargs["label"]},
            frame=pd.DataFrame(),
        ),
    )
    monkeypatch.setattr(
        fv,
        "_load_reconstruction_inputs",
        lambda *_args, **_kwargs: (pd.DataFrame(),) * 4,
    )
    monkeypatch.setattr(
        fv,
        "_reconstruct_outputs",
        lambda **_kwargs: (
            {"forecast_model": _models(), "forecast_calibration": _calibration()},
            {
                "selected_horizon": "expanding",
                "selected_heads": {"margin": "reference", "total": "reference"},
                "horizon_sha256": "c" * 64,
                "calibration_variances": {
                    target: {season: float(season) for season in range(2022, 2026)}
                    for target in ("margin", "total")
                },
                "offsets_sha256": "d" * 64,
            },
        ),
    )
    monkeypatch.setattr(
        fv,
        "_compare_outputs",
        lambda **_kwargs: {
            name: {"row_count": 1, "records_sha": "x"} for name in _output_refs()
        },
    )


def test_verifier_reconstructs_after_envelope_checks(monkeypatch: pytest.MonkeyPatch):
    _patch_reconstruction(monkeypatch)
    manifest = _forecast_manifest()
    storage = _MemoryStorage(
        {"forecast/manifest.json": json.dumps(manifest, sort_keys=True).encode()}
    )
    result = fv.verify_forecast_artifact(
        storage,
        manifest_uri="forecast/manifest.json",
        expected_code_sha="a" * 40,
        environment="preview",
        rating_manifest_uri=REQUIRED_RATING_MANIFEST_URI,
        measurement_manifest_uri="measurement/uri",
        repair_manifest_uri="repair/uri",
    )
    assert result["verified"] is True
    assert result["rejected_seasons"] == [2020, 2026]
    assert result["output_count"] == 6


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda manifest: manifest["identity"].update(code_sha="b" * 40), "code SHA"),
        (lambda manifest: manifest.update(selected_horizon="unknown"), "horizon"),
        (
            lambda manifest: manifest.update(production_activation_authorized=True),
            "production",
        ),
    ],
)
def test_verifier_rejects_invalid_envelope(mutation, message):
    unsigned = _forecast_manifest()
    unsigned.pop("manifest_sha256")
    mutation(unsigned)
    manifest = signed_payload(unsigned)
    storage = _MemoryStorage(
        {"forecast/manifest.json": json.dumps(manifest, sort_keys=True).encode()}
    )
    with pytest.raises(fv.VerificationError, match=message):
        fv.verify_forecast_artifact(
            storage,
            manifest_uri="forecast/manifest.json",
            expected_code_sha="a" * 40,
            environment="preview",
            rating_manifest_uri=REQUIRED_RATING_MANIFEST_URI,
            measurement_manifest_uri="measurement/uri",
            repair_manifest_uri="repair/uri",
        )


def test_verifier_rejects_wrong_parent_before_data_read():
    manifest = _forecast_manifest()
    storage = _MemoryStorage(
        {"forecast/manifest.json": json.dumps(manifest, sort_keys=True).encode()}
    )
    with pytest.raises(fv.VerificationError, match="rating_manifest_uri"):
        fv.verify_forecast_artifact(
            storage,
            manifest_uri="forecast/manifest.json",
            expected_code_sha="a" * 40,
            environment="preview",
            rating_manifest_uri="wrong/uri",
            measurement_manifest_uri="measurement/uri",
            repair_manifest_uri="repair/uri",
        )


def test_real_shape_prediction_digest_detects_producer_perturbation():
    row = {
        "horizon": "expanding",
        "head": "reference",
        "target": "margin",
        "season": 2025,
        "week": 1,
        "game_id": 1,
        "actual": 3.0,
        "prediction": 2.0,
        "absolute_error": 1.0,
        "gaussian_crps": 0.5,
        "offset": 0.0,
        "training_seasons": "2015,2016,2017,2018,2019,2021,2022,2023,2024",
        "completed_game_stage": 0,
        "venue_unknown": True,
    }
    frame = pd.DataFrame([row], columns=FORECAST_PREDICTION_COLUMNS)
    digest, parts = fv._reconstructed_digest("forecast_prediction", frame)
    stored = fv.StoredOutput(
        ref={"row_count": 1, "records_sha": digest}, frame=frame, parts=parts
    )
    result = fv._compare_outputs(
        stored={"forecast_prediction": stored},
        reconstructed={"forecast_prediction": frame},
    )
    assert result["forecast_prediction"]["row_count"] == 1
    perturbed = frame.copy()
    perturbed.loc[0, "prediction"] = 2.25
    with pytest.raises(fv.VerificationError, match="reconstruction"):
        fv._compare_outputs(
            stored={"forecast_prediction": stored},
            reconstructed={"forecast_prediction": perturbed},
        )


@pytest.mark.parametrize("season", [2020, 2026])
def test_rejected_seasons_fail_closed(season: int):
    with pytest.raises(fv.VerificationError, match="rejected seasons"):
        fv._assert_allowed_seasons(
            pd.DataFrame({"season": [2019, season]}), label="fixture"
        )


def test_verifier_import_boundary_excludes_producer_modules():
    tree = ast.parse(Path(fv.__file__).read_text())
    forbidden = {
        "cks_picks_cfb.forecast.offsets",
        "cks_picks_cfb.forecast.heads",
        "cks_picks_cfb.forecast.horizons",
        "cks_picks_cfb.forecast.calibration",
        "scripts.research.run_data_first_forecasts",
    }
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert forbidden.isdisjoint(imported)


def _verification_result() -> dict:
    return {
        "verified": True,
        "run_id": "forecast-v1-20260917-4600ddd-04b",
        "manifest_raw_sha256": FROZEN_RAW_SHA256["forecast"],
        "manifest_canonical_sha256": FORECAST_CANONICAL_SHA256,
        "parent_raw_sha256": {
            role: FROZEN_RAW_SHA256[role]
            for role in ("repair", "measurement", "rating")
        },
        "comparisons": {
            name: {
                "records_sha": records_sha,
                "row_count": 1,
            }
            for name, records_sha in FROZEN_OUTPUT_HASHES.items()
        },
        "rejected_seasons": [2020, 2026],
    }


def test_conditional_publication_is_signed_rereadable_and_idempotent(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        "cks_picks_cfb.forecast.conditional_verification.verify_forecast_artifact",
        lambda *_args, **_kwargs: _verification_result(),
    )
    identity = conditional_identity(
        run_id="conditional-v1-test",
        as_of="2026-09-19T12:00:00Z",
        code_sha="d" * 40,
    )
    storage = _MemoryStorage()
    evidence = run_conditional_verification(storage, identity=identity)
    assert evidence["permitted_use"] == PERMITTED_USE
    assert evidence["forecast_eligibility_restored"] is False
    applied = publish_conditional_verification(
        storage, identity=identity, reviewed_evidence=evidence
    )
    reread = verify_conditional_publication(
        storage, manifest_uri=applied["manifest_uri"]
    )
    repeated = publish_conditional_verification(
        storage, identity=identity, reviewed_evidence=evidence
    )
    assert reread["verified"] is True
    assert repeated["state"] == "already_applied"
    assert repeated["permitted_use"] == PERMITTED_USE


def test_conditional_apply_rejects_unreviewed_evidence():
    identity = conditional_identity(
        run_id="conditional-v1-test",
        as_of="2026-09-19T12:00:00Z",
        code_sha="d" * 40,
    )
    with pytest.raises(ConditionalVerificationError, match="identity mismatch"):
        publish_conditional_verification(
            _MemoryStorage(), identity=identity, reviewed_evidence={}
        )


def test_conditional_failure_evidence_grants_no_scorecard_permission():
    identity = conditional_identity(
        run_id="conditional-v1-failed",
        as_of="2026-09-19T12:00:00Z",
        code_sha="d" * 40,
    )
    storage = _MemoryStorage()
    result = publish_failure(
        storage,
        identity=identity,
        error=fv.VerificationError("forecast_prediction differs from reconstruction"),
    )
    manifest = json.loads(storage.read_bytes(result["manifest_uri"]))
    record = json.loads(storage.read_bytes(result["record_uri"]))
    assert manifest["state"] == record["state"] == "failed"
    assert manifest["permitted_use"] is record["permitted_use"] is None
    assert manifest["scorecard_authorized"] is record["scorecard_authorized"] is False
    assert manifest["output_hashes"] == record["output_hashes"] == FROZEN_OUTPUT_HASHES
