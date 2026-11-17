"""Boundary tests for the read-only ratings audit command."""

import hashlib
import json
from datetime import UTC, datetime

import pytest

from scripts.analysis.audit_v5_ratings import (
    prepared_manifests,
    require_environment,
    serving_comparisons,
)


def test_requires_explicit_r2_backend(monkeypatch):
    monkeypatch.delenv("CFB_STORAGE_BACKEND", raising=False)
    with pytest.raises(ValueError, match="explicitly equal r2"):
        require_environment()


def test_manifest_must_match_captured_release(tmp_path):
    path = tmp_path / "run-manifest.json"
    path.write_text(json.dumps({"output_refs": {}}))
    snapshot = {"releases": {"x": {"run_manifest_sha256": "0" * 64}}}
    with pytest.raises(ValueError, match="captured release"):
        prepared_manifests([path], snapshot)


def test_missing_prepared_output_is_unavailable(tmp_path):
    path = tmp_path / "run-manifest.json"
    path.write_text(
        json.dumps(
            {
                "output_refs": {
                    "features": {"uri": "/missing/features.parquet", "sha256": "0" * 64}
                }
            }
        )
    )
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    snapshot = {"releases": {"x": {"release_id": "x", "run_manifest_sha256": digest}}}
    assert (
        prepared_manifests([path], snapshot)["x"]["outputs"]["features"]["status"]
        == "unavailable"
    )


def test_period_selection_and_preseason_fallback():
    kickoff = datetime(2026, 9, 1, tzinfo=UTC)
    earlier = datetime(2026, 8, 31, tzinfo=UTC)

    def row(team, cutoff, snapshot_id, kind, rating):
        return {
            "team": team,
            "cutoff_utc": cutoff,
            "snapshot_id": snapshot_id,
            "snapshot_class": kind,
            "source_manifest_sha256": "s",
            "week": 1,
            "offense_rating": rating,
            "defense_rating": rating,
        }

    release = {
        "selected_source": {"rating_manifest_sha256": "s"},
        "tables": {
            "games": [
                {
                    "game_id": 1,
                    "week": 1,
                    "start_date": kickoff,
                    "home_team": "Georgia",
                    "away_team": "Florida",
                }
            ],
            "predictions": [{"game_id": 1}],
            "v5_rating_snapshots": [
                row("Georgia", earlier, "current", "current", 2),
                row("Florida", earlier, "x:preseason", "pregame", 3),
                row("Georgia", earlier, "pregame", "pregame", 2),
            ],
        },
    }
    game = serving_comparisons(release, None)["games"][0]
    assert game["period_cutoff"] is not None
    assert game["teams"]["home"]["source"] == "current"
    assert game["teams"]["away"]["source"] == "preseason"
    assert game["original_features"]["status"] == "unavailable"


def test_input_output_collision_rejected(tmp_path):
    from scripts.analysis.audit_v5_ratings import parse_args

    manifest = tmp_path / "model.json"
    with pytest.raises(SystemExit):
        parse_args(
            [
                "--model-manifest",
                str(manifest),
                "--revision-manifest",
                str(tmp_path / "revision.json"),
                "--score-exceptions-git-ref",
                "a" * 40,
                "--environment",
                "production",
                "--last-pregame-week",
                "9",
                "--report",
                str(manifest),
                "--evidence",
                str(tmp_path / "evidence.json"),
            ]
        )


def test_pregame_discrepancy_is_not_hidden_by_missing_features():
    kickoff = datetime(2026, 9, 1, tzinfo=UTC)
    earlier = datetime(2026, 8, 31, tzinfo=UTC)

    def row(team, snapshot_id, kind, rating):
        return {
            "team": team,
            "cutoff_utc": earlier,
            "snapshot_id": snapshot_id,
            "snapshot_class": kind,
            "source_manifest_sha256": "s",
            "week": 1,
            "offense_rating": rating,
            "defense_rating": rating,
        }

    release = {
        "selected_source": {"rating_manifest_sha256": "s"},
        "tables": {
            "games": [
                {
                    "game_id": 1,
                    "week": 1,
                    "start_date": kickoff,
                    "home_team": "Georgia",
                    "away_team": "Florida",
                }
            ],
            "predictions": [{"game_id": 1}],
            "v5_rating_snapshots": [
                row("Georgia", "current", "current", 2),
                row("Florida", "current", "current", 2),
                row("Georgia", "pregame", "pregame", 100),
                row("Florida", "pregame", "pregame", 2),
            ],
        },
    }
    result = serving_comparisons(release, None)
    assert result["status"] == "discrepancy"
    assert result["games"][0]["serving_vs_projected_pregame"] == "discrepancy"


def test_verified_original_ratings_mismatch_sets_discrepancy(tmp_path):
    import pandas as pd

    kickoff = datetime(2026, 9, 1, tzinfo=UTC)
    earlier = datetime(2026, 8, 31, tzinfo=UTC)

    def row(team, kind, value):
        return {
            "team": team,
            "cutoff_utc": earlier,
            "snapshot_id": kind + team,
            "snapshot_class": kind,
            "source_manifest_sha256": "s",
            "week": 1,
            "offense_rating": value,
            "defense_rating": value,
        }

    release = {
        "selected_source": {"rating_manifest_sha256": "s"},
        "tables": {
            "games": [
                {
                    "game_id": 1,
                    "week": 1,
                    "start_date": kickoff,
                    "home_team": "Georgia",
                    "away_team": "Florida",
                }
            ],
            "predictions": [
                {"game_id": 1, "predicted_spread": 0, "predicted_total": 1}
            ],
            "v5_rating_snapshots": [
                row(team, kind, 2)
                for team in ("Georgia", "Florida")
                for kind in ("current", "pregame")
            ],
        },
    }
    features_path, ratings_path = (
        tmp_path / "features.parquet",
        tmp_path / "ratings.parquet",
    )
    pd.DataFrame(
        [
            {
                "game_id": 1,
                "home_offense": 2,
                "home_defense": 2,
                "away_offense": 2,
                "away_defense": 2,
            }
        ]
    ).to_parquet(features_path)
    pd.DataFrame(
        [
            {
                "target_week": 1,
                "team": "Georgia",
                "offense_rating": 100,
                "defense_rating": 2,
            },
            {
                "target_week": 1,
                "team": "Florida",
                "offense_rating": 2,
                "defense_rating": 2,
            },
        ]
    ).to_parquet(ratings_path)
    prepared = {
        "outputs": {
            "features": {
                "status": "verified",
                "path": str(features_path),
                "sha256": "a",
            },
            "ratings": {"status": "verified", "path": str(ratings_path), "sha256": "b"},
        }
    }
    result = serving_comparisons(release, prepared)
    assert result["games"][0]["original_features"]["status"] == "agreement"
    assert result["games"][0]["original_ratings"]["status"] == "discrepancy"
    assert result["status"] == "discrepancy"
