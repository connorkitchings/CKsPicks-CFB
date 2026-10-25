"""Incremental close/open: carried-capture resolution and the history stop gate.

Local storage and frames only; no database or network.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from cks_picks_cfb.data.silver import SILVER_CONTRACTS
from cks_picks_cfb.data.storage.local import LocalStorage
from scripts.pipeline import verify_completed_week_stability as gate
from scripts.pipeline.build_season_revision import carried_capture_ids

SHA = "a" * 64


def write_manifest(
    storage: LocalStorage, dataset: str, version: str, body: dict
) -> str:
    uri = f"lake/silver/dataset={dataset}/version={version}/manifest.json"
    storage.write_bytes(json.dumps(body).encode(), uri)
    return uri


def seed_certified_history(storage: LocalStorage) -> dict:
    """Mimic the certified Week 8 lineage: byplay plus its four parents."""
    parents = {
        "plays": "playsversion1",
        "games": "gamesversion1",
        "teams": "teamsversion1",
        "team_game_stats": "statsversion1",
    }
    write_manifest(
        storage,
        "byplay",
        "byplayversion1",
        {
            "dataset": "byplay",
            "version_id": "byplayversion1",
            "parent_versions": list(parents.values()),
        },
    )
    write_manifest(
        storage,
        "plays",
        parents["plays"],
        {
            "dataset": "plays",
            "version_id": parents["plays"],
            "source_capture_ids": ["cap-play-w0", "cap-play-w1"],
        },
    )
    write_manifest(
        storage,
        "team_game_stats",
        parents["team_game_stats"],
        {
            "dataset": "team_game_stats",
            "version_id": parents["team_game_stats"],
            "source_capture_ids": ["cap-stat-w0"],
        },
    )
    for dataset in ("games", "teams"):
        write_manifest(
            storage,
            dataset,
            parents[dataset],
            {
                "dataset": dataset,
                "version_id": parents[dataset],
                "source_capture_ids": [],
            },
        )
    return {
        "inputs": {
            "byplay": {
                "uri": "lake/silver/dataset=byplay/version=byplayversion1/data.parquet",
                "sha256": SHA,
            }
        }
    }


def test_carried_capture_ids_resolves_the_certified_parents(tmp_path):
    storage = LocalStorage(str(tmp_path))
    previous = seed_certified_history(storage)
    assert carried_capture_ids(storage, previous) == {
        "plays": ["cap-play-w0", "cap-play-w1"],
        "team_game_stats": ["cap-stat-w0"],
    }


def test_carried_capture_ids_refuses_an_unresolvable_parent(tmp_path):
    storage = LocalStorage(str(tmp_path))
    previous = seed_certified_history(storage)
    byplay_uri = previous["inputs"]["byplay"]["uri"]
    manifest_uri = byplay_uri.rsplit("/", 1)[0] + "/manifest.json"
    body = json.loads(storage.read_bytes(manifest_uri).decode())
    body["parent_versions"] = ["missing-version"]
    storage.write_bytes(json.dumps(body).encode(), manifest_uri)
    with pytest.raises(LookupError, match="no resolvable plays parent"):
        carried_capture_ids(storage, previous)


def test_carried_capture_ids_refuses_a_parent_without_captures(tmp_path):
    storage = LocalStorage(str(tmp_path))
    previous = seed_certified_history(storage)
    byplay_uri = previous["inputs"]["byplay"]["uri"]
    manifest_uri = byplay_uri.rsplit("/", 1)[0] + "/manifest.json"
    body = json.loads(storage.read_bytes(manifest_uri).decode())
    body["parent_versions"] = ["emptyversion1"]
    storage.write_bytes(json.dumps(body).encode(), manifest_uri)
    write_manifest(
        storage,
        "plays",
        "emptyversion1",
        {"dataset": "plays", "version_id": "emptyversion1", "source_capture_ids": []},
    )
    with pytest.raises(LookupError, match="lists no source captures"):
        carried_capture_ids(storage, previous)


def games_frame(rows: list[tuple[int, int, int]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["game_id", "week", "venue_id"])


def outcomes_frame(rows: list[tuple[int, int, int]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["game_id", "home_points", "away_points"])


def test_stop_gate_passes_on_identical_completed_weeks():
    games = games_frame([(1, 7, 10), (2, 8, 11)])
    outcomes = outcomes_frame([(1, 31, 24), (2, 17, 13)])
    assert (
        gate.compare_completed_weeks(
            games, games.copy(), outcomes, outcomes.copy(), through_week=7
        )
        == []
    )


def test_stop_gate_names_a_changed_completed_week_row():
    new = games_frame([(1, 7, 10), (2, 7, 11)])
    previous = games_frame([(1, 7, 10), (2, 7, 99)])
    problems = gate.compare_completed_weeks(
        new,
        previous,
        outcomes_frame([(1, 31, 24)]),
        outcomes_frame([(1, 31, 24)]),
        through_week=7,
    )
    assert problems == ["games: game 2 changed columns ['venue_id']"]


def test_stop_gate_ignores_changes_above_the_through_week():
    new = games_frame([(1, 7, 10), (2, 8, 11)])
    previous = games_frame([(1, 7, 10), (2, 8, 99)])
    outcomes = outcomes_frame([(1, 31, 24), (2, 17, 13)])
    assert (
        gate.compare_completed_weeks(
            new, previous, outcomes, outcomes.copy(), through_week=7
        )
        == []
    )


def test_stop_gate_reports_a_lost_completed_game_and_finals_change():
    new = games_frame([(1, 7, 10)])
    previous = games_frame([(1, 7, 10), (2, 7, 11)])
    new_outcomes = outcomes_frame([(1, 31, 24)])
    previous_outcomes = outcomes_frame([(1, 31, 21), (2, 17, 13)])
    problems = gate.compare_completed_weeks(
        new, previous, new_outcomes, previous_outcomes, through_week=7
    )
    assert problems == [
        "games: game 2 is missing from the new completed-week scope",
        "game_outcomes: game 2 lost its certified finals row",
        "game_outcomes: game 1 changed columns ['away_points']",
    ]


def test_stop_gate_reports_a_new_completed_game():
    new = games_frame([(1, 7, 10), (3, 7, 12)])
    previous = games_frame([(1, 7, 10)])
    outcomes = outcomes_frame([(1, 31, 24), (3, 10, 7)])
    previous_outcomes = outcomes_frame([(1, 31, 24)])
    problems = gate.compare_completed_weeks(
        new, previous, outcomes, previous_outcomes, through_week=7
    )
    assert problems == ["games: game 3 is new in the completed-week scope"]


def test_ref_from_input_parses_the_manifest_entry():
    ref = gate._ref_from_input(
        "games",
        {
            "uri": "lake/silver/dataset=games/version=abc/data.parquet",
            "sha256": SHA,
        },
    )
    assert ref.dataset == "games"
    assert ref.version_id == "abc"
    assert ref.content_sha == SHA
    assert ref.schema_version == SILVER_CONTRACTS["games"].schema_version
