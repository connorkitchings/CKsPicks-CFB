"""Focused V5-03A materializer, leakage, and tournament-contract tests."""

from __future__ import annotations

import copy

import pandas as pd
import pytest

from cks_picks_cfb.data.data_first_possession_rating_v1 import candidate_id
from cks_picks_cfb.ratings import possession_rating_materializer as materializer
from cks_picks_cfb.ratings import possession_rating_tournament as tournament
from cks_picks_cfb.ratings.possession_rating_materializer import (
    RatingTournamentInputs,
    _completed_counts,
    _fbs_universe,
    build_boundary_table,
    build_observation_streams,
    build_prior_tables,
    build_terminal_tables,
    compute_tournament,
)
from cks_picks_cfb.ratings.possession_ratings import RatingPrior, replay_states

MEASUREMENTS = ("ppp", "epa_per_possession")
ROLES = ("offense", "defense")


def _noop(*args: object, **kwargs: object) -> None:
    return None


def _population(rows: list[dict]) -> pd.DataFrame:
    columns = [
        "season",
        "week",
        "game_id",
        "kickoff_utc",
        "home_team",
        "away_team",
        "schedule_completed",
        "outcome_valid",
        "forecast_eligible",
        "measurement_usable",
        "population_disposition",
        "measurement_disposition",
        "missing_reason",
        "timing_class",
    ]
    return pd.DataFrame.from_records(rows, columns=columns)


def _game(
    season: int,
    week: int,
    game_id: int,
    kickoff: str,
    home: str,
    away: str,
    *,
    eligible: bool = True,
    completed: bool = True,
    valid: bool = True,
) -> dict:
    return {
        "season": season,
        "week": week,
        "game_id": game_id,
        "kickoff_utc": kickoff,
        "home_team": home,
        "away_team": away,
        "schedule_completed": completed,
        "outcome_valid": valid,
        "forecast_eligible": eligible,
        "measurement_usable": completed and valid,
        "population_disposition": "scoreable" if valid else "invalid",
        "measurement_disposition": "scoreable" if completed and valid else "missing",
        "missing_reason": None,
        "timing_class": "historically_reconstructed",
    }


def _observations(rows: list[dict]) -> pd.DataFrame:
    columns = [
        "season",
        "week",
        "game_id",
        "kickoff_utc",
        "team",
        "opponent",
        "side",
        "measurement_id",
        "unit_role",
        "numerator",
        "denominator",
        "raw_value",
        "usable_exposure",
        "exposure_unit",
        "coverage_status",
        "missing_reason",
        "quality_flags",
        "timing_class",
    ]
    return pd.DataFrame.from_records(rows, columns=columns)


def _observation(
    season: int,
    week: int,
    game_id: int,
    kickoff: str,
    team: str,
    opponent: str,
    measurement: str,
    role: str,
    value: float,
    denominator: float = 10.0,
    coverage: str = "observed",
) -> dict:
    return {
        "season": season,
        "week": week,
        "game_id": game_id,
        "kickoff_utc": kickoff,
        "team": team,
        "opponent": opponent,
        "side": "home",
        "measurement_id": measurement,
        "unit_role": role,
        "numerator": value * denominator,
        "denominator": denominator,
        "raw_value": value,
        "usable_exposure": denominator if coverage == "observed" else 0.0,
        "exposure_unit": "possessions",
        "coverage_status": coverage,
        "missing_reason": None if coverage == "observed" else "quarantined",
        "quality_flags": None,
        "timing_class": "historically_reconstructed",
    }


def _snapshots(rows: list[dict]) -> pd.DataFrame:
    columns = [
        "season",
        "week",
        "as_of_game_id",
        "as_of_kickoff_utc",
        "target_week_cutoff_utc",
        "team",
        "measurement_id",
        "unit_role",
        "adjustment_iteration",
        "raw_value",
        "adjusted_value",
        "primary_exposure",
        "games_exposure",
        "source_game_count",
        "timing_class",
        "availability_policy",
    ]
    return pd.DataFrame.from_records(rows, columns=columns)


def _terminal(rows: list[dict]) -> pd.DataFrame:
    columns = [
        "season",
        "team",
        "measurement_id",
        "unit_role",
        "adjustment_iteration",
        "raw_value",
        "adjusted_value",
        "primary_exposure",
        "games_exposure",
        "source_game_count",
        "timing_class",
    ]
    return pd.DataFrame.from_records(rows, columns=columns)


