import argparse
import warnings

import optuna
import pandas as pd

from cks_picks_cfb.features.v1_pipeline import load_v1_data
from cks_picks_cfb.models.v2_xgboost import V2XGBoostModel

# Suppress warnings
warnings.filterwarnings("ignore")


def load_data(years):
    dfs = []
    # Force default ADJUSTED features
    features = [
        "home_adj_off_epa_pp",
        "home_adj_def_epa_pp",
        "home_adj_off_sr",
        "home_adj_def_sr",
        "away_adj_off_epa_pp",
        "away_adj_def_epa_pp",
        "away_adj_off_sr",
        "away_adj_def_sr",
    ]
    for y in years:
        df = load_v1_data(y, features=features)
        if df is not None:
            dfs.append(df)
    return pd.concat(dfs, ignore_index=True), features


def objective(trial):
    # Hyperparameters
    params = {
        "n_estimators": trial.suggest_int("n_estimators", 500, 3000),
        "learning_rate": trial.suggest_float("learning_rate", 0.001, 0.1, log=True),
        "max_depth": trial.suggest_int("max_depth", 3, 8),
        "subsample": trial.suggest_float("subsample", 0.6, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
        "reg_alpha": trial.suggest_float("reg_alpha", 0.0, 10.0),
        "reg_lambda": trial.suggest_float("reg_lambda", 0.0, 10.0),
        "objective": "reg:squarederror",
        "random_state": 42,
        "n_jobs": -1,
    }

    # Load Data (Memoization would be better but keep it simple)
    # Train: 2021-2023. Test: 2024 (Holdout)
    train_df, features = load_data([2021, 2022, 2023])
    test_df, _ = load_data([2024])

    model = V2XGBoostModel(features=features, **params)
    model.fit(train_df)
    metrics = model.evaluate(test_df)

    # Objective: Minimize RMSE? Or Maximize ROI?
    # Let's optimize for ROI directly, but add a penalty for low Hit Rate or RMSE stability?
    # Simple approach: Return RMSE (minimization) as primary proxy for accuracy.
    # Optuna minimizes by default.

    # We want to MAXIMIZE ROI.
    # So return -1 * ROI.
    roi = metrics.get("roi", -1.0)

    print(f"Trial {trial.number}: ROI {roi:.4f}, RMSE {metrics.get('rmse'):.4f}")

    return -1.0 * roi


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=20, help="Number of trials")
    args = parser.parse_args()

    study = optuna.create_study(direction="minimize")
    study.optimize(objective, n_trials=args.trials)

    print("\nBest Trial:")
    print(study.best_trial.params)
    print(f"Best ROI: {-1 * study.best_value:.4f}")
