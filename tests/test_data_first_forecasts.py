"""Focused V5-04A offset, bridge, horizon, and runner boundaries."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

from cks_picks_cfb.data import data_first_forecast_v1 as forecast_contracts
from cks_picks_cfb.data.data_first_forecast_v1 import (
    FORECAST_DATASETS,
    REQUIRED_RATING_MANIFEST_URI,
    validate_config,
    verify_rating_parent,
)
from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.data.data_first_possession_rating_v1 import RATING_DATASETS
from cks_picks_cfb.data.schema_contracts import schema_for
from cks_picks_cfb.forecast.heads import HeadError, evaluate_heads, select_inner_alpha
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

_MEASUREMENT_URI = (
    "artifacts/research/data-first-football-v1/possession-v1/measurements/runs/"
    "possession-v1-measurements-20260915-18fb0aa-r6/measurement-manifest.json"
)
_REPAIR_URI = (
    "artifacts/research/data-first-football-v1/repair/v2/runs/"
    "repair-v2-20260909T1417Z/repair-manifest.json"
)
_PARENT_URIS = {
    "rating_manifest_uri": REQUIRED_RATING_MANIFEST_URI,
    "measurement_manifest_uri": _MEASUREMENT_URI,
    "repair_manifest_uri": _REPAIR_URI,
}


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


def _rating_manifest() -> dict:
    return signed_payload(
        {
            "schema_version": "data_first_possession_retained_rating_v1",
            "state": "frozen",
            "identity": {
                "environment": "preview",
                "run_id": "possession-v1-ratings-20260917-d029526-cert",
            },
            "selected_candidate": "ppp__rho_0_60__exposure",
            "production_activation_authorized": False,
            "parents": {
                "measurement_manifest_uri": _MEASUREMENT_URI,
                "measurement_manifest_raw_sha256": "m" * 64,
                "repair_manifest_uri": _REPAIR_URI,
                "repair_manifest_raw_sha256": "r" * 64,
            },
            "output_refs": {name: {} for name in RATING_DATASETS},
        }
    )


def _verify_parent(
    *,
    rating_manifest_uri: str,
    measurement_manifest_uri: str,
    repair_manifest_uri: str,
):
    return verify_rating_parent(
        _rating_manifest(),
        rating_manifest_uri=rating_manifest_uri,
        rating_raw_sha256="a" * 64,
        measurement={"identity": {"run_id": "measurement-parent"}},
        measurement_manifest_uri=measurement_manifest_uri,
        measurement_raw_sha256="m" * 64,
        repair={"identity": {"run_id": "repair-parent"}},
        repair_manifest_uri=repair_manifest_uri,
        repair_raw_sha256="r" * 64,
    )


def test_rating_parent_uri_substitution_is_rejected(monkeypatch):
    # A byte-identical measurement manifest (hash matches) served from a
    # different URI must still be rejected: identity binds to the pinned URI.
    with pytest.raises(
        forecast_contracts.ForecastContractError, match="rating manifest URI"
    ):
        _verify_parent(
            rating_manifest_uri=(
                "artifacts/research/data-first-football-v1/possession-v1/ratings/"
                "runs/other-run/retained-rating-manifest.json"
            ),
            measurement_manifest_uri=_MEASUREMENT_URI,
            repair_manifest_uri=_REPAIR_URI,
        )
    with pytest.raises(
        forecast_contracts.ForecastContractError, match="measurement manifest URI"
    ):
        _verify_parent(
            rating_manifest_uri=REQUIRED_RATING_MANIFEST_URI,
            measurement_manifest_uri=_MEASUREMENT_URI + "/substituted",
            repair_manifest_uri=_REPAIR_URI,
        )
    with pytest.raises(
        forecast_contracts.ForecastContractError, match="repair manifest URI"
    ):
        _verify_parent(
            rating_manifest_uri=REQUIRED_RATING_MANIFEST_URI,
            measurement_manifest_uri=_MEASUREMENT_URI,
            repair_manifest_uri="wrong/" + _REPAIR_URI,
        )
    monkeypatch.setattr(
        forecast_contracts,
        "verify_parents",
        lambda measurement, repair: (dict(measurement), dict(repair)),
    )
    parents = _verify_parent(
        rating_manifest_uri=REQUIRED_RATING_MANIFEST_URI,
        measurement_manifest_uri=_MEASUREMENT_URI,
        repair_manifest_uri=_REPAIR_URI,
    )
    assert parents["measurement_manifest_uri"] == _MEASUREMENT_URI
    assert parents["repair_manifest_uri"] == _REPAIR_URI


def test_forecast_identity_requires_pinned_parent_uris():
    kwargs = {
        "run_id": "forecast-v1-test",
        "as_of": "2026-09-17T00:00:00Z",
        "code_sha": "a" * 40,
        "config_sha": "b" * 64,
    }
    parents = _PARENT_URIS | {
        "rating_raw_sha256": "c" * 64,
        "measurement_raw_sha256": "d" * 64,
        "repair_raw_sha256": "e" * 64,
    }
    identity = forecast_contracts.forecast_identity(parents=parents, **kwargs)
    assert identity["parents"]["rating_manifest_uri"] == REQUIRED_RATING_MANIFEST_URI
    incomplete = {
        key: value for key, value in parents.items() if key != "repair_manifest_uri"
    }
    with pytest.raises(forecast_contracts.ForecastContractError, match="exact URIs"):
        forecast_contracts.forecast_identity(parents=incomplete, **kwargs)


def test_config_reporting_season_policy_is_enforced():
    base = {
        "schema_version": "data_first_forecast_config_v1",
        "development_seasons": [
            2015,
            2016,
            2017,
            2018,
            2019,
            2021,
            2022,
            2023,
            2024,
            2025,
        ],
        "forbidden_seasons": [2020],
        "rating_candidate": "ppp__rho_0_60__exposure",
        "horizons": ["expanding", "latest_five"],
        "bridge": {"reference_alpha": 10.0, "alpha_grid": [0.1, 1.0, 10.0, 100.0]},
        "selection": {
            "outer_seasons": [2022, 2023, 2024, 2025],
            "reporting_seasons": [2018, 2019, 2021],
        },
        "production_activation_authorized": False,
    }
    validate_config(base)
    drifted = json.loads(json.dumps(base))
    drifted["selection"]["reporting_seasons"] = [2018, 2019]
    with pytest.raises(
        forecast_contracts.ForecastContractError, match="reporting season"
    ):
        validate_config(drifted)
    overlapped = json.loads(json.dumps(base))
    overlapped["selection"]["outer_seasons"] = [2018, 2022, 2023, 2024, 2025]
    with pytest.raises(forecast_contracts.ForecastContractError, match="overlap"):
        validate_config(overlapped)


_HEAD_KWARGS = {
    "development_seasons": (2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023),
    "outer_seasons": (2022, 2023),
    "alpha_grid": (0.1, 1.0, 10.0, 100.0),
    "floor": 0.05,
    "bootstrap_seed": 2,
    "bootstrap_samples": 25,
}
_REPORTING = (2018, 2019, 2021)


def test_reporting_seasons_are_reported_without_touching_selection():
    frame = _head_frame()
    plain = evaluate_heads(frame, horizon="expanding", **_HEAD_KWARGS)
    with_reporting = evaluate_heads(
        frame, horizon="expanding", reporting_seasons=_REPORTING, **_HEAD_KWARGS
    )
    pd.testing.assert_frame_equal(plain.predictions, with_reporting.predictions)
    pd.testing.assert_frame_equal(plain.models, with_reporting.models)
    assert plain.retained == with_reporting.retained
    reporting = with_reporting.reporting_predictions
    assert set(reporting["season"]) == set(_REPORTING)
    assert set(reporting["head"]) == {"reference", "challenger"}
    assert set(reporting["target"]) == {"margin", "total"}
    assert not set(plain.predictions["season"]) & set(_REPORTING)
    # Reporting seasons are legitimate training history for later fits, so
    # perturbing their outcomes may move fitted values and gate outcomes; what
    # must hold is that the selection population identity is unchanged and the
    # reporting rows themselves are genuinely evaluated (they respond to the
    # perturbation) while never entering selection predictions or plans.
    perturbed = frame.copy()
    mask = perturbed["season"].isin(_REPORTING)
    perturbed.loc[mask, "actual_margin"] = perturbed.loc[mask, "actual_margin"] + 25.0
    perturbed_result = evaluate_heads(
        perturbed, horizon="expanding", reporting_seasons=_REPORTING, **_HEAD_KWARGS
    )
    pd.testing.assert_frame_equal(
        plain.predictions[["season", "week", "game_id", "target", "head"]],
        perturbed_result.predictions[["season", "week", "game_id", "target", "head"]],
    )
    assert not perturbed_result.reporting_predictions.empty
    assert not with_reporting.reporting_predictions[["prediction"]].equals(
        perturbed_result.reporting_predictions[["prediction"]]
    )


def test_reporting_seasons_may_not_overlap_selection():
    with pytest.raises(HeadError, match="overlap"):
        evaluate_heads(
            _head_frame(),
            horizon="expanding",
            reporting_seasons=(2021, 2022),
            **_HEAD_KWARGS,
        )


def test_missing_reporting_population_fails_instead_of_silent_skip():
    truncated = _head_frame()
    truncated = truncated[~truncated["season"].eq(2019)]
    with pytest.raises(HeadError, match="lacks scoreable"):
        evaluate_heads(
            truncated,
            horizon="expanding",
            reporting_seasons=_REPORTING,
            **_HEAD_KWARGS,
        )
    # Without a reporting obligation the same truncated frame succeeds, so the
    # failure above is the reporting gate, not a broken selection population.
    result = evaluate_heads(truncated, horizon="expanding", **_HEAD_KWARGS)
    assert set(result.predictions["season"]) == {2022, 2023}


def _feature_inputs(extra_games: tuple[tuple[int, int, str, str], ...] = ()):
    games = [
        (101, 1, "Alpha", "Gamma"),
        (102, 1, "Beta", "Theta"),
        (103, 2, "Alpha", "Delta"),
        (104, 2, "Beta", "Eta"),
        (105, 3, "Alpha", "Epsilon"),
        (106, 3, "Beta", "Zeta"),
        (107, 4, "Alpha", "Zeta"),
        (108, 4, "Beta", "Epsilon"),
        (109, 5, "Alpha", "Eta"),
        (110, 5, "Beta", "Delta"),
        (111, 6, "Alpha", "Theta"),
        (112, 8, "Alpha", "Beta"),
        *extra_games,
    ]
    population = pd.DataFrame.from_records(
        [
            {
                "season": 2022,
                "week": week,
                "game_id": game_id,
                "kickoff_utc": f"2022-09-{week:02d}T18:00:00Z",
                "home_team": home,
                "away_team": away,
                "forecast_eligible": True,
            }
            for game_id, week, home, away in games
        ]
    )
    outcomes = pd.DataFrame.from_records(
        [
            {
                "season": 2022,
                "game_id": game_id,
                "completed": True,
                "home_points": 28,
                "away_points": 21,
            }
            for game_id, _week, _home, _away in games
        ]
    )
    team_rows = []
    for game_id, _week, home, away in games:
        for team in (home, away):
            team_rows.append(
                {
                    "candidate_id": "ppp__rho_0_60__exposure",
                    "season": 2022,
                    "game_id": game_id,
                    "team": team,
                    "offense_rating": 1.0,
                    "defense_rating": -1.0,
                }
            )
    team_states = pd.DataFrame.from_records(team_rows)
    offsets = pd.DataFrame.from_records(
        [
            {
                "season": 2022,
                "week": week,
                "game_id": game_id,
                "offset_margin": 0.5,
                "offset_total": 1.0,
            }
            for game_id, week, _home, _away in games
        ]
    )
    return population, outcomes, team_states, offsets


def test_feature_frame_sources_regime_stage_from_schedule():
    population, outcomes, team_states, offsets = _feature_inputs()
    frame = runner._feature_frame(
        population=population,
        outcomes=outcomes,
        team_states=team_states,
        offsets=offsets,
    )
    by_game = frame.set_index("game_id")
    # Pregame counts come from kickoff-ordered earlier eligible games only:
    # week-1 opener has none; Zeta's second game bounds game 107; the week-8
    # meeting has min(6, 5) completed before it and clips to regime 4.  The
    # rating-state observation counter (mostly zeros) is never the source.
    assert int(by_game.loc[101, "completed_game_stage"]) == 0
    assert int(by_game.loc[107, "completed_game_stage"]) == 1
    assert int(by_game.loc[112, "completed_game_stage"]) == 4


def test_pregame_counts_are_invariant_to_later_games():
    population, outcomes, team_states, offsets = _feature_inputs()
    base = runner._feature_frame(
        population=population,
        outcomes=outcomes,
        team_states=team_states,
        offsets=offsets,
    )
    later = _feature_inputs(extra_games=((113, 9, "Alpha", "Gamma"),))
    extended = runner._feature_frame(
        population=later[0],
        outcomes=later[1],
        team_states=later[2],
        offsets=later[3],
    )
    earlier = extended[extended["game_id"].ne(113)].reset_index(drop=True)
    pd.testing.assert_frame_equal(base.reset_index(drop=True), earlier)
    new_row = extended[extended["game_id"].eq(113)]
    assert len(new_row) == 1
    assert int(new_row.iloc[0]["completed_game_stage"]) == min(7, 1)


def test_head_metrics_block_is_deterministic_and_complete():
    frame = _head_frame()
    first_computation = evaluate_heads(
        frame, horizon="expanding", reporting_seasons=_REPORTING, **_HEAD_KWARGS
    )
    second_computation = evaluate_heads(
        frame, horizon="expanding", reporting_seasons=_REPORTING, **_HEAD_KWARGS
    )
    first = runner._head_metrics_block({"expanding": first_computation})
    second = runner._head_metrics_block({"expanding": second_computation})
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    populations = runner._horizon_populations({"expanding": first_computation})
    assert populations["expanding"]["margin"] > 0
    assert populations["expanding"]["total"] > 0
    for target in ("margin", "total"):
        block = first["expanding"][target]
        assert set(block["selection"]["by_season"]) == {"2022", "2023"}
        assert set(block["reporting"]["by_season"]) == {"2018", "2019", "2021"}
        assert block["selection"]["pooled"]["n"] == sum(
            value["n"] for value in block["selection"]["by_season"].values()
        )
        assert block["selection"]["by_completed_game_stage"]
