"""Tests for contracts validation helpers."""

import importlib.util
from pathlib import Path

VALIDATION_PATH = Path(__file__).resolve().parents[1] / "contracts" / "validation.py"
spec = importlib.util.spec_from_file_location("contracts_validation", VALIDATION_PATH)
assert spec is not None
contracts_validation = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(contracts_validation)


def test_checked_in_team_maps_are_synchronized():
    assert contracts_validation.check_teams_sync() == []


def test_extract_python_map_includes_values(tmp_path):
    path = tmp_path / "teams.py"
    path.write_text('TEAM_LOGO_MAP = {"A": "Alpha", "B": "Beta"}\n')

    assert contracts_validation.extract_python_map(path) == {"A": "Alpha", "B": "Beta"}


def test_extract_ts_map_includes_values(tmp_path):
    path = tmp_path / "teams.ts"
    path.write_text(
        'export const TEAM_LOGO_MAP: Record<string, string> = {"A": "Alpha", B: "Beta"};\n'
    )

    assert contracts_validation.extract_ts_map(path) == {"A": "Alpha", "B": "Beta"}


def test_projection_sets_registry_is_in_sync():
    assert contracts_validation.check_projection_sets_sync() == []


def test_projection_sets_detects_web_mirror_drift(tmp_path, monkeypatch):
    contracts = tmp_path / "contracts"
    mirror = tmp_path / "web" / "src" / "lib"
    contracts.mkdir()
    mirror.mkdir(parents=True)
    registry = (
        '{"staging_set": "a", "sets": {"a": {"tables": ["t"], "chart_set": null}}}\n'
    )
    (contracts / "projection_sets.json").write_text(registry)
    (mirror / "projection-sets.json").write_text(registry)
    monkeypatch.setattr(contracts_validation, "CONTRACTS_DIR", contracts)
    monkeypatch.setattr(contracts_validation, "ROOT", tmp_path)
    assert contracts_validation.check_projection_sets_sync() == []

    (mirror / "projection-sets.json").write_text(registry.replace('"t"', '"u"'))
    assert any(
        "differs" in e for e in contracts_validation.check_projection_sets_sync()
    )

    (contracts / "projection_sets.json").write_text(
        '{"staging_set": "missing", "sets": {"a": {"tables": ["t", "t"], "chart_set": "zzz"}}}\n'
    )
    errors = contracts_validation.check_projection_sets_sync()
    assert any("staging_set" in e for e in errors)
    assert any("twice" in e for e in errors)
    assert any("unknown chart_set" in e for e in errors)
