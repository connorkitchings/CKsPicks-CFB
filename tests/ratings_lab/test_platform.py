"""Research boundary, chronology, and comparison invariants."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from cks_picks_cfb.ratings_lab.artifacts import (
    LocalLabStore,
    ReadOnlySource,
    ResearchArtifact,
    ResearchStorage,
    open_research_storage,
)
from cks_picks_cfb.ratings_lab.contracts import Game, Observation, Rating
from cks_picks_cfb.ratings_lab.evaluation import (
    common_bridge_predictions,
    paired_comparison,
    validate_prediction_population,
)
from cks_picks_cfb.ratings_lab.measurements import (
    MeasurementRecipe,
    build_cumulative,
    build_individual,
    register_availability_policy,
    register_recipe,
)
from cks_picks_cfb.ratings_lab.replay import CarryoverOnly, replay
from cks_picks_cfb.ratings_lab.updaters import (
    ParameterizedDesign,
    load_candidate_configs,
)


def _storage(tmp_path):
    return ResearchStorage(
        ReadOnlySource(LocalLabStore(tmp_path / "source")),
        LocalLabStore(tmp_path / "output"),
    )


def test_storage_isolation_immutability_and_corruption(tmp_path):
    storage = _storage(tmp_path)
    with pytest.raises(ValueError, match="differ"):
        ResearchStorage(ReadOnlySource(storage.output), storage.output)
    first = storage.write(key="ratings-lab/v1/example.json", data=b"abc")
    assert storage.write(key=first.key, data=b"abc") == first
    with pytest.raises(ValueError, match="conflict"):
        storage.write(key=first.key, data=b"changed")
    with pytest.raises(ValueError, match="remain"):
        storage.write(key="artifacts/production/example.json", data=b"abc")
    with pytest.raises(ValueError, match="checksum"):
        storage.read_output(
            ResearchArtifact(first.storage_identity, first.key, "0" * 64, 3)
        )
    stage = storage.publish_stage(
        stage="corpus", identity="fixed", children=[first], metadata={"rows": 1}
    )
    assert storage.stage_at(stage.key)[0] == stage
    (tmp_path / "output" / first.key).write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="checksum"):
        storage.stage_at(stage.key)


def test_cloud_configuration_never_falls_back_to_preview(monkeypatch):
    for prefix in ("CFB_R2_LAB_SOURCE", "CFB_R2_LAB"):
        for suffix in ("BUCKET", "ACCOUNT_ID", "ACCESS_KEY", "SECRET_KEY"):
            monkeypatch.delenv(f"{prefix}_{suffix}", raising=False)
    with pytest.raises(ValueError, match="missing research storage configuration"):
        open_research_storage()


def _game(season, week, game_id, day, home="A", away="B"):
    time = datetime(season, 9, day, 19, tzinfo=timezone.utc)
    return Game(season, week, game_id, time.isoformat(), home, away)


def _obs(
    game,
    team="A",
    role="offense",
    value=2.0,
    *,
    hours=6,
    kind="individual",
    contributors=(),
):
    available = datetime.fromisoformat(game.kickoff_utc) + timedelta(hours=hours)
    return Observation(
        game.season,
        game.week,
        game.game_id,
        team,
        role,
        "ppp",
        value,
        10.0,
        available.isoformat(),
        "historically_reconstructed",
        kind,
        contributors,
    )


def test_replay_cutoffs_gap_and_external_carryover():
    games = [_game(2019, 1, 1, 1), _game(2019, 2, 2, 8), _game(2021, 1, 3, 1)]
    observations = [_obs(games[0]), _obs(games[1])]
    seeds = {(2019, "A", "offense"): Rating(2.0, 1.0)}
    states = replay(
        games,
        observations,
        design=CarryoverOnly(),
        measurement_id="ppp",
        external_terminals=seeds,
    )
    second = next(
        state
        for state in states
        if state.game_id == 2 and state.team == "A" and state.role == "offense"
    )
    assert second.evidence_game_ids == (1,)
    assert second.rating.mean == 0.0  # carryover has no in-season mean update
    after_gap = next(
        state
        for state in states
        if state.game_id == 3 and state.team == "A" and state.role == "offense"
    )
    assert after_gap.rating.mean == pytest.approx(2.0 * 0.60**2)
    assert after_gap.evidence_game_ids == ()
    with pytest.raises(ValueError, match="buffer"):
        replay(
            games,
            [_obs(games[0], hours=0)],
            design=CarryoverOnly(),
            measurement_id="ppp",
        )
    with pytest.raises(ValueError, match="chronology"):
        _game(2020, 1, 1, 1)


def test_cumulative_contributors_are_replaced_not_added():
    games = [_game(2021, 1, 1, 1), _game(2021, 2, 2, 8), _game(2021, 3, 3, 15)]
    individual = [_obs(games[0], value=2.0), _obs(games[1], value=4.0)]
    snapshots = build_cumulative(games, individual)
    assert snapshots[-1].contributors == (1, 2)
    assert snapshots[-1].value == pytest.approx(3.0)

    class Capture:
        candidate_id = "capture_cumulative_v1"
        mode = "cumulative"

        def initialize(self, previous, *, gap):
            return Rating(0.0, 1.0)

        def estimate(self, prior, evidence):
            return Rating(evidence[-1].value if evidence else prior.mean, 1.0), {
                "consumed": len(evidence)
            }

    states = replay(
        games, individual + snapshots, design=Capture(), measurement_id="ppp"
    )
    last = next(
        state
        for state in states
        if state.game_id == 3 and state.team == "A" and state.role == "offense"
    )
    assert last.rating.mean == pytest.approx(3.0)
    assert last.usable_exposure == 20.0
    assert last.evidence_game_ids == (1, 2)
    assert last.explanation["consumed"] == 1
    wrong = Observation(
        2021,
        2,
        2,
        "A",
        "offense",
        "ppp",
        3.0,
        20.0,
        snapshots[-1].available_utc,
        "historically_reconstructed",
        "cumulative",
        (1, 999),
    )
    with pytest.raises(ValueError, match="inadmissible"):
        replay(games, individual + [wrong], design=Capture(), measurement_id="ppp")


def test_incremental_updates_only_prior_week_and_keeps_provenance():
    games = [
        _game(2022, 1, 1, 1),
        _game(2022, 2, 2, 8),
        _game(2022, 2, 3, 8),
        _game(2022, 3, 4, 15),
    ]
    observations = [
        _obs(games[0], value=2.0),
        _obs(games[1], value=4.0),
        _obs(games[2], value=6.0),
    ]

    class SumEvents:
        candidate_id = "sum_events_v1"
        mode = "incremental"

        def initialize(self, previous, *, gap):
            return Rating(0.0, 1.0)

        def estimate(self, prior, evidence):
            return Rating(prior.mean + sum(row.value for row in evidence), 1.0), {
                "consumed": len(evidence)
            }

    states = replay(games, observations, design=SumEvents(), measurement_id="ppp")
    by_game = {
        state.game_id: state
        for state in states
        if state.team == "A" and state.role == "offense"
    }
    assert by_game[1].rating.mean == 0.0
    assert by_game[2].rating.mean == 2.0
    assert by_game[3].rating.mean == 2.0  # equal kickoff and same week do not enter
    assert by_game[4].rating.mean == 12.0
    assert by_game[4].evidence_game_ids == (1, 2, 3)


def test_delayed_and_postponed_evidence_stays_out_of_pregame_state():
    first = _game(2022, 1, 11, 1, away="FCS-X")
    next_game = _game(2022, 2, 12, 8)
    later = _game(2022, 3, 13, 15)
    delayed = _obs(first, hours=24 * 10)

    class Count:
        candidate_id = "count_events_v1"
        mode = "incremental"

        def initialize(self, previous, *, gap):
            return Rating(0.0, 1.0)

        def estimate(self, prior, evidence):
            return Rating(float(len(evidence)), 1.0), {"count": len(evidence)}

    states = replay(
        [first, next_game, later], [delayed], design=Count(), measurement_id="ppp"
    )
    selected = {
        state.game_id: state
        for state in states
        if state.team == "A" and state.role == "offense"
    }
    assert selected[12].rating.mean == 0.0
    assert selected[13].rating.mean == 1.0
    assert any(state.team == "FCS-X" for state in states)


def test_population_validation_and_paired_bootstrap():
    class CorpusStub:
        v5_predictions = pd.DataFrame(
            [
                {
                    "season": 2022,
                    "week": 1,
                    "game_id": 1,
                    "target": target,
                    "actual": 10.0,
                    "prediction": 8.0,
                    "completed_game_stage": 0,
                    "gaussian_crps": 1.0,
                }
                for target in ("margin", "total")
            ]
        )

    corpus = CorpusStub()
    candidate = corpus.v5_predictions.copy()
    candidate["prediction"] = 9.0
    candidate["absolute_error"] = 1.0
    reference = corpus.v5_predictions.copy()
    reference["absolute_error"] = 2.0
    result = paired_comparison(candidate, reference, corpus, samples=20)
    assert result["paired"]["margin"]["mae_gain"] == 1.0
    assert result["paired"]["total"]["lower_90"] == 1.0
    with pytest.raises(ValueError, match="eligible schedule"):
        validate_prediction_population(candidate.head(1), corpus)


def test_common_bridge_uses_earlier_seasons_and_reports_early_period():
    seasons = (2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024, 2025)
    features = pd.DataFrame(
        [
            {
                "season": season,
                "week": 1,
                "game_id": season,
                "home_offense": index / 4,
                "home_defense": index / 6,
                "away_offense": -index / 5,
                "away_defense": -index / 7,
                "home_host": 1.0,
                "venue_unknown": True,
                "actual_margin": float(index * 2),
                "actual_total": float(40 + index),
                "offset_margin": 0.0,
                "offset_total": 0.0,
                "completed_game_stage": 0,
            }
            for index, season in enumerate(seasons)
        ]
    )

    class CorpusStub:
        v5_features = features
        v5_predictions = pd.DataFrame(
            [
                {
                    "season": season,
                    "week": 1,
                    "game_id": season,
                    "target": target,
                    "actual": float(index * 2 if target == "margin" else 40 + index),
                }
                for index, season in enumerate(seasons)
                if season >= 2022
                for target in ("margin", "total")
            ]
        )

    corpus = CorpusStub()
    main = common_bridge_predictions(corpus, features, candidate_id="synthetic_v1")
    early = common_bridge_predictions(
        corpus, features, candidate_id="synthetic_v1", seasons=(2018, 2019, 2021)
    )
    assert len(main) == 8
    assert len(early) == 6
    assert all(
        int(value) < season
        for season, text in zip(main.season, main.training_seasons)
        for value in text.split(",")
    )
    assert not main.training_seasons.str.contains("2020").any()
    assert main.calibration_count.min() > 0


def test_parameterized_design_initialize_and_estimate():
    design = ParameterizedDesign(
        candidate_id="test_param_v1", k=4.0, rho=0.50, mode="incremental"
    )
    init_blank = design.initialize(None, gap=1)
    assert init_blank == Rating(0.0, 1.0)

    prev = Rating(2.0, 1.0)
    init_carry = design.initialize(prev, gap=1)
    assert init_carry.mean == pytest.approx(1.0)
    assert init_carry.variance == pytest.approx(1.0)

    init_gap2 = design.initialize(prev, gap=2)
    assert init_gap2.mean == pytest.approx(0.5)

    obs = Observation(
        season=2024,
        week=1,
        game_id=101,
        team="A",
        role="offense",
        measurement_id="ppp",
        value=1.5,
        exposure=4.0,
        available_utc="2024-09-01T00:00:00Z",
        timing_class="historically_reconstructed",
    )
    prior = Rating(0.0, 1.0)
    posterior, explanation = design.estimate(prior, [obs])
    assert posterior.mean == pytest.approx(0.75)
    assert posterior.variance == pytest.approx(0.5)
    assert explanation["method"] == "parameterized_exposure"
    assert explanation["k"] == 4.0
    assert explanation["rho"] == 0.50
    assert explanation["usable_exposure"] == 4.0
    assert len(explanation["evidence_contributions"]) == 1


def test_yaml_candidate_loading(tmp_path):
    candidates_dir = tmp_path / "candidates"
    candidates_dir.mkdir()
    yaml_content = """candidate_id: yaml_test_k6_rho05_v1
