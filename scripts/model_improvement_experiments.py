#!/usr/bin/env python3
"""
Model Improvement Experimentation Framework

This script provides a systematic approach to testing different modeling
improvements for both spread and totals predictions.
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import ElasticNet, HuberRegressor, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import cross_val_score
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import RobustScaler, StandardScaler

# xgboost is optional; guard import so script works without it
try:
    import xgboost as xgb  # type: ignore

    _XGB_AVAILABLE = True
except Exception:  # ImportError or runtime issues
    xgb = None  # type: ignore
    _XGB_AVAILABLE = False

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cfb_model.models.features import (
    build_feature_list,
    generate_point_in_time_features,
)


@dataclass
class ModelConfig:
    """Configuration for a model experiment."""

    name: str
    model_class: Any
    model_params: Dict[str, Any]
    scaler_class: Any = None
    scaler_params: Dict[str, Any] = None
    feature_selection: str = "standard"  # standard, extended, reduced


@dataclass
class ExperimentResult:
    """Results from a model experiment."""

    config_name: str
    target: str  # spread or total
    rmse: float
    mae: float
    cv_score_mean: float
    cv_score_std: float
    feature_count: int
    model: Any = None


class ModelExperimentRunner:
    """Framework for running systematic model improvement experiments."""

    def __init__(self, data_root: str = None):
        self.data_root = data_root
        self.results: List[ExperimentResult] = []

    def get_model_configs(self) -> List[ModelConfig]:
        """Define the model configurations to test."""
        configs: List[ModelConfig] = [
            # Baseline
            ModelConfig(
                name="ridge_baseline",
                model_class=Ridge,
                model_params={"alpha": 1.0, "random_state": 42},
            ),
            # Regularization variants
            ModelConfig(
                name="ridge_tuned",
                model_class=Ridge,
                model_params={"alpha": 0.1, "random_state": 42},
            ),
            ModelConfig(
                name="ridge_strong_reg",
                model_class=Ridge,
                model_params={"alpha": 10.0, "random_state": 42},
            ),
            ModelConfig(
                name="elastic_net",
                model_class=ElasticNet,
                model_params={"alpha": 0.1, "l1_ratio": 0.5, "random_state": 42},
            ),
            ModelConfig(
                name="huber_robust",
                model_class=HuberRegressor,
                model_params={"epsilon": 1.35, "max_iter": 1000},
            ),
            # Tree-based models
            ModelConfig(
                name="random_forest",
                model_class=RandomForestRegressor,
                model_params={
                    "n_estimators": 200,
                    "max_depth": 8,
                    "min_samples_split": 10,
                    "min_samples_leaf": 5,
                    "random_state": 42,
                },
            ),
            ModelConfig(
                name="gradient_boosting",
                model_class=GradientBoostingRegressor,
                model_params={
                    "n_estimators": 200,
                    "learning_rate": 0.1,
                    "max_depth": 6,
                    "subsample": 0.8,
                    "random_state": 42,
                },
            ),
            # XGBoost (optional)
            # Added conditionally below based on availability
            # Neural network
            ModelConfig(
                name="neural_network",
                model_class=MLPRegressor,
                model_params={
                    "hidden_layer_sizes": (100, 50),
                    "activation": "relu",
                    "solver": "adam",
                    "alpha": 0.001,
                    "learning_rate": "adaptive",
                    "random_state": 42,
                    "max_iter": 1000,
                },
                scaler_class=StandardScaler,
            ),
            # Scaled versions
            ModelConfig(
                name="ridge_scaled",
                model_class=Ridge,
                model_params={"alpha": 1.0, "random_state": 42},
                scaler_class=StandardScaler,
            ),
            ModelConfig(
                name="ridge_robust_scaled",
                model_class=Ridge,
                model_params={"alpha": 1.0, "random_state": 42},
                scaler_class=RobustScaler,
            ),
        ]

        # Optionally add XGBoost if available
        if _XGB_AVAILABLE:
            configs.append(
                ModelConfig(
                    name="xgboost",
                    model_class=xgb.XGBRegressor,
                    model_params={
                        "n_estimators": 200,
                        "learning_rate": 0.1,
                        "max_depth": 6,
                        "subsample": 0.8,
                        "colsample_bytree": 0.8,
                        "random_state": 42,
                        "n_jobs": 4,
                    },
                )
            )
        else:
            print(
                "Note: xgboost not installed; skipping XGBoost experiments. Install with `uv add xgboost`. "
            )

        # Feature engineering experiments for top models
        top_models = {
            "ridge_strong_reg": {
                "model_class": Ridge,
                "model_params": {"alpha": 10.0, "random_state": 42},
            },
            "random_forest": {
                "model_class": RandomForestRegressor,
                "model_params": {
                    "n_estimators": 200,
                    "max_depth": 8,
                    "min_samples_split": 10,
                    "min_samples_leaf": 5,
                    "random_state": 42,
                },
            },
        }

        for model_name, model_props in top_models.items():
            for feature_set in ["extended", "reduced"]:
                configs.append(
                    ModelConfig(
                        name=f"{model_name}_{feature_set}",
                        model_class=model_props["model_class"],
                        model_params=model_props["model_params"],
                        feature_selection=feature_set,
                    )
                )

        return configs

    def get_extended_features(self, df: pd.DataFrame) -> List[str]:
        """Generate extended feature set with interactions and derived features."""
        standard_features = build_feature_list(df)
        extended_features = standard_features.copy()

        # Add feature interactions for key metrics
        interaction_pairs = [
            ("home_adj_off_epa_pp", "away_adj_def_epa_pp"),
            ("away_adj_off_epa_pp", "home_adj_def_epa_pp"),
            ("home_adj_off_sr", "away_adj_def_sr"),
            ("away_adj_off_sr", "home_adj_def_sr"),
        ]

        for feat1, feat2 in interaction_pairs:
            if feat1 in df.columns and feat2 in df.columns:
                interaction_name = f"interaction_{feat1}_{feat2}"
                df[interaction_name] = df[feat1] * df[feat2]
                extended_features.append(interaction_name)

        # Add differential features (home - away)
        differential_metrics = [
            "adj_off_epa_pp",
            "adj_def_epa_pp",
            "adj_off_sr",
            "adj_def_sr",
        ]
        for metric in differential_metrics:
            home_col = f"home_{metric}"
            away_col = f"away_{metric}"
            if home_col in df.columns and away_col in df.columns:
                diff_name = f"diff_{metric}"
                df[diff_name] = df[home_col] - df[away_col]
                extended_features.append(diff_name)

        return extended_features

    def get_reduced_features(self, df: pd.DataFrame) -> List[str]:
        """Generate reduced feature set focusing on most important metrics."""
        core_features = []

        # Core EPA and success rate features
        for side in ["home", "away"]:
            for prefix in ["adj_off_", "adj_def_"]:
                for metric in ["epa_pp", "sr"]:
                    col = f"{side}_{prefix}{metric}"
                    if col in df.columns:
                        core_features.append(col)

        # Core explosive and finishing features
        for side in ["home", "away"]:
            for metric in ["off_eckel_rate", "off_finish_pts_per_opp"]:
                col = f"{side}_{metric}"
                if col in df.columns:
                    core_features.append(col)

        return core_features

    def load_training_data(self, train_years: List[int]) -> pd.DataFrame:
        """Load and combine training data for multiple years."""
        all_data = []

        for year in train_years:
            print(f"Loading training data for year {year}...")
            # Generate features for all weeks in the training year
            for week in range(1, 16):
                try:
                    weekly_data = generate_point_in_time_features(
                        year, week, self.data_root
                    )
                    all_data.append(weekly_data)
                except ValueError as e:
                    print(f"  Skipping week {week} for year {year}: {e}")
                    continue

        if not all_data:
            raise ValueError("No training data loaded")

        combined_df = pd.concat(all_data, ignore_index=True)

        # Filter to games with complete targets
        target_cols = ["spread_target", "total_target"]
        combined_df = combined_df.dropna(subset=target_cols)

        print(f"Loaded {len(combined_df)} training examples")
        return combined_df

    def run_experiment(
        self, config: ModelConfig, train_df: pd.DataFrame, target: str
    ) -> ExperimentResult:
        """Run a single model experiment."""
        print(f"\n--- Running {config.name} for {target} ---")

        # Get feature set
        if config.feature_selection == "extended":
            features = self.get_extended_features(train_df.copy())
        elif config.feature_selection == "reduced":
            features = self.get_reduced_features(train_df.copy())
        else:
            features = build_feature_list(train_df)

        # Filter to available features and complete data
        available_features = [f for f in features if f in train_df.columns]
        model_data = train_df[available_features + [f"{target}_target"]].dropna()

        x_train = model_data[available_features]
        y = model_data[f"{target}_target"]

        print(f"Using {len(available_features)} features on {len(model_data)} examples")

        # Apply scaling if specified
        scaler = None
        if config.scaler_class:
            scaler = config.scaler_class(**(config.scaler_params or {}))
            x_train = pd.DataFrame(
                scaler.fit_transform(x_train),
                columns=x_train.columns,
                index=x_train.index,
            )

        # Train model
        model = config.model_class(**config.model_params)
        model.fit(x_train, y)

        # Evaluate
        y_pred = model.predict(x_train)
        rmse = np.sqrt(mean_squared_error(y, y_pred))
        mae = mean_absolute_error(y, y_pred)

        # Cross-validation
        cv_scores = cross_val_score(
            model, x_train, y, cv=5, scoring="neg_root_mean_squared_error"
        )
        cv_mean = -cv_scores.mean()
        cv_std = cv_scores.std()

        result = ExperimentResult(
            config_name=config.name,
            target=target,
            rmse=rmse,
            mae=mae,
            cv_score_mean=cv_mean,
            cv_score_std=cv_std,
            feature_count=len(available_features),
            model=model,
        )

        print(f"  RMSE: {rmse:.3f}, MAE: {mae:.3f}")
        print(f"  CV RMSE: {cv_mean:.3f} ± {cv_std:.3f}")

        return result

    def run_all_experiments(
        self, train_years: List[int] = [2019, 2021, 2022, 2023]
    ) -> None:
        """Run all model experiments for both spread and total targets."""
        print("=== Model Improvement Experiments ===")

        # Load training data
        train_df = self.load_training_data(train_years)

        # Get model configurations
        configs = self.get_model_configs()

        # Run experiments for both targets
        for target in ["spread", "total"]:
            print(f"\n{'=' * 50}")
            print(f"EXPERIMENTS FOR {target.upper()} TARGET")
            print(f"{'=' * 50}")

            for config in configs:
                try:
                    result = self.run_experiment(config, train_df, target)
                    self.results.append(result)
                except Exception as e:
                    print(f"ERROR in {config.name} for {target}: {e}")

    def save_results(self, output_file: str = "model_experiment_results.csv") -> None:
        """Save experiment results to CSV."""
        if not self.results:
            print("No results to save")
            return

        results_data = []
        for result in self.results:
            results_data.append(
                {
                    "model": result.config_name,
                    "target": result.target,
                    "rmse": result.rmse,
                    "mae": result.mae,
                    "cv_rmse_mean": result.cv_score_mean,
                    "cv_rmse_std": result.cv_score_std,
                    "feature_count": result.feature_count,
                }
            )

        results_df = pd.DataFrame(results_data)
        results_df.to_csv(output_file, index=False)
        print(f"\nResults saved to {output_file}")

        # Print summary
        print("\n=== EXPERIMENT SUMMARY ===")
        for target in ["spread", "total"]:
            target_results = results_df[results_df["target"] == target]
            if not target_results.empty:
                best_model = target_results.loc[target_results["cv_rmse_mean"].idxmin()]
                print(f"\nBest {target} model: {best_model['model']}")
                print(
                    f"  CV RMSE: {best_model['cv_rmse_mean']:.3f} ± {best_model['cv_rmse_std']:.3f}"
                )
                print(f"  Features: {best_model['feature_count']}")


def main():
    """CLI entry point for model experiments."""
    parser = argparse.ArgumentParser(description="Run model improvement experiments")
    parser.add_argument(
        "--data-root", type=str, default=None, help="Data root directory"
    )
    parser.add_argument(
        "--train-years",
        type=str,
        default="2019,2021,2022,2023",
        help="Comma-separated training years",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="reports/model_experiment_results.csv",
        help="Output CSV file",
    )

    args = parser.parse_args()

    train_years = [int(y.strip()) for y in args.train_years.split(",")]

    runner = ModelExperimentRunner(data_root=args.data_root)
    runner.run_all_experiments(train_years)
    runner.save_results(args.output)


if __name__ == "__main__":
    main()
