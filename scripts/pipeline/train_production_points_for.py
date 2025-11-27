import logging
import sys
import uuid
from pathlib import Path

import hydra
import mlflow
import yaml
from catboost import CatBoostRegressor
from dotenv import load_dotenv
from omegaconf import DictConfig

load_dotenv()

# Add src to path
sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.features.selector import select_features  # noqa: E402
from src.models.features import load_point_in_time_data  # noqa: E402
from src.models.train_model import _concat_years  # noqa: E402
from src.utils.mlflow_tracking import setup_mlflow  # noqa: E402

log = logging.getLogger(__name__)


@hydra.main(config_path="../../conf", config_name="config", version_base="1.2")
def main(cfg: DictConfig):
    run_id = str(uuid.uuid4())
    log.info(f"Starting Production Points-For Training: {run_id}")

    # Setup MLflow
    setup_mlflow()
    experiment_name = "production_training"
    mlflow.set_experiment(experiment_name)

    # Training years: 2019, 2021-2023 (Full historical set excluding COVID 2020)
    # We are NOT training on 2024 yet as that is our test set for the runthrough.
    # In a real production scenario for 2025, we would include 2024.
    # But to validate performance on 2024, we must train only on prior years.
    train_years = [2019, 2021, 2022, 2023]
    adjustment_iteration = 2

    log.info(f"Training years: {train_years}")

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

    log.info(f"Training on {len(train_df)} records.")

    # Load Optimized Parameters
    home_params_path = Path("artifacts/optimization/best_home_points_params.yaml")
    away_params_path = Path("artifacts/optimization/best_away_points_params.yaml")

    if not home_params_path.exists() or not away_params_path.exists():
        log.error("Optimized parameters not found. Run optimization first.")
        return

    with open(home_params_path, "r") as f:
        home_params = yaml.safe_load(f)

    with open(away_params_path, "r") as f:
        away_params = yaml.safe_load(f)

    # Train and Register Home Model
    log.info("Training Home Points Model...")
    home_model = CatBoostRegressor(**home_params)

    with mlflow.start_run(run_name=f"deploy_home_{run_id}"):
        mlflow.log_params(home_params)
        home_model.fit(x_train, y_train_home, verbose=False)

        # Register
        model_name = "cfb_points_for_home"
        log.info(f"Registering model: {model_name}")
        mlflow.catboost.log_model(
            home_model,
            artifact_path="model",
            registered_model_name=model_name,
        )

        # Promote to Production (using MlflowClient)
        client = mlflow.tracking.MlflowClient()
        latest_version = client.get_latest_versions(model_name, stages=["None"])[
            0
        ].version
        client.transition_model_version_stage(
            name=model_name,
            version=latest_version,
            stage="Production",
            archive_existing_versions=True,
        )
        log.info(f"Promoted {model_name} version {latest_version} to Production")

    # Train and Register Away Model
    log.info("Training Away Points Model...")
    away_model = CatBoostRegressor(**away_params)

    with mlflow.start_run(run_name=f"deploy_away_{run_id}"):
        mlflow.log_params(away_params)
        away_model.fit(x_train, y_train_away, verbose=False)

        # Register
        model_name = "cfb_points_for_away"
        log.info(f"Registering model: {model_name}")
        mlflow.catboost.log_model(
            away_model,
            artifact_path="model",
            registered_model_name=model_name,
        )

        # Promote to Production
        client = mlflow.tracking.MlflowClient()
        latest_version = client.get_latest_versions(model_name, stages=["None"])[
            0
        ].version
        client.transition_model_version_stage(
            name=model_name,
            version=latest_version,
            stage="Production",
            archive_existing_versions=True,
        )
        log.info(f"Promoted {model_name} version {latest_version} to Production")


if __name__ == "__main__":
    main()
