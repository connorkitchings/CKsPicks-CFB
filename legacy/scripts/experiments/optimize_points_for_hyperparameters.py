"""
Hyperparameter optimization for Points-For CatBoost models using Optuna.

This script optimizes CatBoost hyperparameters for either 'home_points' or 'away_points'
targets to minimize RMSE on a validation set (2023) or holdout set (2024).
"""

import argparse
import logging
import sys
from pathlib import Path

import mlflow
import numpy as np
import optuna
import pandas as pd
from catboost import CatBoostRegressor
from dotenv import load_dotenv
from omegaconf import OmegaConf
from sklearn.metrics import mean_squared_error

from src.features.selector import select_features
from src.models.features import load_point_in_time_data
from src.models.train_model import _concat_years

load_dotenv()

sys.path.append(str(Path(__file__).resolve().parents[2]))
# noqa: E402
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Configuration
DATA_ROOT = "/Volumes/CK SSD/Coding Projects/cfb_model/"
TRAIN_YEARS = [2019, 2021, 2022]  # Train on these
VALID_YEAR = 2023  # Optimize against this year
TEST_YEAR = 2024  # Final holdout (not used in optimization)
ADJUSTMENT_ITERATION = 2  # Fixed based on previous experiments

# Feature config (standard_v1 features)
FEATURE_CONFIG = OmegaConf.create(
    {
        "features": {
            "name": "standard_v1",
            "groups": ["off_def_stats", "pace_stats", "recency_stats", "luck_stats"],
            "recency_window": "standard",
            "include_pace_interactions": False,
            "exclude": [],
        }
    }
)


def load_data(years: list[int], depth: int) -> pd.DataFrame:
    """Load data for specified years and adjustment iteration depth."""
    all_data = []
    for year in years:
        if year == 2020:
            continue
        for week in range(1, 16):
            df = load_point_in_time_data(
                year, week, DATA_ROOT, adjustment_iteration=depth
            )
            if df is not None:
                all_data.append(df)

    if not all_data:
        raise ValueError(f"No data found for years={years}, depth={depth}")

    return _concat_years(all_data)


def prepare_datasets(target_col: str):
    """Load and prepare training and validation datasets."""
    log.info("Loading training data...")
    train_df = load_data(TRAIN_YEARS, ADJUSTMENT_ITERATION)

    log.info("Loading validation data...")
    valid_df = load_data([VALID_YEAR], ADJUSTMENT_ITERATION)

    # Feature selection
    log.info("Selecting features...")
    x_train_full = select_features(train_df, FEATURE_CONFIG)
    x_valid_full = select_features(valid_df, FEATURE_CONFIG)

    # Common features
    common_features = sorted(
        list(set(x_train_full.columns).intersection(set(x_valid_full.columns)))
    )
    log.info(f"Using {len(common_features)} features")

    # Prepare targets
    train_clean = train_df.dropna(subset=[target_col] + common_features).reset_index(
        drop=True
    )
    valid_clean = valid_df.dropna(subset=[target_col] + common_features).reset_index(
        drop=True
    )

    x_train = train_clean[common_features]
    y_train = train_clean[target_col]

    x_valid = valid_clean[common_features]
    y_valid = valid_clean[target_col]

    return x_train, y_train, x_valid, y_valid


def objective(trial, x_train, y_train, x_valid, y_valid, target_col):
    """Optuna objective function."""

    # Hyperparameter search space
    params = {
        "depth": trial.suggest_int("depth", 4, 8),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.1, log=True),
        "iterations": trial.suggest_categorical("iterations", [500, 800, 1200, 1500]),
        "l2_leaf_reg": trial.suggest_float("l2_leaf_reg", 1.0, 10.0),
        "subsample": trial.suggest_float("subsample", 0.6, 1.0),
        "colsample_bylevel": trial.suggest_float("colsample_bylevel", 0.6, 1.0),
        "min_data_in_leaf": trial.suggest_int("min_data_in_leaf", 1, 20),
        "random_seed": 42,
        "verbose": False,
        "loss_function": "RMSE",
        "eval_metric": "RMSE",
    }

    # Train model
    model = CatBoostRegressor(**params)
    model.fit(
        x_train,
        y_train,
        eval_set=(x_valid, y_valid),
        early_stopping_rounds=50,
        verbose=False,
    )

    # Evaluate
    preds = model.predict(x_valid)
    rmse = np.sqrt(mean_squared_error(y_valid, preds))

    # Log to MLflow
    with mlflow.start_run(nested=True):
        mlflow.log_params(params)
        mlflow.log_metric("rmse", rmse)
        mlflow.set_tag("target", target_col)
        mlflow.set_tag("trial_number", trial.number)

    return rmse


def main():
    parser = argparse.ArgumentParser(description="Optimize Points-For Hyperparameters")
    parser.add_argument(
        "--target",
        type=str,
        required=True,
        choices=["home_points", "away_points"],
        help="Target variable to optimize for",
    )
    parser.add_argument(
        "--n-trials", type=int, default=50, help="Number of Optuna trials"
    )
    parser.add_argument(
        "--experiment-name",
        type=str,
        default="points_for_optimization",
        help="MLflow experiment name",
    )
    args = parser.parse_args()

    # Setup MLflow
    # Setup MLflow
    from src.utils.mlflow_tracking import setup_mlflow

    setup_mlflow()
    mlflow.set_experiment(args.experiment_name)

    # Prepare data
    target_col = args.target
    x_train, y_train, x_valid, y_valid = prepare_datasets(target_col)

    log.info(f"Starting optimization for {args.target} with {args.n_trials} trials...")

    # Create study
    study = optuna.create_study(
        direction="minimize",
        sampler=optuna.samplers.TPESampler(seed=42),
        pruner=optuna.pruners.MedianPruner(n_startup_trials=10, n_warmup_steps=5),
    )

    # Optimize
    study.optimize(
        lambda trial: objective(trial, x_train, y_train, x_valid, y_valid, args.target),
        n_trials=args.n_trials,
    )

    # Results
    log.info("Optimization complete!")
    log.info(f"Best RMSE: {study.best_value:.4f}")
    log.info("Best parameters:")
    for key, value in study.best_params.items():
        log.info(f"  {key}: {value}")

    # Save best params
    output_dir = Path("artifacts/optimization")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"best_{args.target}_params.yaml"

    with open(output_path, "w") as f:
        # Format as YAML
        f.write(f"# Best parameters for {args.target}\n")
        f.write(f"# RMSE: {study.best_value:.4f}\n")
        f.write("# Optimized on 2023 validation set\n\n")
        for key, value in study.best_params.items():
            f.write(f"{key}: {value}\n")

    log.info(f"Saved best parameters to {output_path}")


if __name__ == "__main__":
    main()
