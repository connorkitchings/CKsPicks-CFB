"""Smoke and integration tests for scripts/pipeline/generate_weekly_bets.py CLI."""

from unittest.mock import patch

import pandas as pd
import pytest
from omegaconf import OmegaConf

from scripts.pipeline.generate_weekly_bets import main


def test_cli_help_flag(capsys):
    """Verify that --help exits cleanly with status 0."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "Generate Weekly Bets" in captured.out


def test_cli_invalid_config():
    """Verify that a missing config file raises an appropriate exception."""
    with patch("scripts.pipeline.generate_weekly_bets.OmegaConf.load") as load:
        load.side_effect = FileNotFoundError("missing config")
        with pytest.raises(FileNotFoundError):
            main(
                [
                    "--config",
                    "nonexistent_config_file_12345.yaml",
                    "--year",
                    "2026",
                    "--week",
                    "1",
                ]
            )


def test_cli_generates_a_valid_bundle_prediction_with_in_memory_inputs(tmp_path):
    """Exercise the successful no-network route through parsing, routing, and CSV output."""
    config = OmegaConf.create(
        {
            "year": 2026,
            "week": 0,
            "spread_edge_threshold": 1.0,
            "total_edge_threshold": 1.0,
            "model_bundle_v2": {"artifact_uri": "bundle", "sha256": "x" * 64},
            "system_name": "Fixture",
            "model_id": "fixture-v1",
        }
    )
    refs = [
        {
            "entity": "point_in_time_matchups",
            "year": 2026,
            "dataset": "point_in_time_matchups",
            "version_id": "gold",
            "schema_version": "v1",
            "content_sha": "a" * 64,
            "uri": "gold",
        },
        {
            "entity": "betting_lines",
            "year": 2026,
            "dataset": "betting_lines",
            "version_id": "market",
            "schema_version": "v1",
            "content_sha": "b" * 64,
            "uri": "market",
        },
        {
            "entity": "games",
            "year": 2026,
            "dataset": "games",
            "version_id": "schedule",
            "schema_version": "v1",
            "content_sha": "c" * 64,
            "uri": "schedule",
        },
    ]
    frames = {
        "gold": pd.DataFrame(
            {
                "game_id": [1],
                "season": [2026],
                "week": [0],
                "home_team": ["Home"],
                "away_team": ["Away"],
                "start_date": ["2026-08-29T19:30:00Z"],
                "prediction_regime": ["established"],
                "home_current_season_games": [4],
                "away_current_season_games": [4],
            }
        ),
        "market": pd.DataFrame(
            {
                "game_id": [1],
                "captured_at": ["2026-08-28T19:30:00Z"],
                "spread": [-2.5],
                "total": [51.5],
                "market_snapshot_id": ["snapshot"],
            }
        ),
        "schedule": pd.DataFrame({"game_id": [1], "season": [2026], "week": [0]}),
    }

    class Storage:
        def read_bytes(self, _: str) -> bytes:
            import json

            return json.dumps(refs).encode()

    class Bundle:
        manifest_sha256 = "d" * 64

    def read_dataset(_: object, ref: object) -> pd.DataFrame:
        return frames[getattr(ref, "version_id")]

    def predict(_: object, features: pd.DataFrame, **__: object) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "predicted_spread": [3.5] * len(features),
                "predicted_total": [52.0] * len(features),
                "spread_model_version": ["fixture-spread"] * len(features),
                "total_model_version": ["fixture-total"] * len(features),
                "spread_high_confidence_eligible": [True] * len(features),
                "total_high_confidence_eligible": [True] * len(features),
            }
        )

    output = tmp_path / "bets.csv"
    with (
        patch(
            "scripts.pipeline.generate_weekly_bets.OmegaConf.load", return_value=config
        ),
        patch("scripts.pipeline.generate_weekly_bets.setup_mlflow"),
        patch(
            "scripts.pipeline.generate_weekly_bets.get_storage", return_value=Storage()
        ),
        patch(
            "scripts.pipeline.generate_weekly_bets.load_model_bundle_v2",
            return_value=Bundle(),
        ),
        patch(
            "scripts.pipeline.generate_weekly_bets.read_dataset",
            side_effect=read_dataset,
        ),
        patch(
            "scripts.pipeline.generate_weekly_bets.predict_with_model_bundle_v2",
            side_effect=predict,
        ),
    ):
        main(
            [
                "--config",
                "fixture.yaml",
                "--dataset-refs-uri",
                "fixture-refs.json",
                "--output-csv",
                str(output),
                "--run-id",
                "fixture-run",
            ]
        )

    result = pd.read_csv(output)
    assert result["game_id"].tolist() == [1]
    assert result["run_id"].tolist() == ["fixture-run"]
    assert result["Spread Prediction"].tolist() == [3.5]
    assert result["Total Prediction"].tolist() == [52.0]
