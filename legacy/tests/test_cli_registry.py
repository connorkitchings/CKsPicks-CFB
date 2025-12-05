import json
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from scripts import cli
from scripts.analysis import analysis_cli


def test_plan_ingestion_sequence_default_order():
    tasks = cli.plan_ingestion_sequence(None, None)
    assert [task.key for task in tasks] == cli.DEFAULT_INGESTION_ORDER


def test_plan_ingestion_sequence_only_subset():
    tasks = cli.plan_ingestion_sequence(["plays", "games"], None)
    assert [task.key for task in tasks] == ["plays", "games"]


def test_plan_ingestion_sequence_skip():
    tasks = cli.plan_ingestion_sequence(None, ["plays"])
    assert "plays" not in [task.key for task in tasks]


def test_plan_ingestion_sequence_unknown_raises():
    with pytest.raises(ValueError):
        cli.plan_ingestion_sequence(["unknown"], None)


def test_build_ingest_kwargs_week_alias_for_plays():
    task = cli.INGESTION_REGISTRY["plays"]
    kwargs = cli.build_ingest_kwargs(
        task,
        year=2024,
        data_root="/tmp",
        season_type="regular",
        week=3,
        limit_games=5,
        limit_teams=None,
        storage="storage",
    )
    assert kwargs["only_week"] == 3
    assert kwargs["limit_games"] == 5
    assert kwargs["storage"] == "storage"


def test_build_ingest_kwargs_ignores_week_when_not_supported():
    task = cli.INGESTION_REGISTRY["teams"]
    kwargs = cli.build_ingest_kwargs(
        task,
        year=2024,
        data_root="/tmp",
        season_type="regular",
        week=7,
        limit_games=None,
        limit_teams=None,
    )
    assert "week" not in kwargs


def test_cli_ingest_year_dry_run(tmp_path):
    (tmp_path / "data-root" / "raw").mkdir(parents=True)
    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "ingest-year",
            "2024",
            "--dry-run",
            "--data-root",
            str(tmp_path / "data-root"),
            "--only",
            "teams",
        ],
    )
    assert result.exit_code == 0
    assert "Ingestion plan: teams" in result.stdout
    assert "Dry run requested" in result.stdout


def test_cli_ingest_year_failure_is_reported(tmp_path, monkeypatch):
    (tmp_path / "data-root" / "raw").mkdir(parents=True)
    runner = CliRunner()

    def _raise_on_run(task, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli, "run_ingester", _raise_on_run)
    result = runner.invoke(
        cli.app,
        [
            "ingest-year",
            "2024",
            "--data-root",
            str(tmp_path / "data-root"),
            "--only",
            "teams",
        ],
    )
    assert result.exit_code == 0
    assert "Error during TeamsIngester: boom" in result.stdout


def _write_scored(tmp_path, filename="scored.csv") -> Path:
    data = pd.DataFrame(
        {
            "Week": [1, 1, 2],
            "Spread Bet": ["home", "away", "none"],
            "Spread Bet Result": ["Win", "Loss", "Push"],
            "Total Bet": ["over", "under", "none"],
            "Total Bet Result": ["Win", "Loss", "Push"],
            "edge_spread": [6.5, 6.2, 4.0],
            "predicted_spread_std_dev": [1.2, 2.1, 3.0],
        }
    )
    path = tmp_path / filename
    data.to_csv(path, index=False)
    return path


def test_analysis_split(tmp_path):
    scored_path = _write_scored(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        analysis_cli.app,
        [
            "split",
            str(scored_path),
            "--output-dir",
            str(tmp_path / "out"),
        ],
    )
    assert result.exit_code == 0
    summary_file = tmp_path / "out" / "season_summary.json"
    assert summary_file.exists()
    summary = json.loads(summary_file.read_text())
    assert "spread_overall" in summary


def test_analysis_confidence(tmp_path):
    scored_path = _write_scored(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        analysis_cli.app,
        [
            "confidence",
            str(scored_path),
            "--bet-type",
            "spread",
            "--edge-threshold",
            "6",
            "--std-dev",
            "1.0",
            "--std-dev",
            "2.5",
        ],
    )
    assert result.exit_code == 0
    rows = json.loads(result.stdout)
    assert isinstance(rows, list)
    assert rows[0]["threshold"] == 1.0
