"""Attribution math: aligned deltas, ranks, predictions, bundle deltas and interaction."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cks_picks_cfb.rebuild import attribution_math as am


def test_frame_delta_separates_missing_rows_null_flips_and_size():
    base = pd.DataFrame({"k": [1, 2, 3, 4], "v": [1.0, 2.0, np.nan, 4.0]})
    other = pd.DataFrame({"k": [1, 2, 3, 5], "v": [1.0, 2.5, 3.0, 9.0]})
    report = am.frame_delta(base, other, keys=["k"], columns=["v"], threshold=0.1)
    column = report["columns"]["v"]
    assert report["only_base"] == 1 and report["only_other"] == 1
    assert column["compared"] == 2  # rows 1 and 2 have numbers on both sides
    assert column["changed"] == 2  # 2.0 -> 2.5, and the NaN -> 3.0 flip
    assert column["null_flips"] == 1 and column["over_threshold"] == 1
    assert column["max_abs"] == pytest.approx(0.5)


def test_identical_frames_report_no_change():
    frame = pd.DataFrame({"k": [1, 2], "v": [1.0, 2.0]})
    column = am.frame_delta(frame, frame, keys=["k"], columns=["v"])["columns"]["v"]
    assert column["changed"] == 0 and column["max_abs"] == 0.0


def _states(offense):
    return pd.DataFrame(
        {
            "season": [2024] * 6,
            "team": ["A", "A", "B", "B", "C", "C"],
            "game_id": [1, 4, 2, 5, 3, 6],
            "cutoff_utc": [f"2024-09-0{i}" for i in (1, 4, 2, 5, 3, 6)],
            "offense_rating": offense,
            "defense_rating": [0.0] * 6,
            "overall_rating": offense,
        }
    )


def test_final_ranks_use_each_teams_last_state_and_rank_moves_count_changes():
    base = am.final_ranks(_states([0.1, 0.9, 0.2, 0.5, 0.3, 0.1]))
    other = am.final_ranks(_states([0.1, 0.2, 0.2, 0.5, 0.3, 0.9]))
    moves = am.rank_moves(base, other, over=1)
    assert moves["team_seasons"] == 3
    overall = moves["overall_rating"]
    # A falls 1 -> 3 and C rises 3 -> 1; B holds rank 2 in both.
    assert overall["moved"] == 2 and overall["over_threshold"] == 2
    assert overall["max_move"] == 2


def _bundle(intercept, coef):
    entry = {
        "feature_names": ["a"],
        "center": {"a": 1.0},
        "scale": {"a": 2.0},
        "coefficients": [coef],
        "intercept": intercept,
        "calibration_variance": 4.0,
        "alpha": 10.0,
    }
    return {"targets": {"margin": dict(entry), "total": dict(entry)}}


def _features():
    return pd.DataFrame(
        {
            "season": [2024, 2024],
            "week": [1, 2],
            "game_id": [10, 11],
            "a": [1.0, 3.0],
            "offset_margin": [0.5, 0.5],
            "offset_total": [1.0, 1.0],
        }
    )


def test_predict_applies_offset_plus_standardized_ridge():
    out = am.predict(_bundle(2.0, 4.0), _features())
    assert out["pred_margin"].tolist() == pytest.approx([0.5 + 2.0, 0.5 + 2.0 + 4.0])
    assert out["pred_total"].tolist() == pytest.approx([1.0 + 2.0, 1.0 + 2.0 + 4.0])


def test_bundle_delta_reports_coefficient_intercept_and_calibration_changes():
    delta = am.bundle_delta(_bundle(2.0, 4.0), _bundle(2.5, 3.0))
    assert delta["margin"]["coefficient_deltas"] == {"a": -1.0}
    assert delta["margin"]["intercept_delta"] == pytest.approx(0.5)
    assert delta["margin"]["max_abs_coefficient_delta"] == 1.0


def test_interaction_is_zero_for_additive_effects_and_nonzero_otherwise():
    keys = {"season": [2024], "week": [1], "game_id": [1]}

    def forecast(margin):
        return pd.DataFrame({**keys, "pred_margin": [margin], "pred_total": [margin]})

    additive = {
        "baseline": forecast(10.0),
        "epa_only": forecast(10.0),
        "scoring_only": forecast(11.0),
        "offset_only": forecast(10.5),
        "combined": forecast(11.5),
    }
    assert am.interaction(additive)["pred_margin"]["nonzero"] == 0
    interacting = dict(additive, combined=forecast(12.0))
    result = am.interaction(interacting)["pred_margin"]
    assert result["nonzero"] == 1 and result["max_abs"] == pytest.approx(0.5)


def test_digests_are_deterministic_and_sensitive():
    a = pd.DataFrame({"x": [1, 2]})
    assert am.frame_digest(a) == am.frame_digest(a.copy())
    assert am.frame_digest(a) != am.frame_digest(pd.DataFrame({"x": [1, 3]}))
    assert am.json_sha({"b": 1, "a": 2}) == am.json_sha({"a": 2, "b": 1})


def test_season_changes_handles_season_as_a_key_and_as_a_separate_column():
    from cks_picks_cfb.rebuild import attribution

    base = pd.DataFrame(
        {"season": [2024, 2024, 2025], "game_id": [1, 2, 3], "v": [1.0, 2.0, 3.0]}
    )
    other = base.assign(v=[1.0, 2.5, 3.5])
    assert attribution.season_changes(base, other, ["season", "game_id"], "v") == {
        "2024": 1,
        "2025": 1,
    }
    no_season_key = attribution.season_changes(base, other, ["game_id"], "v")
    assert no_season_key == {"2024": 1, "2025": 1}


def test_canonical_digest_ignores_row_order_column_order_and_numeric_dtype():
    a = pd.DataFrame({"x": [1, 2, 3], "y": [0.5, 0.25, 0.125], "s": ["a", "b", None]})
    shuffled = a.iloc[[2, 0, 1]][["s", "y", "x"]].reset_index(drop=True)
    retyped = shuffled.assign(x=shuffled["x"].astype("float64"))
    assert (
        am.canonical_digest(a)
        == am.canonical_digest(shuffled)
        == am.canonical_digest(retyped)
    )
    assert am.canonical_digest(a) != am.canonical_digest(a.assign(y=[0.5, 0.25, 0.126]))
    assert am.canonical_digest(a) != am.canonical_digest(a.iloc[:2])
