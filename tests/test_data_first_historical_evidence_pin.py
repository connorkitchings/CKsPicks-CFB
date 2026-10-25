"""The retired V4 config is kept only as pinned, historical audit evidence."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml

from scripts.research.audit_data_first_evidence import check_root_checksum

ROOT = Path(__file__).resolve().parents[1]
AUDIT_CONFIG = ROOT / "conf/research/data_first_football_v1/phase1_audit_v1.yaml"
RESTORED = "conf/research/data_first_football_v1/historical/v4_2026.yaml"
RETIRED = "conf/weekly_bets/v4_2026.yaml"
PINNED_SHA256 = "b6a24c22aaf9f5ac1bf25a53a2914f458b3e77992a99d3942648138c2c45f1f1"


def _v4_root() -> dict:
    roots = yaml.safe_load(AUDIT_CONFIG.read_text())["roots"]
    return next(r for r in roots if r["root_id"] == "v4_config")


def test_audit_root_points_at_pinned_historical_copy():
    spec = _v4_root()
    assert spec["kind"] == "local_yaml"
    assert spec["path"] == RESTORED
    assert spec["expected_sha256"] == PINNED_SHA256
    assert (ROOT / spec["path"]).is_file()


def test_restored_file_matches_pinned_checksum():
    raw = (ROOT / _v4_root()["path"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PINNED_SHA256
    check_root_checksum(hashlib.sha256(raw).hexdigest(), _v4_root()["expected_sha256"])
    assert isinstance(yaml.safe_load(raw), dict)


def test_tampered_copy_fails_the_pin(tmp_path):
    tampered = tmp_path / "v4_2026.yaml"
    tampered.write_bytes((ROOT / RESTORED).read_bytes() + b"# edited\n")
    actual = hashlib.sha256(tampered.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="root checksum mismatch"):
        check_root_checksum(actual, _v4_root()["expected_sha256"])


def test_retired_operational_path_stays_absent():
    assert not (ROOT / RETIRED).exists()
