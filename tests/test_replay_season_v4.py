"""Tests for the 2025 selection-time replay tooling."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from scripts.pipeline.refit_game_ordinal_bundle import (
    _frozen_component_model,
    parse_train_years,
)
from scripts.pipeline.replay_season_v4 import (
    build_market_ref,
    week_cutoff,
    write_input_refs,
)

POLICY_YEARS = (2021, 2022, 2023, 2024, 2025)


class FakeStorage:
    def __init__(self, index_rows=None, files=None):
        self.index_rows = list(index_rows or [])
        self.files = dict(files or {})

    def exists(self, uri):
        return uri in self.files

    def read_bytes(self, uri):
        return self.files[uri]

    def write_bytes(self, data, path):
        self.files[path] = data

    def read_index(self, entity, selector):
        assert selector == {"year": 2025}
        return self.index_rows


def test_parse_train_years_defaults_to_policy():
    assert parse_train_years(None, POLICY_YEARS) == POLICY_YEARS


def test_parse_train_years_accepts_leading_window():
    assert parse_train_years("2021,2022,2023,2024", POLICY_YEARS) == (
        2021,
        2022,
        2023,
        2024,
    )


@pytest.mark.parametrize("raw", ["2022,2023", "2024", "2021,2023", "", "2021, 2022, x"])
def test_parse_train_years_rejects_nonleading_windows(raw):
    with pytest.raises(ValueError):
        parse_train_years(raw, POLICY_YEARS)


def test_frozen_component_model_reproduces_column_semantics():
    passthrough = _frozen_component_model([1.0])
    frame = pd.DataFrame({"baseline_spread_prediction": [-3.5, 7.0]})
    assert list(passthrough.predict(frame)) == [-3.5, 7.0]
    blend = _frozen_component_model([0.7, 0.3])
    blended = blend.predict(pd.DataFrame({"prior": [10.0], "current": [20.0]}))
    assert abs(float(blended[0]) - 13.0) < 1e-12


def test_week_cutoff_precedes_first_kickoff():
    games = pd.DataFrame(
        {
            "season": [2025, 2025, 2025],
            "week": [1, 1, 2],
            "start_date": [
                "2025-08-30T20:00:00+00:00",
                "2025-08-31T01:00:00+00:00",
                "2025-09-06T20:00:00+00:00",
            ],
        }
    )
    cutoff = datetime.fromisoformat(week_cutoff(games, year=2025, week=1))
    assert cutoff == datetime(2025, 8, 30, 19, 59, 59, tzinfo=timezone.utc)
    assert cutoff < datetime(2025, 8, 30, 20, 0, 0, tzinfo=timezone.utc)


def test_week_cutoff_rejects_unknown_week():
    games = pd.DataFrame({"season": [2025], "week": [1], "start_date": ["2025-08-30"]})
    with pytest.raises(SystemExit):
        week_cutoff(games, year=2025, week=9)


def test_write_input_refs_entities_and_immutability():
    storage = FakeStorage()
    from cks_picks_cfb.data.lake import DatasetRef

    games_ref = DatasetRef("games", "v1", "games_v2", "a" * 64, "uri-games")
    market_ref = DatasetRef(
        "market_snapshots", "v2", "market_snapshots_v1", "b" * 64, "uri-mkt"
    )
    gold_ref = DatasetRef(
        "point_in_time_matchups_v5",
        "v3",
        "point_in_time_matchups_v5",
        "c" * 64,
        "uri-gold",
    )
    uri = write_input_refs(
        storage,
        pipeline_run_id="replay-2025-v4-w1",
        year=2025,
        games_ref=games_ref,
        market_ref=market_ref,
        gold_ref=gold_ref,
        environment="preview",
    )
    assert uri == "artifacts/preview/pipeline-runs/replay-2025-v4-w1/input_refs.json"
    refs = json.loads(storage.files[uri])
    assert [r["entity"] for r in refs] == [
        "games",
        "betting_lines",
        "point_in_time_matchups",
    ]
    assert all(r["year"] == 2025 for r in refs)
    assert refs[2]["dataset"] == "point_in_time_matchups_v5"
    payload = storage.files[uri]
    write_input_refs(
        storage,
        pipeline_run_id="replay-2025-v4-w1",
        year=2025,
        games_ref=games_ref,
        market_ref=market_ref,
        gold_ref=gold_ref,
        environment="preview",
    )
    assert storage.files[uri] == payload
    gold_ref2 = DatasetRef(
        "point_in_time_matchups_v5",
        "v4",
        "point_in_time_matchups_v5",
        "d" * 64,
        "uri-gold2",
    )
    with pytest.raises(FileExistsError):
        write_input_refs(
            storage,
            pipeline_run_id="replay-2025-v4-w1",
            year=2025,
            games_ref=games_ref,
            market_ref=market_ref,
            gold_ref=gold_ref2,
            environment="preview",
        )


def _quote_rows():
    return [
        {
            "game_id": 1,
            "provider": "Bovada",
            "spread": -6.0,
            "over_under": 38.0,
            "captured_at": "2026-09-09T18:59:57+00:00",
            "quote_id": "q1",
        },
        {
            "game_id": 1,
            "provider": "ESPN Bet",
            "spread": -4.0,
            "over_under": 40.0,
            "captured_at": "2026-09-09T18:59:57+00:00",
            "quote_id": "q2",
        },
        {
            "game_id": 2,
            "provider": "consensus",
            "spread": 3.0,
            "over_under": 55.0,
            "captured_at": "2026-09-09T18:59:57+00:00",
            "quote_id": "q3",
        },
    ]


def test_build_market_ref_canonicalizes_and_registers(monkeypatch):
    storage = FakeStorage(index_rows=_quote_rows())
    games = pd.DataFrame({"game_id": [1, 2], "season": [2025, 2025], "week": [1, 1]})
    registered = []
    monkeypatch.setattr(
        "scripts.pipeline.replay_season_v4.register_dataset_version",
        lambda conn, ref, manifest: registered.append(ref.version_id),
    )
    ref = build_market_ref(
        storage,
        year=2025,
        games=games,
        market_ref_uri="artifacts/preview/refs/replay-2025/market.json",
        environment="preview",
        as_of=datetime.now(timezone.utc),
    )
    assert registered == [ref.version_id]
    snapshots = pd.read_parquet(__import__("io").BytesIO(storage.files[ref.uri]))
    by_game = snapshots.set_index("game_id")
    # Consensus beats the median; providers fall back to median.
    assert by_game.loc[2, "spread_line"] == 3.0
    assert by_game.loc[1, "spread_line"] == -5.0
    assert by_game.loc[1, "total_line"] == 39.0
    assert set(by_game.loc[1, ["season", "week"]]) == {2025, 1}
    # Reuse: the existing ref JSON short-circuits the build.
    ref_again = build_market_ref(
        storage,
        year=2025,
        games=games,
        market_ref_uri="artifacts/preview/refs/replay-2025/market.json",
        environment="preview",
        as_of=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    assert ref_again == ref
    assert registered == [ref.version_id]


def test_build_market_ref_rejects_unknown_games(monkeypatch):
    storage = FakeStorage(index_rows=_quote_rows())
    games = pd.DataFrame({"game_id": [1], "season": [2025], "week": [1]})
    monkeypatch.setattr(
        "scripts.pipeline.replay_season_v4.register_dataset_version",
        lambda conn, ref, manifest: None,
    )
    with pytest.raises(SystemExit):
        build_market_ref(
            storage,
            year=2025,
            games=games,
            market_ref_uri="artifacts/preview/refs/replay-2025/market.json",
            environment="preview",
            as_of=datetime.now(timezone.utc),
        )
