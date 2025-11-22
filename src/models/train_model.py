"""Model training CLI.

Loads opponent-adjusted team-season features, merges with games, builds
feature matrices for spread and total targets, trains the specified models, and
emits metrics/artifacts.
"""

from __future__ import annotations

import argparse
import os
import warnings
from collections.abc import Iterable
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import joblib
import mlflow
import numpy as np
import pandas as pd
import xgboost as xgb
from catboost import CatBoostRegressor
from lightgbm import LGBMRegressor
from sklearn.ensemble import (
    GradientBoostingRegressor,
    HistGradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.linear_model import ElasticNet, HuberRegressor, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.config import MODELS_DIR, get_data_root
from src.models.features import (
    FEATURE_PACK_CHOICES,
    build_feature_list,
    filter_features_by_pack,
    load_point_in_time_data,
)
from src.utils.mlflow_tracking import get_tracking_uri


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


def _build_feature_list(
    df: pd.DataFrame, exclude_rushing_analytics: bool = False
) -> list[str]:
    # build_feature_list currently ignores rushing analytics filtering;
    # keep the argument for compatibility in case future callers need it.
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


@contextmanager
def _suppress_linear_runtime_warnings() -> Iterable[None]:
    """Temporarily ignore benign matmul RuntimeWarnings from numpy/BLAS."""

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="divide by zero encountered in matmul",
            category=RuntimeWarning,
        )
        warnings.filterwarnings(
            "ignore",
            message="overflow encountered in matmul",
            category=RuntimeWarning,
        )
        warnings.filterwarnings(
            "ignore",
            message="invalid value encountered in matmul",
            category=RuntimeWarning,
        )
        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            yield


spread_models = {
    "ridge": Ridge(alpha=0.1),
    "elastic_net": ElasticNet(alpha=0.1, l1_ratio=0.5, random_state=42),
    "huber": Pipeline(
        [
            ("scaler", StandardScaler()),
            ("huber", HuberRegressor(epsilon=1.35, max_iter=500)),
        ]
    ),
    "xgboost": xgb.XGBRegressor(objective="reg:squarederror", random_state=42),
    "hist_gradient_boosting": HistGradientBoostingRegressor(
        learning_rate=0.1,
        max_depth=6,
        max_iter=300,
        l2_regularization=0.0,
        random_state=42,
    ),
    "lightgbm": LGBMRegressor(
        n_estimators=500,
        learning_rate=0.05,
        max_depth=-1,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
    ),
    "catboost": CatBoostRegressor(
        loss_function="RMSE",
        depth=6,
        learning_rate=0.05,
        iterations=800,
        random_seed=42,
        verbose=0,
    ),
}

total_models = {
    "ridge": Ridge(alpha=0.1),
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
    "xgboost": xgb.XGBRegressor(objective="reg:squarederror", random_state=42),
    "hist_gradient_boosting": HistGradientBoostingRegressor(
        learning_rate=0.1,
        max_depth=6,
        max_iter=300,
        l2_regularization=0.0,
        random_state=42,
    ),
    "lightgbm": LGBMRegressor(
        n_estimators=500,
        learning_rate=0.05,
        max_depth=-1,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
    ),
    "catboost": CatBoostRegressor(
        loss_function="RMSE",
        depth=6,
        learning_rate=0.05,
        iterations=800,
        random_seed=42,
        verbose=0,
    ),
}

