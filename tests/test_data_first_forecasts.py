"""Focused V5-04A offset, bridge, horizon, and runner boundaries."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

from cks_picks_cfb.data.data_first_forecast_v1 import FORECAST_DATASETS
from cks_picks_cfb.data.schema_contracts import schema_for
from cks_picks_cfb.forecast.heads import evaluate_heads, select_inner_alpha
from cks_picks_cfb.forecast.horizons import (
    HorizonError,
    fitting_seasons,
    select_horizon,
)
from cks_picks_cfb.forecast.offsets import (
    OffsetError,
    build_offsets,
    regulation_non_offense_events,
)

_RUNNER_PATH = (
    Path(__file__).parents[1] / "scripts/research/run_data_first_forecasts.py"
)
_RUNNER_SPEC = importlib.util.spec_from_file_location("forecast_runner", _RUNNER_PATH)
assert _RUNNER_SPEC and _RUNNER_SPEC.loader
runner = importlib.util.module_from_spec(_RUNNER_SPEC)
_RUNNER_SPEC.loader.exec_module(runner)


def _population() -> pd.DataFrame:
    rows = []
    for season in (2015, 2016):
        for game_id, day, home, away in (
            (1, 1, "Alpha", "Beta"),
            (2, 8, "Alpha", "Beta"),
        ):
            rows.append(
                {
                    "season": season,
                    "week": game_id,
                    "game_id": season * 10 + game_id,
                    "kickoff_utc": f"{season}-09-{day:02d}T18:00:00Z",
                    "home_team": home,
                    "away_team": away,
                    "schedule_completed": True,
                    "outcome_valid": True,
                    "forecast_eligible": True,
                    "measurement_usable": True,
                }
            )
    return pd.DataFrame.from_records(rows)


def _events() -> pd.DataFrame:
    return pd.DataFrame.from_records(
        [
            {
                "season": 2015,
                "game_id": 20151,
                "team": "Alpha",
                "period_class": "regulation",
                "scoring_category": "regulation_non_offense",
                "score_increment": 7,
            },
            {
                "season": 2015,
                "game_id": 20152,
                "team": "Beta",
                "period_class": "overtime",
                "scoring_category": "regulation_non_offense",
                "score_increment": 7,
            },
            {
                "season": 2016,
                "game_id": 20161,
                "team": "Beta",
                "period_class": "regulation",
                "scoring_category": "unresolved",
                "score_increment": 3,
            },
        ]
    )


def test_offset_filter_and_pregame_invariance():
    population = _population()
    result = build_offsets(population, _events(), development_seasons=(2015, 2016))
    first = result.offsets[result.offsets.game_id.eq(20151)].iloc[0]
    second = result.offsets[result.offsets.game_id.eq(20152)].iloc[0]
    first_2016 = result.offsets[result.offsets.game_id.eq(20161)].iloc[0]
    assert bool(first.zero_offset_bootstrap) is True
    assert first.offset_margin == 0.0
    assert second.offset_margin > 0.0
    # The 2016 prior is the paired 2015 league mean: 7 points across four team games.
    assert first_2016.league_mean == pytest.approx(1.75)
    assert len(regulation_non_offense_events(_events())) == 1


def test_offset_blocks_missing_prior_paired_coverage():
    population = _population()
    population.loc[population.season.eq(2015), "measurement_usable"] = False
    with pytest.raises(OffsetError, match="missing paired"):
        build_offsets(population, _events(), development_seasons=(2015, 2016))


def test_horizon_membership_excludes_2020_and_coincides_before_five():
    seasons = (2015, 2016, 2017, 2018, 2019, 2021, 2022)
    assert fitting_seasons(2018, seasons, "expanding") == fitting_seasons(
        2018, seasons, "latest_five"
    )
    assert fitting_seasons(2022, seasons, "latest_five") == (
        2016,
        2017,
        2018,
        2019,
        2021,
    )
    assert 2020 not in fitting_seasons(2022, seasons, "expanding")


def _head_frame() -> pd.DataFrame:
    rows = []
    seasons = (2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023)
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


def test_head_registry_is_earlier_only_and_finite():
    frame = _head_frame()
    result = evaluate_heads(
        frame,
        horizon="expanding",
        development_seasons=(2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023),
        outer_seasons=(2022, 2023),
        alpha_grid=(0.1, 1.0, 10.0, 100.0),
        floor=0.05,
        bootstrap_seed=2,
        bootstrap_samples=25,
    )
    assert set(result.retained) == {"margin", "total"}
    assert result.predictions.prediction.notna().all()
    assert all(
        int(season) < 2022
        for season in result.predictions[result.predictions.season.eq(2022)]
        .training_seasons.iloc[0]
        .split(",")
    )
    assert select_inner_alpha(
        frame[frame.season.lt(2022)],
        target="margin",
        seasons=(2015,),
        alpha_grid=(0.1, 1.0),
        floor=0.05,
    ) == (10.0, True)


def test_horizon_requires_identical_population():
    base = pd.DataFrame.from_records(
        [
            {
                "season": 2022,
                "week": 1,
                "game_id": 1,
                "target": "margin",
                "absolute_error": 1.0,
                "gaussian_crps": 1.0,
                "completed_game_stage": 1,
            },
            {
                "season": 2022,
                "week": 1,
                "game_id": 1,
                "target": "total",
                "absolute_error": 1.0,
                "gaussian_crps": 1.0,
                "completed_game_stage": 1,
            },
        ]
    )
    with pytest.raises(HorizonError, match="identical"):
        select_horizon(base, base.iloc[:1], seed=1, samples=5)


def test_forecast_schemas_are_registered_and_apply_is_blocked():
    for dataset, (_name, version) in FORECAST_DATASETS.items():
        assert schema_for(_name, version).schema_version == version
    with pytest.raises(runner.ForecastRunError, match="blocked"):
        runner.main(
            [
                "--run-id",
                "never-selected",
                "--expected-code-sha",
                "0" * 40,
                "--environment",
                "preview",
                "--as-of",
                "2026-09-17T00:00:00Z",
                "--rating-manifest-uri",
                "rating",
                "--measurement-manifest-uri",
                "measurement",
                "--repair-manifest-uri",
                "repair",
                "--apply",
            ]
        )


def test_preflight_partition_plan_is_naturally_ordered():
    frame = pd.DataFrame.from_records(
        [
            {"season": 2025, "week": 10, "value": 1.0},
            {"season": 2025, "week": 2, "value": 2.0},
        ]
    )
    plan = runner._plan("test", frame, ("season", "week", "value"), ("season", "week"))
    assert [part["partition"]["week"] for part in plan["parts"]] == [2, 10]
