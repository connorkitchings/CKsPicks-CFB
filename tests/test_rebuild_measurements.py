"""Independent PPP verification and streamed history evidence."""

from __future__ import annotations

import pandas as pd

from cks_picks_cfb.rebuild import measurements as stage


def _possessions():
    rows = []
    for drive, eligible in ((1, True), (2, True), (3, False)):
        rows.append(
            {
                "season": 2025,
                "game_id": 1,
                "drive_number": drive,
                "offense": "A",
                "possession_eligible": eligible,
            }
        )
    rows.append(
        {
            "season": 2025,
            "game_id": 1,
            "drive_number": 1,
            "offense": "B",
            "possession_eligible": True,
        }
    )
    return pd.DataFrame(rows)


def _events(extra=()):
    rows = [
        {
            "season": 2025,
            "game_id": 1,
            "team": "A",
            "scoring_category": "eligible_regulation_offense",
            "score_increment": 7,
        },
        {
            "season": 2025,
            "game_id": 1,
            "team": "B",
            "scoring_category": "regulation_non_offense",
            "score_increment": 2,
        },
        *extra,
    ]
    return pd.DataFrame(rows)


def _obs(team, measurement, num, den, status="observed"):
    return {
        "season": 2025,
        "game_id": 1,
        "team": team,
        "unit_role": "offense",
        "measurement_id": measurement,
        "numerator": num,
        "denominator": den,
        "coverage_status": status,
    }


def _good():
    return pd.DataFrame(
        [
            _obs("A", "ppp", 7.0, 2.0),
            _obs("B", "ppp", 0.0, 1.0),
            _obs("A", "non_offense_points", 0.0, 1.0),
            _obs("B", "non_offense_points", 2.0, 1.0),
        ]
    )


def test_matching_observations_pass():
    assert stage.independent_ppp_problems(_good(), _possessions(), _events()) == []


def test_wrong_points_or_denominator_are_caught():
    bad_points = _good()
    bad_points.loc[0, "numerator"] = 6.0
    assert stage.independent_ppp_problems(bad_points, _possessions(), _events())
    bad_den = _good()
    bad_den.loc[0, "denominator"] = 3.0  # counted the ineligible possession
    assert stage.independent_ppp_problems(bad_den, _possessions(), _events())


def test_unresolved_marker_makes_the_team_game_unusable():
    unresolved = _events(
        [
            {
                "season": 2025,
                "game_id": 1,
                "team": "A",
                "scoring_category": "unresolved",
                "score_increment": 0,
            }
        ]
    )
    still_observed = _good()
    assert stage.independent_ppp_problems(still_observed, _possessions(), unresolved)
    held = _good()
    held.loc[[0, 2], "coverage_status"] = "missing"
    assert stage.independent_ppp_problems(held, _possessions(), unresolved) == []


def test_missing_status_where_recomputation_is_usable_is_caught():
    missing = _good()
    missing.loc[0, "coverage_status"] = "missing"
    assert stage.independent_ppp_problems(missing, _possessions(), _events())


def test_history_evidence_is_deterministic_and_order_independent():
    frame = pd.DataFrame({"a": [1, 2, 3], "b": [0.1, 0.2, 0.3]})
    first, second = stage.HistoryEvidence(), stage.HistoryEvidence()
    first.add({"season": 2024, "week": 2}, frame)
    first.add({"season": 2024, "week": 1}, frame.assign(a=[3, 2, 1]))
    second.add({"season": 2024, "week": 1}, frame.assign(a=[3, 2, 1]))
    second.add({"season": 2024, "week": 2}, frame)
    assert first.summary()["digest"] == second.summary()["digest"]
    assert first.summary()["rows"] == 6 and first.summary()["partitions"] == 2
    changed = stage.HistoryEvidence()
    changed.add({"season": 2024, "week": 2}, frame.assign(b=[0.1, 0.2, 0.4]))
    changed.add({"season": 2024, "week": 1}, frame.assign(a=[3, 2, 1]))
    assert changed.summary()["digest"] != first.summary()["digest"]


def test_bundle_prediction_check_uses_named_center_and_scale_and_catches_drift():
    import numpy as np

    from cks_picks_cfb.rebuild import forecast_refit as refit

    features = pd.DataFrame({"a": [0.0, 1.0, 2.0, 3.0], "b": [1.0, 1.0, 1.0, 1.0]})
    bundle = {
        "targets": {
            "margin": {
                "feature_names": ["a"],  # b is constant and dropped from the fit
                "center": {"a": 1.5, "b": 1.0},
                "scale": {"a": 1.0, "b": 0.05},
                "coefficients": [2.0],
                "intercept": 4.0,
                "training_rows": 4,
                "calibration_variance": 3.0,
            }
        }
    }

    def exact_fit(train, test, *, target, alpha, floor):
        return 4.0 + 2.0 * (test["a"].to_numpy(float) - 1.5), None

    assert refit.bundle_prediction_problems(bundle, features, exact_fit) == []
    drifted = {"targets": {"margin": {**bundle["targets"]["margin"], "intercept": 4.5}}}
    assert refit.bundle_prediction_problems(drifted, features, exact_fit)
    short = {"targets": {"margin": {**bundle["targets"]["margin"], "training_rows": 3}}}
    assert refit.bundle_prediction_problems(short, features, exact_fit)
    assert np.isfinite(refit.frame_digest(features) and 1)