type: parameterized_exposure
k: 6.0
rho: 0.50
mode: incremental
description: Test candidate
"""
    (candidates_dir / "test.yaml").write_text(yaml_content)

    loaded = load_candidate_configs(candidates_dir)
    assert "yaml_test_k6_rho05_v1" in loaded
    design = loaded["yaml_test_k6_rho05_v1"]
    assert isinstance(design, ParameterizedDesign)
    assert design.k == 6.0
    assert design.rho == 0.50
    assert design.mode == "incremental"

    prior = Rating(0.0, 1.0)
    obs = Observation(
        season=2024,
        week=1,
        game_id=1,
        team="A",
        role="offense",
        measurement_id="ppp",
        value=2.0,
        exposure=6.0,
        available_utc="2024-09-01T00:00:00Z",
        timing_class="historically_reconstructed",
    )
    post, exp = design.estimate(prior, [obs])
    assert post.mean == pytest.approx(1.0)
    assert exp["k"] == 6.0


def test_yaml_duplicate_rejection(tmp_path):
    candidates_dir = tmp_path / "candidates"
    candidates_dir.mkdir()
    yaml_content = """candidate_id: carryover_only_rho_0_60_v1
type: parameterized_exposure
k: 8.0
rho: 0.60
mode: incremental
"""
    (candidates_dir / "dup.yaml").write_text(yaml_content)

    with pytest.raises(ValueError, match="redefines code-registered id"):
        load_candidate_configs(
            candidates_dir, existing_ids={"carryover_only_rho_0_60_v1"}
        )

    bad_dir = tmp_path / "bad_candidates"
    bad_dir.mkdir()
    (bad_dir / "bad.yaml").write_text("candidate_id: bad_v1\nk: 8.0\n")
    with pytest.raises(ValueError, match="missing fields"):
        load_candidate_configs(bad_dir)


def test_measurement_recipe_extensible():
    recipe = MeasurementRecipe(
        recipe_id="custom_test_recipe_v1",
        measurement_id="epa_per_play",
        availability_policy="v5_later_week_6h_v1",
        description="Custom EPA recipe",
    )
    assert recipe.recipe_id == "custom_test_recipe_v1"
    assert recipe.description == "Custom EPA recipe"

    with pytest.raises(
        ValueError, match="unregistered measurement availability policy"
    ):
        MeasurementRecipe(
            recipe_id="unreg_policy_v1",
            availability_policy="unregistered_policy_v1",
        )

    register_availability_policy("v6_realtime_v1")
    recipe_new_pol = MeasurementRecipe(
        recipe_id="new_pol_v1",
        availability_policy="v6_realtime_v1",
    )
    assert recipe_new_pol.availability_policy == "v6_realtime_v1"

    class MockCorpus:
        def individual_observations(self, m_id):
            return []

        def games(self):
            return []

    with pytest.raises(ValueError, match="unregistered measurement recipe"):
        build_individual(MockCorpus(), recipe)

    called = []

    def custom_builder(corpus, rec):
        called.append(rec.recipe_id)
        return []

    register_recipe("custom_test_recipe_v1", custom_builder)
    result = build_individual(MockCorpus(), recipe)
    assert result == []
    assert called == ["custom_test_recipe_v1"]

    with pytest.raises(ValueError, match="already registered"):
        register_recipe("custom_test_recipe_v1", custom_builder)
