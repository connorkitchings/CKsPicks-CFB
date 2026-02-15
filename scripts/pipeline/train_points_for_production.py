"""
Train and deploy Points-For Mixed Ensemble (CatBoost + XGBoost) for production.

This script trains the optimized CatBoost and default XGBoost models on historical data
(2019, 2021-2023), wraps them in an EnsembleModel, and saves them to the
artifacts/models directory for use by the weekly prediction pipeline.
"""

import argparse
import logging
import sys
from pathlib import Path

import joblib
import mlflow
import pandas as pd
import xgboost as xgb
from catboost import CatBoostRegressor
from dotenv import load_dotenv
from omegaconf import OmegaConf

from cks_picks_cfb.features.selector import select_features
from cks_picks_cfb.models.ensemble import EnsembleModel
from cks_picks_cfb.models.features import load_point_in_time_data
from cks_picks_cfb.models.train_model import _concat_years
from cks_picks_cfb.utils.mlflow_tracking import setup_mlflow

load_dotenv()

sys.path.append(str(Path(__file__).resolve().parents[2]))
# noqa: E402
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Configuration
DATA_ROOT = "/Volumes/CK SSD/Coding Projects/cfb_model/"
TRAIN_YEARS = [2019, 2021, 2022, 2023]
TARGET_YEAR = 2024  # The "model year" we are deploying for
ADJUSTMENT_ITERATION = 2

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


def load_data(years: list[int], depth: int) -> pd.DataFrame:
    """Load data for specified years and adjustment iteration depth."""
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
        raise ValueError(f"No data found for years={years}, depth={depth}")

    return _concat_years(all_data)


def main():
    parser = argparse.ArgumentParser(description="Train Points-For Production Models")
    parser.add_argument(
        "--output-dir",
        type=str,
        default="artifacts/models",
        help="Directory to save models",
    )
    args = parser.parse_args()

    # Setup MLflow
    setup_mlflow()
    mlflow.set_experiment("points_for_production")

    # Load Configs
    cat_config = OmegaConf.load("conf/model/points_for_catboost.yaml")
    xgb_config = OmegaConf.load("conf/model/points_for_xgboost.yaml")

    log.info("Loading training data...")
    train_df = load_data(TRAIN_YEARS, ADJUSTMENT_ITERATION)

    # Feature Selection
    log.info("Selecting features...")
    x_train_full = select_features(train_df, FEATURE_CONFIG)

    # Prepare Targets
    required_cols = ["home_points_for", "away_points_for"]
    train_clean = train_df.dropna(
        subset=required_cols + list(x_train_full.columns)
    ).reset_index(drop=True)

    x_train = train_clean[x_train_full.columns]
    y_home = train_clean["home_points_for"]
    y_away = train_clean["away_points_for"]

    log.info(
        f"Training on {len(train_clean)} records with {len(x_train.columns)} features."
    )

    with mlflow.start_run(run_name=f"production_deploy_{TARGET_YEAR}"):
        mlflow.log_params({"train_years": TRAIN_YEARS, "target_year": TARGET_YEAR})

        # --- Train Home Models ---
        log.info("Training Home Models...")

        # CatBoost
        log.info("  Home CatBoost...")
        home_cat_params = OmegaConf.to_container(cat_config.home_params, resolve=True)
        cb_home = CatBoostRegressor(**home_cat_params)
        cb_home.fit(x_train, y_home, verbose=False)

        # XGBoost
        log.info("  Home XGBoost...")
        xgb_params = OmegaConf.to_container(xgb_config.params, resolve=True)
        # Ensure early_stopping_rounds is handled if present in params (it shouldn't be for production training without eval set)
        # But we might want to set n_estimators to what we found or just use the default 1000.
        xgb_home = xgb.XGBRegressor(**xgb_params)
        xgb_home.fit(x_train, y_home)

        # Ensemble
        home_ensemble = EnsembleModel([cb_home, xgb_home])

        # --- Train Away Models ---
        log.info("Training Away Models...")

        # CatBoost
        log.info("  Away CatBoost...")
        away_cat_params = OmegaConf.to_container(cat_config.away_params, resolve=True)
        cb_away = CatBoostRegressor(**away_cat_params)
        cb_away.fit(x_train, y_away, verbose=False)

        # XGBoost
        log.info("  Away XGBoost...")
        xgb_away = xgb.XGBRegressor(**xgb_params)
        xgb_away.fit(x_train, y_away)

        # Ensemble
        away_ensemble = EnsembleModel([cb_away, xgb_away])

        # --- Save Models ---
        output_path = Path(args.output_dir) / str(TARGET_YEAR)
        output_path.mkdir(parents=True, exist_ok=True)

        home_model_path = output_path / "points_for_home.joblib"
        away_model_path = output_path / "points_for_away.joblib"

        log.info(f"Saving home model to {home_model_path}...")
        joblib.dump(home_ensemble, home_model_path)

        log.info(f"Saving away model to {away_model_path}...")
        joblib.dump(away_ensemble, away_model_path)

        # Log artifacts to MLflow
        mlflow.log_artifact(str(home_model_path), artifact_path="models")
        mlflow.log_artifact(str(away_model_path), artifact_path="models")

        # Save Metadata
        metadata = {
            "train_years": TRAIN_YEARS,
            "target_year": TARGET_YEAR,
            "adjustment_iteration": ADJUSTMENT_ITERATION,
            "feature_config": OmegaConf.to_container(FEATURE_CONFIG, resolve=True),
            "catboost_config": OmegaConf.to_container(cat_config, resolve=True),
            "xgboost_config": OmegaConf.to_container(xgb_config, resolve=True),
            "generated_at": pd.Timestamp.now().isoformat(),
        }
        metadata_path = output_path / "metadata.json"
        import json

        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
        log.info(f"Saved metadata to {metadata_path}")

        log.info("Deployment complete!")


if __name__ == "__main__":
    main()
