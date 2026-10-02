"""Public helper names used by the matchup data layer match their definitions."""

import numpy as np
import pandas as pd

from cks_picks_cfb.ratings import possession_intended_update as iu
from cks_picks_cfb.ratings import possession_live_replay as live
from cks_picks_cfb.ratings import possession_measurements as pm


def test_public_aliases_are_the_private_definitions():
    assert pm.adjust_possession_history is pm._adjust
    assert pm.eligible_possession_play is pm._eligible_play
    assert live.historical_scale is live._historical_scale


def test_eligible_play_mask_matches_row_predicate():
    plays = pd.DataFrame(
        {
            "quarter": [1, 2, 5, 3, 4],
            "st": [0, 0, 0, 1, 0],
            "penalty": [0, 0, 0, 0, 1],
            "twopoint": [0, 0, 0, 0, 0],
            "garbage": [0, 0, 0, 0, 0],
            "play_type": ["Rush", "Pass Reception", "Rush", "Punt", "Rush"],
        }
    )
    mask = pm.eligible_possession_play_mask(plays)
    expected = [pm._eligible_play(r) for r in plays.itertuples(index=False)]
    assert mask.tolist() == expected
    assert mask.tolist()[:2] == [True, True]  # regulation, no special flags
    assert not mask.iloc[2]  # overtime
    assert not mask.iloc[3] and not mask.iloc[4]  # special teams, penalty


def test_usable_ppp_mask_rejects_unobserved_zero_and_nonfinite():
    frame = pd.DataFrame(
        {
            "coverage_status": [
                "observed",
                "missing",
                "observed",
                "observed",
                "observed",
            ],
            "denominator": [10, 10, 0, 10, 10],
            "raw_value": [1.0, 1.0, 1.0, np.nan, 2.0],
            "numerator": [10.0, 10.0, 0.0, 10.0, 20.0],
        }
    )
    assert iu.usable_ppp_mask(frame).tolist() == [True, False, False, False, True]
