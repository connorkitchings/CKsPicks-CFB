from pathlib import Path

import hydra
import mlflow
import pandas as pd
from omegaconf import DictConfig, OmegaConf

from src.features.v1_pipeline import load_v1_data
from src.models.v1_baseline import V1BaselineModel
from src.utils.mlflow_tracking import get_or_create_experiment, get_tracking_uri


def load_and_prepare_data(cfg: DictConfig):
    """Load and concatenate data for configured years."""
    # Load Training Data
    train_dfs = []
    for year in cfg.training.train_years:
        df = load_v1_data(year)
        if df is not None:
            train_dfs.append(df)

    if not train_dfs:
        raise ValueError(f"No training data found for years {cfg.training.train_years}")

    train_df = pd.concat(train_dfs, ignore_index=True)

    # Load Test Data
    test_df = load_v1_data(cfg.training.test_year)
    if test_df is None:
        raise ValueError(f"No test data found for year {cfg.training.test_year}")

    return train_df, test_df


def get_model(cfg: DictConfig):
    """Factory to get model based on config type."""
    if cfg.model.type == "linear_regression":
        # Pass params from config
        params = cfg.model.get("params", {})
        return V1BaselineModel(**params)
    else:
        raise ValueError(f"Unknown model type: {cfg.model.type}")


@hydra.main(config_path="../conf", config_name="config", version_base="1.2")
def main(cfg: DictConfig):
    # Setup MLflow
    mlflow.set_tracking_uri(get_tracking_uri())

    # Handle experiment name safely
    exp_name = "Default"
    if "experiment" in cfg and cfg.experiment is not None:
        exp_name = cfg.experiment.get("name", "Default")

    experiment_id = get_or_create_experiment(exp_name)

    with mlflow.start_run(experiment_id=experiment_id, run_name=cfg.model.name):
        # Log Config
        mlflow.log_params(OmegaConf.to_container(cfg, resolve=True))

        # Load Data
        print("Loading Data...")
        train_df, test_df = load_and_prepare_data(cfg)
        print(f"Train size: {len(train_df)}, Test size: {len(test_df)}")

        # Initialize Model
        model = get_model(cfg)

        # Train
        print("Training...")
        model.fit(train_df)

        # Evaluate
        print("Evaluating...")
        metrics = model.evaluate(test_df)

        # Log Metrics
        mlflow.log_metrics(metrics)
        print(f"Metrics: {metrics}")

        # Save Model (Local & MLflow)
        # For now, just local save if model supports it
        if hasattr(model, "save"):
            model_path = Path("models") / f"{cfg.model.name}.joblib"
            model.save(model_path)
            mlflow.log_artifact(str(model_path))


if __name__ == "__main__":
    main()
