"""Incremental close/open: carried-capture resolution and the history stop gate.

Local storage and frames only; no database or network.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from cks_picks_cfb.data.silver import SILVER_CONTRACTS
from cks_picks_cfb.data.storage.local import LocalStorage
from scripts.pipeline import verify_completed_week_stability as gate
from scripts.pipeline.build_season_revision import (
    carried_capture_ids,
    latest_previous_manifest,
    require_completed_weeks,
)

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


def elo_games_frame(
    rows: list[tuple[int, int, str, float, float, float, float]],
) -> pd.DataFrame:
    """game_id, week, capture id, pregame/postgame Elo for home and away."""
    return pd.DataFrame(
        rows,
        columns=[
            "game_id",
            "week",
            "__capture_id",
            "home_pregame_elo",
            "away_pregame_elo",
            "home_postgame_elo",
            "away_postgame_elo",
        ],
    )


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


def test_stop_gate_ignores_provenance_and_postgame_elo_drift():
    """The two observed drift sources: re-stamped provenance and CFBD's Elo recompute."""
    new = elo_games_frame([(1, 7, "cap-new", 1121.0, 1252.0, 1104.0, 1269.0)])
    previous = elo_games_frame([(1, 7, "cap-old", 1121.0, 1252.0, 1094.0, 1279.0)])
    outcomes = outcomes_frame([(1, 31, 24)])
    assert (
        gate.compare_completed_weeks(
            new, previous, outcomes, outcomes.copy(), through_week=7
        )
        == []
    )


def test_stop_gate_still_stops_on_pregame_elo_drift():
    new = elo_games_frame([(1, 7, "cap-new", 1121.0, 1252.0, 1104.0, 1269.0)])
    previous = elo_games_frame([(1, 7, "cap-new", 1111.0, 1252.0, 1104.0, 1269.0)])
    outcomes = outcomes_frame([(1, 31, 24)])
    problems = gate.compare_completed_weeks(
        new, previous, outcomes, outcomes.copy(), through_week=7
    )
    assert problems == ["games: game 1 changed columns ['home_pregame_elo']"]


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
    assert problems == [
        "games: game 3 is new in the completed-week scope",
        "game_outcomes: game 3 has a finals row that the certified previous "
        "outcomes lack",
    ]


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


def test_stop_gate_reports_a_new_finals_row_for_a_shared_game():
    games = games_frame([(1, 6, 10), (2, 6, 11)])
    problems = gate.compare_completed_weeks(
        games,
        games.copy(),
        outcomes_frame([(1, 31, 24), (2, 17, 13)]),
        outcomes_frame([(1, 31, 24)]),
        through_week=7,
    )
    assert problems == [
        "game_outcomes: game 2 has a finals row that the certified previous "
        "outcomes lack"
    ]


def test_stop_gate_reports_a_column_added_on_one_side():
    new = games_frame([(1, 7, 10)]).assign(neutral_site=True)
    previous = games_frame([(1, 7, 10)])
    outcomes = outcomes_frame([(1, 31, 24)])
    problems = gate.compare_completed_weeks(
        new, previous, outcomes, outcomes.copy(), through_week=7
    )
    assert problems == ["games: column neutral_site exists only in the new data"]


def test_stop_gate_compares_a_shared_added_column():
    new = games_frame([(1, 7, 10)]).assign(neutral_site=True)
    previous = games_frame([(1, 7, 10)]).assign(neutral_site=False)
    outcomes = outcomes_frame([(1, 31, 24)])
    problems = gate.compare_completed_weeks(
        new, previous, outcomes, outcomes.copy(), through_week=7
    )
    assert problems == ["games: game 1 changed columns ['neutral_site']"]


def test_stop_gate_ignores_excluded_columns_present_on_one_side_only():
    new = elo_games_frame([(1, 7, "cap-new", 1121.0, 1252.0, 1104.0, 1269.0)])
    previous = new[["game_id", "week", "home_pregame_elo", "away_pregame_elo"]]
    outcomes = outcomes_frame([(1, 31, 24)])
    assert (
        gate.compare_completed_weeks(
            new, previous, outcomes, outcomes.copy(), through_week=7
        )
        == []
    )


def test_stop_gate_cli_requires_an_explicit_environment(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "gate",
            "--new-games-ref",
            "a",
            "--new-outcomes-ref",
            "b",
            "--previous-games",
            "{}",
            "--previous-outcomes",
            "{}",
            "--through-week",
            "7",
        ],
    )
    with pytest.raises(SystemExit) as exit_info:
        gate.main()
    assert exit_info.value.code == 2


def test_latest_previous_manifest_picks_the_highest_version(tmp_path):
    for version in (1, 2, 3, 10):
        (tmp_path / f"revision_manifest_w8_v{version}.json").write_text("{}")
    (tmp_path / "revision_manifest_w7_v9.json").write_text("{}")
    assert latest_previous_manifest(tmp_path, 8).name == "revision_manifest_w8_v10.json"


def test_latest_previous_manifest_accepts_a_single_v1(tmp_path):
    (tmp_path / "revision_manifest_w8_v1.json").write_text("{}")
    assert latest_previous_manifest(tmp_path, 8).name == "revision_manifest_w8_v1.json"


def test_latest_previous_manifest_refuses_when_none_exist(tmp_path):
    (tmp_path / "revision_manifest_w7_v1.json").write_text("{}")
    with pytest.raises(FileNotFoundError, match="revision_manifest_w8_v<k>"):
        latest_previous_manifest(tmp_path, 8)


def test_require_completed_weeks_names_a_missing_week():
    frames = {
        "plays": pd.DataFrame({"week": [0, 1, 3]}),
        "team_game_stats": pd.DataFrame({"week": [0, 1, 2, 3]}),
    }
    with pytest.raises(LookupError, match="plays Silver has no rows.*week 2"):
        require_completed_weeks(frames, 3)


def test_require_completed_weeks_accepts_full_coverage():
    frames = {
        "plays": pd.DataFrame({"week": [0, 1, 2, 3, 4]}),
        "team_game_stats": pd.DataFrame({"week": [0, 1, 2, 3]}),
    }
    require_completed_weeks(frames, 3)


def test_committed_week_9_manifest_passes_the_repo_loaders():
    from cks_picks_cfb.season.inputs import score_exceptions

    manifest = json.loads(
        Path("conf/season/2026/revision_manifest_w9_v1.json").read_text()
    )
    assert score_exceptions(manifest)
