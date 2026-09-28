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
from cks_picks_cfb.ratings_lab.measurements import build_cumulative
from cks_picks_cfb.ratings_lab.replay import CarryoverOnly, replay


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
