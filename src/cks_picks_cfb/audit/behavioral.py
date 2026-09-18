"""Behavioral assurance matrix for assessed verifiers (read-only).

Executes four deterministic cases per verifier — wrong parent, missing
dataset, corrupted output, and producer-only perturbation — against each
verifier's real runnable surface and records whether observed behavior
matches the expectation for an independent verifier. Uses ``importlib``
(string names) and isolated subprocesses only: this module contains no
static import of any verifier or producer, so the harness import boundary
is unaffected. Never writes to any backend and never repairs anything.
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import types
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from cks_picks_cfb.data.data_first_phase2d import sha256, signed_payload

ROOT = Path(__file__).resolve().parents[3]

CASES = (
    "wrong_parent",
    "missing_dataset",
    "corrupted_output",
    "producer_perturbation",
)

VERIFIERS = ("repair", "measurements", "ratings", "forecasts")

# Producer modules whose sabotage must not change an independent verifier.
PRODUCER_MARKERS = {
    "repair": ("scripts.research.run_data_first_repair_v2",),
    "measurements": ("cks_picks_cfb.ratings.possession_measurements",),
    "ratings": (
        "cks_picks_cfb.ratings.possession_ratings",
        "cks_picks_cfb.ratings.possession_rating_tournament",
        "cks_picks_cfb.ratings.possession_rating_materializer",
        "scripts.research.run_data_first_possession_ratings",
    ),
    "forecasts": (
        "cks_picks_cfb.forecast.offsets",
        "cks_picks_cfb.forecast.heads",
        "cks_picks_cfb.forecast.horizons",
        "cks_picks_cfb.forecast.calibration",
        "cks_picks_cfb.forecast.shadow",
        "scripts.research.run_data_first_forecasts",
    ),
}

VERIFIER_MODULES = {
    "repair": "scripts.research.verify_data_first_repair_v2",
    "measurements": "scripts.research.verify_data_first_possession_measurements",
    "ratings": "scripts.research.verify_data_first_possession_ratings",
    "forecasts": "cks_picks_cfb.forecast.forecast_verification",
}


class BehavioralError(ValueError):
    """Raised when a behavioral cell cannot be constructed."""


def _import_verifier(module_name: str) -> types.ModuleType:
    """Import a verifier from either a direct CLI or package invocation.

    Direct audit execution places ``scripts/research`` on ``sys.path`` rather
    than the repository root.  Verifier entry points intentionally keep their
    repository-qualified ``scripts.*`` names, so the harness establishes that
    import root immediately before its dynamic import.
    """
    root = str(ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    return importlib.import_module(module_name)


class _FakeStorage:
    """Minimal read-only storage double for behavioral probes."""

    def __init__(self, objects: Mapping[str, bytes]) -> None:
        self._objects = dict(objects)

    def read_bytes(self, uri: str) -> bytes:
        if uri in self._objects:
            return self._objects[uri]
        raise FileNotFoundError(f"behavioral fixture absent: {uri}")

    def exists(self, uri: str) -> bool:
        return uri in self._objects


def _poisoned_import(module_name: str, markers: tuple[str, ...]) -> types.ModuleType:
    """Import a verifier with producer modules poisoned.

    Poisoned names raise on any attribute access, so producer code can never
    execute. Importing the verifier itself either succeeds (it does not need
    producers) or fails (it is load-time dependent on them).
    """
    saved = dict(sys.modules)
    for marker in markers:
        poison = types.ModuleType(marker)

        def _raise(name: str, *, _marker: str = marker) -> Any:
            raise ImportError(f"producer {_marker} is poisoned for behavioral probe")

        poison.__getattr__ = _raise  # type: ignore[attr-defined]
        sys.modules[marker] = poison
    try:
        return _import_verifier(module_name)
    finally:
        sys.modules.clear()
        sys.modules.update(saved)


def _fixture_manifest(
    schema: str, run_id: str, parents: Mapping[str, Any]
) -> dict[str, Any]:
    return signed_payload(
        {
            "schema_version": schema,
            "state": "frozen",
            "identity": {
                "run_id": run_id,
                "environment": "preview",
                "code_sha": "be" * 20,
                "config_sha": "cf" * 32,
            },
            "parents": dict(parents),
            "output_refs": {},
            "production_activation_authorized": False,
        }
    )


def _cell(
    verifier: str,
    case: str,
    method: str,
    expected: str,
    observed: str,
) -> dict[str, Any]:
    return {
        "cell_id": f"behavioral.{verifier}.{case}",
        "verifier": verifier,
        "case": case,
        "method": method,
        "expected": expected,
        "observed": observed,
        "match": observed == expected,
    }


def _forecast_cells() -> list[dict[str, Any]]:
    from cks_picks_cfb.forecast.forecast_verification import (  # noqa: PLC0415
        verify_forecast_artifact,
    )

    manifest = _fixture_manifest(
        "data_first_forecast_manifest_v1",
        "forecast-fixture",
        {
            "rating_manifest_uri": "fixture://rating",
            "measurement_manifest_uri": "fixture://measurement",
            "repair_manifest_uri": "fixture://repair",
        },
    )
    manifest["output_refs"] = {
        # Restated (not imported) forecast output identities.
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
    }
    manifest = signed_payload(
        {k: v for k, v in manifest.items() if k != "manifest_sha256"}
    )
    manifest["selected_horizon"] = "expanding"
    manifest = signed_payload(
        {k: v for k, v in manifest.items() if k != "manifest_sha256"}
    )
    raw = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    cells: list[dict[str, Any]] = []
    base = dict(
        manifest_uri="fixture://manifest",
        expected_code_sha="be" * 20,
        environment="preview",
        rating_manifest_uri="fixture://rating",
        measurement_manifest_uri="fixture://measurement",
        repair_manifest_uri="fixture://repair",
    )

    def run(storage: _FakeStorage, **overrides: Any) -> str:
        args = dict(base)
        args.update(overrides)
        try:
            result = verify_forecast_artifact(storage, **args)
        except Exception as exc:  # noqa: BLE001 - any rejection is the observation
            return f"rejected: {type(exc).__name__}"
        return f"accepted: selected={result.get('selected_horizon')}"

    storage = _FakeStorage({"fixture://manifest": raw})
    # wrong parent
    observed = run(storage, rating_manifest_uri="fixture://wrong")
    cells.append(
        _cell(
            "forecasts",
            "wrong_parent",
            "entry verify_forecast_artifact with mismatched parent URI",
            "rejected: VerificationError",
            observed,
        )
    )
    # missing dataset (manifest itself absent)
    observed = run(_FakeStorage({}))
    cells.append(
        _cell(
            "forecasts",
            "missing_dataset",
            "entry verify_forecast_artifact with absent manifest bytes",
            "rejected: FileNotFoundError",
            observed,
        )
    )
    # corrupted output (tampered manifest bytes)
    tampered = json.loads(raw)
    tampered["selected_horizon"] = "tampered"
    corrupted = _FakeStorage(
        {
            "fixture://manifest": json.dumps(
                tampered, sort_keys=True, separators=(",", ":")
            ).encode()
        }
    )
    observed = run(corrupted)
    cells.append(
        _cell(
            "forecasts",
            "corrupted_output",
            "entry verify_forecast_artifact with tampered manifest bytes",
            "rejected: VerificationError",
            observed,
        )
    )
    # producer perturbation: identical behavior with producers poisoned
    _poisoned_import(VERIFIER_MODULES["forecasts"], PRODUCER_MARKERS["forecasts"])
    observed = run(storage)
    cells.append(
        _cell(
            "forecasts",
            "producer_perturbation",
            "entry completes identically with producer modules poisoned",
            "accepted: selected=expanding",
            observed,
        )
    )
    return cells


def _rating_cells() -> list[dict[str, Any]]:
    script = _import_verifier(VERIFIER_MODULES["ratings"])
    verify_manifest = script.verify_manifest
    verify_artifact = _import_verifier(
        "cks_picks_cfb.ratings.possession_rating_verification"
    ).verify_rating_artifact
    # Restated (not imported) so the harness never touches producer-mixed
    # contract modules: the retained candidate and the seven output roles.
    retained_candidate = "ppp__rho_0_60__exposure"
    rating_roles = (
        "rating_registry",
        "priors",
        "noise_fits",
        "rating_states",
        "team_states",
        "bridge_predictions",
        "attribution",
    )
    parents = {
        "measurement_manifest_uri": "fixture://measurement",
        "measurement_manifest_raw_sha256": "00" * 32,
        "repair_manifest_uri": "fixture://repair",
        "repair_manifest_raw_sha256": "11" * 32,
    }
    manifest = _fixture_manifest(
        "data_first_possession_retained_rating_v1", "rating-fixture", parents
    )
    manifest["selected_candidate"] = retained_candidate
    manifest["output_refs"] = {role: {"dataset": role} for role in rating_roles}
    manifest = signed_payload(
        {k: v for k, v in manifest.items() if k != "manifest_sha256"}
    )
    cells: list[dict[str, Any]] = []

    def run_manifest(payload: Mapping[str, Any], code_sha: str = "be" * 20) -> str:
        try:
            verify_manifest(dict(payload), expected_code_sha=code_sha)
        except Exception as exc:  # noqa: BLE001
            return f"rejected: {type(exc).__name__}"
        return "accepted"

    def run_artifact(
        manifest_payload: Mapping[str, Any], storage: _FakeStorage, **overrides: Any
    ) -> str:
        uris = {
            "measurement_manifest_uri": "fixture://measurement",
            "repair_manifest_uri": "fixture://repair",
        }
        uris.update(overrides)
        try:
            verify_artifact(
                storage=storage,
                manifest=dict(manifest_payload),
                manifest_uri="fixture://manifest",
                verifier_code_sha="be" * 20,
                progress=lambda *a, **k: None,
                **uris,
            )
        except Exception as exc:  # noqa: BLE001
            return f"rejected: {type(exc).__name__}"
        return "accepted"

    measurement_raw = json.dumps({"marker": "measurement"}).encode()
    repair_raw = json.dumps({"marker": "repair"}).encode()
    parents_match = dict(parents)
    parents_match["measurement_manifest_raw_sha256"] = sha256(
        json.loads(measurement_raw)
    )
    parents_match["repair_manifest_raw_sha256"] = sha256(json.loads(repair_raw))
    manifest_match = signed_payload(
        {
            k: v
            for k, v in dict(manifest, parents=parents_match).items()
            if k != "manifest_sha256"
        }
    )
    storage = _FakeStorage(
        {"fixture://measurement": measurement_raw, "fixture://repair": repair_raw}
    )
    # wrong parent
    observed = run_artifact(
        manifest_match, storage, measurement_manifest_uri="fixture://wrong"
    )
    cells.append(
        _cell(
            "ratings",
            "wrong_parent",
            "entry verify_rating_artifact with mismatched parent URI",
            "rejected: IndependentRatingError",
            observed,
        )
    )
    # missing dataset
    observed = run_artifact(manifest_match, _FakeStorage({}))
    cells.append(
        _cell(
            "ratings",
            "missing_dataset",
            "entry verify_rating_artifact with absent parent bytes",
            "rejected: FileNotFoundError",
            observed,
        )
    )
    # corrupted output (parent bytes differ from pinned checksums)
    tampered_storage = _FakeStorage(
        {
            "fixture://measurement": json.dumps({"marker": "tampered"}).encode(),
            "fixture://repair": repair_raw,
        }
    )
    observed = run_artifact(manifest_match, tampered_storage)
    cells.append(
        _cell(
            "ratings",
            "corrupted_output",
            "entry verify_rating_artifact with tampered parent bytes",
            "rejected: IndependentRatingError",
            observed,
        )
    )
    # producer perturbation: manifest preamble identical under poison
    _poisoned_import(VERIFIER_MODULES["ratings"], PRODUCER_MARKERS["ratings"])
    observed = run_manifest(manifest)
    cells.append(
        _cell(
            "ratings",
            "producer_perturbation",
            "preamble verify_manifest completes identically with producers poisoned",
            "accepted",
            observed,
        )
    )
    return cells


def _measurement_cells() -> list[dict[str, Any]]:
    script = _import_verifier(VERIFIER_MODULES["measurements"])
    verify_repair = script._verify_repair
    cells: list[dict[str, Any]] = []

    def run(raw: bytes) -> str:
        try:
            verify_repair(raw)
        except Exception as exc:  # noqa: BLE001
            return f"rejected: {type(exc).__name__}"
        return "accepted"

    other = signed_payload({"schema_version": "other_manifest_v1", "state": "x"})
    other_raw = json.dumps(other, sort_keys=True, separators=(",", ":")).encode()
    # wrong parent (a validly signed non-repair manifest)
    cells.append(
        _cell(
            "measurements",
            "wrong_parent",
            "helper _verify_repair with a foreign signed manifest",
            "rejected: PossessionVerificationError",
            run(other_raw),
        )
    )
    # missing dataset (no bytes to verify)
    try:
        _FakeStorage({}).read_bytes("fixture://absent")
        observed = "accepted"
    except Exception as exc:  # noqa: BLE001
        observed = f"rejected: {type(exc).__name__}"
    cells.append(
        _cell(
            "measurements",
            "missing_dataset",
            "absent parent bytes fail closed before verification",
            "rejected: FileNotFoundError",
            observed,
        )
    )
    # corrupted output (tampered repair bytes)
    tampered = json.dumps({"schema_version": "x", "tampered": True}).encode()
    cells.append(
        _cell(
            "measurements",
            "corrupted_output",
            "helper _verify_repair with tampered bytes",
            "rejected: PossessionVerificationError",
            run(tampered),
        )
    )
    # producer perturbation
    _poisoned_import(VERIFIER_MODULES["measurements"], PRODUCER_MARKERS["measurements"])
    cells.append(
        _cell(
            "measurements",
            "producer_perturbation",
            "helper completes identically with producer module poisoned",
            "rejected: PossessionVerificationError",
            run(other_raw),
        )
    )
    return cells


def _repair_cells(tmp_dir: Path) -> list[dict[str, Any]]:
    """Black-box cells: the repair entry is monolithic and non-injectable.

    Each cell runs the real verifier ``main()`` in an isolated subprocess
    with storage pinned to an empty local fixture root, so no producer code
    loads in the audit process and no network or database is touched.
    """
    cells: list[dict[str, Any]] = []
    root = tmp_dir / "repair-probes"
    (root / "artifacts").mkdir(parents=True, exist_ok=True)
    manifest_uri = "artifacts/fixture/repair-manifest.json"

    valid = signed_payload(
        {
            "schema_version": "data_first_repair_manifest_v2",
            "state": "repaired_reconstructed_only",
            "identity": {
                "run_id": "repair-fixture",
                "environment": "preview",
                "code_sha": "be" * 20,
                "config_sha": "cf" * 32,
            },
            "parents": {
                "core_eligibility": {"uri": "fixture://core"},
                "auxiliary_eligibility": {"uri": "fixture://aux"},
                "phase3_retained_diagnostic_only": {"uri": "fixture://p3"},
            },
            "output_refs": {},
            "output_rows": {},
            "production_activation_authorized": False,
        }
    )

    # NOTE: main() prints nothing and returns None on success; any nonzero
    # exit or exception is fail-closed. All fixture scenarios below must fail
    # closed because the fixture root holds no row data by design.
    def run_case_status(
        *, payload: Mapping[str, Any] | None, sha: str = "be" * 20
    ) -> str:
        target = root / manifest_uri
        if target.exists():
            target.unlink()
        if payload is not None:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            )
        env = dict(os.environ)
        env["CFB_STORAGE_BACKEND"] = "local"
        env["CFB_MODEL_DATA_ROOT"] = str(root)
        env["PYTHONPATH"] = "." + os.pathsep + "src"
        code = (
            "from scripts.research.verify_data_first_repair_v2 import main;"
            f"main(['--manifest-uri', {manifest_uri!r}, '--expected-code-sha', {sha!r},"
            " '--environment', 'preview'])"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if proc.returncode != 0:
            return "rejected: nonzero-exit"
        return "accepted"

    # wrong parent: valid signature, foreign parent URIs; unreachable row data
    # means the entry must fail closed before parent validation.
    cells.append(
        _cell(
            "repair",
            "wrong_parent",
            "black-box main() with valid preamble but foreign parents and no row data",
            "rejected: nonzero-exit",
            run_case_status(payload=valid),
        )
    )
    # missing dataset
    cells.append(
        _cell(
            "repair",
            "missing_dataset",
            "black-box main() with absent manifest bytes",
            "rejected: nonzero-exit",
            run_case_status(payload=None),
        )
    )
    # corrupted output
    tampered = dict(valid)
    tampered["state"] = "tampered"
    cells.append(
        _cell(
            "repair",
            "corrupted_output",
            "black-box main() with tampered manifest bytes",
            "rejected: nonzero-exit",
            run_case_status(payload=tampered),
        )
    )
    # producer perturbation: importing the verifier with the producer
    # poisoned must fail — load-time dependence demonstrated behaviorally.
    try:
        _poisoned_import(VERIFIER_MODULES["repair"], PRODUCER_MARKERS["repair"])
        observed = "imported"
    except Exception as exc:  # noqa: BLE001
        observed = f"rejected: {type(exc).__name__}"
    cells.append(
        _cell(
            "repair",
            "producer_perturbation",
            "import of the verifier with producer computation poisoned",
            "rejected: ImportError",
            observed,
        )
    )
    return cells


def run_behavioral_matrix(*, tmp_dir: Path) -> list[dict[str, Any]]:
    """Execute all 16 behavioral cells deterministically."""
    cells: list[dict[str, Any]] = []
    cells.extend(_forecast_cells())
    cells.extend(_rating_cells())
    cells.extend(_measurement_cells())
    cells.extend(_repair_cells(tmp_dir))
    return cells
