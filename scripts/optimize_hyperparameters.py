#!/usr/bin/env python3
"""
Hyperparameter optimization for spread and total models using Optuna and Hydra.
"""

import sys
from pathlib import Path

import hydra
import mlflow
import numpy as np
import pandas as pd
from omegaconf import DictConfig
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import TimeSeriesSplit

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cfb_model.models.features import (
    build_feature_list,
    generate_point_in_time_features,
)


def load_data(years: list[int], data_root: str | None, cache_path: str) -> pd.DataFrame:
    """Load and combine data for multiple years, using a cache to speed up."""
    cache_path = Path(cache_path)
    if cache_path.exists():
        print(f"Loading cached data from {cache_path}...")
        return pd.read_parquet(cache_path)

    print(f"Cache not found. Generating data for years: {years}")
    all_data = []
    for year in years:
        print(f"  Processing year {year}...")
        for week in range(1, 16):
            try:
                weekly_data = generate_point_in_time_features(year, week, data_root)
                all_data.append(weekly_data)
            except ValueError:
                continue
    if not all_data:
        raise ValueError("No data loaded")

    combined_df = pd.concat(all_data, ignore_index=True)
    target_cols = ["spread_target", "total_target"]
    combined_df = combined_df.dropna(subset=target_cols)

    print(f"Loaded {len(combined_df)} examples. Caching to {cache_path}...")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    combined_df.to_parquet(cache_path)

    return combined_df


@hydra.main(config_path="../conf", config_name="optimize_ridge", version_base=None)
def objective(cfg: DictConfig) -> float:
    """Objective function for Optuna optimization."""
    with mlflow.start_run(run_name=f"{cfg.model._target_}_{cfg.target}"):
        mlflow.log_params(cfg.model)
        mlflow.log_params({"target": cfg.target})

        train_years = [int(y.strip()) for y in cfg.core.train_years.split(",")]
        train_cache = Path(cfg.core.output_dir) / f"train_data_cache__{'_'.join(map(str, train_years))}.parquet"
        train_df = load_data(train_years, cfg.core.data_root, train_cache)

        test_cache = Path(cfg.core.output_dir) / f"test_data_cache__{cfg.core.test_year}.parquet"
        test_df = load_data([cfg.core.test_year], cfg.core.data_root, test_cache)

        feature_list = build_feature_list(train_df)
        feature_list = [f for f in feature_list if f in test_df.columns]

        x_train = train_df[feature_list].astype(float).fillna(0)
        y_train = train_df[f"{cfg.target}_target"].astype(float)
        x_test = test_df[feature_list].astype(float).fillna(0)
        y_test = test_df[f"{cfg.target}_target"].astype(float)

        model = hydra.utils.instantiate(cfg.model)

        # Time-series cross-validation
        cv = TimeSeriesSplit(n_splits=5)
        rmses = []
        for train_idx, val_idx in cv.split(x_train):
            x_train_fold, x_val_fold = x_train.iloc[train_idx], x_train.iloc[val_idx]
            y_train_fold, y_val_fold = y_train.iloc[train_idx], y_train.iloc[val_idx]

            model.fit(x_train_fold, y_train_fold)
            preds = model.predict(x_val_fold)
            rmses.append(np.sqrt(mean_squared_error(y_val_fold, preds)))

        cv_rmse = np.mean(rmses)
        mlflow.log_metric("cv_rmse", cv_rmse)

        # Final evaluation on test set
        model.fit(x_train, y_train)
        test_preds = model.predict(x_test)
        test_rmse = np.sqrt(mean_squared_error(y_test, test_preds))
        mlflow.log_metric("test_rmse", test_rmse)

        return test_rmse


if __name__ == "__main__":
    objective()
