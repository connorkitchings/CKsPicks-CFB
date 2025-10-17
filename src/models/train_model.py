"""Model training CLI.

Loads opponent-adjusted team-season features, merges with games, builds
feature matrices for spread and total targets, trains the specified models, and
emits metrics/artifacts.
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Iterable
from dataclasses import dataclass

import joblib
import numpy as np
import pandas as pd
import mlflow
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import ElasticNet, HuberRegressor, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.models.features import (
    build_feature_list,
    generate_point_in_time_features,
)
from src.config import get_data_root, MODELS_DIR, REPORTS_DIR


def _prepare_team_features(team_season_adj_df: pd.DataFrame) -> pd.DataFrame:
    base_cols = ["season", "team", "games_played"]
    off_metric_cols = [
        c for c in team_season_adj_df.columns if c.startswith("adj_off_")
    ]
    for extra in [
        "off_eckel_rate",
        "off_finish_pts_per_opp",
        "stuff_rate",
        "havoc_rate",
    ]:
        if extra in team_season_adj_df.columns:
            off_metric_cols.append(extra)
    def_metric_cols = [
        c for c in team_season_adj_df.columns if c.startswith("adj_def_")
    ]
    off_df = team_season_adj_df[base_cols + off_metric_cols].copy()
    if off_metric_cols:
        off_df = off_df.dropna(subset=off_metric_cols, how="all")
    def_df = team_season_adj_df[base_cols + def_metric_cols].copy()
    if def_metric_cols:
        def_df = def_df.dropna(subset=def_metric_cols, how="all")
    combined = off_df.merge(
        def_df, on=["season", "team"], how="outer", suffixes=("", "_defside")
    )
    if "games_played_x" in combined.columns or "games_played_y" in combined.columns:
        combined["games_played"] = combined[
            [c for c in ["games_played_x", "games_played_y"] if c in combined.columns]
        ].max(axis=1, skipna=True)
        combined = combined.drop(
            columns=[
                c for c in ["games_played_x", "games_played_y"] if c in combined.columns
            ]
        )
    return combined


def _build_feature_list(df: pd.DataFrame) -> list[str]:
    return build_feature_list(df)


@dataclass
class Metrics:
    rmse: float
    mae: float


def _evaluate(y_true: np.ndarray, y_pred: np.ndarray) -> Metrics:
    return Metrics(
        rmse=float(np.sqrt(mean_squared_error(y_true, y_pred))),
        mae=float(mean_absolute_error(y_true, y_pred)),
    )


def _concat_years(dfs: Iterable[pd.DataFrame]) -> pd.DataFrame:
    frames = [df for df in dfs if df is not None and not df.empty]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def main() -> None:
    """CLI entrypoint for training models."""
    parser = argparse.ArgumentParser(description="Train and evaluate ensemble models.")
    parser.add_argument(
        "--train-years",
        type=str,
        default="2019,2021,2022,2023",
        help="Comma-separated list of years to train on.",
    )
    parser.add_argument(
        "--test-year",
        type=int,
        default=2024,
        help="Year to use for testing.",
    )
    parser.add_argument(
        "--data-root",
        type=str,
        default=None,
        help="Absolute path to the data root directory. If not provided, uses CFB_DATA_ROOT from .env or default.",
    )
    args = parser.parse_args()

    train_years = [int(y.strip()) for y in args.train_years.split(",") if y.strip()]
    test_year = args.test_year
    data_root = args.data_root or get_data_root()
    model_dir = MODELS_DIR
    metrics_dir = model_dir / str(test_year) / "metrics"


    # --- MLflow Setup ---
    mlflow.set_experiment("CFB_Model_Training")

    # --- Data Loading ---
    all_training_games = []
    for year in train_years:
        print(f"Generating features for training year: {year}")
        for week in range(1, 16):
            try:
                weekly_features = generate_point_in_time_features(
                    year, week, data_root
                )
                all_training_games.append(weekly_features)
            except ValueError as e:
                print(f"  Skipping week {week} for year {year}: {e}")
                continue
    train_df = _concat_years(all_training_games)

    all_test_games = []
    print(f"Generating features for test year: {test_year}")
    for week in range(1, 16):
        try:
            weekly_features = generate_point_in_time_features(
                test_year, week, data_root
            )
            all_test_games.append(weekly_features)
        except ValueError as e:
            print(f"  Skipping week {week} for year {test_year}: {e}")
            continue
    test_df = _concat_years(all_test_games)

    # --- Feature Preparation ---
    feature_list = _build_feature_list(train_df)
    feature_list = [c for c in feature_list if c in test_df.columns]
    target_cols = ["spread_target", "total_target"]
    train_df = train_df.dropna(subset=feature_list + target_cols)
    test_df = test_df.dropna(subset=feature_list + target_cols)

    X_train = train_df[feature_list]
    y_spread_train = train_df["spread_target"].astype(float)
    y_total_train = train_df["total_target"].astype(float)

    X_test = test_df[feature_list]
    y_spread_test = test_df["spread_target"].astype(float)
    y_total_test = test_df["total_target"].astype(float)

    out_dir = model_dir / str(test_year)
    os.makedirs(out_dir, exist_ok=True)

    # --- Parent MLflow Run ---
    with mlflow.start_run(run_name=f"Ensemble_Training_{test_year}") as parent_run:
        mlflow.log_param("train_years", str(train_years))
        mlflow.log_param("test_year", test_year)
        mlflow.log_param("feature_count", len(feature_list))

        # --- Spread Models ---
        print("Training and logging spread models...")
        spread_models = {
            "ridge": Ridge(alpha=0.1),
            "elastic_net": ElasticNet(alpha=0.1, l1_ratio=0.5, random_state=42),
            "huber": Pipeline(
                [
                    ("scaler", StandardScaler()),
                    ("huber", HuberRegressor(epsilon=1.35, max_iter=500)),
                ]
            ),
        }
        for name, model in spread_models.items():
            with mlflow.start_run(run_name=f"spread_{name}", nested=True):
                print(f"  Training spread_{name}...")
                mlflow.log_params(model.get_params())
                model.fit(X_train, y_spread_train)
                
                preds = model.predict(X_test)
                metrics = _evaluate(y_spread_test.to_numpy(), preds)
                mlflow.log_metrics({"test_rmse": metrics.rmse, "test_mae": metrics.mae})
                
                joblib.dump(model, out_dir / f"spread_{name}.joblib")
                mlflow.sklearn.log_model(model, f"spread_{name}")

        # --- Total Models ---
        print("Training and logging total models...")
        total_models = {
            "random_forest": RandomForestRegressor(
                n_estimators=200, max_depth=8, min_samples_split=10, min_samples_leaf=5, random_state=42
            ),
            "gradient_boosting": GradientBoostingRegressor(
                n_estimators=200, learning_rate=0.1, max_depth=6, subsample=0.8, random_state=42
            ),
        }
        for name, model in total_models.items():
            with mlflow.start_run(run_name=f"total_{name}", nested=True):
                print(f"  Training total_{name}...")
                mlflow.log_params(model.get_params())
                model.fit(X_train, y_total_train)

                preds = model.predict(X_test)
                metrics = _evaluate(y_total_test.to_numpy(), preds)
                mlflow.log_metrics({"test_rmse": metrics.rmse, "test_mae": metrics.mae})

                joblib.dump(model, out_dir / f"total_{name}.joblib")
                mlflow.sklearn.log_model(model, f"total_{name}")

        # --- Evaluate and Log Ensemble Performance ---
        print("Evaluating ensemble predictions...")
        spread_preds = [joblib.load(out_dir / f"spread_{name}.joblib").predict(X_test) for name in spread_models]
        total_preds = [joblib.load(out_dir / f"total_{name}.joblib").predict(X_test) for name in total_models]

        spread_pred_ensemble = np.mean(spread_preds, axis=0)
        total_pred_ensemble = np.mean(total_preds, axis=0)

        spread_metrics = _evaluate(y_spread_test.to_numpy(), spread_pred_ensemble)
        total_metrics = _evaluate(y_total_test.to_numpy(), total_pred_ensemble)

        mlflow.log_metric("ensemble_spread_rmse", spread_metrics.rmse)
        mlflow.log_metric("ensemble_spread_mae", spread_metrics.mae)
        mlflow.log_metric("ensemble_total_rmse", total_metrics.rmse)
        mlflow.log_metric("ensemble_total_mae", total_metrics.mae)

        # --- Persist Final Metrics CSV ---
        os.makedirs(metrics_dir, exist_ok=True)
        metrics_path = metrics_dir / f"model_eval_{test_year}.csv"
        pd.DataFrame(
            [
                {
                    "target": "spread_ensemble",
                    "rmse": spread_metrics.rmse,
                    "mae": spread_metrics.mae,
                },
                {
                    "target": "total_ensemble", 
                    "rmse": total_metrics.rmse, 
                    "mae": total_metrics.mae
                },
            ]
        ).to_csv(metrics_path, index=False)
        print(f"Saved final evaluation metrics to {metrics_path}")

if __name__ == "__main__":
    main()