points_for_models = {
    "ridge": Ridge(alpha=0.1),
    "elastic_net": ElasticNet(alpha=0.1, l1_ratio=0.5, random_state=42),
    "gradient_boosting": GradientBoostingRegressor(
        n_estimators=200,
        learning_rate=0.1,
        max_depth=3,
        subsample=0.8,
        random_state=42,
    ),
    "xgboost": xgb.XGBRegressor(objective="reg:squarederror", random_state=42),
}


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
    parser.add_argument(
        "--model-dir",
        type=str,
        default=None,
        help="Directory to persist trained model artifacts (defaults to artifacts/models).",
    )
    parser.add_argument(
        "--metrics-dir",
        type=str,
        default=None,
        help="Directory to write evaluation metrics CSV (defaults to <model-dir>/<test_year>/metrics).",
    )
    parser.add_argument(
        "--adjustment-iteration",
        type=int,
        default=4,
        help=(
            "Opponent-adjustment iteration depth to load from team_week_adj caches "
            "(default: 4)."
        ),
    )
    parser.add_argument(
        "--offense-adjustment-iteration",
        type=int,
        default=None,
        help=(
            "Override the offensive feature adjustment depth. Defaults to the value "
            "provided via --adjustment-iteration."
        ),
    )
    parser.add_argument(
        "--defense-adjustment-iteration",
        type=int,
        default=None,
        help=(
            "Override the defensive feature adjustment depth. Defaults to the value "
            "provided via --adjustment-iteration."
        ),
    )
    parser.add_argument(
        "--feature-pack",
        action="append",
        dest="feature_packs",
        choices=FEATURE_PACK_CHOICES + ["all"],
        help=(
            "Repeatable flag used to restrict modeling to specific feature packs "
            f"{FEATURE_PACK_CHOICES}. Defaults to all packs when omitted."
        ),
    )
    parser.add_argument(
        "--min-feature-variance",
        type=float,
        default=0.0,
        help=(
            "Drop numeric features whose variance on the training set falls below "
            "this threshold (default keeps all features)."
        ),
    )
    args = parser.parse_args()

    train_years = [int(y.strip()) for y in args.train_years.split(",") if y.strip()]
    test_year = args.test_year
    data_root = args.data_root or get_data_root()
    model_dir = Path(args.model_dir).resolve() if args.model_dir else MODELS_DIR
    metrics_dir = (
        Path(args.metrics_dir).resolve()
        if args.metrics_dir
        else model_dir / str(test_year) / "metrics"
    )
    offense_iteration = (
        args.offense_adjustment_iteration
        if args.offense_adjustment_iteration is not None
        else args.adjustment_iteration
    )
    defense_iteration = (
        args.defense_adjustment_iteration
        if args.defense_adjustment_iteration is not None
        else args.adjustment_iteration
    )

    # --- MLflow Setup ---
    mlflow.set_tracking_uri(get_tracking_uri())
    mlflow.set_experiment("CFB_Model_Training")

    # --- Data Loading ---
    all_training_games = []
    for year in train_years:
        print(f"Loading training data for year: {year}")
        for week in range(1, 16):
            weekly_data = load_point_in_time_data(
                year,
                week,
                data_root,
                adjustment_iteration=args.adjustment_iteration,
                adjustment_iteration_offense=args.offense_adjustment_iteration,
                adjustment_iteration_defense=args.defense_adjustment_iteration,
            )
            if weekly_data is not None:
                all_training_games.append(weekly_data)
    train_df = _concat_years(all_training_games)

    all_test_games = []
    print(f"Loading test data for year: {test_year}")
    for week in range(1, 16):
        weekly_data = load_point_in_time_data(
            test_year,
            week,
            data_root,
            adjustment_iteration=args.adjustment_iteration,
            adjustment_iteration_offense=args.offense_adjustment_iteration,
            adjustment_iteration_defense=args.defense_adjustment_iteration,
        )
        if weekly_data is not None:
            all_test_games.append(weekly_data)
    test_df = _concat_years(all_test_games)

    # --- Feature Preparation ---
    feature_list = _build_feature_list(train_df)
    feature_list = [c for c in feature_list if c in test_df.columns]
    feature_list = filter_features_by_pack(feature_list, args.feature_packs)
    if not feature_list:
        raise ValueError("No features available after applying pack filters.")
    if args.feature_packs:
        print(
            f"Feature packs {args.feature_packs} selected → {len(feature_list)} columns"
        )
    target_cols = ["spread_target", "total_target"]
    train_df = train_df.dropna(subset=feature_list + target_cols)
    test_df = test_df.dropna(subset=feature_list + target_cols)

    x_train = train_df[feature_list]
    y_spread_train = train_df["spread_target"].astype(float)
    y_total_train = train_df["total_target"].astype(float)

    x_test = test_df[feature_list]

    if args.min_feature_variance > 0:
        variances = x_train.var(axis=0, numeric_only=True)
        keep_cols = [
            col
            for col in feature_list
            if variances.get(col, 0.0) >= args.min_feature_variance
        ]
        dropped = [col for col in feature_list if col not in keep_cols]
        if not keep_cols:
            raise ValueError(
                "Variance threshold removed all features; lower --min-feature-variance."
            )
        if dropped:
            print(
                f"Dropping {len(dropped)} low-variance features (threshold={args.min_feature_variance})"
            )
        feature_list = keep_cols
        x_train = x_train[feature_list]
        x_test = x_test[feature_list]
    y_spread_test = test_df["spread_target"].astype(float)
    y_total_test = test_df["total_target"].astype(float)

    out_dir = model_dir / str(test_year)
    os.makedirs(out_dir, exist_ok=True)

    print("Describing x_train:")
    print(x_train.describe())
    print("Checking for infinite values in x_train:")
    print(np.isinf(x_train).sum())

    # --- Parent MLflow Run ---
    with mlflow.start_run(run_name=f"Ensemble_Training_{test_year}"):
        mlflow.log_param("train_years", str(train_years))
        mlflow.log_param("test_year", test_year)
        mlflow.log_param("feature_count", len(feature_list))
        mlflow.log_param("off_adjustment_iteration", offense_iteration)
        mlflow.log_param("def_adjustment_iteration", defense_iteration)

        # --- Spread Models ---
        print("Training and logging spread models...")
        for name, model in spread_models.items():
            with mlflow.start_run(run_name=f"spread_{name}", nested=True):
                print(f"  Training spread_{name}...")
                mlflow.log_params(model.get_params())
                with _suppress_linear_runtime_warnings():
                    model.fit(x_train, y_spread_train)
                    preds = model.predict(x_test)
                metrics = _evaluate(y_spread_test.to_numpy(), preds)
                mlflow.log_metrics({"test_rmse": metrics.rmse, "test_mae": metrics.mae})

                joblib.dump(model, out_dir / f"spread_{name}.joblib")
                mlflow.sklearn.log_model(model, f"spread_{name}")

        # --- Total Models ---
        print("Training and logging total models...")
        for name, model in total_models.items():
            with mlflow.start_run(run_name=f"total_{name}", nested=True):
                print(f"  Training total_{name}...")
                mlflow.log_params(model.get_params())
                with _suppress_linear_runtime_warnings():
                    model.fit(x_train, y_total_train)
                    preds = model.predict(x_test)
                metrics = _evaluate(y_total_test.to_numpy(), preds)
                mlflow.log_metrics({"test_rmse": metrics.rmse, "test_mae": metrics.mae})

                joblib.dump(model, out_dir / f"total_{name}.joblib")
                mlflow.sklearn.log_model(model, f"total_{name}")

        # --- Evaluate and Log Ensemble Performance ---
        print("Evaluating ensemble predictions...")
        spread_preds: list[np.ndarray] = []
        for name in spread_models:
            with _suppress_linear_runtime_warnings():
                spread_preds.append(
                    joblib.load(out_dir / f"spread_{name}.joblib").predict(x_test)
                )

        total_preds: list[np.ndarray] = []
        for name in total_models:
            with _suppress_linear_runtime_warnings():
                total_preds.append(
                    joblib.load(out_dir / f"total_{name}.joblib").predict(x_test)
                )

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
                    "mae": total_metrics.mae,
                },
            ]
        ).to_csv(metrics_path, index=False)
        print(f"Saved final evaluation metrics to {metrics_path}")


if __name__ == "__main__":
    main()
