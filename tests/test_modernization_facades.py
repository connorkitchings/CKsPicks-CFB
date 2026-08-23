"""Focused import and behavior parity checks for the modernization facades."""

import pandas as pd

from cks_picks_cfb.data.silver import SILVER_CONTRACTS
from cks_picks_cfb.data.storage import LocalStorage, Partition, StorageBackend
from cks_picks_cfb.features.aggregations import aggregate_drives
from cks_picks_cfb.features.byplay import calculate_explosive
from cks_picks_cfb.features.core import aggregate_drives as legacy_aggregate_drives
from cks_picks_cfb.features.regimes import canonical_prediction_regime
from cks_picks_cfb.features.rolling_ewma import aggregate_team_season_ewma
from cks_picks_cfb.features.v2_recency import (
    aggregate_team_season_ewma as legacy_aggregate_team_season_ewma,
)


def test_storage_silver_and_feature_facades_remain_import_compatible(tmp_path):
    assert issubclass(LocalStorage, StorageBackend)
    assert Partition({"year": "2026"}).path_suffix().as_posix() == "year=2026"
    assert "games" in SILVER_CONTRACTS
    assert legacy_aggregate_drives is aggregate_drives
    assert callable(calculate_explosive)


def test_ewma_and_regime_compatibility_exports_match_focused_modules():
    frame = pd.DataFrame(
        [
            {"season": 2026, "week": 1, "game_id": 1, "team": "A", "metric": 1.0},
            {"season": 2026, "week": 2, "game_id": 2, "team": "A", "metric": 3.0},
        ]
    )
    pd.testing.assert_frame_equal(
        aggregate_team_season_ewma(frame, 0.5),
        legacy_aggregate_team_season_ewma(frame, 0.5),
    )
    assert canonical_prediction_regime("preseason") == "game_1"
