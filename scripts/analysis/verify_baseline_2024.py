import os
import sys

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from sklearn.metrics import mean_squared_error

# Add project root to path
sys.path.append(os.getcwd())

from src.config import get_data_root
from src.models.features import build_feature_list, load_point_in_time_data


def main():
    year = 2024
    start_week = 1
    end_week = 15

    # Params from conf/model/spread_catboost.yaml
    spread_params = {
        "depth": 6,
        "learning_rate": 0.05,
        "iterations": 800,
        "l2_leaf_reg": 3.0,
        "subsample": 0.8,
        "random_seed": 42,
        "loss_function": "RMSE",
        "verbose": 0,
    }

    results = []

    print(f"Starting Baseline Verification for {year}...")

    for week in range(start_week, end_week + 1):
        print(f"Processing Week {week}...")

        # 1. Load Train Data (2019-2023 + 2024 weeks < current)
        train_dfs = []
        # Historical years
        for y in [2019, 2021, 2022, 2023]:
            # Load all weeks
            for w in range(1, 16):
                df = load_point_in_time_data(
                    y, w, get_data_root(), adjustment_iteration=2
                )
                if df is not None:
                    train_dfs.append(df)

        # Current year partial
        for w in range(1, week):
            df = load_point_in_time_data(
                year, w, get_data_root(), adjustment_iteration=2
            )
            if df is not None:
                train_dfs.append(df)

        if not train_dfs:
            print("No training data found.")
            continue

        train_df = pd.concat(train_dfs, ignore_index=True)

        # 2. Load Test Data with Lines
        test_df = load_point_in_time_data(
            year,
            week,
            get_data_root(),
            adjustment_iteration=2,
            include_betting_lines=True,
        )
        if test_df is None or test_df.empty:
            print(f"No test data for Week {week}")
            continue

        # 3. Prepare Features
        feature_list = build_feature_list(train_df)
        # Ensure intersection
        feature_list = [f for f in feature_list if f in test_df.columns]

        # Drop NAs
        train_df = train_df.dropna(subset=feature_list + ["spread_target"])
        # For test, we keep rows even if lines are missing, but we can't eval ATS without lines
        test_df = test_df.dropna(subset=feature_list + ["spread_target"])

        if train_df.empty or test_df.empty:
            print("Empty data after cleaning.")
            continue

        x_train = train_df[feature_list]
        y_train = train_df["spread_target"]
        x_test = test_df[feature_list]
        y_test = test_df["spread_target"]  # Actual margin

        # 4. Train Model
        model = CatBoostRegressor(**spread_params)
        model.fit(x_train, y_train)

        # 5. Predict
        preds = model.predict(x_test)

        # 6. Store Results
        for idx, (pred, actual) in enumerate(zip(preds, y_test)):
            row = test_df.iloc[idx]
            line = row.get("home_team_spread_line")

            # Straight Up Logic
            su_correct = (pred > 0) == (actual > 0)

            # ATS Logic
            ats_correct = None
            ats_pick = None
            if pd.notna(line):
                # Actual Result: Did Home Cover?
                # Home Margin (actual) > -Line
                # e.g. Line -3.5 (Home Fav). Actual 7. 7 > 3.5. Cover.
                # e.g. Line +3.5 (Home Dog). Actual -2. -2 > -3.5. Cover.

                # Push check
                if actual == -line:
                    ats_result = "Push"
                elif actual > -line:
                    ats_result = "Home"
                else:
                    ats_result = "Away"

                # Model Pick
                # Edge = Pred - (-Line) = Pred + Line
                # If Edge > 0 => Model likes Home
                # If Edge < 0 => Model likes Away

                edge = pred + line
                if edge > 0:
                    ats_pick = "Home"
                else:
                    ats_pick = "Away"

                if ats_result != "Push":
                    ats_correct = ats_pick == ats_result

            results.append(
                {
                    "week": week,
                    "pred_spread": pred,
                    "actual_spread": actual,
                    "line": line,
                    "su_correct": su_correct,
                    "ats_correct": ats_correct,
                    "ats_pick": ats_pick,
                }
            )

    # Analysis
    if not results:
        print("No results generated.")
        return

    res_df = pd.DataFrame(results)

    # SU Analysis
    valid_su = res_df[res_df["actual_spread"] != 0]
    su_acc = valid_su["su_correct"].mean()

    # ATS Analysis
    valid_ats = res_df.dropna(subset=["ats_correct"])
    ats_acc = valid_ats["ats_correct"].mean()

    rmse = np.sqrt(mean_squared_error(res_df["actual_spread"], res_df["pred_spread"]))

    print("\n--- Verification Results (2024) ---")
    print(f"Total Games: {len(res_df)}")
    print(f"RMSE: {rmse:.4f}")
    print(f"Straight Up Win Accuracy: {su_acc:.4%}")
    print(f"ATS Win Accuracy: {ats_acc:.4%} ({len(valid_ats)} games)")

    # Save
    res_df.to_csv("artifacts/validation/baseline_verification_2024.csv", index=False)
    print("Results saved to artifacts/validation/baseline_verification_2024.csv")


if __name__ == "__main__":
    main()
