import pickle

import numpy as np
import pandas as pd
import pytest

from cks_picks_cfb.models.regime_training import (
    fit_candidate_model,
    select_monotone_blend_weights,
)


def test_blend_weight_search_is_selection_only_and_monotone():
    rows = []
    regimes = {1: "one_game", 2: "two_games", 3: "three_games"}
    for season in (2022, 2023, 2024):
        for games, regime in regimes.items():
            rows.append(
                {
                    "season": season,
                    "prediction_regime": regime,
                    "spread_target": float(10 - games * 2),
                    "preseason_component_prediction": 10.0,
                    "current_component_prediction": 2.0,
                }
            )
    weights = select_monotone_blend_weights(
        pd.DataFrame(rows), target="spread", grid=(0.0, 0.25, 0.5, 0.75, 1.0)
    )
    assert weights[0] == 1.0
    assert weights[4] == 0.0
    assert weights[1] >= weights[2] >= weights[3]


def test_blend_weight_search_rejects_locked_test_rows():
    frame = pd.DataFrame(
        {
            "season": [2025],
            "prediction_regime": ["one_game"],
            "spread_target": [1.0],
            "preseason_component_prediction": [1.0],
            "current_component_prediction": [1.0],
        }
    )
    with pytest.raises(ValueError, match="2022-2024"):
        select_monotone_blend_weights(frame, target="spread")


def test_catboost_candidate_is_sklearn_pipeline_compatible_and_serializable():
    """CatBoost must keep working inside sklearn Pipeline as sklearn evolves."""
    frame = pd.DataFrame(
        {
            "off_epa_play_mean": [0.1, 0.2, 0.4, 0.3, 0.5, 0.7],
            "spread_target": [1.0, 1.5, 3.0, 2.5, 4.0, 5.0],
        }
    )

    model = fit_candidate_model(
        frame,
        features=["off_epa_play_mean"],
        target_column="spread_target",
        kind="direct_catboost",
        random_seed=7,
    )
    restored = pickle.loads(pickle.dumps(model))
    prediction = np.asarray(restored.predict(frame[["off_epa_play_mean"]]), dtype=float)

    assert prediction.shape == (len(frame),)
    assert np.isfinite(prediction).all()
