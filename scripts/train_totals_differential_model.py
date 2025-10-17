"""Train the totals models using differential features."""

from __future__ import annotations

import os
from collections.abc import Iterable

import joblib
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor

from src.models.features import (
    build_differential_feature_list,
    build_differential_features,
    generate_point_in_time_features,
)


def _train_and_save(
    model, x_data: pd.DataFrame, y: pd.Series, out_dir: str, name: str
) -> None:
    os.makedirs(out_dir, exist_ok=True)
    model.fit(x_data, y)
    joblib.dump(model, os.path.join(out_dir, f"{name}.joblib"))


def _concat_years(dfs: Iterable[pd.DataFrame]) -> pd.DataFrame:
    frames = [df for df in dfs if df is not None and not df.empty]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def main() -> None:
    """CLI entrypoint for training models."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Train totals models using differential features."
    )
    parser.add_argument(
        "--train-years",
        type=str,
        default="2019,2021,2022,2023",
        help="Comma-separated training years",
    )
    parser.add_argument(
        "--test-year", type=int, default=2024, help="Year to version models under"
    )
    parser.add_argument("--data-root", type=str, default=None, help="Data root path")
    parser.add_argument(
        "--model-dir",
        type=str,
        default="./models/totals_differential",
        help="Output dir for models",
    )
    args = parser.parse_args()

    train_years = [int(y.strip()) for y in args.train_years.split(",") if y.strip()]

    all_training_games = []
    for year in train_years:
        print(f"Generating features for training year: {year}")
        for week in range(1, 16):
            try:
                weekly_features = generate_point_in_time_features(
                    year, week, args.data_root
                )
                all_training_games.append(weekly_features)
            except ValueError as e:
                print(f"  Skipping week {week} for year {year}: {e}")
                continue
    train_df = _concat_years(all_training_games)

    print("Building differential features for training set...")
    train_df = build_differential_features(train_df)

    feature_list = build_differential_feature_list(train_df)

    target_col = "total_target"
    train_df = train_df.dropna(subset=feature_list + [target_col])

    x_train = train_df[feature_list]
    y_total_train = train_df[target_col].astype(float)

    out_dir = os.path.join(args.model_dir, str(args.test_year))

    print("Training total models...")
    total_models = {
        "random_forest": RandomForestRegressor(
            n_estimators=200,
            max_depth=8,
            min_samples_split=10,
            min_samples_leaf=5,
            random_state=42,
        ),
        "gradient_boosting": GradientBoostingRegressor(
            n_estimators=200,
            learning_rate=0.1,
            max_depth=6,
            subsample=0.8,
            random_state=42,
        ),
    }
    for name, model in total_models.items():
        print(f"  Training total_{name}...")
        _train_and_save(model, x_train, y_total_train, out_dir, name=f"total_{name}")

    print(f"Totals models saved to {out_dir}")


if __name__ == "__main__":
    main()
