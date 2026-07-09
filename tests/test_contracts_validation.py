"""Tests for contracts validation helpers."""

import importlib.util
from pathlib import Path

VALIDATION_PATH = Path(__file__).resolve().parents[1] / "contracts" / "validation.py"
spec = importlib.util.spec_from_file_location("contracts_validation", VALIDATION_PATH)
assert spec is not None
contracts_validation = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(contracts_validation)


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
