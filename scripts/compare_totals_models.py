"""
Compare Baseline vs. Mixed Ensemble performance specifically for Totals.

Baseline: CatBoost(depth=6, lr=0.05, iter=800)
Mixed Ensemble: Optimized CatBoost + Default XGBoost
"""

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from catboost import CatBoostRegressor
from dotenv import load_dotenv
from omegaconf import OmegaConf

from src.features.selector import select_features
from src.models.features import load_point_in_time_data
from src.models.train_model import _concat_years
from src.utils.local_storage import LocalStorage

load_dotenv()

sys.path.append(str(Path(__file__).resolve().parents[1]))

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

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


def get_betting_lines(year: int) -> pd.DataFrame:
    storage = LocalStorage(data_root=DATA_ROOT, file_format="csv", data_type="raw")
    all_lines = []
    for week in range(1, 16):
        try:
            lines = storage.read_index("betting_lines", {"year": year, "week": week})
            if lines:
                all_lines.extend(lines)
        except Exception:
            pass

    if not all_lines:
        return pd.DataFrame()

    lines_df = pd.DataFrame(all_lines)
    lines_df["is_dk"] = lines_df["provider"] == "DraftKings"
    # Prefer DraftKings, then fallback
    consensus = lines_df.sort_values(
        ["game_id", "is_dk"], ascending=[True, False]
    ).drop_duplicates("game_id")
    return consensus


def evaluate_hit_rate(y_true, y_pred, lines, bet_type="total"):
    """
    Calculate hit rate against betting lines.
    bet_type: 'total' or 'spread'
    """
    # Merge predictions with lines
    # We need game_ids to merge with lines.
    # This function assumes y_true/y_pred are aligned with the test_df which has 'id'
    return 0.0


