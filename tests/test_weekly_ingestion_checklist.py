"""Exercise weekly checklist CLI boundaries entirely with in-memory dependencies."""

import dataclasses
import importlib
import json
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from cks_picks_cfb.data.lake import DatasetRef, capture_provider_records, read_dataset


class MemoryStorage:
    def __init__(self):
        self.objects = {}

    def describe(self):
        return "r2:fixture-only"

    def exists(self, path):
        return path in self.objects

    def read_bytes(self, path):
        return self.objects[path]

    def write_bytes(self, data, path):
        self.objects[path] = data

    def read_index(self, entity, *_args, **_kwargs):
        import io

        assert entity == "raw/games"
        return pd.read_parquet(
            io.BytesIO(self.objects["raw/games/year=2026/part-0.parquet"])
        ).to_dict("records")

    def write(self, entity, records, partition, overwrite=True):
        self.objects[f"{entity}/{partition.path_suffix()}/part-0.parquet"] = (
            pd.DataFrame(records).to_parquet(index=False)
        )
        return len(records)


@pytest.fixture
def offline(monkeypatch, tmp_path):
    """Deny all network/DB access, dotenv loading, and inherited live credentials."""
    import os

    import dotenv
    import psycopg

    def forbidden(*_args, **_kwargs):
        pytest.fail("Fixture attempted live network/database access")

    monkeypatch.setattr(dotenv, "load_dotenv", lambda *_a, **_kw: False)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(psycopg, "connect", forbidden)
    for key in tuple(os.environ):
        if (
            key.startswith(("CFB_", "CFBD_", "THE_ODDS_", "AWS_"))
            or "DATABASE_URL" in key
        ):
            monkeypatch.delenv(key)
    monkeypatch.setenv("CFB_STORAGE_BACKEND", "r2")
    monkeypatch.setenv("CFB_MODEL_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("CFB_LAKE_DUAL_WRITE", "1")
    monkeypatch.setenv("CFB_REQUIRE_CATALOG", "1")
    monkeypatch.setenv("CFBD_API_KEY", "fixture-only")
    monkeypatch.setenv("DATABASE_URL", "postgresql://fixture.invalid/fixture")
    return MemoryStorage()


def cli(monkeypatch, module, *args):
    monkeypatch.setattr(sys, "argv", [module.__name__, *map(str, args)])
    module.main()


def test_inventory_and_separate_entity_cli_capture_ids(monkeypatch, tmp_path, offline):
    inventory_cli = importlib.import_module(
        "scripts.data.build_expected_request_inventory"
    )
    ingest_cli = importlib.import_module("scripts.data.ingest_week")
    import cfbd

    from cks_picks_cfb.data import catalog
    from cks_picks_cfb.data import storage as storage_module

    # The same pinned raw schedule and explicit policy used by the checklist.
    schedule = pd.DataFrame(
        [
            {
                "id": 10,
                "season": 2026,
                "week": 7,
                "completed": True,
                "start_date": "2026-10-17T18:00:00Z",
                "home_classification": "fbs",
                "away_classification": "fbs",
            },
            {
                "id": 11,
                "season": 2026,
                "week": 7,
                "completed": True,
                "start_date": "2026-10-17T21:00:00Z",
                "home_classification": "fbs",
                "away_classification": "fcs",
            },
        ]
    )
    offline.objects["raw/games/year=2026/part-0.parquet"] = schedule.to_parquet(
        index=False
    )
    monkeypatch.chdir(tmp_path)
    policy = Path("conf/policy/fixture-v1.yaml")
    policy.parent.mkdir(parents=True)
    policy.write_text("policy_version: fixture-v1\nseason: 2026\nassignments: []\n")
    inventory_path = tmp_path / "requests.json"
    monkeypatch.setattr(inventory_cli, "load_dotenv", lambda: False)
    monkeypatch.setattr(inventory_cli, "get_storage", lambda **_kw: offline)
    schedule_uri = "raw/games/year=2026/part-0.parquet"
    cli(
        monkeypatch,
        inventory_cli,
        "--raw-schedule-uri",
        schedule_uri,
        "--policy",
        policy,
        "--season",
        2026,
        "--canonical-week",
        7,
        "--environment",
        "preview",
        "--output",
        inventory_path,
    )
    inventory = json.loads(inventory_path.read_text())
    assert {r["entity"] for r in inventory["requests"]} == {"plays", "game_stats"}
    starts, captures, fetched = [], [], []
    monkeypatch.setattr(
        catalog, "begin_ingestion_run", lambda _url, **kw: starts.append(kw)
    )
    monkeypatch.setattr(
        catalog,
        "register_source_capture",
        lambda _url, cap, **kw: captures.append((cap, kw)),
    )
    monkeypatch.setattr(catalog, "finish_ingestion_run", lambda *_a, **_kw: None)

    assert all(
        r["parameters"]["expected_game_ids"] == [10, 11] for r in inventory["requests"]
    )
    monkeypatch.setattr(storage_module, "get_storage", lambda **_kw: offline)

    class PlaysProvider:
        def get_plays(self, **_kwargs):
            fetched.append("plays")
            return [{"id": f"p{game_id}", "game_id": game_id} for game_id in (10, 11)]

    class StatsProvider:
        def get_game_team_stats(self, **_kwargs):
            fetched.append("game_stats")
            return [{"game_id": game_id} for game_id in (10, 11)]

    monkeypatch.setattr(cfbd, "PlaysApi", lambda _client: PlaysProvider())
    monkeypatch.setattr(cfbd, "GamesApi", lambda _client: StatsProvider())
    # Missing inventory fails at CLI parsing before provider or catalog access.
    with pytest.raises(SystemExit) as exc:
        cli(monkeypatch, ingest_cli, "--year", 2026, "--week", 7, "--entities", "plays")
    assert exc.value.code == 2 and not fetched and not starts
    for entity in ("plays", "game_stats"):
        monkeypatch.setenv("CFB_INGESTION_RUN_ID", f"fixture-w8:{entity}")
        cli(
            monkeypatch,
            ingest_cli,
            "--year",
            2026,
            "--week",
            7,
            "--entities",
            entity,
            "--request-inventory",
            inventory_path,
        )
    assert fetched == ["plays", "game_stats"]
    assert [r["ingestion_run_id"] for r in starts] == [
        "fixture-w8:plays",
        "fixture-w8:game_stats",
    ]
    assert [kw["ingestion_run_id"] for _, kw in captures] == [
        "fixture-w8:plays",
        "fixture-w8:game_stats",
    ]
    assert all(
        r["expected_request_inventory_sha256"] for r in (s["request"] for s in starts)
    )
    # The real ingesters independently select the raw FBS-involved population.
    assert all(
        start["request"]["requests"][0]["parameters"]["expected_game_ids"] == [10, 11]
        for start in starts
    )
    original = offline.objects[schedule_uri]
    offline.objects[schedule_uri] += b"changed"
    counts = len(starts), len(captures), len(fetched), len(offline.objects)
    with pytest.raises(SystemExit) as exc:
        cli(
            monkeypatch,
            ingest_cli,
            "--year",
            2026,
            "--week",
            7,
            "--entities",
            "plays",
            "--request-inventory",
            inventory_path,
        )
    assert exc.value.code == 1
    assert (len(starts), len(captures), len(fetched), len(offline.objects)) == counts
    offline.objects[schedule_uri] = original


def test_market_cli_estimate_capture_snapshot_and_cumulative_history(
    monkeypatch, offline
):
    odds = importlib.import_module("scripts.data.fetch_odds_api_market_quotes")
    snapshot = importlib.import_module("scripts.pipeline.build_week_market_snapshot")
    cumulative = importlib.import_module("scripts.pipeline.build_silver")
    import os

    when = datetime(2026, 10, 18, 15, tzinfo=timezone.utc)
    registered, provider_calls = [], []
    schedule = pd.DataFrame(
        [
            {
                "game_id": 80,
                "home_team": "Alabama",
                "away_team": "Georgia",
                "start_date": "2026-10-20T23:00:00Z",
            }
        ]
    )
    record = {
        "source_event_id": "event80",
        "home_team": "Alabama",
        "away_team": "Georgia",
        "kickoff_utc": "2026-10-20T23:00:00Z",
        "captured_at": when.isoformat(),
        "provider": "book",
        "spread": -3.0,
        "total": 50.0,
    }
    response = SimpleNamespace(
        records=[record],
        captured_at=when,
        effective_at=when,
        request={"regions": "us"},
        provider_api_version="fixture",
        response_metadata={},
    )

    class Provider:
        def fetch_live(self, *_a, **_kw):
            provider_calls.append("live")
            return response

    monkeypatch.setattr(odds, "load_dotenv", lambda: False)
    monkeypatch.setattr(odds, "_week_schedule", lambda *_a: schedule)
    monkeypatch.setattr(odds, "TheOddsAPIAdapter", Provider)
    monkeypatch.setattr(odds, "get_storage", lambda: offline)
    monkeypatch.setattr(odds, "begin_ingestion_run", lambda *_a, **_kw: None)
    monkeypatch.setattr(odds, "finish_ingestion_run", lambda *_a, **_kw: None)
    monkeypatch.setattr(
        odds,
        "register_source_capture",
        lambda _u, cap, **kw: registered.append(
            (dataclasses.replace(cap, state="registered"), kw["ingestion_run_id"])
        ),
    )
    monkeypatch.setenv("CFB_INGESTION_RUN_ID", "fixture-w8:market_quotes")
    cli(monkeypatch, odds, "--year", 2026, "--week", 8)
    assert not provider_calls and not registered
    cli(monkeypatch, odds, "--year", 2026, "--week", 8, "--confirm")
    assert provider_calls == ["live"] and registered[0][1] == "fixture-w8:market_quotes"
    cfbd = capture_provider_records(
        offline,
        provider="cfbd",
        entity="betting_lines",
        records=[
            {
                "game_id": 80,
                "provider": "Consensus",
                "spread": -2.0,
                "over_under": 51.0,
                "captured_at": when.isoformat(),
            }
        ],
        captured_at=when,
        effective_at=when,
        request={},
    )
    registered.append(
        (dataclasses.replace(cfbd, state="registered"), "fixture-w8:betting_lines")
    )
    by_id = {c.capture_id: c for c, _ in registered}

    class CatalogConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def execute(self, _sql, params):
            return SimpleNamespace(
                fetchall=lambda: [
                    (c.capture_id,) for c, run in registered if run in params
                ]
            )

    monkeypatch.setattr(snapshot.psycopg, "connect", lambda *_a: CatalogConnection())
    for module in (snapshot, cumulative):
        monkeypatch.setattr(module, "load_dotenv", lambda: False)
        monkeypatch.setattr(module, "get_storage", lambda **_kw: offline)
        monkeypatch.setattr(module, "source_capture_by_id", lambda _u, cid: by_id[cid])
        monkeypatch.setattr(module, "register_dataset_version", lambda *_a: None)
        monkeypatch.setattr(module, "_code_sha", lambda: "a" * 40)
    args = ("--year", 2026, "--week", 8, "--as-of", "2026-10-18T15:01:00Z")
    with pytest.raises(LookupError, match="No registered market capture"):
        cli(
            monkeypatch,
            snapshot,
            *args,
            "--pipeline-run-id",
            "wrong-id",
            "--output-ref-uri",
            "bad/snapshot.json",
        )
    assert not offline.exists("bad/snapshot.json")
    with pytest.raises(ValueError, match="after.*cutoff"):
        cli(
            monkeypatch,
            snapshot,
            "--year",
            2026,
            "--week",
            8,
            "--as-of",
            "2026-10-18T14:59:00Z",
            "--pipeline-run-id",
            "fixture-w8",
            "--output-ref-uri",
            "late/snapshot.json",
        )
    cli(
        monkeypatch,
        snapshot,
        *args,
        "--pipeline-run-id",
        "fixture-w8",
        "--output-ref-uri",
        "w8/snapshot.json",
    )
    quote_ref = DatasetRef(
        **json.loads(offline.read_bytes("w8/market_quotes_ref.json"))
    )
    assert set(read_dataset(offline, quote_ref).game_id) == {80}
    historical = capture_provider_records(
        offline,
        provider="cfbd",
        entity="betting_lines",
        records=[
            {
                "game_id": 70,
                "provider": "Consensus",
                "spread": -1.0,
                "total": 49.0,
                "captured_at": "2026-10-10T12:00:00Z",
            }
        ],
        captured_at=datetime(2026, 10, 10, 12, tzinfo=timezone.utc),
        effective_at=None,
        request={},
    )
    historical = dataclasses.replace(historical, state="registered")
    by_id[historical.capture_id] = historical
    monkeypatch.setattr(
        cumulative,
        "resolve_runtime_target",
        lambda _e: SimpleNamespace(database_url=os.environ["DATABASE_URL"]),
    )
    capture_args = [a for cid in by_id for a in ("--capture-id", cid)]
    cli(
        monkeypatch,
        cumulative,
        "--dataset",
        "market_quotes",
        *capture_args,
        "--as-of",
        "2026-10-18T15:01:00Z",
        "--environment",
        "preview",
        "--output-ref-uri",
        "cumulative/quotes.json",
    )
    combined_ref = DatasetRef(
        **json.loads(offline.read_bytes("cumulative/quotes.json"))
    )
    combined = read_dataset(offline, combined_ref)
    assert set(combined.game_id) == {70, 80}
    assert len(combined) == 3


@pytest.mark.parametrize("missing", ["finals", "drives", "reconciliation"])
def test_cumulative_season_inputs_reject_missing_prior_week_game(
    offline, tmp_path, missing
):
    from tests.season_fixtures import build_season

    def remove_prior_game(tables):
        tables[missing] = tables[missing].loc[tables[missing].game_id.ne(1)]

    with pytest.raises(ValueError, match="missing|required|incomplete|final scores"):
        build_season(tmp_path, edit=remove_prior_game)


def test_cumulative_season_derives_measurements_and_keeps_prior_quotes(
    offline, tmp_path
):
    from tests.season_fixtures import build_season

    result = build_season(tmp_path)
    assert not {"observations", "scoring_events"} & result["revision"]["inputs"].keys()
    assert set(result["frames"]["measurements"].game_id) == {1, 2, 3, 4}
    grades = result["frames"]["grades"]
    assert set(grades.loc[grades.game_id.eq(1), "quote_id"]) <= {"g1-book1", "g1-book2"}
    assert len(grades.loc[grades.game_id.eq(1)]) == 2
