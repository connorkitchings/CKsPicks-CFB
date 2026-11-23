from pathlib import Path

import pandas as pd
import pytest

from scripts.research import replay_frozen_p3 as p3


@pytest.mark.parametrize("season", [2020, 2026, 2027])
def test_rejects_outside_development_before_loading(season, monkeypatch):
    def block_load(*args):
        pytest.fail("invalid season reached input loading")

    monkeypatch.setattr(p3, "_load_frame", block_load)
    with pytest.raises(ValueError, match="development seasons"):
        p3.replay(Path("unused"), [2025, season])


def test_only_earlier_seasons_fit_and_offset_is_restored(monkeypatch):
    def load_frame(root, seasons):
        assert seasons == (2015, 2016, 2017)
        return pd.DataFrame(
            {
                "season": seasons,
                "game_id": [1, 2, 3],
                "completed_game_stage": [3, 1, 4],
                "actual_margin": [9, 10, 11],
                "offset_margin": [0, 0, 2],
                "FCS": [0, 1, 0],
            }
        )

    def fit_one(train, test, *, target, alpha, floor, features):
        assert train.game_id.tolist() == [1, 2]
        assert test.game_id.tolist() == [3]
        assert (target, alpha, floor) == ("margin", 10.0, 1e-6)
        return (5 if features == p3.P3_FEATURES else 3), 1.0

    monkeypatch.setattr(p3, "_load_frame", load_frame)
    monkeypatch.setattr(p3, "_fit_one", fit_one)
    result = p3.replay(Path("unused"), [2017])
    assert result[["game_id", "baseline", "p3"]].values.tolist() == [[3, 5, 7]]
