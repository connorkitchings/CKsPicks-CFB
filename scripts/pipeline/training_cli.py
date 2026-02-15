#!/usr/bin/env python3
"""Training CLI wrapping model training, grid search, and bankroll simulation."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import typer

from cks_picks_cfb.config import MODELS_DIR, get_data_root

app = typer.Typer(help="Model training and tuning utilities.")


@app.command()
def train(
    train_years: str = typer.Option(
        "2019,2021,2022,2023",
        "--train-years",
        help="Comma-separated list of years to train on.",
    ),
    test_year: int = typer.Option(2024, "--test-year", help="Holdout year."),
    data_root: Path = typer.Option(
        None,
        "--data-root",
        help="Data root directory (defaults to config helper).",
    ),
    model_dir: Path = typer.Option(
        Path(MODELS_DIR),
        "--model-dir",
        help="Directory for saving trained models.",
    ),
    metrics_dir: Path = typer.Option(
        None, "--metrics-dir", help="Directory for evaluation metrics."
    ),
    adjustment_iteration: int = typer.Option(
        4,
        "--adjustment-iteration",
        help="Opponent-adjustment iteration depth to load from weekly caches (default: 4).",
    ),
    offense_adjustment_iteration: int | None = typer.Option(
        None,
        "--offense-adjustment-iteration",
        help="Override offensive feature adjustment depth; defaults to --adjustment-iteration.",
    ),
    defense_adjustment_iteration: int | None = typer.Option(
        None,
        "--defense-adjustment-iteration",
        help="Override defensive feature adjustment depth; defaults to --adjustment-iteration.",
    ),
) -> None:
    """Invoke the standard training pipeline defined in src.models.train_model."""
    resolved_data_root = str(data_root or get_data_root())
    args = [
        "--train-years",
        train_years,
        "--test-year",
        str(test_year),
        "--data-root",
        resolved_data_root,
    ]
    if adjustment_iteration is not None:
        args.extend(["--adjustment-iteration", str(adjustment_iteration)])
    if offense_adjustment_iteration is not None:
        args.extend(
            ["--offense-adjustment-iteration", str(offense_adjustment_iteration)]
        )
    if defense_adjustment_iteration is not None:
        args.extend(
            ["--defense-adjustment-iteration", str(defense_adjustment_iteration)]
        )
    if model_dir:
        args.extend(["--model-dir", str(model_dir)])
    if metrics_dir:
        args.extend(["--metrics-dir", str(metrics_dir)])
    cmd = [sys.executable, "-m", "src.models.train_model", *args]
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    app()
