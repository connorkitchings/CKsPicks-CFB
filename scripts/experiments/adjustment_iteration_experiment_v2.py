"""
Systematic adjustment-iteration depth experiment (CORRECTED VERSION).

This script trains Points-For models (home + away) at each opponent-adjustment
iteration depth (0, 1, 2, 3, 4) using PROPER FEATURE SELECTION and evaluates
derived spread/total predictions on 2024 holdout data.

Usage:
    uv run python scripts/adjustment_iteration_experiment_v2.py
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
from omegaconf import OmegaConf
from sklearn.metrics import mean_absolute_error, mean_squared_error

load_dotenv()

sys.path.append(str(Path(__file__).resolve().parents[2]))
# noqa: E402
from src.features.selector import select_features  # noqa: E402
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
    """Run Points-For experiment for a single  adjustment iteration depth."""
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

    # Use proper feature selection
    log.info("Selecting features using standard_v1 config...")
    x_train_full = select_features(train_df, FEATURE_CONFIG)
    x_test_full = select_features(test_df, FEATURE_CONFIG)

    # Find common features (to handle any year-to-year differences)
    common_features = sorted(
        list(set(x_train_full.columns).intersection(set(x_test_full.columns)))
    )
    log.info(f"Using {len(common_features)} common features")

    # Prepare targets - drop NAs BEFORE selecting features to keep indices aligned
    required_target_cols = [
        "home_points_for",
        "away_points_for",
        "spread_target",
        "total_target",
    ]
    train_clean = train_df.dropna(
        subset=required_target_cols + common_features
    ).reset_index(drop=True)
    test_clean = test_df.dropna(
        subset=required_target_cols + common_features
    ).reset_index(drop=True)

    x_train = train_clean[common_features]
    y_train_home = train_clean["home_points_for"]
    y_train_away = train_clean["away_points_for"]

    x_test = test_clean[common_features]
    y_test_home = test_clean["home_points_for"]
    y_test_away = test_clean["away_points_for"]
    y_test_spread = test_clean["spread_target"]
    y_test_total = test_clean["total_target"]

    log.info(f"Final training size: {len(x_train)}, test size: {len(x_test)}")

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
        "n_train": len(x_train),
        "n_test": len(x_test),
        "n_features": len(common_features),
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

    with mlflow.start_run(run_name="Adjustment_Iteration_Systematic_Comparison_v2"):
        mlflow.log_param("train_years", str(TRAIN_YEARS))
        mlflow.log_param("test_year", TEST_YEAR)
        mlflow.log_param("depths", str(DEPTHS))
        mlflow.log_param("feature_config", "standard_v1")

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
            output_path = output_dir / "adjustment_iteration_summary_v2.csv"
            summary_df.to_csv(output_path, index=False)
            log.info(f"\\nSaved summary to {output_path}")

            # Log as artifact
            mlflow.log_artifact(str(output_path))

            # Print summary table
            log.info("\\n" + "=" * 90)
            log.info("SUMMARY OF ALL DEPTHS")
            log.info("=" * 90)
            print(summary_df.to_string(index=False))

            # Find best depth by spread RMSE
            best_spread_row = summary_df.loc[summary_df["spread_rmse"].idxmin()]
            best_total_row = summary_df.loc[summary_df["total_rmse"].idxmin()]

            log.info(
                f"\\nBest depth by spread RMSE: {int(best_spread_row['depth'])} (RMSE={best_spread_row['spread_rmse']:.2f})"
            )
            log.info(
                f"Best depth by total RMSE: {int(best_total_row['depth'])} (RMSE={best_total_row['total_rmse']:.2f})"
            )

            mlflow.log_metric("best_depth_spread", int(best_spread_row["depth"]))
            mlflow.log_metric("best_spread_rmse", best_spread_row["spread_rmse"])
            mlflow.log_metric("best_depth_total", int(best_total_row["depth"]))
            mlflow.log_metric("best_total_rmse", best_total_row["total_rmse"])


if __name__ == "__main__":
    main()
