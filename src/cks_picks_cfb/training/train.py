"""Standardized training script driven by experiment config."""

import argparse
import json

import joblib
import pandas as pd

from cks_picks_cfb.config import MODELS_DIR
from cks_picks_cfb.config.experiments import get_experiment
from cks_picks_cfb.models.features import load_merged_dataset


def train_experiment(experiment_name: str, data_root: str | None = None):
    """
    Train a model based on an experiment configuration.

    Args:
        experiment_name: Name of the experiment to run.
        data_root: Path to data root.
    """
    exp = get_experiment(experiment_name)
    print(f"Starting training for experiment: {exp.name}")

    # 1. Load Training Data
    # We need to load data for all training years.
    # This logic needs to be robust. For now, simplified loop.
    training_years = [
        y for y in range(exp.start_year, 2024) if y not in exp.exclude_years
    ]

    dfs = []
    for year in training_years:
        print(f"Loading data for {year}...")
        try:
            df = load_merged_dataset(year, data_root)
            dfs.append(df)
        except Exception as e:
            print(f"Skipping {year}: {e}")

    if not dfs:
        raise ValueError("No training data loaded.")

    full_df = pd.concat(dfs, ignore_index=True)

    # 2. Prepare Features and Target
    x = full_df[exp.features]  # noqa: N806
    y = full_df[exp.target]

    # Handle missing values (simple imputation for now)
    x = x.fillna(0)
    y = y.dropna()
    x = x.loc[y.index]

    # 3. Train Model
    print(f"Training {exp.model_type} model...")
    if exp.model_type == "catboost":
        from catboost import CatBoostRegressor

        model = CatBoostRegressor(**exp.hyperparameters)
        model.fit(x, y, verbose=100)
    else:
        raise NotImplementedError(f"Model type {exp.model_type} not implemented.")

    # 4. Save Artifacts
    output_dir = MODELS_DIR / exp.name
    output_dir.mkdir(parents=True, exist_ok=True)

    model_path = output_dir / "model.joblib"
    joblib.dump(model, model_path)
    print(f"Model saved to {model_path}")

    # Save feature list
    feature_path = output_dir / "features.json"
    with open(feature_path, "w") as f:
        json.dump(exp.features, f)

    # Save config
    config_path = output_dir / "config.json"
    with open(config_path, "w") as f:
        # Convert dataclass to dict if needed, or just dump relevant fields
        json.dump(
            {
                "name": exp.name,
                "features": exp.features,
                "hyperparameters": exp.hyperparameters,
            },
            f,
            indent=2,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("experiment", type=str, help="Name of the experiment to run")
    parser.add_argument("--data-root", type=str)
    args = parser.parse_args()

    train_experiment(args.experiment, args.data_root)
