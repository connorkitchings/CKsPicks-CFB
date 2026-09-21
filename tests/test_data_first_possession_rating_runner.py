"""Evidence-bound apply contracts for the V5-03 rating runner."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import pytest

from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.data.data_first_possession_rating_v1 import (
    RATING_DATASETS,
    REQUIRED_R9_CERTIFICATION_SHA256,
)
from cks_picks_cfb.data.data_first_possession_v1 import POSSESSION_MANIFEST_SCHEMA
from cks_picks_cfb.ratings.possession_rating_materializer import (
    RatingTournamentInputs,
)
from scripts.research import run_data_first_possession_ratings as runner

_FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "ratings"
    / "test_possession_rating_materializer.py"
)
_spec = importlib.util.spec_from_file_location("_rating_mat_fixture", _FIXTURE_PATH)
_fixture_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fixture_module)
_fixture = _fixture_module._fixture


class _MemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.write_order: list[str] = []

    def exists(self, uri: str) -> bool:
        return uri in self.objects

    def read_bytes(self, uri: str) -> bytes:
        return self.objects[uri]

    def write_bytes(self, data: bytes, path: str) -> None:
        self.objects[path] = data
        self.write_order.append(path)

    def list_files(self, prefix: str) -> list[str]:
        return sorted(key for key in self.objects if key.startswith(prefix))


_MEASUREMENT_URI = "artifacts/parents/possession/measurement-manifest.json"
_REPAIR_URI = "artifacts/parents/repair/repair-manifest.json"


def _seed_parents(storage: _MemoryStorage) -> None:
    population_ref = {
        "dataset": "possession_population",
        "version_id": "v1",
        "schema_version": "data_first_possession_population_v1",
        "content_sha": "a" * 64,
        "uri": "lake/gold/dataset=possession_population/version=v1/data.parquet",
    }
    measurement = signed_payload(
        {
            "schema_version": POSSESSION_MANIFEST_SCHEMA,
            "identity": {
                "environment": "preview",
                "run_id": "possession-v1-measurements-20260921-r9",
            },
            "certification_sha256": REQUIRED_R9_CERTIFICATION_SHA256,
            "output_refs": {"population": population_ref},
            "production_activation_authorized": False,
        }
    )
    repair = signed_payload(
        {
            "schema_version": "data_first_repair_manifest_v2",
            "state": "repaired_reconstructed_only",
            "timing_class": "historically_reconstructed",
            "identity": {
                "environment": "preview",
                "run_id": "repair-v2-20260909T1417Z",
            },
            "population": {
                "scheduled_games": 8936,
                "forecast_eligible_games": 8935,
                "measurement_usable_games": 8903,
                "measurement_missing_games": 33,
            },
            "output_refs": {
                "population": {
                    **population_ref,
                    "dataset": "repair_population",
                    "schema_version": "data_first_repair_population_v2",
                }
            },
            "production_activation_authorized": False,
        }
    )
    storage.objects[_MEASUREMENT_URI] = json.dumps(
        measurement, sort_keys=True, separators=(",", ":")
    ).encode()
    storage.objects[_REPAIR_URI] = json.dumps(
        repair, sort_keys=True, separators=(",", ":")
    ).encode()


def _args(run_id: str = "rating-run-test") -> argparse.Namespace:
    return argparse.Namespace(
        run_id=run_id,
        as_of="2026-09-16T00:00:00Z",
        expected_code_sha="f" * 40,
        config=str(runner.DEFAULT_CONFIG),
        measurement_manifest_uri=_MEASUREMENT_URI,
        repair_manifest_uri=_REPAIR_URI,
    )


@pytest.fixture()
def inputs() -> RatingTournamentInputs:
    return _fixture()


def _dry_run_evidence(
    storage: _MemoryStorage, args: argparse.Namespace, tmp_path: Path
) -> tuple[dict, Path]:
    payload = runner.preflight(storage=storage, args=args)
    path = tmp_path / "preflight-evidence.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return payload, path


def test_apply_publishes_manifest_last_and_is_evidence_bound(
    monkeypatch, inputs, tmp_path
) -> None:
    storage = _MemoryStorage()
    _seed_parents(storage)
    monkeypatch.setattr(
        runner, "load_rating_inputs", lambda **kwargs: inputs, raising=True
    )
    args = _args()
    payload, path = _dry_run_evidence(storage, args, tmp_path)
    identity = payload["identity"]
    evidence = runner._load_rating_preflight_evidence(path, identity=identity)
    assert evidence.selected_candidate == payload["selected_candidate"]

    result = runner.apply(
        storage=storage, args=args, identity=identity, evidence=evidence
    )
    assert result["state"] == "applied"
    prefix = f"{runner.POSSESSION_RATING_OUTPUT_ROOT}/{args.run_id}"
    assert storage.exists(f"{prefix}/publication-plan.json")
    assert storage.exists(f"{prefix}/identity.json")
    for name in RATING_DATASETS:
        assert storage.exists(f"{prefix}/{name}-ref.json")
    manifest_uri = f"{prefix}/{runner.RATING_MANIFEST_NAME}"
    assert storage.exists(manifest_uri)
    assert storage.write_order[-1] == manifest_uri
    manifest = json.loads(storage.read_bytes(manifest_uri))
    assert manifest["state"] == "frozen"
    assert manifest["production_activation_authorized"] is False
    assert set(manifest["output_refs"]) == set(RATING_DATASETS)
    assert manifest["selected_candidate"] == payload["selected_candidate"]


def test_repeat_apply_returns_already_applied(monkeypatch, inputs, tmp_path) -> None:
    storage = _MemoryStorage()
    _seed_parents(storage)
    monkeypatch.setattr(
        runner, "load_rating_inputs", lambda **kwargs: inputs, raising=True
    )
    args = _args()
    payload, path = _dry_run_evidence(storage, args, tmp_path)
    identity = payload["identity"]
    evidence = runner._load_rating_preflight_evidence(path, identity=identity)
    first = runner.apply(
        storage=storage, args=args, identity=identity, evidence=evidence
    )
    assert first["state"] == "applied"
    before = dict(storage.objects)
    second = runner.apply(
        storage=storage, args=args, identity=identity, evidence=evidence
    )
    assert second["state"] == "already_applied"
    assert storage.objects == before


def test_apply_rejects_partial_prefix_permanently(
    monkeypatch, inputs, tmp_path
) -> None:
    storage = _MemoryStorage()
    _seed_parents(storage)
    monkeypatch.setattr(
        runner, "load_rating_inputs", lambda **kwargs: inputs, raising=True
    )
    args = _args()
    payload, path = _dry_run_evidence(storage, args, tmp_path)
    identity = payload["identity"]
    evidence = runner._load_rating_preflight_evidence(path, identity=identity)
    prefix = f"{runner.POSSESSION_RATING_OUTPUT_ROOT}/{args.run_id}"
    storage.objects[f"{prefix}/publication-plan.json"] = b"{}"
    with pytest.raises(runner.PossessionRatingRunError, match="ineligible"):
        runner.apply(storage=storage, args=args, identity=identity, evidence=evidence)


def test_apply_rejects_drifted_evidence(monkeypatch, inputs, tmp_path) -> None:
    storage = _MemoryStorage()
    _seed_parents(storage)
    monkeypatch.setattr(
        runner, "load_rating_inputs", lambda **kwargs: inputs, raising=True
    )
    args = _args()
    payload, path = _dry_run_evidence(storage, args, tmp_path)
    drifted = json.loads(path.read_text())
    victim = drifted["preflight_plans"]["priors"]
    victim["records_sha"] = "0" * 64
    drifted["output_records_sha256"]["priors"] = "0" * 64
    path.write_text(json.dumps(drifted, sort_keys=True))
    identity = drifted["identity"]
    evidence = runner._load_rating_preflight_evidence(path, identity=identity)
    with pytest.raises(runner.PossessionRatingRunError, match="differs from"):
        runner.apply(storage=storage, args=args, identity=identity, evidence=evidence)


def test_evidence_loader_rejects_identity_mismatch(
    monkeypatch, inputs, tmp_path
) -> None:
    storage = _MemoryStorage()
    _seed_parents(storage)
    monkeypatch.setattr(
        runner, "load_rating_inputs", lambda **kwargs: inputs, raising=True
    )
    args = _args()
    payload = dict(runner.preflight(storage=storage, args=args))
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(payload, sort_keys=True, default=str))
    other = dict(payload["identity"])
    other["as_of"] = "2020-01-01T00:00:00Z"
    with pytest.raises(
        runner.PossessionRatingRunError, match="identity does not match"
    ):
        runner._load_rating_preflight_evidence(path, identity=other)


def test_evidence_loader_rejects_unordered_partitions(
    monkeypatch, inputs, tmp_path
) -> None:
    storage = _MemoryStorage()
    _seed_parents(storage)
    monkeypatch.setattr(
        runner, "load_rating_inputs", lambda **kwargs: inputs, raising=True
    )
    args = _args()
    payload = dict(runner.preflight(storage=storage, args=args))
    parts = payload["preflight_plans"]["priors"]["parts"]
    if len(parts) < 2:
        pytest.skip("fixture needs multiple priors partitions")
    payload["preflight_plans"]["priors"]["parts"] = list(reversed(parts))
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(payload, sort_keys=True, default=str))
    with pytest.raises(runner.PossessionRatingRunError, match="unordered"):
        runner._load_rating_preflight_evidence(path, identity=payload["identity"])


def test_existing_manifest_rejects_identity_collision(
    monkeypatch, inputs, tmp_path
) -> None:
    storage = _MemoryStorage()
    _seed_parents(storage)
    monkeypatch.setattr(
        runner, "load_rating_inputs", lambda **kwargs: inputs, raising=True
    )
    args = _args()
    payload, path = _dry_run_evidence(storage, args, tmp_path)
    identity = payload["identity"]
    evidence = runner._load_rating_preflight_evidence(path, identity=identity)
    runner.apply(storage=storage, args=args, identity=identity, evidence=evidence)
    manifest_uri = (
        f"{runner.POSSESSION_RATING_OUTPUT_ROOT}/{args.run_id}"
        f"/{runner.RATING_MANIFEST_NAME}"
    )
    other = dict(identity)
    other["identity_sha256"] = "different"
    with pytest.raises(runner.PossessionRatingRunError, match="different identity"):
        runner._existing_rating_manifest(
            storage, manifest_uri=manifest_uri, identity=other
        )
