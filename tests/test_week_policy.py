"""Tests for the versioned canonical-week policy module."""

import pandas as pd
import pytest
import yaml

from cks_picks_cfb.data.week_policy import (
    WeekAssignment,
    WeekPolicySpec,
    build_policy_rows,
    canonical_week_overrides_for_season,
    load_week_policy_spec,
)


def _write_policy(tmp_path, *, policy_version="canonical_week_2026_v1", season=2026):
    payload = {
        "policy_version": policy_version,
        "season": season,
        "assignments": [
            {
                "game_id": 100,
                "kickoff_utc": "2026-08-29T16:00:00Z",
                "canonical_week": 0,
            }
        ],
    }
    path = tmp_path / "policy.yaml"
    path.write_text(yaml.safe_dump(payload))
    return path


def test_load_week_policy_spec_validates(tmp_path):
    path = _write_policy(tmp_path)
    spec = load_week_policy_spec(path)
    assert spec.policy_version == "canonical_week_2026_v1"
    assert spec.season == 2026
    assert len(spec.assignments) == 1
    assert spec.assignments[0].game_id == 100
    assert spec.assignments[0].canonical_week == 0


def test_canonical_week_overrides_are_loaded_from_versioned_policy(tmp_path):
    path = _write_policy(tmp_path)
    path.rename(tmp_path / "canonical_week_2026_v1.yaml")

    assert canonical_week_overrides_for_season(2026, policy_directory=tmp_path) == {
        100: 0
    }


def test_load_week_policy_spec_rejects_duplicate_game(tmp_path):
    payload = {
        "policy_version": "v1",
        "season": 2026,
        "assignments": [
            {
                "game_id": 100,
                "kickoff_utc": "2026-08-29T16:00:00Z",
                "canonical_week": 0,
            },
            {
                "game_id": 100,
                "kickoff_utc": "2026-08-29T19:00:00Z",
                "canonical_week": 0,
            },
        ],
    }
    path = tmp_path / "dup.yaml"
    path.write_text(yaml.safe_dump(payload))
    with pytest.raises(ValueError, match="Duplicate"):
        load_week_policy_spec(path)


def test_build_policy_rows_assigns_canonical_weeks():
    games = pd.DataFrame(
        [
            {
                "season": 2026,
                "game_id": 100,
                "provider_week": 1,
                "kickoff_utc": pd.Timestamp("2026-08-29T16:00:00Z"),
            },
            {
                "season": 2026,
                "game_id": 200,
                "provider_week": 1,
                "kickoff_utc": pd.Timestamp("2026-08-29T19:00:00Z"),
            },
            {
                "season": 2026,
                "game_id": 300,
                "provider_week": 2,
                "kickoff_utc": pd.Timestamp("2026-09-05T16:00:00Z"),
            },
        ]
    )
    spec = WeekPolicySpec(
        policy_version="v1",
        season=2026,
        assignments=(
            WeekAssignment(
                game_id=100,
                kickoff_utc=pd.Timestamp("2026-08-29T16:00:00Z"),
                canonical_week=0,
            ),
        ),
    )
    rows = build_policy_rows(games, spec, season=2026)
    assert len(rows) == 3
    by_game = rows.set_index("game_id")
    assert by_game.loc[100, "canonical_week"] == 0
    assert by_game.loc[100, "provider_week"] == 1
    assert by_game.loc[200, "canonical_week"] == 1
    assert by_game.loc[300, "canonical_week"] == 2


def test_build_policy_rows_rejects_unknown_game():
    games = pd.DataFrame(
        [
            {
                "season": 2026,
                "game_id": 100,
                "provider_week": 1,
                "kickoff_utc": pd.Timestamp("2026-08-29T16:00:00Z"),
            }
        ]
    )
    spec = WeekPolicySpec(
        policy_version="v1",
        season=2026,
        assignments=(
            WeekAssignment(
                game_id=999,
                kickoff_utc=pd.Timestamp("2026-08-29T16:00:00Z"),
                canonical_week=0,
            ),
        ),
    )
    with pytest.raises(ValueError, match="unknown game"):
        build_policy_rows(games, spec, season=2026)


def test_build_policy_rows_rejects_kickoff_mismatch():
    games = pd.DataFrame(
        [
            {
                "season": 2026,
                "game_id": 100,
                "provider_week": 1,
                "kickoff_utc": pd.Timestamp("2026-08-29T16:00:00Z"),
            }
        ]
    )
    spec = WeekPolicySpec(
        policy_version="v1",
        season=2026,
        assignments=(
            WeekAssignment(
                game_id=100,
                kickoff_utc=pd.Timestamp("2026-08-30T02:00:00Z"),
                canonical_week=0,
            ),
        ),
    )
    with pytest.raises(ValueError, match="kickoff"):
        build_policy_rows(games, spec, season=2026)


def test_build_policy_rows_rejects_wrong_season():
    games = pd.DataFrame(
        [
            {
                "season": 2026,
                "game_id": 100,
                "provider_week": 1,
                "kickoff_utc": pd.Timestamp("2026-08-29T16:00:00Z"),
            }
        ]
    )
    spec = WeekPolicySpec(policy_version="v1", season=2025, assignments=())
    with pytest.raises(ValueError, match="season"):
        build_policy_rows(games, spec, season=2026)
