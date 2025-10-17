"""Experimental model training script using differential features."""

from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import ElasticNet, HuberRegressor, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.models.features import (
    build_differential_feature_list,
    build_differential_features,
    generate_point_in_time_features,
)
from src.config import REPORTS_DIR, METRICS_SUBDIR


def _train_and_save(
    model, x_data: pd.DataFrame, y: pd.Series, out_dir: str, name: str
) -> None:
    os.makedirs(out_dir, exist_ok=True)
    model.fit(x_data, y)
    joblib.dump(model, os.path.join(out_dir, f"{name}.joblib"))


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
    import argparse

    parser = argparse.ArgumentParser(
        description="Train models on multiple years and evaluate on a test year."
    )
    parser.add_argument(
        "--train-years",
        type=str,
        default="2019,2021,2022,2023",
        help="Comma-separated training years",
    )
    parser.add_argument("--test-year", type=int, default=2024, help="Holdout test year")
    parser.add_argument("--data-root", type=str, default=None, help="Data root path")
    parser.add_argument(
        "--model-dir",
        type=str,
        default="./models/differential",
        help="Output dir for models",
    )
    parser.add_argument(
        "--metrics-dir",
        type=str,
        default=str(REPORTS_DIR / METRICS_SUBDIR),
        help="Output dir for metrics CSV",
    )
    args = parser.parse_args()

    train_years = [int(y.strip()) for y in args.train_years.split(",") if y.strip()]
    test_year = int(args.test_year)

    # Generate point-in-time features for all weeks in all training years
    all_training_games = []
    for year in train_years:
        print(f"Generating features for training year: {year}")
        for week in range(1, 16):
            try:
                weekly_features = generate_point_in_time_features(
                    year, week, args.data_root
                )
                all_training_games.append(weekly_features)
            except ValueError as e:
                print(f"  Skipping week {week} for year {year}: {e}")
                continue
    train_df = _concat_years(all_training_games)

    # Generate point-in-time features for all weeks in the test year
    all_test_games = []
    print(f"Generating features for test year: {test_year}")
    for week in range(1, 16):
        try:
            weekly_features = generate_point_in_time_features(
                test_year, week, args.data_root
            )
            all_test_games.append(weekly_features)
        except ValueError as e:
            print(f"  Skipping week {week} for year {test_year}: {e}")
            continue
    test_df = _concat_years(all_test_games)

    # ---- Build Differential Features ----
    print("Building differential features for training and test sets...")
    train_df = build_differential_features(train_df)
    test_df = build_differential_features(test_df)

    # Build feature list from the new differential features
    feature_list = build_differential_feature_list(train_df)
    feature_list = [c for c in feature_list if c in test_df.columns]

    # Filter rows with complete features/targets
    target_cols = ["spread_target", "total_target"]
    train_df = train_df.dropna(subset=feature_list + target_cols)
    test_df = test_df.dropna(subset=feature_list + target_cols)

    x_train = train_df[feature_list]
    y_spread_train = train_df["spread_target"].astype(float)
    y_total_train = train_df["total_target"].astype(float)

    x_test = test_df[feature_list]
    y_spread_test = test_df["spread_target"].astype(float)
    y_total_test = test_df["total_target"].astype(float)

    out_dir = os.path.join(args.model_dir, str(test_year))

    # --- Spread Models ---
    print("Training spread models...")
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
        print(f"  Training spread_{name}...")
        _train_and_save(model, x_train, y_spread_train, out_dir, name=f"spread_{name}")

    # --- Total Models ---
    print("Training total models...")
    total_models = {
        "random_forest": RandomForestRegressor(
            n_estimators=200,
            max_depth=8,
            min_samples_split=10,
            min_samples_leaf=5,
            random_state=42,
        ),
        "gradient_boosting": GradientBoostingRegressor(
            n_estimators=200,
            learning_rate=0.1,
            max_depth=6,
            subsample=0.8,
            random_state=42,
        ),
    }
    for name, model in total_models.items():
        print(f"  Training total_{name}...")
        _train_and_save(model, x_train, y_total_train, out_dir, name=f"total_{name}")

    # --- Load back and evaluate ensemble on test ---
    print("Evaluating ensemble predictions...")
    spread_preds = []
    for name in spread_models:
        model = joblib.load(os.path.join(out_dir, f"spread_{name}.joblib"))
        spread_preds.append(model.predict(x_test))

    total_preds = []
    for name in total_models:
        model = joblib.load(os.path.join(out_dir, f"total_{name}.joblib"))
        total_preds.append(model.predict(x_test))

    # Average the predictions for the ensemble
    spread_pred = np.mean(spread_preds, axis=0)
    total_pred = np.mean(total_preds, axis=0)

    spread_metrics = _evaluate(y_spread_test.to_numpy(), spread_pred)
    total_metrics = _evaluate(y_total_test.to_numpy(), total_pred)

    # Persist metrics
    os.makedirs(args.metrics_dir, exist_ok=True)
    metrics_path = os.path.join(
        args.metrics_dir, f"model_eval_differential_{test_year}.csv"
    )
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
    print(f"Saved evaluation metrics to {metrics_path}")


if __name__ == "__main__":
    main()
