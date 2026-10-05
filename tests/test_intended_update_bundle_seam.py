"""The corrected-rebuild fit entry point and its leakage guard."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cks_picks_cfb.forecast import intended_update_bundle as bundle_module
from cks_picks_cfb.forecast.heads import FEATURES
from cks_picks_cfb.forecast.live import DEVELOPMENT_SEASONS


def _frame(seasons=DEVELOPMENT_SEASONS, games=40) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    rows = []
    game_id = 0
    for season in seasons:
        for _ in range(games):
            game_id += 1
            row = {name: float(rng.normal()) for name in FEATURES}
            margin = (
                3.0 * row[FEATURES[0]] - 2.0 * row[FEATURES[1]] + rng.normal(scale=2)
            )
            row.update(
                season=season,
                week=1 + game_id % 12,
                game_id=game_id,
                actual_margin=margin,
                actual_total=45.0 + row[FEATURES[0]] + rng.normal(scale=3),
                offset_margin=0.5,
                offset_total=0.25,
            )
            rows.append(row)
    return pd.DataFrame(rows)


def test_fit_bundle_from_frame_exports_both_targets():
    bundle, counts = bundle_module.fit_bundle_from_frame(_frame())
    assert set(bundle["targets"]) == {"margin", "total"}
    assert bundle["feature_order"] == list(FEATURES)
    assert counts["margin"] > 0 and counts["total"] > 0
    for target in ("margin", "total"):
        assert bundle["targets"][target]["calibration_variance"] >= 1e-6


@pytest.mark.parametrize("bad", [2020, 2026])
def test_guard_rejects_forbidden_seasons(bad):
    frame = pd.concat([_frame(), _frame((bad,))], ignore_index=True)
    with pytest.raises(bundle_module.IntendedBundleError, match="forbidden"):
        bundle_module.assert_pre2026_frame(frame)
    with pytest.raises(bundle_module.IntendedBundleError):
        bundle_module.fit_bundle_from_frame(frame)


def test_guard_requires_every_development_season():
    partial = _frame(DEVELOPMENT_SEASONS[:-1])
    with pytest.raises(bundle_module.IntendedBundleError, match="differ"):
        bundle_module.assert_pre2026_frame(partial)
