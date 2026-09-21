"""Independent verifier contracts: boundary, agreement, perturbation, CLI."""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.data.data_first_possession_rating_v1 import (
    RATING_DATASETS,
    REQUIRED_R9_CERTIFICATION_SHA256,
)
from cks_picks_cfb.data.data_first_possession_v1 import POSSESSION_MANIFEST_SCHEMA
from cks_picks_cfb.ratings import possession_rating_verification as verifier
from scripts.research import run_data_first_possession_ratings as ratings_runner
from scripts.research import verify_data_first_possession_ratings as verify_script

_FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "ratings"
    / "test_possession_rating_materializer.py"
)

_MEASUREMENT_URI = "artifacts/parents/possession/measurement-manifest.json"
_REPAIR_URI = "artifacts/parents/repair/repair-manifest.json"


class _VStorage:
    """In-memory storage with write, prefix listing, and write ordering."""

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


def _seed_parents(storage: _VStorage) -> None:
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


def _rating_args(run_id: str) -> argparse.Namespace:
    return argparse.Namespace(
        run_id=run_id,
        as_of="2026-09-16T00:00:00Z",
        expected_code_sha="f" * 40,
        config=str(ratings_runner.DEFAULT_CONFIG),
        measurement_manifest_uri=_MEASUREMENT_URI,
        repair_manifest_uri=_REPAIR_URI,
    )


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_fixture_module = _load_module("_rating_mat_fixture", _FIXTURE_PATH)

_forbidden = {
    "cks_picks_cfb.ratings.possession_ratings",
    "cks_picks_cfb.ratings.possession_rating_tournament",
    "cks_picks_cfb.ratings.possession_rating_materializer",
    "scripts.research.run_data_first_possession_ratings",
    "scripts.research.run_data_first_possession_measurements",
}


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module)
    return modules


def test_verifier_import_boundary() -> None:
    for path in (
        Path(verifier.__file__),
        Path(verify_script.__file__).resolve(),
    ):
        imported = _imported_modules(path)
        violations = {
            name
            for name in imported
            if any(
                name == forbidden or name.startswith(forbidden + ".")
                for forbidden in _forbidden
            )
        }
        assert not violations, f"{path.name} imports producer code: {violations}"
    verifier_imports = _imported_modules(Path(verifier.__file__))
    assert not any(name.startswith("scripts.") for name in verifier_imports)


def _noop(*args: object, **kwargs: object) -> None:
    return None


def _verifier_parents(inputs) -> verifier.VerifierParents:
    return verifier.VerifierParents(
        population=inputs.population,
        observations=inputs.observations,
        snapshots=inputs.snapshots,
        terminal=inputs.terminal,
        outcomes=inputs.outcomes,
        context=dict(inputs.context),
        history_audit={
            "history_parts": int(inputs.history_audit.get("history_parts", 0)),
            "history_rows": int(inputs.history_audit.get("history_rows", 0)),
            "availability_violations": 0,
            "snapshot_value_mismatches": 0,
        },
    )


def test_producer_verifier_bit_exact_agreement() -> None:
    inputs = _fixture_module._fixture()
    from cks_picks_cfb.ratings.possession_rating_materializer import compute_tournament

    computation = compute_tournament(inputs=inputs, progress=_noop)
    evidence = computation.preflight_evidence()
    rebuilt = verifier.reconstruct_tournament(
        parents=_verifier_parents(inputs), progress=_noop
    )
    assert rebuilt.selected_candidate == computation.selected_candidate
    assert rebuilt.candidate_status == computation.candidate_status
    assert rebuilt.selection_sha256 == evidence["selection_sha256"]
    assert rebuilt.row_counts == evidence["row_counts"]
    assert rebuilt.records_shas == evidence["output_records_sha256"]
    for name in RATING_DATASETS:
        plan = computation.plans[name]
        expected_parts = [
            {
                "partition": dict(part["partition"]),
                "row_count": int(part["row_count"]),
                "records_sha": str(part["records_sha"]),
            }
            for part in plan.parts
        ]
        assert rebuilt.parts[name] == expected_parts
        assert plan.row_count == rebuilt.row_counts[name]
        assert plan.records_sha == rebuilt.records_shas[name]


def test_verifier_detects_perturbed_parents() -> None:
    inputs = _fixture_module._fixture()
    baseline = verifier.reconstruct_tournament(
        parents=_verifier_parents(inputs), progress=_noop
    )
    perturbed = inputs.snapshots.copy()
    # Game 6 is the certified boundary target for the week-1 sources, so its
    # snapshots are definitely consumed by observation streams.
    boundary_game = 6
    mask = perturbed["as_of_game_id"].eq(boundary_game)
    assert int(mask.sum()) > 0
    perturbed.loc[mask, "adjusted_value"] = (
        pd.to_numeric(perturbed.loc[mask, "adjusted_value"], errors="coerce") * 1.5
        + 0.25
    )
    altered_inputs = _fixture_module.RatingTournamentInputs(
        population=inputs.population,
        observations=inputs.observations,
        snapshots=perturbed,
        terminal=inputs.terminal,
        outcomes=inputs.outcomes,
        context=inputs.context,
        history_audit=inputs.history_audit,
        source_refs=inputs.source_refs,
        population_sha256=inputs.population_sha256,
    )
    changed = verifier.reconstruct_tournament(
        parents=_verifier_parents(altered_inputs), progress=_noop
    )
    assert (
        changed.records_shas["bridge_predictions"]
        != baseline.records_shas["bridge_predictions"]
    )
    assert (
        changed.records_shas["rating_states"] != baseline.records_shas["rating_states"]
    )
    # Terminal-derived outputs are untouched by a snapshot perturbation.
    assert changed.records_shas["priors"] == baseline.records_shas["priors"]
    assert (
        changed.records_shas["rating_registry"]
        == baseline.records_shas["rating_registry"]
    )


