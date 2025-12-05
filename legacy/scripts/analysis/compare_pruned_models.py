"""Compare pruned Points-For models against baseline."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
# noqa: E402
import mlflow
import numpy as np
import pandas as pd

from src.models.features import load_point_in_time_data
from src.models.train_model import _concat_years


def load_ensemble_from_registry(model_name_prefix: str, num_seeds: int = 5) -> list:
    """Load ensemble models from MLflow registry."""
    models = []
    for i in range(1, num_seeds + 1):
        model_name = f"{model_name_prefix}_seed_{i}"
        try:
            model_uri = f"models:/{model_name}/Production"
            model = mlflow.catboost.load_model(model_uri)
            models.append(model)
            print(f"Loaded {model_name}")
        except Exception as e:
            print(f"Failed to load {model_name}: {e}")
    return models


def ensemble_predict(models: list, data_frame: pd.DataFrame) -> np.ndarray:
    """Get average prediction from ensemble."""
    predictions = np.array([model.predict(data_frame) for model in models])
    return predictions.mean(axis=0)


def evaluate(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """Calculate RMSE and MAE."""
    errors = y_true - y_pred
    return {
        "rmse": np.sqrt(np.mean(errors**2)),
        "mae": np.mean(np.abs(errors)),
    }


def main():
    # Setup
    # Setup
    from src.utils.mlflow_tracking import setup_mlflow

    setup_mlflow()

    print("Loading 2024 test data...")
    # Load 2024 test data
    test_year = 2024
    test_data = []
    for week in range(1, 17):
        df = load_point_in_time_data(
            test_year,
            week,
            "/Volumes/CK SSD/Coding Projects/cfb_model",
            adjustment_iteration=2,
        )
        if df is not None:
            test_data.append(df)

    test_df = _concat_years(test_data)
    print(f"Test data shape: {test_df.shape}")

    # Load baseline models
    print("\nLoading baseline models...")
    baseline_home = load_ensemble_from_registry("points_for_home")
    baseline_away = load_ensemble_from_registry("points_for_away")

    # Load pruned models
    print("\nLoading pruned models...")
    pruned_home = load_ensemble_from_registry("points_for_home_pruned")
    pruned_away = load_ensemble_from_registry("points_for_away_pruned")

    if not baseline_home or not baseline_away:
        print("ERROR: Could not load baseline models")
        return

    if not pruned_home or not pruned_away:
        print("ERROR: Could not load pruned models")
        return

    # Get feature lists
    baseline_home_features = baseline_home[0].feature_names_
    baseline_away_features = baseline_away[0].feature_names_
    pruned_home_features = pruned_home[0].feature_names_
    pruned_away_features = pruned_away[0].feature_names_

    print(
        f"\nBaseline uses {len(baseline_home_features)} home features, {len(baseline_away_features)} away features"
    )
    print(
        f"Pruned uses {len(pruned_home_features)} home features, {len(pruned_away_features)} away features"
    )

    # Check for missing features and add them as zeros
    all_features = (
        set(baseline_home_features)
        | set(baseline_away_features)
        | set(pruned_home_features)
        | set(pruned_away_features)
    )
    missing = [f for f in all_features if f not in test_df.columns]

    if missing:
        print(f"\nAdding {len(missing)} missing features as zeros")
        for feat in missing:
            test_df[feat] = 0.0

    # Prepare test sets
    test_complete = test_df.dropna(subset=["home_points", "away_points"]).copy()

    print(f"\nEvaluating on {len(test_complete)} complete games...")

    # Baseline predictions
    print("\n=== BASELINE MODELS ===")
    home_pred_baseline = ensemble_predict(
        baseline_home, test_complete[baseline_home_features]
    )
    away_pred_baseline = ensemble_predict(
        baseline_away, test_complete[baseline_away_features]
    )

    home_metrics_baseline = evaluate(
        test_complete["home_points"].values, home_pred_baseline
    )
    away_metrics_baseline = evaluate(
        test_complete["away_points"].values, away_pred_baseline
    )

    print(
        f"Home Points: RMSE={home_metrics_baseline['rmse']:.2f}, MAE={home_metrics_baseline['mae']:.2f}"
    )
    print(
        f"Away Points: RMSE={away_metrics_baseline['rmse']:.2f}, MAE={away_metrics_baseline['mae']:.2f}"
    )

    # Derived metrics
    spread_pred_baseline = home_pred_baseline - away_pred_baseline
    total_pred_baseline = home_pred_baseline + away_pred_baseline

    spread_actual = test_complete["home_points"] - test_complete["away_points"]
    total_actual = test_complete["home_points"] + test_complete["away_points"]

    spread_metrics_baseline = evaluate(spread_actual.values, spread_pred_baseline)
    total_metrics_baseline = evaluate(total_actual.values, total_pred_baseline)

    print(
        f"Derived Spread: RMSE={spread_metrics_baseline['rmse']:.2f}, MAE={spread_metrics_baseline['mae']:.2f}"
    )
    print(
        f"Derived Total: RMSE={total_metrics_baseline['rmse']:.2f}, MAE={total_metrics_baseline['mae']:.2f}"
    )

    # Pruned predictions
    print("\n=== PRUNED MODELS ===")
    home_pred_pruned = ensemble_predict(
        pruned_home, test_complete[pruned_home_features]
    )
    away_pred_pruned = ensemble_predict(
        pruned_away, test_complete[pruned_away_features]
    )

    home_metrics_pruned = evaluate(
        test_complete["home_points"].values, home_pred_pruned
    )
    away_metrics_pruned = evaluate(
        test_complete["away_points"].values, away_pred_pruned
    )

    print(
        f"Home Points: RMSE={home_metrics_pruned['rmse']:.2f}, MAE={home_metrics_pruned['mae']:.2f}"
    )
    print(
        f"Away Points: RMSE={away_metrics_pruned['rmse']:.2f}, MAE={away_metrics_pruned['mae']:.2f}"
    )

    # Derived metrics
    spread_pred_pruned = home_pred_pruned - away_pred_pruned
    total_pred_pruned = home_pred_pruned + away_pred_pruned

    spread_metrics_pruned = evaluate(spread_actual.values, spread_pred_pruned)
    total_metrics_pruned = evaluate(total_actual.values, total_pred_pruned)

    print(
        f"Derived Spread: RMSE={spread_metrics_pruned['rmse']:.2f}, MAE={spread_metrics_pruned['mae']:.2f}"
    )
    print(
        f"Derived Total: RMSE={total_metrics_pruned['rmse']:.2f}, MAE={total_metrics_pruned['mae']:.2f}"
    )

    # Summary comparison
    print("\n=== COMPARISON (Baseline → Pruned) ===")
    print(
        f"Home Points RMSE: {home_metrics_baseline['rmse']:.2f} → {home_metrics_pruned['rmse']:.2f} ({home_metrics_pruned['rmse'] - home_metrics_baseline['rmse']:+.2f})"
    )
    print(
        f"Away Points RMSE: {away_metrics_baseline['rmse']:.2f} → {away_metrics_pruned['rmse']:.2f} ({away_metrics_pruned['rmse'] - away_metrics_baseline['rmse']:+.2f})"
    )
    print(
        f"Spread RMSE: {spread_metrics_baseline['rmse']:.2f} → {spread_metrics_pruned['rmse']:.2f} ({spread_metrics_pruned['rmse'] - spread_metrics_baseline['rmse']:+.2f})"
    )
    print(
        f"Total RMSE: {total_metrics_baseline['rmse']:.2f} → {total_metrics_pruned['rmse']:.2f} ({total_metrics_pruned['rmse'] - total_metrics_baseline['rmse']:+.2f})"
    )

    print(
        f"\nFeature reduction: {len(baseline_home_features)} → {len(pruned_home_features)} ({(1 - len(pruned_home_features) / len(baseline_home_features)) * 100:.1f}% reduction)"
    )


if __name__ == "__main__":
    main()
