"""
Hyperparameter optimization for Points-For XGBoost models using Optuna.
"""

import argparse
import logging
import sys
from pathlib import Path

import mlflow
import numpy as np
import optuna
import pandas as pd
import xgboost as xgb
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

DATA_ROOT = "/Volumes/CK SSD/Coding Projects/cfb_model/"
TRAIN_YEARS = [2019, 2021, 2022]
VALID_YEAR = 2023
ADJUSTMENT_ITERATION = 2

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
    return _concat_years(all_data)


def prepare_datasets(target_col: str):
    log.info("Loading training data...")
    train_df = load_data(TRAIN_YEARS, ADJUSTMENT_ITERATION)
    log.info("Loading validation data...")
    valid_df = load_data([VALID_YEAR], ADJUSTMENT_ITERATION)

    x_train_full = select_features(train_df, FEATURE_CONFIG)
    x_valid_full = select_features(valid_df, FEATURE_CONFIG)

    common_features = sorted(
        list(set(x_train_full.columns).intersection(set(x_valid_full.columns)))
    )

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
    params = {
        "n_estimators": trial.suggest_int("n_estimators", 500, 1500),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.1, log=True),
        "max_depth": trial.suggest_int("max_depth", 3, 9),
        "subsample": trial.suggest_float("subsample", 0.6, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
        "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
        "gamma": trial.suggest_float("gamma", 0.0, 5.0),
        "reg_alpha": trial.suggest_float("reg_alpha", 0.0, 5.0),
        "reg_lambda": trial.suggest_float("reg_lambda", 0.0, 5.0),
        "objective": "reg:squarederror",
        "n_jobs": -1,
        "random_state": 42,
        "early_stopping_rounds": 50,
    }

    model = xgb.XGBRegressor(**params)
    model.fit(
        x_train,
        y_train,
        eval_set=[(x_valid, y_valid)],
        verbose=False,
    )

    preds = model.predict(x_valid)
    rmse = np.sqrt(mean_squared_error(y_valid, preds))

    with mlflow.start_run(nested=True):
        mlflow.log_params(params)
        mlflow.log_metric("rmse", rmse)
        mlflow.set_tag("target", target_col)

    return rmse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--target", type=str, required=True, choices=["home_points", "away_points"]
    )
    parser.add_argument("--n-trials", type=int, default=50)
    parser.add_argument(
        "--experiment-name", type=str, default="points_for_xgboost_optimization"
    )
    args = parser.parse_args()

    # Setup MLflow
    from src.utils.mlflow_tracking import setup_mlflow

    setup_mlflow()
    mlflow.set_experiment(args.experiment_name)

    target_col = (
        "home_points_for" if args.target == "home_points" else "away_points_for"
    )
    x_train, y_train, x_valid, y_valid = prepare_datasets(target_col)

    study = optuna.create_study(
        direction="minimize", sampler=optuna.samplers.TPESampler(seed=42)
    )
    study.optimize(
        lambda trial: objective(trial, x_train, y_train, x_valid, y_valid, args.target),
        n_trials=args.n_trials,
    )

    output_dir = Path("artifacts/optimization")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"best_{args.target}_xgboost_params.yaml"

    with open(output_path, "w") as f:
        f.write(f"# Best XGBoost parameters for {args.target}\n")
        f.write(f"# RMSE: {study.best_value:.4f}\n\n")
        for key, value in study.best_params.items():
            f.write(f"{key}: {value}\n")

    log.info(f"Saved best parameters to {output_path}")


if __name__ == "__main__":
    main()
