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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cks_picks_cfb.config import REPORTS_DIR


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
    to_drop = [column for column in upper.columns if any(upper[column] > 0.90)]
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
    min_features_to_select = 10

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


def get_points_for_features(df: pd.DataFrame, prefix: str) -> list[str]:
    """Generate a list of numeric feature names for a given prefix."""

    metrics = [
        "adj_off_epa_pp",
        "adj_def_epa_pp",
        "adj_off_sr",
        "adj_def_sr",
        "adj_off_ypp",
        "adj_def_ypp",
        "adj_off_rush_ypp",
        "adj_off_pass_ypp",
        "adj_off_expl_overall_10",
        "adj_off_expl_overall_20",
        "adj_off_expl_overall_30",
        "adj_off_expl_rush",
        "adj_off_expl_pass",
        "adj_off_eckel_rate",
        "adj_off_finish_pts_per_opp",
        "adj_off_third_down_conversion_rate",
        "adj_def_third_down_conversion_rate",
        "games_played",
    ]

    features = []
    for metric in metrics:
        col = f"{prefix}{metric}"
        if col in df.columns:
            features.append(col)

    return features


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Run systematic feature selection for the points-for model."
    )
    parser.add_argument(
        "--slice-path",
        type=str,
        default="outputs/prototypes/points_for_training_slice_2023_filtered.csv",
        help="Path to the training data slice.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(REPORTS_DIR / "feature_selection"),
        help="Output directory for results",
    )
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    df = pd.read_csv(args.slice_path)

    home_features = get_points_for_features(df, "home_")
    away_features = get_points_for_features(df, "away_")

    selected_home_features = select_features(df, "home_points", home_features)
    selected_away_features = select_features(df, "away_points", away_features)

    results = {
        "home_features": selected_home_features,
        "away_features": selected_away_features,
    }
    output_path = os.path.join(args.output_dir, "points_for_selected_features.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n✅ Feature selection complete. Results saved to {output_path}")
    print(f"  Home features selected: {len(selected_home_features)}")
    print(f"  Away features selected: {len(selected_away_features)}")


if __name__ == "__main__":
    main()
