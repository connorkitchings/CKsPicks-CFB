"""Focused V5-04B calibration module tests."""

from __future__ import annotations

import pandas as pd
import pytest

from cks_picks_cfb.forecast.calibration import (
    CalibrationError,
    CalibrationResult,
    calibrate_uncertainty,
)


def _calibration_frame() -> pd.DataFrame:
    """Build a minimal feature frame spanning 2015-2022 for calibration tests."""
    rows = []
    seasons = (2015, 2016, 2017, 2018, 2019, 2021, 2022)
    game_id = 0
    for season in seasons:
        for week in (1, 2):
            game_id += 1
            value = float(season - 2014 + week)
            rows.append(
                {
                    "season": season,
                    "week": week,
                    "game_id": game_id,
                    "home_offense": value,
                    "home_defense": value / 2,
                    "away_offense": -value / 3,
                    "away_defense": value / 4,
                    "home_host": 1.0,
                    "venue_unknown": True,
                    "actual_margin": value * 1.5,
                    "actual_total": 35 + value,
                    "offset_margin": 0.2,
                    "offset_total": 0.4,
                    "completed_game_stage": min(week, 4),
                }
            )
    return pd.DataFrame.from_records(rows)


def test_calibration_residual_chronology():
    """First eligible residual season is 2017 (after 2015, 2016 fitting seasons)."""
    frame = _calibration_frame()
    result = calibrate_uncertainty(
        frame,
        horizon="expanding",
        development_seasons=(2015, 2016, 2017, 2018, 2019, 2021, 2022),
        outer_seasons=(2018, 2022),
        alpha_grid=(0.1, 1.0, 10.0, 100.0),
        floor=0.05,
    )
    assert isinstance(result, CalibrationResult)
    assert set(result.records.columns) == {
        "target",
        "season",
        "residual_count",
        "variance",
        "fallback_reason",
    }
    for season in (2018, 2022):
        for target in ("margin", "total"):
            row = result.records[
                (result.records.season == season) & (result.records.target == target)
            ]
            assert len(row) == 1
            assert int(row.iloc[0].residual_count) > 0
            assert row.iloc[0].fallback_reason == ""


def test_calibration_variance_floor_enforcement():
    """Variance is floored at residual_floor (default 1e-6)."""
    frame = _calibration_frame()
    result = calibrate_uncertainty(
        frame,
        horizon="expanding",
        development_seasons=(2015, 2016, 2017, 2018, 2019, 2021, 2022),
        outer_seasons=(2022,),
        alpha_grid=(0.1, 1.0, 10.0, 100.0),
        floor=0.05,
        residual_floor=1e-6,
    )
    for target in ("margin", "total"):
        row = result.records[
            (result.records.season == 2022) & (result.records.target == target)
        ]
        assert float(row.iloc[0].variance) >= 1e-6


def test_calibration_fallback_no_prior_residuals():
    """Outer season with no eligible residual seasons gets fallback."""
    frame = _calibration_frame()
    result = calibrate_uncertainty(
        frame,
        horizon="expanding",
        development_seasons=(2015, 2016, 2017, 2018, 2019, 2021, 2022),
        outer_seasons=(2016,),
        alpha_grid=(0.1, 1.0, 10.0, 100.0),
        floor=0.05,
        residual_floor=1e-6,
    )
    for target in ("margin", "total"):
        row = result.records[
            (result.records.season == 2016) & (result.records.target == target)
        ]
        assert len(row) == 1
        assert int(row.iloc[0].residual_count) == 0
        assert float(row.iloc[0].variance) == 1e-6
        assert row.iloc[0].fallback_reason == "no_prior_residuals"


def test_calibration_per_target_independence():
    """Margin and total have separate variance tracks."""
    frame = _calibration_frame()
    result = calibrate_uncertainty(
        frame,
        horizon="expanding",
        development_seasons=(2015, 2016, 2017, 2018, 2019, 2021, 2022),
        outer_seasons=(2022,),
        alpha_grid=(0.1, 1.0, 10.0, 100.0),
        floor=0.05,
    )
    assert "margin" in result.variances
    assert "total" in result.variances
    assert 2022 in result.variances["margin"]
    assert 2022 in result.variances["total"]
    margin_var = result.variances["margin"][2022]
    total_var = result.variances["total"][2022]
    assert isinstance(margin_var, float)
    assert isinstance(total_var, float)


def test_calibration_deterministic_output():
    """Identical inputs produce identical outputs."""
    frame = _calibration_frame()
    kwargs = dict(
        horizon="expanding",
        development_seasons=(2015, 2016, 2017, 2018, 2019, 2021, 2022),
        outer_seasons=(2018, 2022),
        alpha_grid=(0.1, 1.0, 10.0, 100.0),
        floor=0.05,
    )
    result1 = calibrate_uncertainty(frame, **kwargs)
    result2 = calibrate_uncertainty(frame, **kwargs)
    pd.testing.assert_frame_equal(result1.records, result2.records)
    assert result1.variances == result2.variances


def test_calibration_future_perturbation_invariance():
    """Adding later-season data does not alter earlier calibration."""
    frame = _calibration_frame()
    early = frame[frame.season.le(2021)]
    result_early = calibrate_uncertainty(
        early,
        horizon="expanding",
        development_seasons=(2015, 2016, 2017, 2018, 2019, 2021),
        outer_seasons=(2018, 2021),
        alpha_grid=(0.1, 1.0, 10.0, 100.0),
        floor=0.05,
    )
    result_full = calibrate_uncertainty(
        frame,
        horizon="expanding",
        development_seasons=(2015, 2016, 2017, 2018, 2019, 2021, 2022),
        outer_seasons=(2018, 2021),
        alpha_grid=(0.1, 1.0, 10.0, 100.0),
        floor=0.05,
    )
    early_records = result_early.records[
        result_early.records.season.isin((2018, 2021))
    ].reset_index(drop=True)
    full_records = result_full.records[
        result_full.records.season.isin((2018, 2021))
    ].reset_index(drop=True)
    pd.testing.assert_frame_equal(early_records, full_records)


def test_calibration_missing_columns_raises():
    """Calibration frame must have required columns."""
    frame = pd.DataFrame({"season": [2022], "week": [1]})
    with pytest.raises(CalibrationError, match="lacks columns"):
        calibrate_uncertainty(
            frame,
            horizon="expanding",
            development_seasons=(2015, 2016, 2017),
            outer_seasons=(2022,),
            alpha_grid=(0.1, 1.0),
            floor=0.05,
        )
