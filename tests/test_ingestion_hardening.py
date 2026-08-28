from types import SimpleNamespace

import pandas as pd
import pytest

from cks_picks_cfb.data.game_stats import GameStatsIngester
from cks_picks_cfb.data.plays import PlaysIngester
from cks_picks_cfb.data.venues import VenuesIngester
from cks_picks_cfb.data.week_policy import CanonicalWeekGame
from cks_picks_cfb.features.byplay import apply_data_corrections


class MemoryIndexStorage:
    def __init__(self, games):
        self.games = games
        self.writes = []

    def describe(self):
        return "memory"

    def read_index(self, entity, *_args, **_kwargs):
        return list(self.games) if entity == "raw/games" else []

    def write(self, entity, records, partition, overwrite=True):
        self.writes.append((entity, list(records), partition, overwrite))
        return len(records)


class LakeMemoryStorage(MemoryIndexStorage):
    def __init__(self, games=()):
        super().__init__(games)
        self.objects = {}

    def exists(self, path):
        return path in self.objects

    def read_bytes(self, path):
        return self.objects[path]

    def write_bytes(self, data, path):
        self.objects[path] = data


def test_game_stats_accepts_and_preserves_week_zero(monkeypatch):
    monkeypatch.setenv("CFBD_API_KEY", "test-key")
    storage = MemoryIndexStorage([{"id": 10, "week": 0}, {"id": 11, "week": 1}])
    ingester = GameStatsIngester(year=2026, week=0, storage=storage)

    assert ingester.get_fbs_games_info() == [(10, 0)]


def test_week_zero_uses_provider_week_one_and_exact_games(monkeypatch):
    monkeypatch.setenv("CFBD_API_KEY", "test-key")
    storage = MemoryIndexStorage(
        [{"id": 10, "week": 1}, {"id": 11, "week": 1}, {"id": 12, "week": 2}]
    )
    selected = (CanonicalWeekGame(game_id=10, provider_week=1, canonical_week=0),)
    monkeypatch.setattr(
        "cks_picks_cfb.data.plays.select_canonical_week_games",
        lambda *_args, **_kwargs: selected,
    )
    monkeypatch.setattr(
        "cks_picks_cfb.data.game_stats.select_canonical_week_games",
        lambda *_args, **_kwargs: selected,
    )
    plays = PlaysIngester(year=2026, only_week=0, storage=storage)
    stats = GameStatsIngester(year=2026, week=0, storage=storage)

    assert plays.source_requests()[0].parameters["week"] == 1
    assert plays.source_requests()[0].parameters["expected_game_ids"] == [10]
    assert stats.source_requests()[0].parameters["week"] == 1
    assert stats.source_requests()[0].parameters["expected_game_ids"] == [10]


def test_week_zero_source_responses_filter_provider_week_one(monkeypatch):
    monkeypatch.setenv("CFBD_API_KEY", "test-key")
    storage = MemoryIndexStorage([{"id": 10, "week": 1}])

    class FakePlaysApi:
        def get_plays(self, **_kwargs):
            return [
                SimpleNamespace(id="p10", game_id=10),
                SimpleNamespace(id="p11", game_id=11),
            ]

    class FakeStatsApi:
        def get_game_team_stats(self, **_kwargs):
            return [SimpleNamespace(game_id=10), SimpleNamespace(game_id=11)]

    monkeypatch.setattr(
        "cks_picks_cfb.data.plays.cfbd.PlaysApi", lambda _client: FakePlaysApi()
    )
    monkeypatch.setattr(
        "cks_picks_cfb.data.game_stats.cfbd.GamesApi", lambda _client: FakeStatsApi()
    )
    plays = PlaysIngester(year=2026, only_week=0, storage=storage)
    stats = GameStatsIngester(year=2026, week=0, storage=storage)
    request = {
        "year": 2026,
        "season_type": "regular",
        "week": 1,
        "canonical_week": 0,
        "classification": "fbs",
        "expected_game_ids": [10],
    }

    assert [
        row["provider_record"].game_id for row in plays.fetch_source_request(request)
    ] == [10]
    assert [
        row["provider_record"].game_id for row in stats.fetch_source_request(request)
    ] == [10]


