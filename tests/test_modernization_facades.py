"""Focused import and behavior parity checks for the modernization facades."""

from cks_picks_cfb.data.silver import SILVER_CONTRACTS
from cks_picks_cfb.data.storage import LocalStorage, Partition, StorageBackend
from cks_picks_cfb.features.aggregations import aggregate_drives
from cks_picks_cfb.features.byplay import calculate_explosive
from cks_picks_cfb.features.core import aggregate_drives as legacy_aggregate_drives
from cks_picks_cfb.features.regimes import canonical_prediction_regime


def test_storage_silver_and_feature_facades_remain_import_compatible(tmp_path):
    assert issubclass(LocalStorage, StorageBackend)
    assert Partition({"year": "2026"}).path_suffix().as_posix() == "year=2026"
    assert "games" in SILVER_CONTRACTS
    assert legacy_aggregate_drives is aggregate_drives
    assert callable(calculate_explosive)


def test_regime_compatibility_exports_match_focused_modules():
    assert canonical_prediction_regime("preseason") == "game_1"
