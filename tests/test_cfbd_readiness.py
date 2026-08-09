from __future__ import annotations

from types import SimpleNamespace

import pytest

from cks_picks_cfb.data.base import BaseIngester, DataUnavailableError
from cks_picks_cfb.data.betting_lines import (
    BettingLineCoverageError,
    BettingLinesIngester,
)
from cks_picks_cfb.data.storage import Partition


class EmptyIngester(BaseIngester):
    @property
    def entity_name(self) -> str:
        return "raw/empty"

    def fetch_data(self):
        return []

    def transform_data(self, data):
        return data


class FakeBettingApi:
    def __init__(self, game_lines):
        self.game_lines = game_lines

    def get_lines(self, **_kwargs):
        return self.game_lines


class MemoryStorage:
    def __init__(self):
        self.records: dict[str, list[dict]] = {}

    def describe(self) -> str:
        return "memory"

    def write(self, entity, records, _partition, overwrite=True):
        assert overwrite
        self.records[entity] = list(records)
        return len(records)

    def partition_exists(self, entity, _partition) -> bool:
        return entity in self.records


def test_empty_cfbd_response_is_availability_error(monkeypatch):
    monkeypatch.setenv("CFBD_API_KEY", "test-key")
    storage = MemoryStorage()
    ingester = EmptyIngester(year=2026, storage=storage)

    with pytest.raises(DataUnavailableError, match="source availability"):
        ingester.run()

    assert not storage.partition_exists("raw/empty", Partition({"year": "2026"}))


def test_full_line_coverage_is_required_before_write(monkeypatch):
    monkeypatch.setenv("CFBD_API_KEY", "test-key")
    storage = MemoryStorage()
    api = FakeBettingApi(
        [
            SimpleNamespace(
                id=1,
                week=1,
                lines=[SimpleNamespace(provider="Book", spread=-3.5)],
            ),
            SimpleNamespace(id=2, week=1, lines=[]),
        ]
    )
    monkeypatch.setattr(
        "cks_picks_cfb.data.betting_lines.cfbd.BettingApi", lambda _client: api
    )
    ingester = BettingLinesIngester(
        year=2026,
        week=1,
        storage=storage,
        require_full_coverage=True,
    )
    monkeypatch.setattr(ingester, "get_fbs_game_ids", lambda: [1, 2])

    with pytest.raises(BettingLineCoverageError) as error:
        ingester.run()

    assert error.value.missing_game_ids == {1, 2}
    assert error.value.missing_spread_game_ids == {2}
    assert error.value.missing_total_game_ids == {1, 2}
    assert "raw/betting_lines" not in storage.records


def test_partial_lines_can_be_saved_outside_publish_gate(monkeypatch):
    monkeypatch.setenv("CFBD_API_KEY", "test-key")
    storage = MemoryStorage()
    api = FakeBettingApi(
        [
            SimpleNamespace(
                id=1,
                week=1,
                lines=[SimpleNamespace(provider="Book", spread=-3.5)],
            ),
            SimpleNamespace(id=2, week=1, lines=[]),
        ]
    )
    monkeypatch.setattr(
        "cks_picks_cfb.data.betting_lines.cfbd.BettingApi", lambda _client: api
    )
    ingester = BettingLinesIngester(year=2026, week=1, storage=storage)
    monkeypatch.setattr(ingester, "get_fbs_game_ids", lambda: [1, 2])

    ingester.run()

    rows = storage.records["raw/betting_lines"]
    assert len(rows) == 1
    expected = {
        "year": 2026,
        "season_type": "regular",
        "week": 1,
        "game_id": 1,
        "provider": "Book",
        "spread": -3.5,
        "formatted_spread": None,
        "spread_open": None,
        "over_under": None,
        "over_under_open": None,
        "home_moneyline": None,
        "away_moneyline": None,
    }
    assert {key: rows[0][key] for key in expected} == expected
    assert rows[0]["captured_at"]
    assert rows[0]["quote_id"]