def _outcomes(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame.from_records(
        rows,
        columns=["season", "game_id", "completed", "home_points", "away_points"],
    )


def _empty_context() -> dict[str, pd.DataFrame]:
    return {}


def _fixture(
    *,
    seasons: tuple[int, ...] = (2017, 2018),
    teams: tuple[str, ...] = ("Alpha", "Beta", "Gamma"),
) -> RatingTournamentInputs:
    """Small two-season fixture: FBS pair (3 games each) plus a two-game FCS team."""
    population_rows: list[dict] = []
    observation_rows: list[dict] = []
    snapshot_rows: list[dict] = []
    terminal_rows: list[dict] = []
    outcome_rows: list[dict] = []
    game_counter = 0
    schedule = {
        1: [("Alpha", "Beta", 18)],
        2: [("Alpha", "Beta", 18)],
        3: [("Alpha", "Gamma", 16), ("Beta", "Gamma", 20)],
    }
    for season in seasons:
        for week in (1, 2, 3):
            for home, away, hour in schedule[week]:
                game_counter += 1
                game_id = game_counter
                kickoff = f"{season}-09-{week:02d}T{hour:02d}:00:00Z"
                population_rows.append(
                    _game(season, week, game_id, kickoff, home, away)
                )
                outcome_rows.append(
                    {
                        "season": season,
                        "game_id": game_id,
                        "completed": True,
                        "home_points": 21 + week * 2 + game_id % 5,
                        "away_points": 14 + week + game_id % 3,
                    }
                )
                for team, opponent in ((home, away), (away, home)):
                    for measurement in MEASUREMENTS:
                        for role in ROLES:
                            value = 2.0 + 0.4 * week + (
                                0.7 if team == teams[0] else -0.5
                            )
                            observation_rows.append(
                                _observation(
                                    season,
                                    week,
                                    game_id,
                                    kickoff,
                                    team,
                                    opponent,
                                    measurement,
                                    role,
                                    value,
                                )
                            )
                            snapshot_rows.append(
                                {
                                    "season": season,
                                    "week": week,
                                    "as_of_game_id": game_id,
                                    "as_of_kickoff_utc": kickoff,
                                    "target_week_cutoff_utc": kickoff,
                                    "team": team,
                                    "measurement_id": measurement,
                                    "unit_role": role,
                                    "adjustment_iteration": 4,
                                    "raw_value": value,
                                    "adjusted_value": value
                                    + (0.2 if team == teams[0] else -0.2),
                                    "primary_exposure": 10.0 * week,
                                    "games_exposure": week,
                                    "source_game_count": week,
                                    "timing_class": "historically_reconstructed",
                                    "availability_policy": (
                                        "prior_week_and_source_kickoff_plus_6h"
                                    ),
                                }
                            )
        for team in teams:
            for measurement in MEASUREMENTS:
                for role in ROLES:
                    terminal_rows.append(
                        {
                            "season": season,
                            "team": team,
                            "measurement_id": measurement,
                            "unit_role": role,
                            "adjustment_iteration": 4,
                            "raw_value": 2.2,
                            "adjusted_value": 2.2
                            + (0.3 if team == teams[0] else -0.3),
                            "primary_exposure": 33.0,
                            "games_exposure": 3,
                            "source_game_count": 3,
                            "timing_class": "historically_reconstructed",
                        }
                    )
    return RatingTournamentInputs(
        population=_population(population_rows),
        observations=_observations(observation_rows),
        snapshots=_snapshots(snapshot_rows),
        terminal=_terminal(terminal_rows),
        outcomes=_outcomes(outcome_rows),
        context=_empty_context(),
        history_audit={"history_parts": 0, "history_rows": 0},
        source_refs={},
        population_sha256="fixture",
    )


def _states_for(
    computation, candidate: str
) -> pd.DataFrame:
    return computation.predictions[
        computation.predictions["candidate_id"].eq(candidate)
    ]


class TestBoundaryTable:
    def test_boundary_requires_later_week_and_six_hour_buffer(self):
        population = _population(
            [
                _game(2017, 1, 1, "2017-09-01T18:00:00Z", "Alpha", "Beta"),
                _game(2017, 1, 2, "2017-09-01T21:00:00Z", "Chi", "Delta"),
                _game(2017, 2, 3, "2017-09-09T14:00:00Z", "Alpha", "Gamma"),
                _game(2017, 3, 4, "2017-09-16T20:00:00Z", "Beta", "Delta"),
            ]
        )
        boundaries = build_boundary_table(population)
        by_game = boundaries.set_index("game_id")
        # Game 1 available at 2017-09-02T00:00Z; game 3 is the first later-week
        # kickoff at or after that moment.  Game 2 is same-week so excluded.
        assert int(by_game.loc[1, "boundary_game_id"]) == 3
        assert int(by_game.loc[2, "boundary_game_id"]) == 3
        assert int(by_game.loc[3, "boundary_game_id"]) == 4
        # Game 4 is the season's last game and has no certified boundary.
        assert 4 not in by_game.index

    def test_boundary_respects_six_hour_availability_buffer(self):
        population = _population(
            [
                # Week 1 game kicking off the same morning as week 2 games.
                _game(2017, 1, 1, "2017-09-09T10:00:00Z", "Alpha", "Beta"),
                _game(2017, 2, 2, "2017-09-09T14:00:00Z", "Alpha", "Beta"),
                _game(2017, 2, 3, "2017-09-09T18:00:00Z", "Chi", "Delta"),
                _game(2017, 3, 4, "2017-09-16T18:00:00Z", "Alpha", "Beta"),
            ]
        )
        boundaries = build_boundary_table(population)
        by_game = boundaries.set_index("game_id")
        # Game 1 is available at 16:00; the 14:00 later-week game is too early,
        # so its boundary is the 18:00 game 3.
        assert int(by_game.loc[1, "boundary_game_id"]) == 3
        assert int(by_game.loc[2, "boundary_game_id"]) == 4
        assert int(by_game.loc[3, "boundary_game_id"]) == 4

    def test_boundary_never_selects_same_week_games(self):
        population = _population(
            [
                _game(2018, 1, 10, "2018-09-01T12:00:00Z", "Alpha", "Beta"),
                _game(2018, 1, 11, "2018-09-02T12:00:00Z", "Chi", "Delta"),
                _game(2018, 2, 12, "2018-09-08T12:00:00Z", "Alpha", "Chi"),
            ]
        )
        boundaries = build_boundary_table(population)
        for row in boundaries.itertuples(index=False):
            source = population.set_index("game_id").loc[int(row.game_id)]
            assert int(row.boundary_game_id) != int(row.game_id)
            boundary = population.set_index("game_id").loc[
                int(row.boundary_game_id)
            ]
            assert int(boundary.week) > int(source.week)


class TestObservationStreams:
    def test_stream_uses_boundary_snapshot_and_season_scales(self):
        inputs = _fixture(seasons=(2017,))
        boundaries = build_boundary_table(inputs.population)
        tables = build_terminal_tables(inputs.terminal)
        streams = build_observation_streams(
            inputs=inputs, boundaries=boundaries, terminal_tables=tables
        )
        stream = streams[("ppp", "offense")]
        # 2017 has no preceding season: fallback center 0.0, scale 1.0.
        assert (stream["season"] == 2017).all()
        alpha = stream[stream["team"].eq("Alpha")]
        # Alpha's week-3 game is the season's last eligible kickoff window and
        # has no certified boundary, so only weeks 1-2 supply observations.
        assert len(alpha) == 2
        assert alpha["usable_exposure"].eq(10.0).all()
        # Defense streams carry the sign reversal relative to adjusted values.
        defense = streams[("ppp", "defense")]
        alpha_defense = defense[defense["team"].eq("Alpha")]
        alpha_offense = stream[stream["team"].eq("Alpha")].sort_values("game_id")
        alpha_defense = alpha_defense.sort_values("game_id")
        assert (
            alpha_defense["adjusted_z"].to_numpy()
            == -alpha_offense["adjusted_z"].to_numpy()
        ).all()

    def test_missing_snapshot_value_drops_observation(self):
        inputs = _fixture(seasons=(2017,))
        inputs = RatingTournamentInputs(
            **(inputs.__dict__ | {"snapshots": inputs.snapshots.iloc[:-4]})
        )
        boundaries = build_boundary_table(inputs.population)
        tables = build_terminal_tables(inputs.terminal)
        streams = build_observation_streams(
            inputs=inputs, boundaries=boundaries, terminal_tables=tables
        )
        stream = streams[("ppp", "offense")]
        assert len(stream) < 6


class TestIncrementalEquivalence:
    def _stream_rows(self, count: int, base: float) -> pd.DataFrame:
        rows = []
        for index in range(count):
            rows.append(
                {
                    "game_id": 100 + index,
                    "kickoff_utc": f"2018-09-{index + 1:02d}T18:00:00Z",
                    "adjusted_z": base + index,
                    "usable_exposure": 8.0 + index,
                }
            )
        return pd.DataFrame(rows)

    @pytest.mark.parametrize(
        ("updater", "half_life"),
        [
            ("exposure", None),
            ("half_life_2", 2.0),
            ("half_life_4", 4.0),
            ("half_life_8", 8.0),
        ],
    )
    def test_analytic_matches_replay_states(self, updater, half_life):
        rows = self._stream_rows(5, 0.5)
        prior = RatingPrior(0.25, 0.6, "terminal", 2017)
        state = materializer._IncrementalState(
            prior=prior,
            updater=updater,
            k=8.0,
            half_life=half_life,
            q=0.0,
            r=1.0,
        )
        for cutoff_index in range(1, len(rows) + 1):
            for row in rows.iloc[:cutoff_index].itertuples(index=False):
                state.assimilate(
                    row.kickoff_utc, float(row.adjusted_z), float(row.usable_exposure)
                )
            cutoff = pd.Timestamp(rows.iloc[cutoff_index - 1]["kickoff_utc"]) + (
                pd.Timedelta(hours=18)
            )
            expected = replay_states(
                prior=prior,
                observations=rows.iloc[:cutoff_index],
                updater=updater,
                definition="ppp",
                cutoff=cutoff,
            )
            mean, variance, weight, _process, exposure, completed = state.state(cutoff)
            assert mean == pytest.approx(expected.mean, abs=1e-12)
            assert variance == pytest.approx(expected.variance, abs=1e-12)
            assert weight == pytest.approx(expected.evidence_weight, abs=1e-12)
            assert exposure == pytest.approx(expected.usable_exposure, abs=1e-12)
            assert completed == expected.completed_games
            # reset for the next cutoff prefix
            state = materializer._IncrementalState(
                prior=prior,
                updater=updater,
                k=8.0,
                half_life=half_life,
                q=0.0,
                r=1.0,
            )

    def test_kalman_incremental_matches_step_chain(self):
        rows = self._stream_rows(4, -0.3)
        prior = RatingPrior(0.1, 0.8, "terminal", 2017)
        state = materializer._IncrementalState(
            prior=prior, updater="kalman", k=8.0, half_life=None, q=0.05, r=2.0
        )
        from cks_picks_cfb.ratings.possession_ratings import RatingState, kalman_step

        chain = RatingState(
            prior.mean, prior.variance, prior.mean, prior.variance, 0.0, 0.0, 0.0, 0
        )
        previous = rows.iloc[0]["kickoff_utc"]
        for row in rows.itertuples(index=False):
            state.assimilate(
                row.kickoff_utc, float(row.adjusted_z), float(row.usable_exposure)
            )
            days = (
                pd.Timestamp(row.kickoff_utc) - pd.Timestamp(previous)
            ).total_seconds() / 86400.0
            chain = kalman_step(
                chain,
                observation=float(row.adjusted_z),
                exposure=float(row.usable_exposure),
                elapsed_days=days if days > 0 else 0.0,
                q=0.05,
                r=2.0,
            )
            previous = row.kickoff_utc
        cutoff = pd.Timestamp(rows.iloc[-1]["kickoff_utc"]) + pd.Timedelta(days=2)
        mean, variance, *_ = state.state(cutoff)
        advanced = kalman_step(
            chain, observation=None, exposure=0.0, elapsed_days=2.0, q=0.05, r=2.0
        )
        assert mean == pytest.approx(advanced.mean, abs=1e-12)
        assert variance == pytest.approx(advanced.variance, abs=1e-12)


def _lower_fbs_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(materializer, "FBS_MINIMUM_SCHEDULED_GAMES", 3)


class TestUniverseAndStages:
    def test_fbs_universe_threshold(self, monkeypatch):
        _lower_fbs_threshold(monkeypatch)
        inputs = _fixture()
        fbs = _fbs_universe(inputs.population)
        assert (2017, "Alpha") in fbs
        assert (2017, "Beta") in fbs
        assert (2017, "Gamma") not in fbs

    def test_completed_counts_exclude_future_and_invalid(self):
        population = _population(
            [
                _game(2018, 1, 1, "2018-09-01T18:00:00Z", "Alpha", "Beta"),
                _game(2018, 1, 2, "2018-09-01T21:00:00Z", "Chi", "Delta", valid=False),
                _game(2018, 2, 3, "2018-09-08T18:00:00Z", "Alpha", "Chi"),
            ]
        )
        counts = _completed_counts(population)
        assert counts[(2018, 1)] == {}
        assert counts[(2018, 3)]["Alpha"] == 1
        assert counts[(2018, 3)].get("Chi", 0) == 0  # invalid outcome excluded


class TestPriors:
    def test_no_predecessor_uses_neutral_and_2019_gap_decays(self):
        terminal_rows = []
        for season in (2019, 2021):
            for team in ("Alpha", "Beta"):
                for measurement in MEASUREMENTS:
                    for role in ROLES:
                        terminal_rows.append(
                            {
                                "season": season,
                                "team": team,
                                "measurement_id": measurement,
                                "unit_role": role,
                                "adjustment_iteration": 4,
                                "raw_value": 2.0,
                                "adjusted_value": 2.0,
                                "primary_exposure": 120.0,
                                "games_exposure": 12,
                                "source_game_count": 12,
                                "timing_class": "historically_reconstructed",
                            }
                        )
        tables = build_terminal_tables(_terminal(terminal_rows))
        priors = build_prior_tables(context={}, terminal_tables=tables)
        rho = priors[("ppp", "rho_0_60")]
        first = rho[
            rho["season"].eq(2019) & rho["team"].eq("Alpha") & rho["unit_role"].eq("offense")
        ].iloc[0]
        assert first["prior_source"] == "neutral"
        gap = rho[
            rho["season"].eq(2021) & rho["team"].eq("Alpha") & rho["unit_role"].eq("offense")
        ].iloc[0]
        assert gap["annual_decay_steps"] == 2
        assert gap["prior_variance"] == pytest.approx(
            0.60**4 * (1.0 / (1.0 + 120.0 / 8.0)) + 1 - 0.60**4
        )

    def test_future_context_rows_cannot_change_earlier_priors(self):
        terminal_rows = []
        for season in (2017, 2018):
            for team in ("Alpha", "Beta"):
                for measurement in MEASUREMENTS:
                    for role in ROLES:
                        terminal_rows.append(
                            {
                                "season": season,
                                "team": team,
                                "measurement_id": measurement,
                                "unit_role": role,
                                "adjustment_iteration": 4,
                                "raw_value": 2.0,
                                "adjusted_value": 2.0 + 0.1 * season,
                                "primary_exposure": 60.0,
                                "games_exposure": 6,
                                "source_game_count": 6,
                                "timing_class": "historically_reconstructed",
                            }
                        )
        tables = build_terminal_tables(_terminal(terminal_rows))
        context = {
            "recruiting_ridge": pd.DataFrame(
                {
                    "season": [2018, 2018],
                    "team": ["Alpha", "Beta"],
                    "recruiting_current": [10.0, 8.0],
                    "recruiting_4yr": [9.0, 9.0],
                    "recruiting_trend": [1.0, -1.0],
                }
            )
        }
        baseline = build_prior_tables(context={}, terminal_tables=tables)
        perturbed = build_prior_tables(context=context, terminal_tables=tables)
        for family in ("recruiting_ridge", "all_context_ridge"):
            early_baseline = baseline[("ppp", family)].query("season == 2017")
            early_perturbed = perturbed[("ppp", family)].query("season == 2017")
            pd.testing.assert_frame_equal(
                early_baseline.reset_index(drop=True),
                early_perturbed.reset_index(drop=True),
            )


class TestTournamentSelection:
    @staticmethod
    def _all_sixty_rows(
        *,
        reference_error: float = 10.0,
        challenger_error: float | None = None,
        challenger: str | None = None,
        seasons: tuple[int, ...] = (2024,),
        season_override: tuple[int, float] | None = None,
        omit_reference: bool = False,
        restrict_stages: bool = False,
    ) -> pd.DataFrame:
        reference = candidate_id("ppp", "rho_0_60", "exposure")
        rows = []
        from cks_picks_cfb.data.data_first_possession_rating_v1 import (
            candidate_registry,
        )

        for item in candidate_registry():
            current = item["candidate_id"]
            if current == reference and omit_reference:
                continue
            stages = (
                [4]
                if restrict_stages and current != reference
                else range(5)
            )
            for season in seasons:
                for target in ("margin", "total"):
                    for stage in stages:
                        error = reference_error
                        if current == challenger:
                            error = challenger_error or reference_error
                            if season_override and season == season_override[0]:
                                error = season_override[1]
                        rows.append(
                            {
                                "candidate_id": current,
                                "definition": item["definition"],
                                "season": season,
                                "week": stage + 1,
                                "game_id": stage + 1,
                                "target": target,
                                "absolute_error": float(error),
                                "completed_game_stage": stage,
                            }
                        )
        return pd.DataFrame(rows)

    def test_invalid_reference_blocks_definition(self, monkeypatch):
        monkeypatch.setattr(
            tournament,
            "_bootstrap",
            lambda *args, **kwargs: (0.0, 0.0, 0.0),
        )
        reference = candidate_id("ppp", "rho_0_60", "exposure")
        rows = self._all_sixty_rows()
        with pytest.raises(
            tournament.PossessionTournamentError, match="blocks definition"
        ):
            tournament.select_candidates(
                rows, validity={reference: "kalman_noise_fit_failed"}
            )

    def test_validity_failure_reports_sentinel_and_never_selects(self, monkeypatch):
        monkeypatch.setattr(
            tournament,
            "_bootstrap",
            lambda *args, **kwargs: (0.0, 0.0, 0.0),
        )
        failed = candidate_id("ppp", "recruiting_ridge", "kalman")
        rows = self._all_sixty_rows()
        result = tournament.select_candidates(
            rows, validity={failed: "kalman_noise_fit_failed"}
        )
        failure = result[result["candidate_id"].eq(failed)].iloc[0]
        assert not failure["valid"]
        assert failure["selection_reason"] == (
            "validity_failure: kalman_noise_fit_failed"
        )
        assert failure["pooled_mae"] == -1.0
        assert not failure["selected"]

    def test_season_regression_blocks_otherwise_passing_challenger(self, monkeypatch):
        monkeypatch.setattr(
            tournament,
            "_bootstrap",
            lambda *args, **kwargs: (1.0, 1.0, 1.0),
        )
        challenger = candidate_id("ppp", "neutral", "half_life_8")
        rows = self._all_sixty_rows(
            challenger=challenger,
            challenger_error=9.0,
            seasons=(2023, 2024),
            season_override=(2023, 10.6),
        )
        result = tournament.select_candidates(rows)
        challenger_row = result[result["candidate_id"].eq(challenger)].iloc[0]
        assert not challenger_row["valid"]
        assert not challenger_row["regression_gate"]

    def test_population_difference_between_candidate_and_reference_raises(
        self, monkeypatch
    ):
        monkeypatch.setattr(
            tournament,
            "_bootstrap",
            lambda *args, **kwargs: (0.0, 0.0, 0.0),
        )
        rows = self._all_sixty_rows()
        challenger = candidate_id("ppp", "neutral", "exposure")
        rows = rows[
            ~(rows["candidate_id"].eq(challenger) & rows["game_id"].eq(1))
        ]
        with pytest.raises(
            tournament.PossessionTournamentError, match="population differs"
        ):
            tournament.select_candidates(rows)


class TestFullTournament:
    def test_deterministic_selection_and_plan_digests(self, monkeypatch):
        _lower_fbs_threshold(monkeypatch)
        inputs = _fixture()
        first = compute_tournament(inputs=inputs, progress=_noop, retain_frames=True)
        second = compute_tournament(
            inputs=copy.deepcopy(inputs), progress=_noop, retain_frames=True
        )
        assert first.selected_candidate == second.selected_candidate
        assert first.candidate_status == second.candidate_status
        for name, plan in first.plans.items():
            assert plan.records_sha == second.plans[name].records_sha
            assert plan.row_count == second.plans[name].row_count
            assert [part["partition"] for part in plan.parts] == [
                part["partition"] for part in second.plans[name].parts
            ]
        evidence = first.preflight_evidence()
        for field in (
            "candidate_status",
            "selected_candidate",
            "selection_sha256",
            "preflight_plans",
            "row_counts",
            "output_records_sha256",
        ):
            assert field in evidence

    def test_all_sixty_candidates_reported_with_equal_bridge_population(self, monkeypatch):
        _lower_fbs_threshold(monkeypatch)
        inputs = _fixture()
        computation = compute_tournament(inputs=inputs, progress=_noop)
        assert len(computation.attribution) == 60
        assert set(computation.candidate_status.values()) <= {"ok"}
        counts = computation.predictions.groupby("candidate_id").size()
        assert counts.nunique() == 1
        reference = _states_for(
            computation, candidate_id("ppp", "rho_0_60", "exposure")
        )
        assert len(reference) > 0
        assert computation.diagnostics["venue_fallback"]["reason"] == (
            "venue_facts_unavailable_in_certified_parents"
        )
        assert computation.diagnostics["fbs_team_seasons"] >= 4

    def test_same_game_and_future_perturbations_leave_earlier_states_unchanged(self, monkeypatch):
        _lower_fbs_threshold(monkeypatch)
        inputs = _fixture()
        baseline = compute_tournament(inputs=inputs, progress=_noop, retain_frames=True)
        base_states = baseline.frames["rating_states"][
            baseline.frames["rating_states"]["season"].eq(2017)
        ].reset_index(drop=True)
        perturbed = copy.deepcopy(inputs)
        # Perturb every 2018 snapshot value (same-season and future evidence).
        mask = perturbed.snapshots["season"].eq(2018)
        perturbed.snapshots.loc[mask, "adjusted_value"] = (
            perturbed.snapshots.loc[mask, "adjusted_value"] + 5.0
        )
        # Perturb 2018 terminal and outcomes.
        mask = perturbed.terminal["season"].eq(2018)
        perturbed.terminal.loc[mask, "adjusted_value"] = (
            perturbed.terminal.loc[mask, "adjusted_value"] + 3.0
        )
        perturbed.outcomes.loc[
            perturbed.outcomes["season"].eq(2018), "home_points"
        ] += 10
        after = compute_tournament(inputs=perturbed, progress=_noop, retain_frames=True)
        later_states = after.frames["rating_states"][
            after.frames["rating_states"]["season"].eq(2017)
        ].reset_index(drop=True)
        pd.testing.assert_frame_equal(base_states, later_states)

    def test_fcs_team_without_predecessor_uses_partial_pool(self, monkeypatch):
        _lower_fbs_threshold(monkeypatch)
        inputs = _fixture()
        computation = compute_tournament(inputs=inputs, progress=_noop, retain_frames=True)
        states = computation.frames["rating_states"]
        candidate = candidate_id("ppp", "rho_0_60", "exposure")
        fcs_rows = states[
            states["candidate_id"].eq(candidate)
            & states["team"].eq("Gamma")
            & states["season"].eq(2017)
        ]
        assert len(fcs_rows) > 0
        pooled = fcs_rows[
            fcs_rows["fallback_reason"].isin(
                ("preceding_fcs_partial_pool", "neutral_no_preceding_fcs_cohort")
            )
        ]
        assert len(pooled) > 0, "expected FCS fallback rows in the first season"

    def test_fbs_team_without_predecessor_keeps_neutral_prior(self, monkeypatch):
        _lower_fbs_threshold(monkeypatch)
        inputs = _fixture()
        computation = compute_tournament(inputs=inputs, progress=_noop, retain_frames=True)
        states = computation.frames["rating_states"]
        candidate = candidate_id("ppp", "rho_0_60", "exposure")
        rows = states[
            states["candidate_id"].eq(candidate)
            & states["team"].eq("Alpha")
            & states["season"].eq(2017)
        ]
        assert len(rows) > 0
        assert not rows["fallback_reason"].eq("preceding_fcs_partial_pool").any()

    def test_partition_plans_are_strictly_ordered_and_schema_valid(self, monkeypatch):
        _lower_fbs_threshold(monkeypatch)
        inputs = _fixture()
        computation = compute_tournament(inputs=inputs, progress=_noop)
        for name, plan in computation.plans.items():
            keys = [
                tuple(part["partition"][key] for key in plan.partition_keys)
                for part in plan.parts
            ]
            assert keys == sorted(keys)
            if plan.partition_keys:
                assert sum(part["row_count"] for part in plan.parts) == plan.row_count
            else:
                assert not plan.parts
                assert plan.row_count > 0
