"""Silver stage helpers: config identity, capture-manifest pin, season guard."""

from __future__ import annotations

import hashlib
import json

import pytest

from cks_picks_cfb.rebuild import silver
from cks_picks_cfb.rebuild.errors import GateError
from cks_picks_cfb.rebuild.plan import HISTORICAL_SEASONS


def test_config_sha_changes_with_nullable_ppa():
    on = silver.config_sha()
    off = silver.config_sha({**silver.PIPELINE_CONFIG, "nullable_ppa": False})
    assert on != off
    assert on == silver.config_sha()


def test_capture_manifest_accepts_raw_or_signed_hash_only():
    raw = json.dumps({"manifest_sha256": "a" * 64, "x": 1}).encode()
    silver.check_capture_manifest(raw, hashlib.sha256(raw).hexdigest())
    silver.check_capture_manifest(raw, "a" * 64)
    with pytest.raises(GateError):
        silver.check_capture_manifest(raw, "b" * 64)


def test_season_list_rejects_2020_and_partial_sets():
    assert silver.season_list(HISTORICAL_SEASONS) == list(HISTORICAL_SEASONS)
    with pytest.raises(GateError):
        silver.season_list(HISTORICAL_SEASONS + (2020,))
    with pytest.raises(GateError):
        silver.season_list((2015, 2016))


def test_season_refs_require_every_parent_and_derived_dataset():
    entries = [
        {"season": 2024, "dataset": name}
        for name in (*silver.PARENT_ORDER, *silver.DERIVED)
    ]
    assert len(silver._season_refs({"entries": entries}, 2024)) == 9
    with pytest.raises(GateError, match="lacks"):
        silver._season_refs({"entries": entries[:-1]}, 2024)


def test_value_differences_normalize_legacy_nan_strings():
    import pandas as pd

    new = pd.DataFrame(
        {"a": [None, "x", "y"], "ppa": [None, 1.0, None], "extra": [1, 2, 3]}
    )
    legacy = pd.DataFrame({"a": ["nan", "x", "z"], "ppa": [0.0, 1.0, 0.0]})
    assert silver.value_differences(new, legacy) == {"a": 1, "ppa": 2}
    with pytest.raises(GateError):
        silver.value_differences(new, legacy.iloc[:2])
