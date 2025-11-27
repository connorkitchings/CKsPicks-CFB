#!/usr/bin/env python3
"""
Systematic feature selection using a hybrid approach.

This script implements the three-stage feature selection process outlined in the
feature engineering guide:
1. Filter: Remove low-variance and highly correlated features.
2. Embedded: Use RandomForest to select the top N features.
3. Wrapper: Use RFECV to find the optimal subset.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.feature_selection import RFECV, VarianceThreshold
from sklearn.model_selection import TimeSeriesSplit

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import REPORTS_DIR
from src.models.features import (
    build_feature_list,
    generate_point_in_time_features,
)


def load_training_data(train_years: list[int], data_root: str | None) -> pd.DataFrame:
    """Load and combine training data for multiple years."""
    all_data = []
    print(f"Loading training data for years: {train_years}")
    for year in train_years:
        print(f"  Processing year {year}...")
        for week in range(1, 16):
            try:
                weekly_data = generate_point_in_time_features(year, week, data_root)
                all_data.append(weekly_data)
            except ValueError:
                continue
    if not all_data:
        raise ValueError("No training data loaded")
    combined_df = pd.concat(all_data, ignore_index=True)
    target_cols = ["spread_target", "total_target"]
    combined_df = combined_df.dropna(subset=target_cols)
    print(f"Loaded {len(combined_df)} training examples")
    return combined_df


def select_features(
    df: pd.DataFrame, target_col: str, feature_list: list[str]
) -> list[str]:
    """
    Performs the hybrid feature selection process.
    """
    print(f"\n--- Starting feature selection for target: {target_col} ---")
    data = df[feature_list + [target_col]].dropna()
    x = data[feature_list]
    y = data[target_col]

    # --- Stage 1: Filter Methods ---
    print(f"Stage 1: Filtering {x.shape[1]} initial features...")

    # 1a: Remove low-variance features
    variance_selector = VarianceThreshold(threshold=0.01)
    x_var = variance_selector.fit_transform(x)
    var_features = x.columns[variance_selector.get_support()]
    print(f"  {len(var_features)} features remain after variance threshold.")

    # 1b: Remove highly correlated features
    corr_matrix = pd.DataFrame(x_var, columns=var_features).corr().abs()
    upper = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
    to_drop = [
        column for column in upper.columns if any(upper[column] > 0.90)
    ]  # Using 0.90 threshold
    x_filtered = pd.DataFrame(x_var, columns=var_features).drop(columns=to_drop)
    filtered_features = x_filtered.columns.tolist()
    print(f"  {len(filtered_features)} features remain after correlation filter.")

    # --- Stage 2: Embedded Method (Feature Importance) ---
    print("Stage 2: Selecting top 50 features using RandomForest importance...")
    rf = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
    rf.fit(x_filtered, y)
    importances = pd.Series(rf.feature_importances_, index=filtered_features)
    top_50_features = importances.nlargest(50).index.tolist()

    # --- Stage 3: Wrapper Method (RFECV) ---
    print("Stage 3: Final selection using RFECV...")
    x_top50 = x_filtered[top_50_features]
    min_features_to_select = 10  # Minimum number of features to consider

    # Use TimeSeriesSplit for cross-validation
    cv = TimeSeriesSplit(n_splits=5)

    rfe_estimator = RandomForestRegressor(n_estimators=50, random_state=42, n_jobs=-1)
    rfecv = RFECV(
        estimator=rfe_estimator,
        step=1,
        cv=cv,
        scoring="neg_mean_squared_error",
        min_features_to_select=min_features_to_select,
        n_jobs=-1,
    )
    rfecv.fit(x_top50, y)

    final_features = x_top50.columns[rfecv.support_].tolist()
    print(f"  RFECV selected {len(final_features)} final features.")

    return final_features


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description="Run systematic feature selection.")
    parser.add_argument(
        "--train-years",
        type=str,
        default="2019,2021,2022,2023",
        help="Comma-separated training years",
    )
    parser.add_argument("--data-root", type=str, default=None, help="Data root path")
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(REPORTS_DIR / "feature_selection"),
        help="Output directory for results",
    )
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    train_years = [int(y.strip()) for y in args.train_years.split(",")]

    # Load data
    df = load_training_data(train_years, args.data_root)
    initial_features = build_feature_list(df)

    # Run selection for each target
    spread_features = select_features(df, "spread_target", initial_features)
    total_features = select_features(df, "total_target", initial_features)

    # Save results
    results = {
        "spread_features": spread_features,
        "total_features": total_features,
    }
    output_path = os.path.join(args.output_dir, "selected_features.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n✅ Feature selection complete. Results saved to {output_path}")
    print(f"  Spread features selected: {len(spread_features)}")
    print(f"  Total features selected: {len(total_features)}")


if __name__ == "__main__":
    main()
