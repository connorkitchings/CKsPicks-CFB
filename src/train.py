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
    # Extract features list if available
    features = None
    if "features" in cfg and "features" in cfg.features:
        features = list(cfg.features.features)

    # Load Training Data
    train_dfs = []

    # Check for recency features
    use_recency = False
    if "features" in cfg and "params" in cfg.features:
        if cfg.features.params.get("type") == "recency":
            use_recency = True
            alpha = cfg.features.params.get("alpha", 0.5)

    for year in cfg.training.train_years:
        if use_recency:
            from src.features.v2_recency import load_v2_recency_data

            print(f"Loading Recency Weighted data for {year} (alpha={alpha})...")
            df = load_v2_recency_data(year, alpha=alpha)
        else:
            df = load_v1_data(year, features=features)

        if df is not None:
            train_dfs.append(df)

    if not train_dfs:
        raise ValueError(f"No training data found for years {cfg.training.train_years}")

    train_df = pd.concat(train_dfs, ignore_index=True)

    # Load Test Data
    if use_recency:
        from src.features.v2_recency import load_v2_recency_data

        print(
            f"Loading Recency Weighted data for {cfg.training.test_year} (alpha={alpha})..."
        )
        test_df = load_v2_recency_data(cfg.training.test_year, alpha=alpha)
    else:
        test_df = load_v1_data(cfg.training.test_year, features=features)

    if test_df is None:
        raise ValueError(f"No test data found for year {cfg.training.test_year}")

    return train_df, test_df


def get_model(cfg: DictConfig, feature_override=None):
    """Factory to get model based on config type."""
    # Use override if provided, else config
    features = feature_override
    if features is None and "features" in cfg and "features" in cfg.features:
        features = list(cfg.features.features)

    if cfg.model.type == "linear_regression":
        # Pass params from config
        params = cfg.model.get("params", {})
        # Convert DictConfig to dict for unpacking
        params = OmegaConf.to_container(params, resolve=True)
        return V1BaselineModel(features=features, **params)
    elif cfg.model.type == "catboost":
        from src.models.v2_catboost import V2CatBoostModel

        params = cfg.model.get("params", {})
        params = OmegaConf.to_container(params, resolve=True)
        return V2CatBoostModel(features=features, **params)
    elif cfg.model.type == "xgboost":
        from src.models.v2_xgboost import V2XGBoostModel

        params = cfg.model.get("params", {})
        params = OmegaConf.to_container(params, resolve=True)
        # remove early_stopping_rounds from init params if passed, as it's usually for fit
        if "early_stopping_rounds" in params:
            del params["early_stopping_rounds"]
        return V2XGBoostModel(features=features, **params)
    elif cfg.model.type == "ensemble":
        from src.models.v2_ensemble import V2EnsembleModel

        params = cfg.model.get("params", {})
        params = OmegaConf.to_container(params, resolve=True)
        return V2EnsembleModel(features=features, **params)
    elif cfg.model.type == "stacking":
        from src.models.v2_stacking import V2StackingModel

        params = cfg.model.get("params", {})
        params = OmegaConf.to_container(params, resolve=True)
        return V2StackingModel(features=features, **params)
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

        # Feature Selection & Interaction Generation
        from src.features.selector import select_features

        # Note: select_features modifies df in-place to add interactions,
        # then returns the selected subset. We want the side-effect (interactions added to df)
        # and the list of selected columns.
        X_train = select_features(train_df, cfg)
        X_test = select_features(test_df, cfg)

        final_features = list(X_train.columns)
        print(f"Selected {len(final_features)} features (including interactions).")

        # Initialize Model
        model = get_model(cfg, feature_override=final_features)

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
            # Determine extension
            ext = ".joblib"
            if cfg.model.type == "xgboost":
                ext = ".json"
            elif cfg.model.type == "catboost":
                ext = ".cbm"

            model_path = Path("models") / f"{cfg.model.name}{ext}"
            model.save(model_path)

            # wrapper might append extension, check for it
            if not model_path.exists():
                if Path(f"{model_path}.json").exists():
                    model_path = Path(f"{model_path}.json")

            if model_path.exists():
                mlflow.log_artifact(str(model_path))
            else:
                print(f"Warning: Could not find saved model at {model_path}")


if __name__ == "__main__":
    main()
