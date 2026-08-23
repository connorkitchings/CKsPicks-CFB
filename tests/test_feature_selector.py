"""Behavioral tests for configured feature selection."""

from __future__ import annotations

import pandas as pd
from omegaconf import OmegaConf

from cks_picks_cfb.features.selector import (
    RECENCY_BASE_FEATURES,
    get_feature_groups,
    get_feature_set_id,
    select_features,
)


def _config(**features):
    return OmegaConf.create({"features": {"name": "fixture", **features}})


def test_groups_are_explicit_and_feature_id_is_order_stable():
    groups = get_feature_groups()

    assert {"off_def_stats", "pace_stats", "recency_stats", "weather_stats"} <= set(
        groups
    )
    first = _config(groups=["pace_stats", "weather_stats"], recency_window="standard")
    second = _config(groups=["weather_stats", "pace_stats"], recency_window="standard")
    assert get_feature_set_id(first) == get_feature_set_id(second)


def test_select_features_expands_recency_variants_and_honors_allowlist(capsys):
    permitted = next(iter(RECENCY_BASE_FEATURES))
    frame = pd.DataFrame(
        {
            f"home_{permitted}_last_1": [1.0],
            f"away_{permitted}_last_1": [2.0],
            "home_not_allowed_last_1": [3.0],
            "home_temperature_last_2": [4.0],
        }
    )
    cfg = _config(
        groups=["recency_stats", "does_not_exist"],
        recency_window="fast",
        include_last_2=True,
    )

    selected = select_features(frame, cfg)

    assert list(selected) == sorted(
        [
            f"away_{permitted}_last_1",
            f"home_{permitted}_last_1",
            "home_temperature_last_2",
        ]
    )
    assert "requested base features" in capsys.readouterr().out


def test_select_features_builds_requested_and_weather_interactions():
    frame = pd.DataFrame(
        {
            "home_off": [2.0],
            "away_def": [3.0],
            "away_off": [5.0],
            "home_def": [7.0],
            "wind_speed": [11.0],
            "home_off_pass_ypp": [13.0],
            "away_off_pass_ypp": [17.0],
            "home_temperature": [19.0],
            "away_temperature": [23.0],
            "precipitation": [29.0],
        }
    )
    cfg = _config(
        groups=["weather_stats", "temperature"],
        recency_window="standard",
        interactions=[["off", "def"]],
        exclude=["away_temperature"],
    )

    selected = select_features(frame, cfg)

    assert selected.loc[0, "home_off_x_away_def"] == 6.0
    assert selected.loc[0, "away_off_x_home_def"] == 35.0
    assert selected.loc[0, "home_wind_speed_x_off_pass_ypp"] == 143.0
    assert selected.loc[0, "away_wind_speed_x_off_pass_ypp"] == 187.0
    assert "away_temperature" not in selected
    assert "home_temperature" in selected


def test_select_features_uses_home_weather_fallback_and_ignores_absent_pairs():
    frame = pd.DataFrame(
        {
            "home_wind_speed": [2.0],
            "home_off_pass_ypp": [4.0],
            "home_adj_off_epa_pp": [6.0],
            "away_adj_off_epa_pp": [8.0],
        }
    )
    cfg = _config(
        groups=["weather_stats", "off_def_stats"],
        recency_window="standard",
        interactions=[["missing", "also_missing"]],
    )

    selected = select_features(frame, cfg)

    assert selected.loc[0, "home_wind_speed_x_off_pass_ypp"] == 8.0
    assert {"home_adj_off_epa_pp", "away_adj_off_epa_pp"} <= set(selected)
