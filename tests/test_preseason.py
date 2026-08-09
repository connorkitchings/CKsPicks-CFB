from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from cks_picks_cfb.data.storage import LocalStorage, Partition
from cks_picks_cfb.preseason import (
    PRESEASON_FEATURES,
    REQUIRED_SNAPSHOT_SOURCES,
    PreseasonSnapshotIngester,
    blend_early_season_predictions,
    build_preseason_matchups,
    fit_preseason_models,
    predict_preseason,
    select_blend_weights,
    snapshot_is_complete,
    write_snapshot_source,
)

AS_OF = "2024-08-15"


@pytest.fixture
def storage(tmp_path: Path) -> LocalStorage:
    return LocalStorage(str(tmp_path))


def _write(storage: LocalStorage, entity: str, records: list[dict], year: int = 2024):
    storage.write(entity, records, Partition({"year": str(year)}))


def _snapshot_records(source: str) -> list[dict]:
    if source == "returning_production":
        return [
            {
                "team": "Alabama",
                "total_ppa": 10,
                "total_passing_ppa": 4,
                "total_rushing_ppa": 3,
                "total_receiving_ppa": 3,
                "percent_ppa": 0.7,
                "passing_usage": 0.4,
                "rushing_usage": 0.3,
            },
            {
                "team": "Auburn",
                "total_ppa": 7,
                "total_passing_ppa": 2,
                "total_rushing_ppa": 3,
                "total_receiving_ppa": 2,
                "percent_ppa": 0.5,
                "passing_usage": 0.2,
                "rushing_usage": 0.4,
            },
        ]
    if source == "transfers":
        return [
            {
                "origin": "Auburn",
                "destination": "Alabama",
                "position": "QB",
                "rating": 0.98,
            },
            {
                "origin": "Alabama",
                "destination": "Auburn",
                "position": "WR",
                "rating": 0.90,
            },
        ]
    if source == "recruiting":
        return [
            {"team": team, "year": year, "points": points}
            for team, points in (("Alabama", 300.0), ("Auburn", 250.0))
            for year in range(2021, 2025)
        ]
    if source == "talent":
        return [
            {"team": "Alabama", "talent": 900.0},
            {"team": "Auburn", "talent": 800.0},
        ]
    if source == "coaches":
        return [
            {
                "first_name": "A",
                "last_name": "Coach",
                "seasons": [
                    {"school": "Alabama", "year": 2022},
                    {"school": "Alabama", "year": 2023},
                    {"school": "Alabama", "year": 2024},
                ],
            },
            {
                "first_name": "B",
                "last_name": "Coach",
                "seasons": [{"school": "Auburn", "year": 2024}],
            },
        ]
    raise AssertionError(source)


def _write_complete_snapshot(storage: LocalStorage) -> None:
    for source in REQUIRED_SNAPSHOT_SOURCES:
        write_snapshot_source(
            storage,
            year=2024,
            as_of=AS_OF,
            source=source,
            records=_snapshot_records(source),
        )


def _write_base_data(storage: LocalStorage) -> None:
    _write(
        storage,
        "raw/games",
        [
            {
                "id": 1,
                "week": 1,
                "home_team": "Alabama",
                "away_team": "Auburn",
                "home_points": 31,
                "away_points": 17,
                "neutral_site": False,
                "home_conference": "SEC",
                "away_conference": "SEC",
            }
        ],
    )
    _write(
        storage,
        "raw/teams",
        [
            {"school": "Alabama", "classification": "fbs"},
            {"school": "Auburn", "classification": "fbs"},
        ],
    )
    _write(
        storage,
        "processed/team_week_adj",
        [
            {
                "team": "Alabama",
                "week": 15,
                "iteration": 2,
                "adj_off_epa_pp": 0.30,
                "adj_def_epa_pp": -0.10,
                "adj_off_sr": 0.50,
                "adj_def_sr": 0.40,
                "plays_per_game": 72,
            },
            {
                "team": "Auburn",
                "week": 15,
                "iteration": 2,
                "adj_off_epa_pp": 0.10,
                "adj_def_epa_pp": -0.02,
                "adj_off_sr": 0.45,
                "adj_def_sr": 0.44,
                "plays_per_game": 65,
            },
        ],
        year=2023,
    )


