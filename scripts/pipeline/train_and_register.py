import logging
import sys
from pathlib import Path

import hydra
import mlflow
import mlflow.catboost
from dotenv import load_dotenv
from omegaconf import DictConfig

load_dotenv()

# Add src to path
sys.path.append(str(Path(__file__).resolve().parents[2]))
# noqa: E402
from catboost import CatBoostRegressor  # noqa: E402

from scripts.utils.model_registry import promote_to_production  # noqa: E402
from src.features.selector import get_feature_set_id, select_features  # noqa: E402
from src.models.features import load_point_in_time_data  # noqa: E402
from src.models.train_model import (  # noqa: E402
    _concat_years,
)
from src.utils.mlflow_tracking import setup_mlflow  # noqa: E402

log = logging.getLogger(__name__)


@hydra.main(config_path="../../conf", config_name="config", version_base="1.2")
def main(cfg: DictConfig):
    log.info("Starting ensemble training and registration...")

    # Setup MLflow
    setup_mlflow()
    experiment_name = (
        cfg.experiment.name if "experiment" in cfg and cfg.experiment else "default"
    )
    mlflow.set_experiment(experiment_name)

    # Training years: 2019, 2021-2023
    train_years = [2019, 2021, 2022, 2023]
    adjustment_iteration = cfg.model.get(
        "adjustment_iteration", cfg.data.adjustment_iteration
    )

    log.info(f"Training years: {train_years}")
    log.info(f"Adjustment iteration: {adjustment_iteration}")

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
    train_df = train_df.dropna(subset=[cfg.target])

    x_train = select_features(train_df, cfg)
    y_train = train_df[cfg.target]

    log.info(
        f"Training on {len(train_df)} records with {len(x_train.columns)} features."
    )

    # Train 5 models with different seeds
    base_seed = cfg.model.params.get("random_seed", 42)
    num_seeds = 5

    for i in range(num_seeds):
        seed = base_seed + i
        if "model_registry_name" in cfg:
            model_name = f"{cfg.model_registry_name}_seed_{i + 1}"
        else:
            model_name = f"spread_catboost_pruned_seed_{i + 1}"
        log.info(f"--- Training Model {i + 1}/{num_seeds} (Seed {seed}) ---")

        # Update params with new seed
        params = dict(cfg.model.params)
        params["random_seed"] = seed

        if cfg.model.type == "catboost":
            model = CatBoostRegressor(**params)
        else:
            log.error(f"Model type {cfg.model.type} not supported for this script.")
            return

        with mlflow.start_run() as run:
            # Log params
            mlflow.log_params(params)
            mlflow.log_param("features", cfg.features.name)
            mlflow.log_param("target", cfg.target)
            mlflow.log_param("feature_set_id", get_feature_set_id(cfg))
            mlflow.log_param("calibration_bias", cfg.model.get("calibration_bias", 0.0))
            mlflow.log_param("ensemble_seed_index", i)

            log.info("Fitting model...")
            model.fit(x_train, y_train, verbose=False)

            # Log model
            log.info("Logging model to MLflow...")
            mlflow.catboost.log_model(
                cb_model=model,
                artifact_path="model",
                registered_model_name=None,
            )

            run_id = run.info.run_id
            log.info(f"Run ID: {run_id}")

        # Register Model
        log.info(f"Registering model as {model_name}...")
        artifact_uri = f"runs:/{run_id}/model"

        registered_model = mlflow.register_model(
            model_uri=artifact_uri, name=model_name
        )
        version = registered_model.version

        client = mlflow.tracking.MlflowClient()
        client.update_model_version(
            name=model_name,
            version=version,
            description=f"Pruned spread model (Top 40 features). Trained on {train_years}. Seed {seed}.",
        )

        log.info(f"Registered version {version}")

        # Promote to Production
        log.info("Promoting to Production...")
        promote_to_production(model_name, version=version)

    log.info("Ensemble training complete.")


if __name__ == "__main__":
    main()
