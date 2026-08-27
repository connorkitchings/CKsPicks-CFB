"""Cross-lineage hard-gate behavior."""

from __future__ import annotations

import pandas as pd

from cks_picks_cfb.ratings.cross_lineage import compare_season


def _inputs(*, home_team: str = "Alpha", home_points: int = 24):
    return {
        "games": pd.DataFrame(
            [{"season": 2019, "game_id": 1, "home_team": home_team, "away_team": "Beta"}]
        ),
        "game_outcomes": pd.DataFrame(
            [{"season": 2019, "game_id": 1, "home_points": home_points, "away_points": 17}]
        ),
        "teams": pd.DataFrame([{"season": 2019, "school": "Alpha"}, {"season": 2019, "school": "Beta"}]),
    }


def test_cross_lineage_accepts_equal_evidence_and_rejects_hard_conflicts():
    baseline = _inputs()
    assert all(compare_season(season=2019, successor=baseline, legacy=_inputs()).values())

    assert not compare_season(
        season=2019, successor=baseline, legacy=_inputs(home_team="Gamma")
    )["game_identity_ok"]
    assert not compare_season(
        season=2019, successor=baseline, legacy=_inputs(home_points=21)
    )["scores_ok"]
