"""
Systematic adjustment-iteration depth experiment.

This script trains Points-For models (home + away) at each opponent-adjustment
iteration depth (0, 1, 2, 3, 4) and evaluates derived spread/total predictions
on 2024 holdout data.

Usage:
    uv run python scripts/adjustment_iteration_experiment.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from dotenv import load_dotenv
from sklearn.metrics import mean_absolute_error, mean_squared_error

load_dotenv()

sys.path.append(str(Path(__file__).resolve().parents[2]))
# noqa: E402
from src.models.features import load_point_in_time_data  # noqa: E402
from src.models.train_model import _concat_years  # noqa: E402

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Configuration
DATA_ROOT = "/Volumes/CK SSD/Coding Projects/cfb_model/"
TRAIN_YEARS = [2019, 2021, 2022, 2023]  # Skip 2020
TEST_YEAR = 2024
DEPTHS = [0, 1, 2, 3, 4]
RANDOM_SEED = 42

# CatBoost params (from points_for_catboost.yaml)
CATBOOST_PARAMS = {
    "depth": 6,
    "learning_rate": 0.05,
    "iterations": 800,
    "l2_leaf_reg": 3.0,
    "subsample": 0.8,
    "random_seed": RANDOM_SEED,
    "verbose": False,
}


def load_training_data(years: list[int], depth: int) -> pd.DataFrame:
    """Load training data for specified years and adjustment iteration depth."""
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
        raise ValueError(f"No training data found for depth={depth}")

    return _concat_years(all_data)


def load_test_data(year: int, depth: int) -> pd.DataFrame:
    """Load test data for specified year and adjustment iteration depth."""
    all_data = []
    for week in range(1, 16):
        df = load_point_in_time_data(year, week, DATA_ROOT, adjustment_iteration=depth)
        if df is not None:
            all_data.append(df)

    if not all_data:
        raise ValueError(f"No test data found for year={year}, depth={depth}")

    return _concat_years(all_data)


def run_experiment_for_depth(depth: int) -> dict:
    """Run Points-For experiment for a single adjustment iteration depth."""
    log.info(f"\\n{'=' * 60}")
    log.info(f"Running experiment for adjustment_iteration={depth}")
    log.info(f"{'=' * 60}")

    # Load data
    log.info("Loading training data...")
    train_df = load_training_data(TRAIN_YEARS, depth)
    log.info(f"Loaded {len(train_df)} training games")

    log.info("Loading test data...")
    test_df = load_test_data(TEST_YEAR, depth)
    log.info(f"Loaded {len(test_df)} test games")

    # Prepare features (use all numeric columns except meta and targets)
    exclude_cols = {
        "id",
        "season",
        "week",
        "home_team",
        "away_team",
        "spread_target",
        "total_target",
        "home_points_for",
        "away_points_for",
        "home_team_spread_line",
        "over_under_line",
    }
    feature_cols = [
        c
        for c in train_df.columns
        if c not in exclude_cols
        and train_df[c].dtype in [np.float64, np.int64, np.float32, np.int32]
    ]

    # Ensure features exist in both train and test
    feature_cols = [c for c in feature_cols if c in test_df.columns]
    log.info(f"Using {len(feature_cols)} features")

    # Prepare targets
    required_cols = feature_cols + [
        "home_points_for",
        "away_points_for",
        "spread_target",
        "total_target",
    ]
    train_df = train_df.dropna(subset=required_cols)
    test_df = test_df.dropna(subset=required_cols)

    x_train = train_df[feature_cols]
    y_train_home = train_df["home_points_for"]
    y_train_away = train_df["away_points_for"]

    x_test = test_df[feature_cols]
    y_test_home = test_df["home_points_for"]
    y_test_away = test_df["away_points_for"]
    y_test_spread = test_df["spread_target"]
    y_test_total = test_df["total_target"]

    # Train home points model
    log.info("Training home points model...")
    model_home = CatBoostRegressor(**CATBOOST_PARAMS)
    model_home.fit(x_train, y_train_home)

    # Train away points model
    log.info("Training away points model...")
    model_away = CatBoostRegressor(**CATBOOST_PARAMS)
    model_away.fit(x_train, y_train_away)

    # Predict on test set
    log.info("Generating predictions...")
    pred_home = model_home.predict(x_test)
    pred_away = model_away.predict(x_test)

    # Derive spread and total
    pred_spread = pred_home - pred_away
    pred_total = pred_home + pred_away

    # Compute metrics
    home_rmse = np.sqrt(mean_squared_error(y_test_home, pred_home))
    home_mae = mean_absolute_error(y_test_home, pred_home)

    away_rmse = np.sqrt(mean_squared_error(y_test_away, pred_away))
    away_mae = mean_absolute_error(y_test_away, pred_away)

    spread_rmse = np.sqrt(mean_squared_error(y_test_spread, pred_spread))
    spread_mae = mean_absolute_error(y_test_spread, pred_spread)
    spread_bias = np.mean(pred_spread - y_test_spread)

    total_rmse = np.sqrt(mean_squared_error(y_test_total, pred_total))
    total_mae = mean_absolute_error(y_test_total, pred_total)
    total_bias = np.mean(pred_total - y_test_total)

    results = {
        "depth": depth,
        "home_rmse": home_rmse,
        "home_mae": home_mae,
        "away_rmse": away_rmse,
        "away_mae": away_mae,
        "spread_rmse": spread_rmse,
        "spread_mae": spread_mae,
        "spread_bias": spread_bias,
        "total_rmse": total_rmse,
        "total_mae": total_mae,
        "total_bias": total_bias,
        "n_train": len(train_df),
        "n_test": len(test_df),
    }

    log.info(f"\\nResults for depth={depth}:")
    log.info(f"  Home Points:  RMSE={home_rmse:.2f}, MAE={home_mae:.2f}")
    log.info(f"  Away Points:  RMSE={away_rmse:.2f}, MAE={away_mae:.2f}")
    log.info(
        f"  Spread:       RMSE={spread_rmse:.2f}, MAE={spread_mae:.2f}, Bias={spread_bias:.2f}"
    )
    log.info(
        f"  Total:        RMSE={total_rmse:.2f}, MAE={total_mae:.2f}, Bias={total_bias:.2f}"
    )

    return results


def main():
    """Run experiments for all depths and save results."""
    # Setup MLflow
    # Setup MLflow
    from src.utils.mlflow_tracking import setup_mlflow

    setup_mlflow()
    mlflow.set_experiment("adjustment_iteration_experiments")

    all_results = []

    with mlflow.start_run(run_name="Adjustment_Iteration_Systematic_Comparison"):
        mlflow.log_param("train_years", str(TRAIN_YEARS))
        mlflow.log_param("test_year", TEST_YEAR)
        mlflow.log_param("depths", str(DEPTHS))

        for depth in DEPTHS:
            try:
                results = run_experiment_for_depth(depth)
                all_results.append(results)

                # Log metrics to MLflow
                mlflow.log_metrics(
                    {
                        f"depth_{depth}_home_rmse": results["home_rmse"],
                        f"depth_{depth}_away_rmse": results["away_rmse"],
                        f"depth_{depth}_spread_rmse": results["spread_rmse"],
                        f"depth_{depth}_total_rmse": results["total_rmse"],
                        f"depth_{depth}_spread_bias": results["spread_bias"],
                        f"depth_{depth}_total_bias": results["total_bias"],
                    }
                )

            except Exception as e:
                log.error(f"Error running depth={depth}: {e}", exc_info=True)
                continue

        # Save summary table
        if all_results:
            summary_df = pd.DataFrame(all_results)
            output_dir = Path("./artifacts/reports/metrics")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / "adjustment_iteration_summary.csv"
            summary_df.to_csv(output_path, index=False)
            log.info(f"\\nSaved summary to {output_path}")

            # Log as artifact
            mlflow.log_artifact(str(output_path))

            # Print summary table
            log.info("\\n" + "=" * 80)
            log.info("SUMMARY OF ALL DEPTHS")
            log.info("=" * 80)
            print(summary_df.to_string(index=False))

            # Find best depth by spread RMSE
            best_row = summary_df.loc[summary_df["spread_rmse"].idxmin()]
            log.info(
                f"\\nBest depth by spread RMSE: {int(best_row['depth'])} (RMSE={best_row['spread_rmse']:.2f})"
            )

            mlflow.log_metric("best_depth", int(best_row["depth"]))
            mlflow.log_metric("best_spread_rmse", best_row["spread_rmse"])


if __name__ == "__main__":
    main()
