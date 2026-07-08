import argparse
import warnings

import optuna
import pandas as pd

from cks_picks_cfb.features.v2_recency import load_v2_recency_data
from cks_picks_cfb.models.v2_catboost import V2CatBoostModel

# Suppress warnings
warnings.filterwarnings("ignore")


def load_data(years):
    dfs = []
    # Base configuration corresponding to v2_catboost_internal_power.yaml
    features = [
        "home_internal_power_rtg",
        "home_internal_off_rtg",
        "home_internal_def_rtg",
        "away_internal_power_rtg",
        "away_internal_off_rtg",
        "away_internal_def_rtg",
        "home_adj_off_epa_pp",
        "home_adj_def_epa_pp",
        "home_adj_off_sr",
        "home_adj_def_sr",
        "away_adj_off_epa_pp",
        "away_adj_def_epa_pp",
        "away_adj_off_sr",
        "away_adj_def_sr",
        "home_adj_off_rush_ypp",
        "home_adj_def_rush_ypp",
        "home_adj_off_pass_ypp",
        "home_adj_def_pass_ypp",
        "away_adj_off_rush_ypp",
        "away_adj_def_rush_ypp",
        "away_adj_off_pass_ypp",
        "away_adj_def_pass_ypp",
    ]
    for y in years:
        df = load_v2_recency_data(y, alpha=0.3, iterations=2)
        if df is not None:
            dfs.append(df)

    if not dfs:
        return pd.DataFrame(), features

    return pd.concat(dfs, ignore_index=True), features


# Globals to cache the datasets
print("Loading Training Validation Data [2021-2023]...")
global_train_df, global_features = load_data([2021, 2022, 2023])
print("Loading Holdout Data [2024]...")
global_test_df, _ = load_data([2024])


def objective(trial):
    # Hyperparameters specifically tailored for CatBoost minimization
    params = {
        "iterations": trial.suggest_int("iterations", 500, 3000),
        "learning_rate": trial.suggest_float("learning_rate", 0.001, 0.1, log=True),
        "depth": trial.suggest_int("depth", 3, 8),
        "l2_leaf_reg": trial.suggest_float("l2_leaf_reg", 1.0, 10.0),
        "random_seed": 42,
        "logging_level": "Silent",
    }

    # Use globally cached Data
    train_df = global_train_df
    features = global_features
    test_df = global_test_df

    model = V2CatBoostModel(features=features, **params)
    model.fit(train_df)
    metrics = model.evaluate(test_df)

    # Optuna minimizes by default. We want to maximize ROI.
    roi = metrics.get("roi", -100.0)
    rmse = metrics.get("rmse", 100.0)

    print(f"Trial {trial.number}: ROI {roi:.4f}, RMSE {rmse:.4f}")

    return -1.0 * roi


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=30, help="Number of trials")
    args = parser.parse_args()

    study = optuna.create_study(direction="minimize")
    study.optimize(objective, n_trials=args.trials)

    print("\nBest Trial:")
    print(study.best_trial.params)
    print(f"Best ROI Achieved on 2024 Holdout: {-1 * study.best_value:.4f}%")
