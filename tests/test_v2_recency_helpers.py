"""Offline tests for recency lineage and training-frame assembly."""

from __future__ import annotations

import pandas as pd
import pytest

from cks_picks_cfb.features import v2_recency


def test_normalize_games_counts_and_prior_snapshots_preserve_chronology():
    games = v2_recency._normalize_games_df(
        [{"id": 1, "week": 1, "season_type": "postseason"}]
    )
    assert games.loc[0, "game_id"] == 1
    assert games.loc[0, "week"] == 16

    history = pd.DataFrame(
        [
            {"team": "A", "game_id": 1, "week": 0, "date": "2026-08-20T12:00:00Z"},
            {"team": "A", "game_id": 2, "week": 1, "date": "2026-08-27T12:00:00Z"},
        ]
    )
    assert v2_recency._current_game_counts(history, 1).to_dict() == {"A": 1}
    assert v2_recency._current_game_counts(
        history, 9, "2026-08-25T12:00:00Z"
    ).to_dict() == {"A": 1}

    def reader(entity, year):
        assert entity == "team_week_adj"
        assert year == 2025
        return [
            {"team": "A", "week": 1, "rating": 1.0},
            {"team": "A", "week": 2, "rating": 2.0},
            {"team": "B", "week": 1, "rating": 3.0},
        ]

    snapshot = v2_recency._latest_prior_team_snapshot(reader, 2026)
    assert snapshot.set_index("team")["rating"].to_dict() == {"A": 2.0, "B": 3.0}
    with pytest.raises(ValueError, match="2020"):
        v2_recency._latest_prior_team_snapshot(reader, 2020)


def test_prior_seed_rows_use_latest_snapshot_and_league_mean_for_new_teams():
    games = pd.DataFrame(
        [
            {
                "game_id": 10,
                "week": 0,
                "home_team": "A",
                "away_team": "New",
                "start_date": "2026-08-20T12:00:00Z",
            }
        ]
    )

    def reader(entity, year):
        assert (entity, year) == ("team_week_adj", 2025)
        return [
            {"team": "A", "week": 2, "rating": 10.0},
            {"team": "B", "week": 2, "rating": 20.0},
        ]

    rows = v2_recency._prior_seed_rows(games, reader, 2026)
    assert rows.set_index("team")["rating"].to_dict() == {"A": 10.0, "New": 15.0}
    assert rows["seeded_from_prior_season"].all()


def test_merge_for_training_uses_completed_filter_and_prediction_regimes(monkeypatch):
    games = [
        {
            "id": 1,
            "season": 2026,
            "week": 1,
            "home_team": "A",
            "away_team": "B",
            "completed": True,
            "home_points": 28,
            "away_points": 17,
            "home_pregame_elo": 1500,
            "away_pregame_elo": 1450,
        },
        {
            "id": 2,
            "season": 2026,
            "week": 2,
            "home_team": "C",
            "away_team": "D",
            "completed": False,
            "home_points": None,
            "away_points": None,
        },
    ]

    def reader(entity, year):
        assert year == 2026
        return games if entity == "games" else []

    for name in (
        "merge_external_ratings",
        "merge_recruiting_composite",
        "merge_rankings",
    ):
        monkeypatch.setattr(
            f"cks_picks_cfb.features.external.{name}",
            lambda frame, *_args, **_kwargs: frame,
        )
    stats = pd.DataFrame(
        [
            {
                "game_id": 1,
                "season": 2026,
                "week": 1,
                "team": "A",
                "metric": 1.0,
                "current_season_games": 4,
            },
            {
                "game_id": 1,
                "season": 2026,
                "week": 1,
                "team": "B",
                "metric": 2.0,
                "current_season_games": 3,
            },
            {
                "game_id": 2,
                "season": 2026,
                "week": 2,
                "team": "C",
                "metric": 3.0,
                "current_season_games": 4,
            },
            {
                "game_id": 2,
                "season": 2026,
                "week": 2,
                "team": "D",
                "metric": 4.0,
                "current_season_games": 4,
            },
        ]
    )

    training = v2_recency._merge_for_training(stats, 2026, dataset_reader=reader)
    assert training["game_id"].tolist() == [1]
    assert training.loc[0, "spread_target"] == 11
    assert training.loc[0, "elo_diff"] == 50
    assert {"home_metric", "away_metric"} <= set(training)

    prediction = v2_recency._merge_for_training(
        stats, 2026, for_prediction=True, dataset_reader=reader
    )
    assert prediction["game_id"].tolist() == [1, 2]
    assert (
        prediction.loc[prediction["game_id"] == 1, "prediction_regime"].item()
        == "three_games"
    )
    assert prediction.loc[prediction["game_id"] == 2, "high_confidence_eligible"].item()


def test_load_v2_recency_data_orchestrates_adjustment_with_in_memory_reader(
    monkeypatch,
):
    games = [
        {
            "id": 1,
            "season": 2026,
            "week": 1,
            "home_team": "A",
            "away_team": "B",
            "season_type": "regular",
        }
    ]
    team_game = [
        {
            "game_id": 1,
            "season": 2026,
            "week": 1,
            "team": "A",
            "def_epa_pp": 1.0,
            "def_sr": 2.0,
            "def_pass_ypp": 3.0,
            "def_rush_ypp": 4.0,
        },
        {
            "game_id": 1,
            "season": 2026,
            "week": 1,
            "team": "B",
            "def_epa_pp": 2.0,
            "def_sr": 3.0,
            "def_pass_ypp": 4.0,
            "def_rush_ypp": 5.0,
        },
    ]

    def reader(entity, _year):
        return {"games": games, "team_game": team_game}[entity]

    monkeypatch.setattr(
        v2_recency,
        "aggregate_team_season_ewma",
        lambda _frame, alpha: pd.DataFrame(
            [
                {
                    "game_id": 1,
                    "season": 2026,
                    "week": 1,
                    "team": "A",
                    "home_adj_off_pass_ypp": 2.0,
                },
                {
                    "game_id": 1,
                    "season": 2026,
                    "week": 1,
                    "team": "B",
                    "home_adj_off_pass_ypp": 3.0,
                },
            ]
        ),
    )
    monkeypatch.setattr(
        v2_recency,
        "apply_iterative_opponent_adjustment",
        lambda frame, _prior, iterations: frame.assign(iteration=iterations),
    )
    monkeypatch.setattr(
        "cks_picks_cfb.features.internal_ratings.add_internal_power_ratings",
        lambda frame: frame.assign(internal_power_rtg=1.0),
    )
    captured = {}

    def merge(frame, year, **kwargs):
        captured.update(frame=frame, year=year, kwargs=kwargs)
        return frame

    monkeypatch.setattr(v2_recency, "_merge_for_training", merge)

    result = v2_recency.load_v2_recency_data(2026, dataset_reader=reader, iterations=2)

    assert result is captured["frame"]
    assert captured["year"] == 2026
    assert set(result["team"]) == {"A", "B"}
    assert set(result["current_season_games"]) == {0}
    assert set(result["iteration"]) == {2}