def test_game_stats_accepts_historical_cfbd_id_field(monkeypatch):
    monkeypatch.setenv("CFBD_API_KEY", "test-key")
    storage = MemoryIndexStorage([{"id": 10, "week": 1}])

    class FakeStatsApi:
        def get_game_team_stats(self, **_kwargs):
            return [SimpleNamespace(id=10), SimpleNamespace(id=11)]

    monkeypatch.setattr(
        "cks_picks_cfb.data.game_stats.cfbd.GamesApi", lambda _client: FakeStatsApi()
    )
    request = {
        "year": 2015,
        "season_type": "regular",
        "week": 1,
        "classification": "fbs",
        "expected_game_ids": [10],
    }
    stats = GameStatsIngester(year=2015, storage=storage)

    assert [
        row["provider_record"].id for row in stats.fetch_source_request(request)
    ] == [10]


def test_venues_accept_exact_source_request_ids_without_raw_games(monkeypatch):
    monkeypatch.setenv("CFBD_API_KEY", "test-key")

    class FakeVenuesApi:
        def get_venues(self, **_kwargs):
            return [SimpleNamespace(id=12), SimpleNamespace(id=34), SimpleNamespace(id=56)]

    monkeypatch.setattr(
        "cks_picks_cfb.data.venues.cfbd.VenuesApi", lambda _client: FakeVenuesApi()
    )
    venues = VenuesIngester(year=2016, storage=MemoryIndexStorage([]))

    result = venues.fetch_source_request({"expected_venue_ids": [12, 34]})

    assert [venue.id for venue in result] == [12, 34]


def test_unknown_play_week_fails_instead_of_becoming_week_zero(monkeypatch):
    monkeypatch.setenv("CFBD_API_KEY", "test-key")
    storage = MemoryIndexStorage([])
    ingester = PlaysIngester(year=2026, only_week=0, storage=storage)

    with pytest.raises(ValueError, match="no resolvable week"):
        ingester.ingest_data([{"id": "p1", "game_id": 10, "week": None}])

    assert storage.writes == []


def test_one_failed_week_prevents_partial_plays_write(monkeypatch):
    monkeypatch.setenv("CFBD_API_KEY", "test-key")
    monkeypatch.setenv("CFB_SOURCE_MAX_ATTEMPTS", "1")
    storage = MemoryIndexStorage([{"id": 10, "week": 0}, {"id": 11, "week": 1}])

    class FakePlaysApi:
        def get_plays(self, *, week, **_kwargs):
            if week == 1:
                raise RuntimeError("provider failed")
            return [SimpleNamespace(id="p1", game_id=10, week=0)]

    monkeypatch.setattr(
        "cks_picks_cfb.data.plays.cfbd.PlaysApi", lambda _client: FakePlaysApi()
    )
    ingester = PlaysIngester(year=2026, storage=storage)

    with pytest.raises(RuntimeError, match="provider failed"):
        ingester.run()

    assert storage.writes == []


def test_catalog_failure_cannot_mutate_compatibility_projection(monkeypatch):
    monkeypatch.setenv("CFBD_API_KEY", "test-key")
    monkeypatch.setenv("CFB_LAKE_DUAL_WRITE", "1")
    monkeypatch.setenv("DATABASE_URL", "postgres://preview.invalid/test")
    storage = LakeMemoryStorage([{"id": 10, "week": 0}])

    monkeypatch.setattr(
        "cks_picks_cfb.data.catalog.begin_ingestion_run", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        "cks_picks_cfb.data.catalog.finish_ingestion_run",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "cks_picks_cfb.data.catalog.register_source_capture",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("catalog down")),
    )

    class FakePlaysApi:
        def get_plays(self, **_kwargs):
            return [SimpleNamespace(id="p1", game_id=10, week=0)]

    monkeypatch.setattr(
        "cks_picks_cfb.data.plays.cfbd.PlaysApi", lambda _client: FakePlaysApi()
    )
    ingester = PlaysIngester(year=2026, only_week=0, storage=storage)

    with pytest.raises(RuntimeError, match="catalog down"):
        ingester.run()

    assert storage.writes == []
    assert any(path.startswith("lake/bronze/") for path in storage.objects)


def test_versioned_play_correction_is_exact_and_fail_closed():
    plays = pd.DataFrame(
        [{"game_id": 1, "drive_number": 2, "play_number": 3, "yards_gained": 4}]
    )
    corrections = pd.DataFrame(
        [
            {
                "record_key": {
                    "game_id": 1,
                    "drive_number": 2,
                    "play_number": 3,
                },
                "changed_field": "yards_gained",
                "old_value": 4,
                "new_value": 7,
            }
        ]
    )
    corrected = apply_data_corrections(plays, corrections)
    assert corrected.loc[0, "yards_gained"] == 7

    corrections.loc[0, "old_value"] = 99
    with pytest.raises(ValueError, match="old-value mismatch"):
        apply_data_corrections(plays, corrections)