def _applied_storage(monkeypatch, tmp_path, run_id: str = "verify-test"):
    storage = _VStorage()
    _seed_parents(storage)
    inputs = _fixture_module._fixture()
    monkeypatch.setattr(
        ratings_runner, "load_rating_inputs", lambda **kwargs: inputs, raising=True
    )
    args = _rating_args(run_id)
    payload = ratings_runner.preflight(storage=storage, args=args)
    path = tmp_path / f"{run_id}-evidence.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str))
    identity = payload["identity"]
    evidence = ratings_runner._load_rating_preflight_evidence(path, identity=identity)
    result = ratings_runner.apply(
        storage=storage, args=args, identity=identity, evidence=evidence
    )
    assert result["state"] == "applied"
    prefix = f"{ratings_runner.POSSESSION_RATING_OUTPUT_ROOT}/{run_id}"
    manifest_uri = f"{prefix}/{ratings_runner.RATING_MANIFEST_NAME}"
    manifest = json.loads(storage.read_bytes(manifest_uri))
    parents = _verifier_parents(inputs)
    monkeypatch.setattr(
        verifier, "load_verifier_parents", lambda **kwargs: parents, raising=True
    )
    return storage, manifest, manifest_uri, payload


def test_verifier_confirms_applied_artifact(monkeypatch, tmp_path) -> None:
    storage, manifest, manifest_uri, _ = _applied_storage(monkeypatch, tmp_path)
    report = verifier.verify_rating_artifact(
        storage=storage,
        manifest=manifest,
        manifest_uri=manifest_uri,
        measurement_manifest_uri=_MEASUREMENT_URI,
        repair_manifest_uri=_REPAIR_URI,
        verifier_code_sha="v" * 40,
        progress=_noop,
    )
    assert report["status"] == "verified"
    assert report["selected_candidate"] == manifest["selected_candidate"]
    assert report["selection_sha256"] == manifest["selection"]["selection_sha256"]
    assert (
        report["output_records_sha256"]
        == manifest["selection"]["output_records_sha256"]
    )
    assert storage.exists(report["verifier_manifest_uri"])
    repeat = verifier.verify_rating_artifact(
        storage=storage,
        manifest=manifest,
        manifest_uri=manifest_uri,
        measurement_manifest_uri=_MEASUREMENT_URI,
        repair_manifest_uri=_REPAIR_URI,
        verifier_code_sha="v" * 40,
        progress=_noop,
    )
    assert repeat["verifier_manifest_sha256"] == report["verifier_manifest_sha256"]


def test_verifier_catches_tampered_stored_artifact(monkeypatch, tmp_path) -> None:
    storage, manifest, manifest_uri, _ = _applied_storage(
        monkeypatch, tmp_path, run_id="verify-tamper"
    )
    children = sorted(key for key in storage.objects if key.endswith("/data.parquet"))
    assert children, "applied artifact must contain child objects"
    victim = children[0]
    raw = bytearray(storage.objects[victim])
    raw[-1] ^= 0xFF
    storage.objects[victim] = bytes(raw)
    with pytest.raises(verifier.IndependentRatingError):
        verifier.verify_rating_artifact(
            storage=storage,
            manifest=manifest,
            manifest_uri=manifest_uri,
            measurement_manifest_uri=_MEASUREMENT_URI,
            repair_manifest_uri=_REPAIR_URI,
            verifier_code_sha="v" * 40,
            progress=_noop,
        )


def test_verify_cli_reports_verified(monkeypatch, tmp_path, capsys) -> None:
    storage, manifest, manifest_uri, _ = _applied_storage(
        monkeypatch, tmp_path, run_id="verify-cli"
    )
    monkeypatch.setattr(
        verify_script, "get_storage", lambda environment: storage, raising=True
    )
    monkeypatch.setattr(verify_script, "_git_sha", lambda: "v" * 40)
    code_sha = manifest["identity"]["code_sha"]
    verify_script.main(
        [
            "--manifest-uri",
            manifest_uri,
            "--expected-code-sha",
            code_sha,
            "--environment",
            "preview",
            "--measurement-manifest-uri",
            _MEASUREMENT_URI,
            "--repair-manifest-uri",
            _REPAIR_URI,
        ]
    )
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "verified"
    assert report["selected_candidate"] == manifest["selected_candidate"]


def test_verify_cli_rejects_tampered_artifact(monkeypatch, tmp_path, capsys) -> None:
    storage, manifest, manifest_uri, _ = _applied_storage(
        monkeypatch, tmp_path, run_id="verify-cli-tamper"
    )
    children = sorted(key for key in storage.objects if key.endswith("/data.parquet"))
    raw = bytearray(storage.objects[children[0]])
    raw[-1] ^= 0xFF
    storage.objects[children[0]] = bytes(raw)
    monkeypatch.setattr(
        verify_script, "get_storage", lambda environment: storage, raising=True
    )
    monkeypatch.setattr(verify_script, "_git_sha", lambda: "v" * 40)
    with pytest.raises(verify_script.PossessionRatingVerificationError):
        verify_script.main(
            [
                "--manifest-uri",
                manifest_uri,
                "--expected-code-sha",
                manifest["identity"]["code_sha"],
                "--environment",
                "preview",
                "--measurement-manifest-uri",
                _MEASUREMENT_URI,
                "--repair-manifest-uri",
                _REPAIR_URI,
            ]
        )
