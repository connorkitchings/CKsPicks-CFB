import os
import sys

import mlflow
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, mean_squared_error

# Add project root to path
sys.path.append(os.getcwd())
from omegaconf import OmegaConf

from src.config import get_data_root
from src.features.selector import select_features
from src.models.features import load_point_in_time_data
from src.utils.mlflow_tracking import setup_mlflow


def evaluate_models():
    setup_mlflow()
    years = [2024, 2025]
    data_root = get_data_root()

    # Load Models
    print("Loading models...")
    # Note: train_and_register.py appends _seed_X. We'll use seed 5 for evaluation (confirmed existence).
    spread_model_name = "spread_catboost_ppr_seed_5"
    total_model_name = "totals_xgboost_ppr_seed_5"

    spread_model = mlflow.pyfunc.load_model(f"models:/{spread_model_name}/Production")
    total_model = mlflow.pyfunc.load_model(f"models:/{total_model_name}/Production")

    # Load Feature Configs (to select features correctly)
    # We need to construct a dummy cfg object for select_features
    # But select_features needs the config object.

    # Let's load the configs from disk
    spread_cfg = OmegaConf.load("conf/features/ppr_v1.yaml")
    total_cfg = OmegaConf.load("conf/features/standard_v1.yaml")

    # Wrap in a structure that select_features expects (cfg.features)
    spread_full_cfg = OmegaConf.create({"features": spread_cfg})
    total_full_cfg = OmegaConf.create({"features": total_cfg})

    results = []

    for year in years:
        print(f"Evaluating {year}...")
        for week in range(1, 16):  # Weeks 1-15
            try:
                df = load_point_in_time_data(
                    year, week, data_root, include_betting_lines=True
                )
            except Exception:
                # print(f"  Week {week}: Failed to load data ({e})")
                continue

            if df is None or df.empty:
                continue

            # Filter to completed games
            if "spread_target" not in df.columns or "total_target" not in df.columns:
                continue

            df = df.dropna(subset=["spread_target", "total_target"])
            if df.empty:
                continue

            # --- Spread Prediction ---
            X_spread = select_features(df, spread_full_cfg)
            # Ensure columns match model expectation (MLflow usually handles this if signature is logged,
            # but CatBoost/XGBoost might be picky about column order if passed as DF)
            # We'll trust select_features returns the right set.

            spread_preds = spread_model.predict(X_spread)

            # --- Total Prediction ---
            X_total = select_features(df, total_full_cfg)
            if "home_drives_per_game_last_3" in X_total.columns:
                print("DEBUG: home_drives_per_game_last_3 IS in X_total")
            else:
                print("DEBUG: home_drives_per_game_last_3 IS NOT in X_total")
                print(f"DEBUG: X_total columns: {X_total.columns.tolist()[:10]}...")

            total_preds = total_model.predict(X_total)

            # --- Metrics ---
            # Spread RMSE
            spread_rmse = np.sqrt(mean_squared_error(df["spread_target"], spread_preds))

            # Total RMSE
            total_rmse = np.sqrt(mean_squared_error(df["total_target"], total_preds))

            # Spread Accuracy (Direction)
            # Target > 0 (Home Win), Pred > 0 (Home Win)
            spread_acc = accuracy_score(df["spread_target"] > 0, spread_preds > 0)

            # ATS Accuracy (vs Line)
            if "spread_line" in df.columns:
                # Residual = Target + Line
                # Pred Residual = Pred + Line
                # We want to know if we picked the right side of the line.
                # If Pred > -Line, we pick Home.
                # If Target > -Line, Home Covered.

                # Let's use the logic:
                # Predicted Margin > -Line => Bet Home
                # Predicted Margin < -Line => Bet Away

                # Outcome:
                # Actual Margin > -Line => Home Cover
                # Actual Margin < -Line => Away Cover

                # Bet Home (1) or Away (-1)
                bets = np.where(spread_preds > -df["spread_line"], 1, -1)
                outcomes = np.where(df["spread_target"] > -df["spread_line"], 1, -1)

                # Filter pushes
                valid_idx = (df["spread_target"] != -df["spread_line"]) & (
                    spread_preds != -df["spread_line"]
                )
                if valid_idx.sum() > 0:
                    ats_acc = accuracy_score(outcomes[valid_idx], bets[valid_idx])
                else:
                    ats_acc = np.nan
            else:
                ats_acc = np.nan

            results.append(
                {
                    "year": year,
                    "week": week,
                    "n_games": len(df),
                    "spread_rmse": spread_rmse,
                    "total_rmse": total_rmse,
                    "spread_acc": spread_acc,
                    "ats_acc": ats_acc,
                }
            )

    results_df = pd.DataFrame(results)
    print("\nResults by Year:")
    print(
        results_df.groupby("year")[
            ["spread_rmse", "total_rmse", "spread_acc", "ats_acc"]
        ].mean()
    )

    print("\nOverall Results:")
    print(results_df[["spread_rmse", "total_rmse", "spread_acc", "ats_acc"]].mean())

    # Weighted average by n_games
    wm = lambda x: np.average(x, weights=results_df.loc[x.index, "n_games"])
    print("\nWeighted Overall Results:")
    print(
        results_df.agg(
            {"spread_rmse": wm, "total_rmse": wm, "spread_acc": wm, "ats_acc": wm}
        )
    )


if __name__ == "__main__":
    evaluate_models()
