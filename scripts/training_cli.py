#!/usr/bin/env python3
"""Training CLI wrapping model training, grid search, and bankroll simulation."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import typer
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import ElasticNet, HuberRegressor, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.config import METRICS_SUBDIR, REPORTS_DIR, get_data_root
from src.models.features import (
    build_differential_feature_list,
    build_differential_features,
    generate_point_in_time_features,
)

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
        None, "--model-dir", help="Directory for saving trained models."
    ),
    metrics_dir: Path = typer.Option(
        None, "--metrics-dir", help="Directory for evaluation metrics."
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
    if model_dir:
        args.extend(["--model-dir", str(model_dir)])
    if metrics_dir:
        args.extend(["--metrics-dir", str(metrics_dir)])
    cmd = [sys.executable, "-m", "src.models.train_model", *args]
    subprocess.run(cmd, check=True)


@dataclass
class Metrics:
    rmse: float
    mae: float


def _evaluate(y_true: np.ndarray, y_pred: np.ndarray) -> Metrics:
    from sklearn.metrics import mean_absolute_error, mean_squared_error

    return Metrics(
        rmse=float(np.sqrt(mean_squared_error(y_true, y_pred))),
        mae=float(mean_absolute_error(y_true, y_pred)),
    )


def _generate_point_in_time(years: list[int], data_root: str | None) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for year in years:
        typer.echo(f"Generating features for year {year}")
        for week in range(1, 16):
            try:
                frames.append(generate_point_in_time_features(year, week, data_root))
            except ValueError as exc:
                typer.echo(f"  Skipping week {week}: {exc}")
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


@app.command()
def differential(
    train_years: str = typer.Option(
        "2019,2021,2022,2023",
        "--train-years",
        help="Comma-separated training years",
    ),
    test_year: int = typer.Option(2024, "--test-year", help="Holdout/test year"),
    data_root: Path = typer.Option(
        None, "--data-root", help="Data root (defaults to config helper)."
    ),
    model_dir: Path = typer.Option(
        Path("./models/differential"),
        "--model-dir",
        help="Directory to store trained models.",
    ),
    metrics_dir: Path = typer.Option(
        REPORTS_DIR / METRICS_SUBDIR,
        "--metrics-dir",
        help="Directory to store evaluation metrics.",
    ),
) -> None:
    """Train spread & total models using differential features."""
    train_year_list = [int(y.strip()) for y in train_years.split(",") if y.strip()]
    resolved_root = str(data_root) if data_root else None

    train_df = _generate_point_in_time(train_year_list, resolved_root)
    test_df = _generate_point_in_time([test_year], resolved_root)
    if train_df.empty or test_df.empty:
        raise typer.BadParameter("Insufficient data to train differential models.")

    typer.echo("Building differential features...")
    train_df = build_differential_features(train_df)
    test_df = build_differential_features(test_df)

    feature_list = build_differential_feature_list(train_df)
    feature_list = [c for c in feature_list if c in test_df.columns]
    target_cols = ["spread_target", "total_target"]
    train_df = train_df.dropna(subset=feature_list + target_cols)
    test_df = test_df.dropna(subset=feature_list + target_cols)

    x_train = train_df[feature_list]
    y_spread_train = train_df["spread_target"].astype(float)
    y_total_train = train_df["total_target"].astype(float)
    x_test = test_df[feature_list]
    y_spread_test = test_df["spread_target"].astype(float)
    y_total_test = test_df["total_target"].astype(float)

    out_dir = Path(model_dir) / str(test_year)
    out_dir.mkdir(parents=True, exist_ok=True)

    spread_models = {
        "spread_ridge": Ridge(alpha=0.1),
        "spread_elastic_net": ElasticNet(alpha=0.1, l1_ratio=0.5, random_state=42),
        "spread_huber": Pipeline(
            [
                ("scaler", StandardScaler()),
                ("huber", HuberRegressor(epsilon=1.35, max_iter=500)),
            ]
        ),
    }
    total_models = {
        "total_random_forest": RandomForestRegressor(
            n_estimators=200,
            max_depth=8,
            min_samples_split=10,
            min_samples_leaf=5,
            random_state=42,
        ),
        "total_gradient_boosting": GradientBoostingRegressor(
            n_estimators=200,
            learning_rate=0.1,
            max_depth=6,
            subsample=0.8,
            random_state=42,
        ),
    }

    typer.echo("Training spread models...")
    for name, model in spread_models.items():
        typer.echo(f"  {name}")
        model.fit(x_train, y_spread_train)
        joblib.dump(model, out_dir / f"{name}.joblib")

    typer.echo("Training total models...")
    for name, model in total_models.items():
        typer.echo(f"  {name}")
        model.fit(x_train, y_total_train)
        joblib.dump(model, out_dir / f"{name}.joblib")

    spread_preds = [
        joblib.load(out_dir / f"{name}.joblib").predict(x_test)
        for name in spread_models
    ]
    total_preds = [
        joblib.load(out_dir / f"{name}.joblib").predict(x_test) for name in total_models
    ]

    spread_metrics = _evaluate(y_spread_test.to_numpy(), np.mean(spread_preds, axis=0))
    total_metrics = _evaluate(y_total_test.to_numpy(), np.mean(total_preds, axis=0))

    metrics_dir = Path(metrics_dir)
    metrics_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = metrics_dir / f"model_eval_differential_{test_year}.csv"
    pd.DataFrame(
        [
            {
                "target": "spread",
                "rmse": spread_metrics.rmse,
                "mae": spread_metrics.mae,
            },
            {"target": "total", "rmse": total_metrics.rmse, "mae": total_metrics.mae},
        ]
    ).to_csv(metrics_path, index=False)
    typer.echo(f"Metrics saved to {metrics_path}")


if __name__ == "__main__":
    app()
