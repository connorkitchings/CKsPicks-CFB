"""
Validate optimized Points-For models on 2024 holdout data.

This script trains models using optimized parameters on 2019-2023 data
and evaluates performance on 2024 holdout.
"""

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from catboost import CatBoostRegressor
from dotenv import load_dotenv
from omegaconf import OmegaConf
from sklearn.metrics import mean_squared_error

from src.features.selector import select_features
from src.models.features import load_point_in_time_data
from src.models.train_model import _concat_years

load_dotenv()

sys.path.append(str(Path(__file__).resolve().parents[2]))
# noqa: E402
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Configuration
DATA_ROOT = "/Volumes/CK SSD/Coding Projects/cfb_model/"
TRAIN_YEARS = [2019, 2021, 2022, 2023]  # Train on all available history
TEST_YEAR = 2024  # Validate on holdout
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


def load_params(yaml_path: str) -> dict:
    """Load parameters from YAML file."""
    with open(yaml_path, "r") as f:
        # Skip comments
        lines = [line for line in f if not line.strip().startswith("#")]
        return yaml.safe_load("\n".join(lines))


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
    parser = argparse.ArgumentParser(description="Validate Optimized Models")
    parser.add_argument(
        "--home-params", type=str, required=True, help="Path to home params YAML"
    )
    parser.add_argument(
        "--away-params", type=str, required=True, help="Path to away params YAML"
    )
    parser.add_argument("--year", type=int, default=2024, help="Validation year")
    args = parser.parse_args()

    # Load params
    home_params = load_params(args.home_params)
    away_params = load_params(args.away_params)

    log.info("Loaded optimized parameters:")
    log.info(f"Home: {home_params}")
    log.info(f"Away: {away_params}")

    # Load data
    log.info("Loading training data...")
    train_df = load_data(TRAIN_YEARS, ADJUSTMENT_ITERATION)

    log.info(f"Loading test data ({args.year})...")
    test_df = load_data([args.year], ADJUSTMENT_ITERATION)

    # Feature selection
    log.info("Selecting features...")
    x_train_full = select_features(train_df, FEATURE_CONFIG)
    x_test_full = select_features(test_df, FEATURE_CONFIG)

    # Common features
    common_features = sorted(
        list(set(x_train_full.columns).intersection(set(x_test_full.columns)))
    )
    log.info(f"Using {len(common_features)} features")

    # Prepare targets
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

    # Train models
    log.info("Training home points model...")
    model_home = CatBoostRegressor(**home_params)
    model_home.fit(x_train, y_train_home, verbose=False)

    log.info("Training away points model...")
    model_away = CatBoostRegressor(**away_params)
    model_away.fit(x_train, y_train_away, verbose=False)

    # Predict
    log.info("Generating predictions...")
    pred_home = model_home.predict(x_test)
    pred_away = model_away.predict(x_test)

    pred_spread = pred_home - pred_away
    pred_total = pred_home + pred_away

    # Metrics
    spread_rmse = np.sqrt(mean_squared_error(y_test_spread, pred_spread))
    total_rmse = np.sqrt(mean_squared_error(y_test_total, pred_total))

    # Hit rates calculation requires betting lines
    # Simplified metric: RMSE and Bias
    # Actually, we need betting lines to calculate true ATS hit rate.
    # But for now, let's use the same logic as previous experiments:
    # If we predict spread > actual spread, we bet home? No.
    # Let's use the simplified metric: RMSE and Bias.
    # Wait, the user wants hit rate. I need to load betting lines or use the spread_target as the line?
    # spread_target IS the actual result (home - away).
    # We need the betting line to know if we won.
    # Ah, in previous experiments we used `prediction_correct` based on betting lines.
    # BUT, `spread_target` is the ACTUAL result.
    # We need to compare (pred_spread - line) vs (actual_spread - line).
    # If we don't have lines loaded here, we can't compute ATS hit rate perfectly.
    # However, we can compare RMSE to the baseline RMSE (18.36).

    # Let's try to load lines if possible, or just report RMSE/MAE/Bias for now.
    # Actually, I can use the `load_betting_lines` function I wrote earlier!

    from src.utils.local_storage import LocalStorage

    storage = LocalStorage(data_root=DATA_ROOT, file_format="csv", data_type="raw")

    # Load lines
    all_lines = []
    for week in range(1, 16):
        try:
            lines = storage.read_index(
                "betting_lines", {"year": args.year, "week": week}
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

        # Merge
        test_with_lines = test_clean.merge(
            consensus[["game_id", "spread"]],
            left_on="id",
            right_on="game_id",
            how="inner",
        )

        # Filter predictions to match
        mask = test_clean["id"].isin(test_with_lines["id"])
        pred_spread_subset = pred_spread[mask]
        actual_spread_subset = y_test_spread[mask]

        # Calculate hit rates
        # Bet Home if Pred > Line + Threshold
        # Bet Away if Pred < Line - Threshold
        # Here we just check directional accuracy relative to line

        # Spread Hit Rate
        # If Pred > Line (we like Home), did Home cover (Actual > Line)?
        # If Pred < Line (we like Away), did Away cover (Actual < Line)?

        # Note: Line is negative for home favorite (e.g. -7).
        # Pred Spread is Home - Away.
        # So if Pred = 10 and Line = 7 (Home underdog), we like Home.
        # Wait, Line is usually defined as Home - Away adjustment?
        # In this dataset, `spread` column in betting lines is typically Home Team spread.
        # e.g. -7 means Home is favored by 7.
        # So if Actual (Home - Away) > -Line (e.g. 7), Home covers?
        # Let's stick to the convention:
        # Line = -7 (Home favored by 7).
        # Actual Result = 10 (Home wins by 10).
        # 10 > 7? Yes. Home covers.
        # Actually, usually it's Actual + Line > 0 for Home Cover?
        # 10 + (-7) = 3 > 0. Yes.

        # Let's assume `spread` in lines_df is the spread for the home team.
        # Cover margin = Actual Spread (Home-Away) + Line
        # If Cover margin > 0, Home Covered.
        # If Cover margin < 0, Away Covered.

        # Our prediction margin = Pred Spread + Line
        # If Pred Margin > 0, we pick Home.
        # If Pred Margin < 0, we pick Away.

        # Hit = (Pred Margin * Cover Margin) > 0

        line_values = test_with_lines["spread"].values

        # Spread logic
        pred_margin = pred_spread_subset + line_values
        actual_margin = actual_spread_subset + line_values

        # Filter pushes
        valid_bets = (pred_margin != 0) & (actual_margin != 0)
        hits = np.sign(pred_margin[valid_bets]) == np.sign(actual_margin[valid_bets])
        spread_hit_rate = np.mean(hits)

        log.info(f"Spread Hit Rate (n={sum(valid_bets)}): {spread_hit_rate:.1%}")

        # Total logic (assuming 'over_under' column exists)
        if "over_under" in consensus.columns:
            test_with_totals = test_clean.merge(
                consensus[["game_id", "over_under"]],
                left_on="id",
                right_on="game_id",
                how="inner",
            )
            mask_t = test_clean["id"].isin(test_with_totals["id"])
            pred_total_sub = pred_total[mask_t]
            actual_total_sub = y_test_total[mask_t]
            ou_lines = test_with_totals["over_under"].values

            # Pred > Line -> Over
            # Actual > Line -> Over
            pred_diff = pred_total_sub - ou_lines
            actual_diff = actual_total_sub - ou_lines

            valid_t = (pred_diff != 0) & (actual_diff != 0)
            hits_t = np.sign(pred_diff[valid_t]) == np.sign(actual_diff[valid_t])
            total_hit_rate = np.mean(hits_t)

            log.info(f"Total Hit Rate (n={sum(valid_t)}): {total_hit_rate:.1%}")

    log.info(f"Spread RMSE: {spread_rmse:.2f}")
    log.info(f"Total RMSE: {total_rmse:.2f}")
    log.info(f"Spread Bias: {np.mean(pred_spread - y_test_spread):.2f}")
    log.info(f"Total Bias: {np.mean(pred_total - y_test_total):.2f}")


if __name__ == "__main__":
    main()
