#!/usr/bin/env python3
"""
Hyperparameter optimization for spread and total models.

Uses GridSearchCV with time-series aware cross-validation to find optimal
hyperparameters for both Ridge (spreads) and RandomForest (totals) models.
Evaluates on 2024 holdout to confirm improvements.
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cfb_model.models.features import (
    build_feature_list,
    generate_point_in_time_features,
)


@dataclass
class OptimizationResult:
    """Results from hyperparameter optimization."""

    model_name: str
    target: str
    best_params: dict[str, Any]
    best_cv_score: float
    cv_std: float
    train_rmse: float
    test_rmse: float
    test_mae: float
    improvement_vs_baseline: float


class HyperparameterOptimizer:
    """Optimize hyperparameters for CFB betting models."""

    def __init__(self, data_root: str | None = None):
        """Initialize optimizer with data root path."""
        self.data_root = data_root
        self.results: list[OptimizationResult] = []

    def load_training_data(
        self, train_years: list[int], min_week: int = 1, max_week: int = 15
    ) -> pd.DataFrame:
        """Load and combine training data for multiple years."""
        all_data = []

        print(f"Loading training data for years: {train_years}")
        for year in train_years:
            print(f"  Processing year {year}...")
            for week in range(min_week, max_week + 1):
                try:
                    weekly_data = generate_point_in_time_features(
                        year, week, self.data_root
                    )
                    all_data.append(weekly_data)
                except ValueError:
                    # Expected for early weeks with insufficient data
                    continue

        if not all_data:
            raise ValueError("No training data loaded")

        combined_df = pd.concat(all_data, ignore_index=True)

        # Filter to games with complete targets
        target_cols = ["spread_target", "total_target"]
        combined_df = combined_df.dropna(subset=target_cols)

        print(f"Loaded {len(combined_df)} training examples")
        return combined_df

    def load_test_data(self, test_year: int) -> pd.DataFrame:
        """Load test data for holdout evaluation."""
        print(f"Loading test data for year {test_year}...")
        test_data = []

        for week in range(1, 16):
            try:
                weekly_data = generate_point_in_time_features(
                    test_year, week, self.data_root
                )
                test_data.append(weekly_data)
            except ValueError:
                continue

        if not test_data:
            raise ValueError(f"No test data loaded for year {test_year}")

        combined_df = pd.concat(test_data, ignore_index=True)
        target_cols = ["spread_target", "total_target"]
        combined_df = combined_df.dropna(subset=target_cols)

        print(f"Loaded {len(combined_df)} test examples")
        return combined_df

    def get_ridge_param_grid(self) -> dict[str, list]:
        """Get parameter grid for Ridge regression."""
        return {
            "alpha": [0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0],
            "fit_intercept": [True],
            "solver": ["auto"],
        }

    def get_randomforest_param_grid(self, *, fast: bool = False) -> dict[str, list]:
        """Get parameter grid for RandomForest.

        If fast=True, return a smaller grid for quicker iteration.
        """
        if fast:
            return {
                "n_estimators": [150, 200, 250],
                "max_depth": [8, 10, None],
                "min_samples_split": [5, 10, 15],
                "min_samples_leaf": [2, 5],
                "max_features": ["sqrt", "log2"],
                "random_state": [42],
            }
        return {
            "n_estimators": [100, 150, 200, 250, 300],
            "max_depth": [6, 8, 10, 12, None],
            "min_samples_split": [5, 10, 15, 20],
            "min_samples_leaf": [2, 4, 5, 8],
            "max_features": ["sqrt", "log2", None],
            "random_state": [42],
        }

    def optimize_model(
        self,
        model,
        param_grid: dict[str, list],
        x_train: pd.DataFrame,
        y_train: pd.Series,
        x_test: pd.DataFrame,
        y_test: pd.Series,
        model_name: str,
        target: str,
        baseline_rmse: float,
    ) -> OptimizationResult:
        """Run grid search optimization for a model."""
        print(f"\n{'=' * 60}")
        print(f"Optimizing {model_name} for {target}")
        print(f"{'=' * 60}")
        print(f"Parameter grid size: {np.prod([len(v) for v in param_grid.values()])}")
        print(f"Training samples: {len(x_train)}")
        print(f"Test samples: {len(x_test)}")

        # Use TimeSeriesSplit for cross-validation (respects temporal order)
        cv = TimeSeriesSplit(n_splits=5)

        # Grid search with negative RMSE as scoring
        grid_search = GridSearchCV(
            estimator=model,
            param_grid=param_grid,
            cv=cv,
            scoring="neg_root_mean_squared_error",
            n_jobs=-1,  # Use all CPUs
            verbose=1,
            return_train_score=True,
        )

        print("\nRunning grid search...")
        grid_search.fit(x_train, y_train)

        # Best parameters and CV score
        best_params = grid_search.best_params_
        best_cv_score = -grid_search.best_score_  # Convert back to positive RMSE
        cv_std = grid_search.cv_results_["std_test_score"][grid_search.best_index_]

        print(f"\nBest parameters: {best_params}")
        print(f"Best CV RMSE: {best_cv_score:.3f} ± {cv_std:.3f}")

        # Evaluate on training set
        best_model = grid_search.best_estimator_
        train_pred = best_model.predict(x_train)
        train_rmse = np.sqrt(mean_squared_error(y_train, train_pred))

        # Evaluate on test set
        test_pred = best_model.predict(x_test)
        test_rmse = np.sqrt(mean_squared_error(y_test, test_pred))
        test_mae = mean_absolute_error(y_test, test_pred)

        improvement = ((baseline_rmse - test_rmse) / baseline_rmse) * 100

        print("\nResults:")
        print(f"  Train RMSE: {train_rmse:.3f}")
        print(f"  Test RMSE:  {test_rmse:.3f}")
        print(f"  Test MAE:   {test_mae:.3f}")
        print(f"  Baseline:   {baseline_rmse:.3f}")
        print(f"  Improvement: {improvement:+.2f}%")

        return OptimizationResult(
            model_name=model_name,
            target=target,
            best_params=best_params,
            best_cv_score=best_cv_score,
            cv_std=cv_std,
            train_rmse=train_rmse,
            test_rmse=test_rmse,
            test_mae=test_mae,
            improvement_vs_baseline=improvement,
        )

    def run_optimization(
        self,
        train_years: list[int],
        test_year: int,
        optimize_spreads: bool = True,
        optimize_totals: bool = True,
        fast: bool = False,
    ) -> None:
        """Run full hyperparameter optimization."""
        print("\n" + "=" * 60)
        print("HYPERPARAMETER OPTIMIZATION")
        print("=" * 60)

        # Load data
        train_df = self.load_training_data(train_years)
        test_df = self.load_test_data(test_year)

        # Build feature list
        feature_list = build_feature_list(train_df)
        feature_list = [f for f in feature_list if f in test_df.columns]
        print(f"\nUsing {len(feature_list)} features")

        # Prepare datasets
        x_train = train_df[feature_list].astype(float)
        x_test = test_df[feature_list].astype(float)

        # Optimize spreads (Ridge)
        if optimize_spreads:
            print("\n" + "=" * 60)
            print("SPREAD MODEL OPTIMIZATION (Ridge Regression)")
            print("=" * 60)

            y_spread_train = train_df["spread_target"].astype(float)
            y_spread_test = test_df["spread_target"].astype(float)

            # Baseline: current alpha=0.1
            baseline_model = Ridge(alpha=0.1)
            baseline_model.fit(x_train, y_spread_train)
            baseline_pred = baseline_model.predict(x_test)
            baseline_rmse = np.sqrt(mean_squared_error(y_spread_test, baseline_pred))

            print(f"\nBaseline (alpha=0.1) RMSE: {baseline_rmse:.3f}")

            # Optimize
            result = self.optimize_model(
                model=Ridge(),
                param_grid=self.get_ridge_param_grid(),
                x_train=x_train,
                y_train=y_spread_train,
                x_test=x_test,
                y_test=y_spread_test,
                model_name="Ridge",
                target="spread",
                baseline_rmse=baseline_rmse,
            )
            self.results.append(result)

        # Optimize totals (RandomForest)
        if optimize_totals:
            print("\n" + "=" * 60)
            print("TOTAL MODEL OPTIMIZATION (RandomForest)")
            print("=" * 60)

            y_total_train = train_df["total_target"].astype(float)
            y_total_test = test_df["total_target"].astype(float)

            # Baseline: current configuration
            baseline_model = RandomForestRegressor(
                n_estimators=200,
                max_depth=8,
                min_samples_split=10,
                min_samples_leaf=5,
                random_state=42,
            )
            baseline_model.fit(x_train, y_total_train)
            baseline_pred = baseline_model.predict(x_test)
            baseline_rmse = np.sqrt(mean_squared_error(y_total_test, baseline_pred))

            print(f"\nBaseline RMSE: {baseline_rmse:.3f}")

            # Optimize
            result = self.optimize_model(
                model=RandomForestRegressor(),
                param_grid=self.get_randomforest_param_grid(fast=fast),
                x_train=x_train,
                y_train=y_total_train,
                x_test=x_test,
                y_test=y_total_test,
                model_name="RandomForest",
                target="total",
                baseline_rmse=baseline_rmse,
            )
            self.results.append(result)

    def save_results(self, output_dir: str) -> None:
        """Save optimization results."""
        os.makedirs(output_dir, exist_ok=True)

        # Save detailed results as JSON
        results_data = []
        for result in self.results:
            results_data.append(
                {
                    "model_name": result.model_name,
                    "target": result.target,
                    "best_params": result.best_params,
                    "best_cv_score": result.best_cv_score,
                    "cv_std": result.cv_std,
                    "train_rmse": result.train_rmse,
                    "test_rmse": result.test_rmse,
                    "test_mae": result.test_mae,
                    "improvement_vs_baseline": result.improvement_vs_baseline,
                }
            )

        json_path = os.path.join(output_dir, "hyperparameter_optimization_results.json")
        with open(json_path, "w") as f:
            json.dump(results_data, f, indent=2)
        print(f"\n✅ Results saved to {json_path}")

        # Save summary as CSV
        summary_df = pd.DataFrame(
            [
                {
                    "model": r.model_name,
                    "target": r.target,
                    "cv_rmse": r.best_cv_score,
                    "cv_std": r.cv_std,
                    "test_rmse": r.test_rmse,
                    "test_mae": r.test_mae,
                    "improvement_%": r.improvement_vs_baseline,
                }
                for r in self.results
            ]
        )
        csv_path = os.path.join(output_dir, "hyperparameter_optimization_summary.csv")
        summary_df.to_csv(csv_path, index=False)
        print(f"✅ Summary saved to {csv_path}")

    def print_summary(self) -> None:
        """Print optimization summary."""
        print("\n" + "=" * 60)
        print("OPTIMIZATION SUMMARY")
        print("=" * 60)

        for result in self.results:
            print(f"\n{result.model_name} ({result.target}):")
            print(f"  Best CV RMSE: {result.best_cv_score:.3f} ± {result.cv_std:.3f}")
            print(f"  Test RMSE: {result.test_rmse:.3f}")
            print(f"  Improvement: {result.improvement_vs_baseline:+.2f}%")
            print(f"  Best params: {result.best_params}")

        print("\n" + "=" * 60)


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Optimize hyperparameters for spread and total models"
    )
    parser.add_argument(
        "--train-years",
        type=str,
        default="2019,2021,2022,2023",
        help="Comma-separated training years",
    )
    parser.add_argument("--test-year", type=int, default=2024, help="Holdout test year")
    parser.add_argument("--data-root", type=str, default=None, help="Data root path")
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./reports/optimization",
        help="Output directory for results",
    )
    parser.add_argument(
        "--skip-spreads",
        action="store_true",
        help="Skip spread model optimization",
    )
    parser.add_argument(
        "--skip-totals",
        action="store_true",
        help="Skip total model optimization",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Use a smaller grid for faster optimization",
    )

    args = parser.parse_args()

    train_years = [int(y.strip()) for y in args.train_years.split(",")]

    optimizer = HyperparameterOptimizer(data_root=args.data_root)

    try:
        optimizer.run_optimization(
            train_years=train_years,
            test_year=args.test_year,
            optimize_spreads=not args.skip_spreads,
            optimize_totals=not args.skip_totals,
            fast=args.fast,
        )

        optimizer.print_summary()
        optimizer.save_results(args.output_dir)

    except Exception as e:
        print(f"\n❌ Error during optimization: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
