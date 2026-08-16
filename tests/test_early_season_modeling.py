import pandas as pd
import pytest

from cks_picks_cfb.models.early_season import (
    add_points_derived_predictions,
    add_team_side_shrinkage,
    prior_strength_designs,
    require_frozen_prior_strengths,
    shrink_to_prior,
)
from cks_picks_cfb.models.regime_training import MAX_ABS_MODEL_FEATURE, _model_values


def test_shrinkage_uses_team_specific_exposure_and_preserves_fallbacks():
    prior = pd.Series([1.0, 1.0, None])
    current = pd.Series([3.0, 3.0, 4.0])
    exposure = pd.Series([0, 100, 10])
    value, weight = shrink_to_prior(prior, current, exposure, prior_strength=100)
    assert value.tolist() == [1.0, 2.0, 4.0]
    assert weight.tolist() == [0.0, 0.5, 1.0]


def test_team_side_shrinkage_does_not_use_opponent_exposure():
    frame = pd.DataFrame(
        {
            "home_prior_adj_off_epa_pp": [1.0],
            "home_adj_off_epa_pp": [3.0],
            "home_n_off_plays": [100],
            "away_prior_adj_off_epa_pp": [1.0],
            "away_adj_off_epa_pp": [3.0],
            "away_n_off_plays": [0],
        }
    )
    home = add_team_side_shrinkage(
        frame,
        side="home",
        metrics=["adj_off_epa_pp"],
        exposure_column="home_n_off_plays",
        prior_strength=100,
    )
    away = add_team_side_shrinkage(
        home,
        side="away",
        metrics=["adj_off_epa_pp"],
        exposure_column="away_n_off_plays",
        prior_strength=100,
    )
    assert away.loc[0, "home_shrunk_adj_off_epa_pp"] == 2.0
    assert away.loc[0, "away_shrunk_adj_off_epa_pp"] == 1.0


def test_points_predictions_are_nonnegative_and_coherent():
    result = add_points_derived_predictions(
        pd.DataFrame({"home": [-2.0], "away": [21.0]}),
        home_column="home",
        away_column="away",
    )
    assert result.loc[0, "points_derived_home_points"] == 0.0
    assert result.loc[0, "points_derived_spread_prediction"] == -21.0
    assert result.loc[0, "points_derived_total_prediction"] == 21.0


def test_prior_strengths_must_be_from_the_frozen_grid():
    require_frozen_prior_strengths({"plays": 100, "drives": 20, "games": 4})
    with pytest.raises(ValueError, match="frozen grid"):
        require_frozen_prior_strengths({"plays": 99})


def test_prior_strength_design_grid_is_complete_and_reproducible():
    designs = prior_strength_designs()
    assert len(designs) == 64
    assert designs[0] == {"plays": 50.0, "drives": 5.0, "games": 1.0}
    assert designs[-1] == {"plays": 400.0, "drives": 40.0, "games": 8.0}


def test_model_values_treat_nonfinite_and_extreme_values_as_missing():
    result = _model_values(
        pd.DataFrame({"x": [1.0, float("inf"), MAX_ABS_MODEL_FEATURE * 2]}),
        ["x"],
    )
    assert result["x"].notna().sum() == 1
