"""Static compatibility checks for repository ownership boundaries."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "conf/repository/compatibility_v1.yaml"


def _manifest() -> dict:
    return yaml.safe_load(MANIFEST_PATH.read_text())


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _assert_no_prohibited_imports(paths: list[Path], prefixes: list[str]) -> None:
    violations: list[str] = []
    for path in paths:
        for imported in _imports(path):
            if any(imported == prefix or imported.startswith(f"{prefix}.") for prefix in prefixes):
                violations.append(f"{path.relative_to(ROOT)} imports {imported}")
    assert violations == []


def test_production_code_does_not_import_research_namespaces():
    manifest = _manifest()
    prefixes = manifest["dependency_rules"]["prohibited_import_prefixes"]
    library_paths = sorted((ROOT / "src/cks_picks_cfb").rglob("*.py"))
    script_paths = [ROOT / path for path in manifest["supported_production_scripts"]]

    _assert_no_prohibited_imports(library_paths + script_paths, prefixes)


def test_declared_compatibility_paths_exist():
    manifest = _manifest()
    declared: list[str] = []
    for paths in manifest["required_paths"].values():
        declared.extend(paths)
    for benchmark in manifest["named_research_benchmarks"].values():
        declared.extend(benchmark["paths"])

    missing = [path for path in declared if not (ROOT / path).exists()]
    assert missing == []


def test_declared_public_make_targets_exist():
    manifest = _manifest()
    makefile = (ROOT / "Makefile").read_text()
    declared_targets = set(re.findall(r"^([A-Za-z0-9_.-]+):", makefile, flags=re.MULTILINE))

    missing = sorted(set(manifest["public_make_targets"]) - declared_targets)
    assert missing == []


def test_data_first_research_roots_exist():
    manifest = _manifest()
    assert (ROOT / manifest["research"]["command_root"]).is_dir()
    assert (ROOT / manifest["research"]["config_root"]).is_dir()


def test_production_configs_do_not_reference_data_first_artifacts():
    manifest = _manifest()
    namespace = manifest["research"]["artifact_namespace"]
    violations = [
        path
        for path in manifest["production_configs"]
        if namespace in (ROOT / path).read_text()
    ]
    assert violations == []


def test_data_first_configs_do_not_reference_production_outputs():
    manifest = _manifest()
    config_root = ROOT / manifest["research"]["config_root"]
    prefixes = manifest["dependency_rules"]["prohibited_research_output_prefixes"]
    violations: list[str] = []
    for path in sorted(config_root.rglob("*.yaml")) + sorted(config_root.rglob("*.yml")):
        content = path.read_text()
        for prefix in prefixes:
            if prefix in content:
                violations.append(f"{path.relative_to(ROOT)} references {prefix}")
    assert violations == []
