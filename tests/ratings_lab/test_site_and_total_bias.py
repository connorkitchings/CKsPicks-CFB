import numpy as np
import pandas as pd
import pytest

from cks_picks_cfb.ratings_lab.site_context import (
    conference_group,
    game_context,
    home_venues,
    venue_class,
)
from cks_picks_cfb.ratings_lab.total_bias import (
    bias_share_of_mse,
    error_correlation,
    level_and_slope,
    paired_errors,
    quantile_bands,
    rolling_recentering,
    team_points_split,
)


def _games() -> pd.DataFrame:
    rows = []
    for i in range(4):  # Alpha hosts at venue 1 four times
        rows.append(("Alpha", "Zed", False, 1.0, "SEC", "ACC", True))
    rows.append(("Alpha", "Zed", True, 99.0, "SEC", "ACC", False))  # neutral flag
    rows.append(
        ("Alpha", "Zed", False, 55.0, "SEC", "ACC", False)
    )  # elsewhere, unflagged
    rows.append(("Alpha", "Zed", False, np.nan, "SEC", "ACC", False))  # unknown venue
    rows.append(("Alpha", "Zed", np.nan, 1.0, "SEC", "ACC", False))  # unknown flag
    frame = pd.DataFrame(
        rows,
        columns=[
            "home_team",
            "away_team",
            "neutral_site",
            "venue_id",
            "home_conference",
            "away_conference",
            "conference_game",
        ],
    )
    frame["season"] = 2022
    frame["game_id"] = range(len(frame))
    return frame


def test_venue_classes_cover_all_four_cases():
    games = _games()
    labels = venue_class(games).tolist()
    assert labels == [
        "home venue",
        "home venue",
        "home venue",
        "home venue",
        "neutral site",
        "non-home venue, not flagged neutral",
        "venue unknown",
        "venue unknown",
    ]
    assert home_venues(games)["Alpha"] == {1}


def test_conference_group_uses_the_seasons_label():
    labels = conference_group(
        pd.Series(["SEC", "Sun Belt", "FBS Independents", "AWC", "Pac-12"])
    )
    assert labels.tolist() == [
        "Power",
        "Group of 5",
        "FBS independent",
        "other",
        "Power",
    ]


def test_game_context_labels_conference_games():
    context = game_context(_games())
    assert context["conference_game_label"].iloc[0] == "conference game"
    assert context["conference_game_label"].iloc[-1] == "non-conference game"
    assert len(context) == 8


def _predictions(n=400, seed=0, bias=-2.0):
    rng = np.random.default_rng(seed)
    rows = []
    for season in (2021, 2022, 2023):
        pred_total = rng.normal(56, 3, n)
        pred_margin = rng.normal(0, 10, n)
        act_total = pred_total + bias + rng.normal(0, 15, n)
        act_margin = pred_margin + rng.normal(0, 15, n)
        for target, pred, act in (
            ("margin", pred_margin, act_margin),
            ("total", pred_total, act_total),
        ):
            rows.append(
                pd.DataFrame(
                    {
                        "season": season,
                        "game_id": np.arange(n),
                        "target": target,
                        "prediction": pred,
                        "actual": act,
                        "interval_90_lower": pred - 25,
                        "interval_90_upper": pred + 25,
                    }
                )
            )
    return pd.concat(rows, ignore_index=True)


def test_team_points_errors_recombine_into_margin_and_total_errors():
    errors = paired_errors(_predictions())
    assert np.allclose(errors.home_error - errors.away_error, errors.margin_error)
    assert np.allclose(errors.home_error + errors.away_error, errors.total_error)
    split = team_points_split(errors)
    assert split.iloc[-1]["season"] == "pooled"
    assert split.iloc[-1]["games"] == len(errors)
    assert split.iloc[-1]["home_bias"] + split.iloc[-1]["away_bias"] == pytest.approx(
        errors.total_error.mean()
    )


def test_level_offset_shows_slope_near_one_and_negative_gap():
    total = _predictions(n=4000)
    total = total[total.target.eq("total")]
    fit = level_and_slope(total).set_index("season")
    assert fit.loc["pooled", "level_gap"] == pytest.approx(-2.0, abs=0.5)
    assert fit.loc["pooled", "slope"] == pytest.approx(1.0, abs=0.15)


def test_rolling_recentering_uses_only_earlier_seasons():
    total = _predictions()
    total = total[total.target.eq("total")]
    roll = rolling_recentering(total).set_index("season")
    assert roll.loc[2021, "shift"] == 0.0
    earlier = total[total.season.eq(2021)]
    assert roll.loc[2022, "shift"] == pytest.approx(
        (earlier.actual - earlier.prediction).mean()
    )
    # a changed 2023 outcome must not change the 2023 shift
    changed = total.copy()
    changed.loc[changed.season.eq(2023), "actual"] += 50
    assert rolling_recentering(changed).set_index("season").loc[
        2023, "shift"
    ] == pytest.approx(roll.loc[2023, "shift"])
    assert roll.loc[2023, "same_season"]["bias"] == pytest.approx(0.0, abs=1e-9)


def test_recentering_removes_a_constant_offset_exactly():
    total = _predictions()
    total = total[total.target.eq("total")].copy()
    total["actual"] = total["prediction"] - 3.0
    roll = rolling_recentering(total).set_index("season")
    assert roll.loc[2022, "rolling"]["mae"] == pytest.approx(0.0, abs=1e-9)
    assert roll.loc[2022, "base"]["mae"] == pytest.approx(3.0)


def test_error_correlation_detects_shared_error():
    errors = paired_errors(_predictions())
    errors["total_error"] = errors["margin_error"]
    corr = error_correlation(errors)
    assert corr.iloc[-1]["correlation"] == pytest.approx(1.0)


def test_bias_share_and_quantile_bands():
    total = _predictions()
    total = total[total.target.eq("total")]
    assert 0 < bias_share_of_mse(total) < 1
    labels, edges = quantile_bands(total["prediction"], 5)
    assert len(edges) == 4
    assert labels.nunique() == 5
    assert labels.value_counts().min() >= len(total) // 5 - 1
