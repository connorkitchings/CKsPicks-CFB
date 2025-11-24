import logging
import sys
import uuid
from pathlib import Path

import hydra
import mlflow
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from omegaconf import DictConfig, OmegaConf

load_dotenv()

# Add src to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from catboost import CatBoostRegressor  # noqa: E402
from sklearn.metrics import mean_absolute_error, mean_squared_error  # noqa: E402

from src.features.selector import select_features  # noqa: E402
from src.models.features import load_point_in_time_data  # noqa: E402
from src.models.train_model import _concat_years  # noqa: E402
from src.utils.mlflow_tracking import setup_mlflow  # noqa: E402

log = logging.getLogger(__name__)


def compute_derived_metrics(
    test_df: pd.DataFrame,
    home_preds: np.ndarray,
    away_preds: np.ndarray,
    home_actuals: np.ndarray,
    away_actuals: np.ndarray,
) -> dict:
    """Compute metrics for derived spread and total."""

    # Derived predictions
    pred_spread = home_preds - away_preds
    pred_total = home_preds + away_preds

    # Actuals
    actual_spread = home_actuals - away_actuals
    actual_total = home_actuals + away_actuals

    # Metrics
    spread_rmse = np.sqrt(mean_squared_error(actual_spread, pred_spread))
    spread_mae = mean_absolute_error(actual_spread, pred_spread)

    total_rmse = np.sqrt(mean_squared_error(actual_total, pred_total))
    total_mae = mean_absolute_error(actual_total, pred_total)

    return {
        "spread_rmse": spread_rmse,
        "spread_mae": spread_mae,
        "total_rmse": total_rmse,
        "total_mae": total_mae,
        "pred_spread": pred_spread,
        "pred_total": pred_total,
    }


@hydra.main(config_path="../conf", config_name="config", version_base="1.2")
def main(cfg: DictConfig):
    run_id = str(uuid.uuid4())
    log.info(f"Starting Points-For prototype run: {run_id}")

    # Setup MLflow
    setup_mlflow(f"file://{cfg.paths.artifacts_dir}/mlruns")
    experiment_name = "points_for_prototype"
    mlflow.set_experiment(experiment_name)

    # Training years: 2019, 2021-2023
    train_years = [2019, 2021, 2022, 2023]
    test_years = [2024]

    adjustment_iteration = cfg.model.get(
        "adjustment_iteration", cfg.data.adjustment_iteration
    )

    log.info(f"Training years: {train_years}")
    log.info(f"Test years: {test_years}")
    log.info(f"Adjustment iteration: {adjustment_iteration}")

    # Load Training Data
    all_train_data = []
    for t_year in train_years:
        for week in range(1, 16):
            df = load_point_in_time_data(
                t_year,
                week,
                cfg.paths.data_dir,
                adjustment_iteration=adjustment_iteration,
            )
            if df is not None:
                all_train_data.append(df)

    if not all_train_data:
        log.error("No training data found.")
        return

    train_df = _concat_years(all_train_data)
    # Drop rows where either home or away score is missing
    train_df = train_df.dropna(subset=["home_points", "away_points"])

    x_train = select_features(train_df, cfg)
    y_train_home = train_df["home_points"]
    y_train_away = train_df["away_points"]

    log.info(
        f"Training on {len(train_df)} records with {len(x_train.columns)} features."
    )

    # Initialize Models
    # We use the same params for both home and away models for this prototype
    if cfg.model.type == "catboost":
        home_model = CatBoostRegressor(**cfg.model.params)
        away_model = CatBoostRegressor(**cfg.model.params)
    else:
        log.error(f"Model type {cfg.model.type} not supported for this script.")
        return

    with mlflow.start_run(run_name=run_id):
        mlflow.log_params(OmegaConf.to_container(cfg.model.params, resolve=True))
        mlflow.log_param("features", cfg.features.name)
        mlflow.log_param("adjustment_iteration", adjustment_iteration)

        # Train Home Model
        log.info("Training Home Points Model...")
        home_model.fit(x_train, y_train_home, verbose=False)

        # Train Away Model
        log.info("Training Away Points Model...")
        away_model.fit(x_train, y_train_away, verbose=False)

        # Evaluate on Test Year
        log.info("Evaluating on 2024...")
        all_test_data = []
        for week in range(1, 16):
            df = load_point_in_time_data(
                2024,
                week,
                cfg.paths.data_dir,
                adjustment_iteration=adjustment_iteration,
            )
            if df is not None:
                all_test_data.append(df)

        test_df = _concat_years(all_test_data)
        test_df = test_df.dropna(subset=["home_points", "away_points"])
        x_test = select_features(test_df, cfg)

        # Ensure feature alignment
        missing_cols = set(x_train.columns) - set(x_test.columns)
        for c in missing_cols:
            x_test[c] = 0.0  # or np.nan

        # Reorder to match training exactly
        x_test = x_test[x_train.columns]

        # Predict
        home_preds = home_model.predict(x_test)
        away_preds = away_model.predict(x_test)

        # Compute Metrics
        metrics = compute_derived_metrics(
            test_df,
            home_preds,
            away_preds,
            test_df["home_points"].values,
            test_df["away_points"].values,
        )

        log.info(f"Derived Spread RMSE: {metrics['spread_rmse']:.4f}")
        log.info(f"Derived Total RMSE: {metrics['total_rmse']:.4f}")

        mlflow.log_metric("derived_spread_rmse", metrics["spread_rmse"])
        mlflow.log_metric("derived_spread_mae", metrics["spread_mae"])
        mlflow.log_metric("derived_total_rmse", metrics["total_rmse"])
        mlflow.log_metric("derived_total_mae", metrics["total_mae"])

        # Save predictions for analysis
        pred_df = test_df[
            [
                "id",
                "season",
                "week",
                "home_team",
                "away_team",
                "home_points",
                "away_points",
            ]
        ].copy()
        pred_df["pred_home_score"] = home_preds
        pred_df["pred_away_score"] = away_preds
        pred_df["pred_spread"] = metrics["pred_spread"]
        pred_df["pred_total"] = metrics["pred_total"]
        pred_df["actual_spread"] = test_df["home_points"] - test_df["away_points"]
        pred_df["actual_total"] = test_df["home_points"] + test_df["away_points"]

        out_path = (
            Path(cfg.paths.artifacts_dir)
            / "predictions"
            / "points_for_prototype"
            / f"{run_id}_predictions.csv"
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pred_df.to_csv(out_path, index=False)
        log.info(f"Saved predictions to {out_path}")


if __name__ == "__main__":
    main()