def main():
    # Load Data
    log.info("Loading data...")
    train_df = load_data(TRAIN_YEARS, ADJUSTMENT_ITERATION)
    test_df = load_data([TEST_YEAR], ADJUSTMENT_ITERATION)

    # Feature Selection
    x_train_full = select_features(train_df, FEATURE_CONFIG)
    x_test_full = select_features(test_df, FEATURE_CONFIG)
    common_features = sorted(
        list(set(x_train_full.columns).intersection(set(x_test_full.columns)))
    )

    required_cols = [
        "home_points_for",
        "away_points_for",
        "total_target",
        "spread_target",
    ]
    train_clean = train_df.dropna(subset=required_cols + common_features).reset_index(
        drop=True
    )
    test_clean = test_df.dropna(subset=required_cols + common_features).reset_index(
        drop=True
    )

    x_train = train_clean[common_features]
    y_home_train = train_clean["home_points_for"]
    y_away_train = train_clean["away_points_for"]

    x_test = test_clean[common_features]
    y_total_test = test_clean["total_target"]
    y_spread_test = test_clean["spread_target"]

    # Load Betting Lines
    lines_df = get_betting_lines(TEST_YEAR)
    test_with_lines = test_clean.merge(
        lines_df[["game_id", "over_under", "spread"]],
        left_on="id",
        right_on="game_id",
        how="inner",
    )

    # Align x_test with lines
    mask = test_clean["id"].isin(test_with_lines["id"])
    x_test_lines = x_test[mask]
    y_total_test_lines = y_total_test[mask]
    y_spread_test_lines = y_spread_test[mask]
    lines_subset = test_with_lines

    # --- 1. Baseline CatBoost ---
    log.info("Training Baseline CatBoost...")
    base_params = {
        "depth": 6,
        "learning_rate": 0.05,
        "iterations": 800,
        "loss_function": "RMSE",
        "random_seed": 42,
        "verbose": 0,
    }
    cb_home_base = CatBoostRegressor(**base_params).fit(x_train, y_home_train)
    cb_away_base = CatBoostRegressor(**base_params).fit(x_train, y_away_train)

    pred_home_base = cb_home_base.predict(x_test_lines)
    pred_away_base = cb_away_base.predict(x_test_lines)
    pred_total_base = pred_home_base + pred_away_base
    pred_spread_base = pred_home_base - pred_away_base

    # --- 2. Mixed Ensemble ---
    log.info("Training Mixed Ensemble...")
    # Optimized CatBoost Params (Hardcoded from walkthrough)
    home_cat_opt = {
        "depth": 6,
        "learning_rate": 0.02458,
        "iterations": 800,
        "l2_leaf_reg": 6.6488,
        "subsample": 0.7514,
        "colsample_bylevel": 0.6982,
        "min_data_in_leaf": 13,
        "loss_function": "RMSE",
        "random_seed": 42,
        "verbose": 0,
    }
    away_cat_opt = {
        "depth": 7,
        "learning_rate": 0.01379,
        "iterations": 1500,
        "l2_leaf_reg": 2.7971,
        "subsample": 0.8057,
        "colsample_bylevel": 0.8370,
        "min_data_in_leaf": 1,
        "loss_function": "RMSE",
        "random_seed": 42,
        "verbose": 0,
    }
    # Default XGBoost Params
    xgb_params = {
        "n_estimators": 1000,
        "learning_rate": 0.05,
        "max_depth": 6,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "objective": "reg:squarederror",
        "n_jobs": -1,
        "random_state": 42,
    }

    cb_home_opt = CatBoostRegressor(**home_cat_opt).fit(x_train, y_home_train)
    xgb_home = xgb.XGBRegressor(**xgb_params).fit(x_train, y_home_train)

    cb_away_opt = CatBoostRegressor(**away_cat_opt).fit(x_train, y_away_train)
    xgb_away = xgb.XGBRegressor(**xgb_params).fit(x_train, y_away_train)

    pred_home_ens = (
        cb_home_opt.predict(x_test_lines) + xgb_home.predict(x_test_lines)
    ) / 2
    pred_away_ens = (
        cb_away_opt.predict(x_test_lines) + xgb_away.predict(x_test_lines)
    ) / 2
    pred_total_ens = pred_home_ens + pred_away_ens
    pred_spread_ens = pred_home_ens - pred_away_ens

    # --- Evaluation ---
    def calc_metrics(pred_total, pred_spread, name):
        # Totals
        ou_lines = lines_subset["over_under"].values
        # Pred > Line -> Over. Actual > Line -> Over.
        # We check if (Pred - Line) has same sign as (Actual - Line)
        pred_diff = pred_total - ou_lines
        actual_diff = y_total_test_lines - ou_lines
        valid = (pred_diff != 0) & (actual_diff != 0)
        hits = np.sign(pred_diff[valid]) == np.sign(actual_diff[valid])
        total_acc = np.mean(hits)

        # Spreads
        # Line is usually Home Spread (e.g. -7).
        # Pred Spread is Home - Away.
        # Pred Margin = Pred Spread + Line.
        # Actual Margin = Actual Spread + Line.
        spread_lines = lines_subset["spread"].values
        pred_margin = pred_spread + spread_lines
        actual_margin = y_spread_test_lines + spread_lines
        valid_s = (pred_margin != 0) & (actual_margin != 0)
        hits_s = np.sign(pred_margin[valid_s]) == np.sign(actual_margin[valid_s])
        spread_acc = np.mean(hits_s)

        log.info(f"--- {name} ---")
        log.info(f"Total Hit Rate: {total_acc:.1%} (n={sum(valid)})")
        log.info(f"Spread Hit Rate: {spread_acc:.1%} (n={sum(valid_s)})")
        return total_acc, spread_acc

    calc_metrics(pred_total_base, pred_spread_base, "Baseline CatBoost")
    calc_metrics(pred_total_ens, pred_spread_ens, "Mixed Ensemble")


if __name__ == "__main__":
    main()
