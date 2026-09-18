"""Verifier-independence checks via static import boundaries.

A verifier counts as independent only with both an enforced producer-import
boundary and passing behavioral tests. Existing certification labels never
override this standard. Uses AST analysis only; never imports the modules it
inspects.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]

AUDIT_PACKAGE = Path(__file__).resolve().parent

# Files comprising the audit harness itself (package + both research CLIs).
HARNESS_FILES = (
    AUDIT_PACKAGE / "__init__.py",
    AUDIT_PACKAGE / "register.py",
    AUDIT_PACKAGE / "checks.py",
    AUDIT_PACKAGE / "independence.py",
    AUDIT_PACKAGE / "verification.py",
    ROOT / "scripts" / "research" / "run_data_first_historical_audit.py",
    ROOT / "scripts" / "research" / "verify_data_first_historical_audit.py",
)

# Producer computations the audit harness must never import. Schema
# contracts, generic storage readers, and signing utilities are allowed.
HARNESS_FORBIDDEN_IMPORTS = (
    "possession_measurements",
    "possession_rating_materializer",
    "possession_rating_tournament",
    "possession_ratings",
    "forecast.offsets",
    "forecast.heads",
    "forecast.horizons",
    "forecast.calibration",
    "forecast.shadow",
    "run_data_first_repair_v2",
    "run_data_first_possession_measurements",
    "run_data_first_possession_ratings",
    "run_data_first_forecasts",
    "run_data_first_phase3",
    "run_data_first_phase4",
)

# Assessed verifiers and the producer modules each must not import.
ASSESSED_VERIFIERS: dict[str, dict[str, Any]] = {
    "repair": {
        "path": ROOT / "scripts" / "research" / "verify_data_first_repair_v2.py",
        "forbidden": ("run_data_first_repair_v2",),
    },
    "measurements": {
        "path": ROOT
        / "src"
        / "cks_picks_cfb"
        / "ratings"
        / "possession_verification.py",
        "forbidden": (
            "possession_measurements",
            "possession_rating_materializer",
            "run_data_first_possession_measurements",
        ),
    },
    "ratings": {
        "path": ROOT
        / "src"
        / "cks_picks_cfb"
        / "ratings"
        / "possession_rating_verification.py",
        "forbidden": (
            "possession_ratings",
            "possession_rating_tournament",
            "possession_rating_materializer",
            "run_data_first_possession_ratings",
        ),
    },
    "forecasts": {
        "path": ROOT
        / "src"
        / "cks_picks_cfb"
        / "forecast"
        / "forecast_verification.py",
        "forbidden": (
            "forecast.offsets",
            "forecast.heads",
            "forecast.horizons",
            "forecast.calibration",
            "forecast.shadow",
            "run_data_first_forecasts",
        ),
    },
}

# Producer reconstruction helpers whose absence from the forecast verifier's
# verify function confirms the seeded reconstruction gap. Manifest-byte reads
# are metadata validation, not output reconstruction, and are handled
# separately below.
FORECAST_RECONSTRUCTION_MARKERS = (
    "_build_offsets",
    "_feature_frame",
    "_fit_one",
    "_select_inner_alpha",
    "_fitting_seasons",
    "_calibrate_uncertainty",
)


class IndependenceError(ValueError):
    """Raised when an independence boundary cannot be evaluated."""


def scan_imports(path: Path, forbidden: tuple[str, ...]) -> list[dict[str, Any]]:
    """Return producer-import violations found by AST analysis."""
    try:
        tree = ast.parse(path.read_text())
    except (OSError, SyntaxError) as exc:
        raise IndependenceError(f"cannot parse {path}: {exc}") from exc
    violations: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            modules = [node.module or ""]
        else:
            continue
        for module in modules:
            for marker in forbidden:
                if marker in module:
                    violations.append(
                        {
                            "file": str(path),
                            "lineno": node.lineno,
                            "import": module,
                            "marker": marker,
                        }
                    )
    return violations


def repair_producer_import_present(
    path: Path | None = None,
) -> bool:
    """Confirm whether the Repair verifier imports producer computation."""
    target = path or ASSESSED_VERIFIERS["repair"]["path"]
    return bool(scan_imports(target, ("run_data_first_repair_v2",)))


def forecast_reconstruction_absent(
    path: Path | None = None,
) -> bool:
    """Confirm the forecast verifier never reconstructs stored outputs.

    Returns True when ``verify_forecast_artifact`` calls none of the
    producer reconstruction helpers, performs no partitioned-dataset reads,
    and reads bytes only from its own manifest URI (metadata validation).
    Any other byte/dataset read would reach stored forecast outputs.
    """
    target = path or ASSESSED_VERIFIERS["forecasts"]["path"]
    try:
        tree = ast.parse(target.read_text())
    except (OSError, SyntaxError) as exc:
        raise IndependenceError(f"cannot parse {target}: {exc}") from exc
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
            node.name == "verify_forecast_artifact"
        ):
            for child in ast.walk(node):
                if not isinstance(child, ast.Call):
                    continue
                func = child.func
                if isinstance(func, ast.Name):
                    if func.id in FORECAST_RECONSTRUCTION_MARKERS:
                        return False
                    if func.id in ("read_dataset", "iter_partitioned_dataset"):
                        return False
                    if func.id == "read_bytes":
                        args = child.args
                        if (
                            len(args) != 1
                            or not isinstance(args[0], ast.Name)
                            or args[0].id != "manifest_uri"
                        ):
                            return False
                elif isinstance(func, ast.Attribute):
                    if func.attr in ("read_dataset", "iter_partitioned_dataset"):
                        return False
                    if func.attr == "read_bytes":
                        # Only the manifest's own bytes may be read (metadata
                        # validation); any other byte read reaches stored outputs.
                        args = child.args
                        if (
                            len(args) != 1
                            or not isinstance(args[0], ast.Name)
                            or args[0].id != "manifest_uri"
                        ):
                            return False
            return True
    raise IndependenceError("verify_forecast_artifact not found")


def classify_verifier(boundary_ok: bool, behavioral_ok: bool) -> str:
    """Classify a verifier as independent only when both gates pass."""
    return "independent" if (boundary_ok and behavioral_ok) else "dependent"


def run_independence_checks() -> tuple[list[dict[str, Any]], dict[str, bool]]:
    """Run harness self-scan, assessed-verifier scans, and condition checks."""
    results: list[dict[str, Any]] = []

    harness_violations: list[dict[str, Any]] = []
    for path in HARNESS_FILES:
        if path.exists():
            harness_violations.extend(scan_imports(path, HARNESS_FORBIDDEN_IMPORTS))
    results.append(
        {
            "check_id": "independence.harness.boundary",
            "layer": "assurance",
            "category": "import_boundary",
            "status": "fail" if harness_violations else "pass",
            "expected": "audit harness imports no producer computations",
            "observed": "ok"
            if not harness_violations
            else f"violations={harness_violations[:4]}",
            "population": "audit harness files",
            "evidence_refs": [str(path) for path in HARNESS_FILES],
        }
    )

    for stage, spec in ASSESSED_VERIFIERS.items():
        path = spec["path"]
        violations = scan_imports(path, tuple(spec["forbidden"]))
        results.append(
            {
                "check_id": f"independence.{stage}.boundary",
                "layer": "assurance",
                "category": "import_boundary",
                "status": "fail" if violations else "pass",
                "expected": f"{stage} verifier imports no producer computations",
                "observed": "ok" if not violations else f"violations={violations[:4]}",
                "population": f"{stage} verifier",
                "evidence_refs": [str(path)],
            }
        )

    conditions = {
        "audit-structural-001": repair_producer_import_present(),
        "audit-structural-002": forecast_reconstruction_absent(),
    }
    results.append(
        {
            "check_id": "independence.seeded_conditions",
            "layer": "assurance",
            "category": "structural_findings",
            "status": "pass" if all(conditions.values()) else "fail",
            "expected": "both seeded structural conditions confirmed present",
            "observed": f"conditions={conditions}",
            "population": "repair + forecast verifiers",
            "evidence_refs": [
                str(ASSESSED_VERIFIERS["repair"]["path"]),
                str(ASSESSED_VERIFIERS["forecasts"]["path"]),
            ],
        }
    )
    return results, conditions


def gate_inputs(conditions: Mapping[str, bool]) -> dict[str, bool]:
    return dict(conditions)
