"""
Train XGBoost Points-For models and evaluate ensemble with CatBoost.
"""

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
import yaml
from catboost import CatBoostRegressor
from dotenv import load_dotenv
from omegaconf import OmegaConf
from sklearn.metrics import mean_squared_error

from src.features.selector import select_features
from src.models.features import load_point_in_time_data
from src.models.train_model import _concat_years

load_dotenv()

sys.path.append(str(Path(__file__).resolve().parents[1]))

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Configuration
DATA_ROOT = "/Volumes/CK SSD/Coding Projects/cfb_model/"
TRAIN_YEARS = [2019, 2021, 2022, 2023]
TEST_YEAR = 2024
ADJUSTMENT_ITERATION = 2

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


def load_params(yaml_path: str) -> dict:
    with open(yaml_path, "r") as f:
        lines = [line for line in f if not line.strip().startswith("#")]
        return yaml.safe_load("\n".join(lines))


def load_data(years: list[int], depth: int) -> pd.DataFrame:
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
    return _concat_years(all_data)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--home-cat-params", type=str, required=True)
    parser.add_argument("--away-cat-params", type=str, required=True)
    parser.add_argument("--home-xgb-params", type=str, required=True)
    parser.add_argument("--away-xgb-params", type=str, required=True)
    args = parser.parse_args()

    # Load data
    log.info("Loading data...")
    train_df = load_data(TRAIN_YEARS, ADJUSTMENT_ITERATION)
    test_df = load_data([TEST_YEAR], ADJUSTMENT_ITERATION)

    x_train_full = select_features(train_df, FEATURE_CONFIG)
    x_test_full = select_features(test_df, FEATURE_CONFIG)
    common_features = sorted(
        list(set(x_train_full.columns).intersection(set(x_test_full.columns)))
    )

    required_cols = [
        "home_points_for",
        "away_points_for",
        "spread_target",
        "total_target",
    ]
    train_clean = train_df.dropna(subset=required_cols + common_features).reset_index(
        drop=True
    )
    test_clean = test_df.dropna(subset=required_cols + common_features).reset_index(
        drop=True
    )

    x_train = train_clean[common_features]
    y_train_home = train_clean["home_points_for"]
    y_train_away = train_clean["away_points_for"]

    x_test = test_clean[common_features]
    y_test_spread = test_clean["spread_target"]
    y_test_total = test_clean["total_target"]

    # Train CatBoost (Optimized)
    log.info("Training CatBoost models...")
    home_cat_params = load_params(args.home_cat_params)
    away_cat_params = load_params(args.away_cat_params)

    cb_home = CatBoostRegressor(**home_cat_params, verbose=False)
    cb_home.fit(x_train, y_train_home)

    cb_away = CatBoostRegressor(**away_cat_params, verbose=False)
    cb_away.fit(x_train, y_train_away)

    # Train XGBoost (Optimized)
    log.info("Training XGBoost models...")
    home_xgb_params = load_params(args.home_xgb_params)
    away_xgb_params = load_params(args.away_xgb_params)

    # Ensure early_stopping_rounds is in constructor if needed, or just rely on n_estimators from optimization
    # The optimization script saved params including early_stopping_rounds if we put it there?
    # No, we removed it from fit, but passed to constructor in optimization script.
    # The saved yaml has the params.
    # We should pass them to constructor.

    xgb_home = xgb.XGBRegressor(**home_xgb_params)
    xgb_home.fit(x_train, y_train_home)

    xgb_away = xgb.XGBRegressor(**away_xgb_params)
    xgb_away.fit(x_train, y_train_away)

    # Predictions
    log.info("Generating predictions...")

    # CatBoost Preds
    cb_pred_home = cb_home.predict(x_test)
    cb_pred_away = cb_away.predict(x_test)

    # XGBoost Preds
    xgb_pred_home = xgb_home.predict(x_test)
    xgb_pred_away = xgb_away.predict(x_test)

    # Ensemble (Simple Average)
    ens_pred_home = (cb_pred_home + xgb_pred_home) / 2
    ens_pred_away = (cb_pred_away + xgb_pred_away) / 2

    # Derived
    ens_pred_spread = ens_pred_home - ens_pred_away
    ens_pred_total = ens_pred_home + ens_pred_away

    # Metrics
    spread_rmse = np.sqrt(mean_squared_error(y_test_spread, ens_pred_spread))
    total_rmse = np.sqrt(mean_squared_error(y_test_total, ens_pred_total))

    # Hit Rates
    from src.utils.local_storage import LocalStorage

    storage = LocalStorage(data_root=DATA_ROOT, file_format="csv", data_type="raw")

    all_lines = []
    for week in range(1, 16):
        try:
            lines = storage.read_index(
                "betting_lines", {"year": TEST_YEAR, "week": week}
            )
            if lines:
                all_lines.extend(lines)
        except Exception:
            pass

    if all_lines:
        lines_df = pd.DataFrame(all_lines)
        lines_df["is_dk"] = lines_df["provider"] == "DraftKings"
        consensus = lines_df.sort_values(
            ["game_id", "is_dk"], ascending=[True, False]
        ).drop_duplicates("game_id")

        test_with_lines = test_clean.merge(
            consensus[["game_id", "spread"]],
            left_on="id",
            right_on="game_id",
            how="inner",
        )
        mask = test_clean["id"].isin(test_with_lines["id"])

        pred_spread_sub = ens_pred_spread[mask]
        actual_spread_sub = y_test_spread[mask]
        lines_sub = test_with_lines["spread"].values

        # Hit logic
        pred_margin = pred_spread_sub + lines_sub
        actual_margin = actual_spread_sub + lines_sub
        valid = (pred_margin != 0) & (actual_margin != 0)
        hits = np.sign(pred_margin[valid]) == np.sign(actual_margin[valid])

        log.info(f"Ensemble Spread Hit Rate: {np.mean(hits):.1%}")
        log.info(f"Ensemble Spread RMSE: {spread_rmse:.2f}")
        log.info(f"Ensemble Total RMSE: {total_rmse:.2f}")

        # Compare to CatBoost only
        cb_pred_spread = cb_pred_home - cb_pred_away
        cb_pred_sub = cb_pred_spread[mask]
        cb_pred_margin = cb_pred_sub + lines_sub
        cb_hits = np.sign(cb_pred_margin[valid]) == np.sign(actual_margin[valid])
        log.info(f"CatBoost-Only Spread Hit Rate: {np.mean(cb_hits):.1%}")


if __name__ == "__main__":
    main()
