"""Model training script with Hydra, Optuna, and MLflow Registry integration.

Usage:
    # Standard training
    uv run python src/models/train_model.py

    # Hyperparameter optimization
    uv run python src/models/train_model.py mode=optimize

    # Debug run
    uv run python src/models/train_model.py +experiment=debug
"""

import logging
from pathlib import Path

import hydra
import joblib
import mlflow
import numpy as np
import optuna
import pandas as pd
from catboost import CatBoostRegressor
from omegaconf import DictConfig, OmegaConf
from sklearn.metrics import mean_absolute_error, mean_squared_error

from src.config import MODELS_DIR, get_data_root
from src.models.features import (
    build_feature_list,
    filter_features_by_pack,
    load_point_in_time_data,
)
from src.utils.mlflow_tracking import get_tracking_uri
from src.utils.model_registry import generate_model_id, register_model

log = logging.getLogger(__name__)


def _evaluate(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "mae": float(mean_absolute_error(y_true, y_pred)),
    }


def _concat_years(dfs: list[pd.DataFrame]) -> pd.DataFrame:
    frames = [df for df in dfs if df is not None and not df.empty]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def load_data(cfg: DictConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load training and testing data based on configuration."""
    data_root = cfg.paths.data_dir or get_data_root()
    train_years = cfg.data.train_years
    test_year = cfg.data.test_year

    # Resolve adjustment iterations
    adj_iter = cfg.data.adjustment_iteration
    off_iter = cfg.data.adjustment_iteration_offense or adj_iter
    def_iter = cfg.data.adjustment_iteration_defense or adj_iter

    log.info(f"Loading training data for years: {train_years}")
    all_training_games = []
    for year in train_years:
        for week in range(1, 16):
            weekly_data = load_point_in_time_data(
                year,
                week,
                data_root,
                adjustment_iteration=adj_iter,
                adjustment_iteration_offense=off_iter,
                adjustment_iteration_defense=def_iter,
                include_betting_lines=False,  # We focus on Points-For (absolute) for now
            )
            if weekly_data is not None:
                all_training_games.append(weekly_data)
    train_df = _concat_years(all_training_games)

    log.info(f"Loading test data for year: {test_year}")
    all_test_games = []
    for week in range(1, 16):
        weekly_data = load_point_in_time_data(
            test_year,
            week,
            data_root,
            adjustment_iteration=adj_iter,
            adjustment_iteration_offense=off_iter,
            adjustment_iteration_defense=def_iter,
            include_betting_lines=False,
        )
        if weekly_data is not None:
            all_test_games.append(weekly_data)
    test_df = _concat_years(all_test_games)

    return train_df, test_df


def prepare_features(
    train_df: pd.DataFrame, test_df: pd.DataFrame, cfg: DictConfig
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Prepare feature matrices."""
    feature_list = build_feature_list(train_df)

    # Filter by pack if specified
    if cfg.features.get("packs"):
        feature_list = filter_features_by_pack(feature_list, cfg.features.packs)

    # Ensure features exist in test set
    feature_list = [c for c in feature_list if c in test_df.columns]

    if not feature_list:
        raise ValueError("No features available after filtering.")

    # Drop rows with missing features/targets
    target_cols = ["home_points", "away_points"]  # Points-For targets
    train_df = train_df.dropna(subset=feature_list + target_cols)
    test_df = test_df.dropna(subset=feature_list + target_cols)

    return train_df, test_df, feature_list


def train_model(
    x_train, y_train, x_test, y_test, params: dict, model_type: str = "catboost"
):
    """Train a single model."""
    if model_type == "catboost":
        model = CatBoostRegressor(**params)
        model.fit(x_train, y_train, verbose=0)
        preds = model.predict(x_test)
        return model, preds
    elif model_type == "xgboost":
        import xgboost as xgb

        model = xgb.XGBRegressor(**params)
        model.fit(x_train, y_train, verbose=False)
        preds = model.predict(x_test)
        return model, preds
    else:
        raise ValueError(f"Unsupported model type: {model_type}")


def objective(
    trial: optuna.Trial, x_train, y_train, x_test, y_test, cfg: DictConfig
) -> float:
    """Optuna objective function."""
    # Suggest parameters based on config
    params = {}
    for param_name, param_config in cfg.tuning.params.items():
        if param_config.type == "float":
            params[param_name] = trial.suggest_float(
                param_name,
                param_config.low,
                param_config.high,
                log=param_config.get("log", False),
            )
        elif param_config.type == "int":
            params[param_name] = trial.suggest_int(
                param_name, param_config.low, param_config.high
            )

    # Add fixed params
    params.update({"loss_function": "RMSE", "random_seed": 42, "verbose": 0})

    model, preds = train_model(
        x_train, y_train, x_test, y_test, params, model_type=cfg.model.type
    )
    metrics = _evaluate(y_test, preds)
    return metrics["rmse"]


@hydra.main(version_base=None, config_path="../../conf", config_name="config")
def main(cfg: DictConfig) -> None:
    mlflow.set_tracking_uri(get_tracking_uri())
    mlflow.set_experiment("CFB_Model_Training")

    # Load Data
    train_df, test_df = load_data(cfg)
    train_df, test_df, feature_list = prepare_features(train_df, test_df, cfg)

    x_train = train_df[feature_list]
    x_test = test_df[feature_list]

    # Targets (Points-For)
    targets = {
        "home": ("home_points", train_df["home_points"], test_df["home_points"]),
        "away": ("away_points", train_df["away_points"], test_df["away_points"]),
    }

    mode = cfg.get("mode", "train")  # train or optimize

    if mode == "optimize":
        log.info("Starting Hyperparameter Optimization...")
        study = optuna.create_study(direction=cfg.tuning.direction)

        # Optimize for Home Score (can be extended to Away)
        y_train = targets["home"][1]
        y_test = targets["home"][2]

        study.optimize(
            lambda trial: objective(trial, x_train, y_train, x_test, y_test, cfg),
            n_trials=cfg.tuning.n_trials,
        )

        log.info(f"Best params: {study.best_params}")
        # Save best params
        out_path = Path("conf/model/params/catboost_best.yaml")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        OmegaConf.save(DictConfig(study.best_params), out_path)
        log.info(f"Saved best params to {out_path}")
        return

    # Standard Training
    with mlflow.start_run(run_name=f"PointsFor_{cfg.data.test_year}") as run:
        mlflow.log_params(OmegaConf.to_container(cfg, resolve=True))
        mlflow.log_param("feature_count", len(feature_list))

        for target_name, (_, y_train, y_test) in targets.items():
            log.info(f"Training {target_name} model...")

            # Use params from config
            params = OmegaConf.to_container(cfg.model.params, resolve=True)

            model, preds = train_model(
                x_train, y_train, x_test, y_test, params, model_type=cfg.model.type
            )
            metrics = _evaluate(y_test, preds)

            mlflow.log_metrics(
                {
                    f"{target_name}_rmse": metrics["rmse"],
                    f"{target_name}_mae": metrics["mae"],
                }
            )

            # Register Model
            model_id = generate_model_id(
                model_type=cfg.model.type,
                feature_set=cfg.features.get("name", "custom"),
                tuning="baseline",  # TODO: dynamic
                data_version=f"train_{min(cfg.data.train_years)}_{max(cfg.data.train_years)}",
            )

            # Prepare input example for signature inference
            input_example = x_train.head(5)

            # Log and Register with signature
            mlflow.sklearn.log_model(
                model,
                f"model_{target_name}",
                input_example=input_example,
                # Signature is inferred from input_example
            )
            register_model(
                run_id=run.info.run_id,
                model_name=f"PointsFor_{target_name.capitalize()}",
                model_id=model_id,
                tags={"target": target_name, "framework": cfg.model.type},
            )

            # Save local artifact
            out_dir = MODELS_DIR / str(cfg.data.test_year)
            out_dir.mkdir(parents=True, exist_ok=True)
            joblib.dump(model, out_dir / f"{target_name}_catboost.joblib")

        log.info("Training complete.")


if __name__ == "__main__":
    main()
