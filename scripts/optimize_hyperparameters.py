#!/usr/bin/env python3
"""
Hyperparameter optimization for spread and total models.
This script is refactored to remove Hydra and Optuna dependencies.
It performs a simple grid search over predefined parameters.
"""

import argparse
import sys
from pathlib import Path
import itertools

import mlflow
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import TimeSeriesSplit

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import get_data_root, REPORTS_DIR
from src.models.features import (
    build_feature_list,
    generate_point_in_time_features,
)


def load_data(years: list[int], data_root: str | None, cache_path: Path) -> pd.DataFrame:
    """Load and combine data for multiple years, using a cache to speed up."""
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


def run_optimization(
    train_years: list[int],
    test_year: int,
    target: str,
    data_root: str,
    output_dir: Path,
):
    """Performs a simple grid search for the given target."""
    mlflow.set_experiment(f"CFB_Model_Optimization_{target}")

    # --- Data Loading ---
    train_cache_path = output_dir / f"train_data_cache__{'_'.join(map(str, train_years))}.parquet"
    train_df = load_data(train_years, data_root, train_cache_path)

    test_cache_path = output_dir / f"test_data_cache__{test_year}.parquet"
    test_df = load_data([test_year], data_root, test_cache_path)

    # --- Feature Preparation ---
    feature_list = build_feature_list(train_df)
    feature_list = [f for f in feature_list if f in test_df.columns]

    x_train = train_df[feature_list].astype(float).fillna(0)
    y_train = train_df[f"{target}_target"].astype(float)
    x_test = test_df[feature_list].astype(float).fillna(0)
    y_test = test_df[f"{target}_target"].astype(float)

    # --- Grid Search Definition (Simplified) ---
    # In a real scenario, this would be more extensive.
    # This is a placeholder to remove the Hydra dependency.
    param_grid = {
        'alpha': [0.1, 1.0, 10.0],
    }
    model_class = Ridge

    print(f"--- Starting Grid Search for {target} using {model_class.__name__} ---")
    results = []

    # Iterate over all combinations of parameters
    keys, values = zip(*param_grid.items())
    for param_values in itertools.product(*values):
        params = dict(zip(keys, param_values))
        
        with mlflow.start_run(run_name=f"{model_class.__name__}_{params}"):
            mlflow.log_params(params)
            mlflow.log_param("target", target)

            model = model_class(**params)

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

            print(f"Params: {params} -> CV RMSE: {cv_rmse:.4f}, Test RMSE: {test_rmse:.4f}")
            results.append({
                "params": params,
                "cv_rmse": cv_rmse,
                "test_rmse": test_rmse,
            })

    # --- Save Results ---
    results_df = pd.DataFrame(results)
    results_path = output_dir / f"optimization_results_{target}.csv"
    results_df.to_csv(results_path, index=False)
    print(f"Optimization results for {target} saved to {results_path}")


def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Hyperparameter optimization script.")
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
        "--target",
        type=str,
        choices=["spread", "total"],
        required=True,
        help="Prediction target: 'spread' or 'total'.",
    )
    parser.add_argument(
        "--data-root",
        type=str,
        default=None,
        help="Absolute path to the data root directory.",
    )
    args = parser.parse_args()

    data_root = args.data_root or get_data_root()
    output_dir = REPORTS_DIR / "optimization"
    output_dir.mkdir(parents=True, exist_ok=True)

    run_optimization(
        train_years=[int(y.strip()) for y in args.train_years.split(",")],
        test_year=args.test_year,
        target=args.target,
        data_root=data_root,
        output_dir=output_dir,
    )


if __name__ == "__main__":
    main()