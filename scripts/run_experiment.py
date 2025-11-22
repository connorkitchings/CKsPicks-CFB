import logging
import sys
import uuid
from datetime import datetime
from pathlib import Path

import hydra
import mlflow
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from omegaconf import DictConfig, OmegaConf

load_dotenv()

# Add src to path
# Add src to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from catboost import CatBoostRegressor  # noqa: E402
from sklearn.linear_model import Ridge  # noqa: E402
from sklearn.metrics import mean_absolute_error, mean_squared_error  # noqa: E402

from src.features.selector import get_feature_set_id, select_features  # noqa: E402
from src.models.features import load_point_in_time_data  # noqa: E402
from src.models.train_model import _concat_years  # noqa: E402

log = logging.getLogger(__name__)


@hydra.main(config_path="../conf", config_name="config", version_base="1.2")
def main(cfg: DictConfig):
    run_id = str(uuid.uuid4())
    log.info(f"Starting experiment run: {run_id}")
    log.info(f"Config:\n{OmegaConf.to_yaml(cfg)}")

    # Setup MLflow
    mlflow_tracking_uri = f"file://{cfg.paths.artifacts_dir}/mlruns"
    mlflow.set_tracking_uri(mlflow_tracking_uri)
    experiment_name = cfg.experiment.name if cfg.experiment else "default"
    mlflow.set_experiment(experiment_name)

    # Define WFV years
    # Default to 2023, 2024 if not specified
    test_years = cfg.get("test_years", [2023, 2024])
    start_train_year = cfg.get("start_train_year", 2019)

    metrics = []

    with mlflow.start_run(run_name=run_id):
        # Log params
        mlflow.log_params(OmegaConf.to_container(cfg.model.params, resolve=True))
        mlflow.log_param("features", cfg.features.name)
        mlflow.log_param("target", cfg.target)
        mlflow.log_param("feature_set_id", get_feature_set_id(cfg))

        for year in test_years:
            log.info(f"--- Processing Test Year: {year} ---")

            # Load Training Data
            train_years = list(range(start_train_year, year))
            log.info(f"Loading training data for years: {train_years}")

            all_train_data = []
            # We load week-by-week to ensure point-in-time correctness if needed,
            # but for training set (past years), we can load all weeks.
            # However, load_point_in_time_data is designed for specific weeks.
            # To be safe and consistent with WFV script, we iterate.

            # Optimization: For past years, we can load the full season if available,
            # but load_point_in_time_data might be safer.
            # Let's stick to the pattern in walk_forward_validation.py for now.

            for t_year in train_years:
                # Load all weeks for training year
                # Assuming 15 weeks max
                for week in range(1, 16):
                    df = load_point_in_time_data(
                        t_year,
                        week,
                        cfg.paths.data_dir,
                        adjustment_iteration=4,  # Default to 4 for now
                    )
                    if df is not None:
                        all_train_data.append(df)

            if not all_train_data:
                log.warning(f"No training data found for year {year}. Skipping.")
                continue

            train_df = _concat_years(all_train_data)

            # Load Test Data
            # For test year, we validate week by week?
            # Or just train once on T-1 and predict T?
            # The plan says "Train on seasons [Start, T-1], Validate on Season T".
            # Usually this implies retraining every week (expanding window) OR training once per season.
            # For simplicity and speed in this refactor, let's do ONCE per season first (Train on <T, Test on T).
            # But strictly speaking, for betting, we retrain every week.
            # Let's do week-by-week evaluation to be accurate.

            # We need to retrain every week to be truly point-in-time correct?
            # Actually, if we train on [2019-2022], we can predict ALL of 2023 without leakage
            # IF we don't use 2023 data in training.
            # So we can train ONCE on [2019-2022] and predict 2023.
            # This is the "Season-Holdout" approach.
            # The "Walk-Forward" approach usually adds Week 1 of 2023 to train Week 2.
            # Let's stick to Season-Holdout for this baseline to match "Train on seasons [Start, T-1]".

            log.info(f"Training model on {len(train_df)} records...")
            train_df = train_df.dropna(subset=[cfg.target])
            X_train = select_features(train_df, cfg)  # noqa: N806
            y_train = train_df[cfg.target]

            # Initialize Model
            if cfg.model.type == "catboost":
                model = CatBoostRegressor(**cfg.model.params)
            elif cfg.model.type == "ridge":
                model = Ridge(**cfg.model.params)
            else:
                raise ValueError(f"Unknown model type: {cfg.model.type}")

            model.fit(X_train, y_train)

            # Evaluate on Test Year
            log.info(f"Evaluating on {year}...")
            all_test_data = []
            for week in range(1, 16):
                df = load_point_in_time_data(
                    year, week, cfg.paths.data_dir, adjustment_iteration=4
                )
                if df is not None:
                    all_test_data.append(df)

            if not all_test_data:
                log.warning(f"No test data found for year {year}.")
                continue

            test_df = _concat_years(all_test_data)
            test_df = test_df.dropna(subset=[cfg.target])
            X_test = select_features(test_df, cfg)  # noqa: N806
            y_test = test_df[cfg.target]

            preds = model.predict(X_test)

            rmse = np.sqrt(mean_squared_error(y_test, preds))
            mae = mean_absolute_error(y_test, preds)

            log.info(f"Year {year} RMSE: {rmse:.4f}, MAE: {mae:.4f}")
            metrics.append({"year": year, "rmse": rmse, "mae": mae})

            # Save predictions
            pred_df = test_df[["id", "season", "week", "home_team", "away_team"]].copy()
            pred_df["prediction"] = preds
            pred_df["actual"] = y_test

            out_path = (
                Path(cfg.paths.artifacts_dir)
                / "predictions"
                / experiment_name
                / run_id
                / f"{year}_predictions.csv"
            )
            out_path.parent.mkdir(parents=True, exist_ok=True)
            pred_df.to_csv(out_path, index=False)

        # Aggregate Metrics
        if metrics:
            avg_rmse = np.mean([m["rmse"] for m in metrics])
            avg_mae = np.mean([m["mae"] for m in metrics])

            mlflow.log_metric("rmse_test", avg_rmse)
            mlflow.log_metric("mae_test", avg_mae)
            log.info(f"Run complete. Avg RMSE: {avg_rmse:.4f}, Avg MAE: {avg_mae:.4f}")

            # Log to experiment_log.csv
            log_entry = {
                "run_id": run_id,
                "timestamp": datetime.utcnow().isoformat(),
                "experiment_name": experiment_name,
                "model_type": cfg.model.type,
                "target": cfg.target,
                "rmse_test": avg_rmse,
                "mae_test": avg_mae,
                "config_path": "conf/config.yaml",
            }
            log_path = Path(cfg.paths.artifacts_dir) / "experiment_log.csv"
            pd.DataFrame([log_entry]).to_csv(
                log_path, mode="a", header=not log_path.exists(), index=False
            )
        else:
            log.warning("No metrics computed.")


if __name__ == "__main__":
    main()