def test_snapshot_is_immutable_and_requires_nonempty_sources(storage: LocalStorage):
    _write_complete_snapshot(storage)
    assert snapshot_is_complete(storage, 2024, AS_OF)
    with pytest.raises(FileExistsError):
        write_snapshot_source(
            storage,
            year=2024,
            as_of=AS_OF,
            source="talent",
            records=_snapshot_records("talent"),
        )

    incomplete = "2024-08-16"
    for source in REQUIRED_SNAPSHOT_SOURCES:
        write_snapshot_source(
            storage,
            year=2024,
            as_of=incomplete,
            source=source,
            records=[] if source == "coaches" else _snapshot_records(source),
        )
    assert not snapshot_is_complete(storage, 2024, incomplete)


def test_snapshot_ingester_writes_each_requested_source(
    storage: LocalStorage, monkeypatch
):
    ingester = PreseasonSnapshotIngester(2024, AS_OF, storage, cfbd_config=object())
    monkeypatch.setattr(ingester, "fetch", lambda source: _snapshot_records(source))
    counts = ingester.run(("talent", "transfers"))
    assert counts == {"talent": 2, "transfers": 2}


def test_build_matchups_uses_snapshot_data_and_excludes_lines(storage: LocalStorage):
    _write_base_data(storage)
    _write_complete_snapshot(storage)
    result = build_preseason_matchups(
        storage, year=2024, as_of=AS_OF, include_targets=True
    )

    assert len(result) == 1
    assert result.loc[0, "spread_target"] == 14
    assert result.loc[0, "total_target"] == 48
    assert result.loc[0, "home_coach_tenure"] == 3
    assert result.loc[0, "away_coach_new"] == 1
    assert result.loc[0, "home_transfer_in_qb"] == 1
    assert result.loc[0, "away_transfer_out_qb"] == 1
    assert set(PRESEASON_FEATURES).issubset(result.columns)
    assert not any("line" in feature for feature in PRESEASON_FEATURES)


def test_preseason_pipeline_imputes_and_predicts_without_market_features():
    rng = np.random.default_rng(7)
    frame = pd.DataFrame(
        rng.normal(size=(120, len(PRESEASON_FEATURES))), columns=PRESEASON_FEATURES
    )
    frame.loc[0, "home_return_total_ppa"] = np.nan
    frame["spread_target"] = rng.normal(size=len(frame))
    frame["total_target"] = 45 + rng.normal(size=len(frame))
    bundle = fit_preseason_models(frame, alpha=1.0)
    spread, total = predict_preseason(bundle, frame)
    assert len(spread) == len(frame)
    assert len(total) == len(frame)
    assert bundle["features"] == list(PRESEASON_FEATURES)


def test_blend_routes_by_less_experienced_team():
    preseason = np.array([10.0, 20.0, 30.0, 40.0])
    recency = np.array([1.0, 2.0, 3.0, 4.0])
    result = blend_early_season_predictions(
        preseason,
        recency,
        home_games=[0, 1, 2, 3],
        away_games=[1, 2, 3, 3],
        weights={1: 0.6, 2: 0.25},
    )
    assert result.tolist() == pytest.approx([10.0, 12.8, 9.75, 4.0])


def test_select_blend_weights_uses_training_only_predictions():
    validation = pd.DataFrame(
        {
            "home_current_season_games": [1, 1, 2, 2],
            "away_current_season_games": [1, 2, 2, 3],
            "spread_target": [10.0, 10.0, 3.0, 3.0],
            "total_target": [50.0, 50.0, 40.0, 40.0],
            "preseason_spread": [10.0, 10.0, 9.0, 9.0],
            "recency_spread": [1.0, 1.0, 3.0, 3.0],
            "preseason_total": [50.0, 50.0, 60.0, 60.0],
            "recency_total": [20.0, 20.0, 40.0, 40.0],
        }
    )
    assert select_blend_weights(validation, grid=(0.0, 0.5, 1.0)) == {
        1: 1.0,
        2: 0.0,
    }
