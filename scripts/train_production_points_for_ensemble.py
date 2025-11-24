"""
Train and register production Points-For ensemble models.

This script trains a seeded ensemble of CatBoost models for both the home_points and
away_points targets. Each individual model is registered to the MLflow Model Registry,
allowing for robust, versioned production deployments.

This script is designed to be run once per production model "vintage" (e.g., once a year
or when a major feature/logic change occurs).

Example usage (from project root):
`uv run python scripts/train_production_points_for_ensemble.py`
"""

import logging
import sys
from pathlib import Path

import hydra
import mlflow
import mlflow.catboost
from catboost import CatBoostRegressor
from dotenv import load_dotenv
from omegaconf import DictConfig, OmegaConf

load_dotenv()

# Add src to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.model_registry import promote_to_production  # noqa: E402
from src.features.selector import get_feature_set_id, select_features  # noqa: E402
from src.models.features import load_point_in_time_data  # noqa: E402
from src.models.train_model import _concat_years  # noqa: E402
from src.utils.mlflow_tracking import setup_mlflow  # noqa: E402

log = logging.getLogger(__name__)


def train_and_register_target(
    cfg: DictConfig,
    target: str,
    model_registry_name: str,
    x_train,
    y_train,
    train_years,
):
    """
    Trains a seeded ensemble for a single target and registers models to MLflow.
    """
    log.info(f"--- Starting training for target: {target} ---")

    base_seed = cfg.model.params.get("random_seed", 42)
    num_seeds = cfg.model.get("num_seeds", 5)

    for i in range(num_seeds):
        seed = base_seed + i
        model_name_seeded = f"{model_registry_name}_seed_{i + 1}"
        log.info(f"Training Model {i + 1}/{num_seeds} (Seed {seed}) for {target}")

        if target == "home_points":
            params = dict(cfg.model.home_params)
        elif target == "away_points":
            params = dict(cfg.model.away_params)
        else:
            raise ValueError(f"Unknown target: {target}")
        params["random_seed"] = seed

        if cfg.model.type != "catboost":
            log.error(f"Model type {cfg.model.type} not supported.")
            raise ValueError(f"Unsupported model type: {cfg.model.type}")

        model = CatBoostRegressor(**params)

        with mlflow.start_run(
            run_name=f"train_{model_name_seeded}",
            description=f"Training run for {target} model, seed {seed}",
        ) as run:
            # Log params
            mlflow.log_params(params)
            mlflow.log_param("features_name", cfg.features.name)
            mlflow.log_param("feature_set_id", get_feature_set_id(cfg))
            mlflow.log_param("target", target)
            mlflow.log_param("ensemble_seed_index", i)
            mlflow.log_param("train_years", str(train_years))

            log.info(f"Fitting model for {target}...")
            model.fit(x_train, y_train, verbose=False)

            log.info("Logging model to MLflow...")
            mlflow.catboost.log_model(
                cb_model=model,
                artifact_path="model",
                registered_model_name=None,  # Register manually later
            )
            run_id = run.info.run_id
            log.info(f"Run ID for seed {seed}: {run_id}")

        # Register Model
        log.info(f"Registering model as {model_name_seeded}...")
        artifact_uri = f"runs:/{run_id}/model"
        registered_model = mlflow.register_model(
            model_uri=artifact_uri, name=model_name_seeded
        )
        version = registered_model.version

        client = mlflow.tracking.MlflowClient()
        client.update_model_version(
            name=model_name_seeded,
            version=version,
            description=(
                f"Points-For Production Model for {target}. "
                f"Trained on {train_years}. Seed {seed}."
            ),
        )

        log.info(f"Registered version {version} for {model_name_seeded}")

        # Promote to Production
        log.info(f"Promoting {model_name_seeded} to Production...")
        promote_to_production(model_name_seeded, version=version)


@hydra.main(
    config_path="../conf/experiment",
    config_name="points_for_production_training",
    version_base="1.2",
)
def main(cfg: DictConfig):
    log.info("Starting Production Points-For Ensemble Training and Registration.")
    log.info(f"Config:\n{OmegaConf.to_yaml(cfg)}")

    # --- MLflow Setup ---
    setup_mlflow(f"file://{cfg.paths.artifacts_dir}/mlruns")
    experiment_name = cfg.experiment.name
    mlflow.set_experiment(experiment_name)
    log.info(f"MLflow experiment set to: {experiment_name}")

    # --- Data Loading ---
    train_years = cfg.data.train_years
    adjustment_iteration = cfg.data.adjustment_iteration
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
        log.error("No training data found. Aborting.")
        return

    train_df = _concat_years(all_train_data)
    train_df = train_df.dropna(subset=["home_points", "away_points"])

    x_train = select_features(train_df, cfg)
    y_train_home = train_df["home_points"]
    y_train_away = train_df["away_points"]

    log.info(
        f"Training on {len(train_df)} records with {len(x_train.columns)} features."
    )

    # --- Train and Register Home Models ---
    train_and_register_target(
        cfg,
        "home_points",
        cfg.model.model_registry_name_home,
        x_train,
        y_train_home,
        train_years,
    )

    # --- Train and Register Away Models ---
    train_and_register_target(
        cfg,
        "away_points",
        cfg.model.model_registry_name_away,
        x_train,
        y_train_away,
        train_years,
    )

    log.info("Production Points-For ensemble training complete.")


if __name__ == "__main__":
    main()
