import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

# Add project root to path
sys.path.append(os.getcwd())

from omegaconf import OmegaConf

from src.features.selector import select_features
from src.models.features import load_point_in_time_data
from src.models.train_model import _concat_years

DATA_ROOT = "/Volumes/CK SSD/Coding Projects/cfb_model/"
TRAIN_YEARS = [2019, 2021, 2022, 2023]
TEST_YEAR = 2024
ADJUSTMENT_ITERATION = 2

# Feature config (standard_v1)
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


def load_data(years):
    all_data = []
    for year in years:
        if year == 2020:
            continue
        for week in range(1, 16):
            df = load_point_in_time_data(
                year,
                week,
                DATA_ROOT,
                adjustment_iteration=ADJUSTMENT_ITERATION,
                include_betting_lines=True,
            )
            if df is not None:
                # Ensure game_id is present (it's usually 'id')
                if "id" in df.columns:
                    df["game_id"] = df["id"]
                all_data.append(df)
    return _concat_years(all_data)


def main():
    print("Loading standard training data...")
    raw_df = load_data(TRAIN_YEARS + [TEST_YEAR])

    print("Loading PPR features...")
    ppr_df = pd.read_csv("data/processed/ppr_features.csv")

    # Merge
    print("Merging data...")
    # PPR features: game_id, ppr_home_rating, ppr_away_rating, ppr_predicted_spread, ppr_predicted_total
    merged_df = raw_df.merge(ppr_df, on="game_id", how="inner")
    print(f"Merged data shape: {merged_df.shape}")

    # Select Features
    print("Selecting features...")
    # Get standard features
    x_standard = select_features(merged_df, FEATURE_CONFIG)

    # Add PPR features
    ppr_cols = ["ppr_home_rating", "ppr_away_rating", "ppr_predicted_spread"]

    # Combine
    x_features = pd.concat([x_standard, merged_df[ppr_cols]], axis=1)

    # Target: Home Score - Away Score (Spread)
    # In this codebase, 'points_for' columns are used for scores.
    if "home_points_for" not in merged_df.columns:
        print(
            "Error: 'home_points_for' not found. Available columns:",
            merged_df.columns.tolist()[:10],
        )
        return

    y = merged_df["home_points_for"] - merged_df["away_points_for"]

    # Drop NaNs in target
    valid_mask = y.notna()
    x_features = x_features[valid_mask]
    y = y[valid_mask]
    merged_df = merged_df[valid_mask]

    # Split Train/Test
    train_mask = merged_df["season"].isin(TRAIN_YEARS)
    test_mask = merged_df["season"] == TEST_YEAR

    x_train = x_features[train_mask]
    y_train = y[train_mask]
    x_test = x_features[test_mask]
    y_test = y[test_mask]

    print(f"Train samples: {len(x_train)}, Test samples: {len(x_test)}")

    # Train
    print("Training CatBoost...")
    model = CatBoostRegressor(
        iterations=1000,
        learning_rate=0.05,
        depth=6,
        loss_function="RMSE",
        verbose=100,
        random_seed=42,
    )

    model.fit(x_train, y_train, eval_set=(x_test, y_test), early_stopping_rounds=50)

    # Evaluate
    preds = model.predict(x_test)
    rmse = np.sqrt(mean_squared_error(y_test, preds))
    mae = mean_absolute_error(y_test, preds)
    print(f"\nTest RMSE: {rmse:.4f}")
    print(f"Test MAE: {mae:.4f}")

    # Betting Evaluation
    if "spread_line" in merged_df.columns:
        print("\nEvaluating Betting Performance (2024)...")
        test_df = merged_df[test_mask].copy()
        test_df["pred_spread"] = preds

        thresholds = [0.0, 2.5, 5.0]
        for th in thresholds:
            wins = 0
            losses = 0
            pushes = 0

            for _, row in test_df.iterrows():
                line = row["spread_line"]
                if pd.isna(line):
                    continue

                pred = row["pred_spread"]

                # Edge calculation
                # Vegas implies Home Margin = -line (e.g. Line -7 => Home by 7)
                # Wait, check load_point_in_time_data logic:
                # merged_df["spread_residual_target"] = merged_df["spread_target"] + merged_df["spread_line"]
                # spread_target = Home - Away.
                # If Home wins by 7 (Target=7) and Line is -7. Residual = 0.
                # So Line is indeed negative for favorites.
                vegas_margin = -line

                if pred > (vegas_margin + th):
                    # Bet Home
                    actual_margin = row["home_points_for"] - row["away_points_for"]
                    if actual_margin > vegas_margin:
                        wins += 1
                    elif actual_margin < vegas_margin:
                        losses += 1
                    else:
                        pushes += 1
                elif pred < (vegas_margin - th):
                    # Bet Away
                    actual_margin = row["home_points_for"] - row["away_points_for"]
                    if actual_margin < vegas_margin:
                        wins += 1
                    elif actual_margin > vegas_margin:
                        losses += 1
                    else:
                        pushes += 1

            total = wins + losses
            win_rate = wins / total if total > 0 else 0.0
            print(f"Threshold {th}: {wins}-{losses}-{pushes} ({win_rate:.1%})")

    # Feature Importance
    print("\nFeature Importance:")
    fi = model.get_feature_importance(prettified=True)
    print(fi.head(10))

    # Save Model
    out_dir = Path("artifacts/models")
    out_dir.mkdir(parents=True, exist_ok=True)
    model_path = out_dir / "stacked_model.cbm"
    model.save_model(str(model_path))
    print(f"\nSaved model to {model_path}")


if __name__ == "__main__":
    main()
