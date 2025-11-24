"""Weekly calibration monitoring for Points-For models.

This script analyzes recent predictions to detect bias, drift, and calibration issues
in the production Points-For models.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

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
        except Exception as e:
            print(f"Warning: Failed to load {model_name}: {e}")
    return models


def ensemble_predict(models: list, data_frame: pd.DataFrame) -> np.ndarray:
    """Get average prediction from ensemble."""
    predictions = np.array([model.predict(data_frame) for model in models])
    return predictions.mean(axis=0)


def calculate_calibration_metrics(actual: np.ndarray, predicted: np.ndarray) -> dict:
    """Calculate calibration metrics."""
    errors = actual - predicted

    return {
        "mean_error": np.mean(errors),
        "rmse": np.sqrt(np.mean(errors**2)),
        "mae": np.mean(np.abs(errors)),
        "std_error": np.std(errors),
        "median_error": np.median(errors),
        "bias": np.mean(errors),  # Same as mean_error, for clarity
    }


def check_drift(
    current_metrics: dict, baseline_metrics: dict, thresholds: dict
) -> list:
    """Check for significant drift from baseline."""
    alerts = []

    # Check bias drift
    bias_change = abs(current_metrics["bias"] - baseline_metrics.get("bias", 0))
    if bias_change > thresholds["bias_threshold"]:
        alerts.append(
            f"⚠️  BIAS DRIFT: {bias_change:.2f} points (threshold: {thresholds['bias_threshold']:.2f})"
        )

    # Check RMSE degradation
    rmse_change = current_metrics["rmse"] - baseline_metrics.get(
        "rmse", current_metrics["rmse"]
    )
    if rmse_change > thresholds["rmse_threshold"]:
        alerts.append(
            f"⚠️  RMSE DEGRADATION: +{rmse_change:.2f} points (threshold: {thresholds['rmse_threshold']:.2f})"
        )

    return alerts


def main(year: int = 2024, start_week: int = 1, end_week: int = None):
    """Run calibration monitoring for specified weeks."""
    mlflow.set_tracking_uri(
        "file:///Users/connorkitchings/Desktop/Repositories/cfb_model/artifacts/mlruns"
    )

    print(f"=== Weekly Calibration Monitoring ({year}) ===\n")

    # Load models
    print("Loading models from registry...")
    home_models = load_ensemble_from_registry("points_for_home")
    away_models = load_ensemble_from_registry("points_for_away")

    if not home_models or not away_models:
        print("ERROR: Could not load models")
        return

    print(f"Loaded {len(home_models)} home models, {len(away_models)} away models\n")

    # Get feature names
    home_features = home_models[0].feature_names_
    away_features = away_models[0].feature_names_

    # Load data for specified weeks
    if end_week is None:
        end_week = 16

    weekly_data = []
    for week in range(start_week, end_week + 1):
        df = load_point_in_time_data(
            year,
            week,
            "/Volumes/CK SSD/Coding Projects/cfb_model",
            adjustment_iteration=2,
        )
        if df is not None:
            df["week"] = week
            weekly_data.append(df)

    if not weekly_data:
        print("ERROR: No data found")
        return

    all_data = _concat_years(weekly_data)

    # Add missing features as zeros
    all_features = set(home_features) | set(away_features)
    missing = [f for f in all_features if f not in all_data.columns]
    if missing:
        for feat in missing:
            all_data[feat] = 0.0

    # Filter to complete games
    complete = all_data.dropna(subset=["home_points", "away_points"]).copy()

    print(f"Analyzing {len(complete)} complete games (weeks {start_week}-{end_week})\n")

    # Get predictions
    home_pred = ensemble_predict(home_models, complete[home_features])
    away_pred = ensemble_predict(away_models, complete[away_features])

    # Calculate derived predictions
    spread_pred = home_pred - away_pred
    total_pred = home_pred + away_pred

    # Calculate actuals
    spread_actual = complete["home_points"] - complete["away_points"]
    total_actual = complete["home_points"] + complete["away_points"]

    # Calculate calibration metrics
    print("=== CALIBRATION METRICS ===\n")

    home_metrics = calculate_calibration_metrics(
        complete["home_points"].values, home_pred
    )
    away_metrics = calculate_calibration_metrics(
        complete["away_points"].values, away_pred
    )
    spread_metrics = calculate_calibration_metrics(spread_actual.values, spread_pred)
    total_metrics = calculate_calibration_metrics(total_actual.values, total_pred)

    print("Home Points:")
    print(f"  Bias (Mean Error): {home_metrics['bias']:+.2f} points")
    print(f"  RMSE: {home_metrics['rmse']:.2f}")
    print(f"  MAE: {home_metrics['mae']:.2f}")
    print(f"  Std Error: {home_metrics['std_error']:.2f}\n")

    print("Away Points:")
    print(f"  Bias (Mean Error): {away_metrics['bias']:+.2f} points")
    print(f"  RMSE: {away_metrics['rmse']:.2f}")
    print(f"  MAE: {away_metrics['mae']:.2f}")
    print(f"  Std Error: {away_metrics['std_error']:.2f}\n")

    print("Spread (Derived):")
    print(f"  Bias (Mean Error): {spread_metrics['bias']:+.2f} points")
    print(f"  RMSE: {spread_metrics['rmse']:.2f}")
    print(f"  MAE: {spread_metrics['mae']:.2f}")
    print(f"  Std Error: {spread_metrics['std_error']:.2f}\n")

    print("Total (Derived):")
    print(f"  Bias (Mean Error): {total_metrics['bias']:+.2f} points")
    print(f"  RMSE: {total_metrics['rmse']:.2f}")
    print(f"  MAE: {total_metrics['mae']:.2f}")
    print(f"  Std Error: {total_metrics['std_error']:.2f}\n")

    # Check for drift (using 2024 baseline from our earlier analysis)
    baseline_spread = {"bias": 0.0, "rmse": 18.69}  # From baseline comparison
    baseline_total = {"bias": 0.0, "rmse": 17.18}

    thresholds = {
        "bias_threshold": 1.0,  # Alert if bias > 1 point
        "rmse_threshold": 1.5,  # Alert if RMSE degrades by > 1.5 points
    }

    print("=== DRIFT DETECTION ===\n")

    spread_alerts = check_drift(spread_metrics, baseline_spread, thresholds)
    total_alerts = check_drift(total_metrics, baseline_total, thresholds)

    if spread_alerts:
        print("Spread Alerts:")
        for alert in spread_alerts:
            print(f"  {alert}")
    else:
        print("✅ Spread: No significant drift detected")

    if total_alerts:
        print("\nTotal Alerts:")
        for alert in total_alerts:
            print(f"  {alert}")
    else:
        print("✅ Total: No significant drift detected")

    # Weekly breakdown
    if len(weekly_data) > 1:
        print("\n=== WEEKLY BREAKDOWN ===\n")
        for week_num in range(start_week, end_week + 1):
            week_data = complete[complete["week"] == week_num]
            if len(week_data) == 0:
                continue

            week_home_pred = ensemble_predict(home_models, week_data[home_features])
            week_away_pred = ensemble_predict(away_models, week_data[away_features])
            week_spread_pred = week_home_pred - week_away_pred
            week_spread_actual = week_data["home_points"] - week_data["away_points"]

            week_spread_metrics = calculate_calibration_metrics(
                week_spread_actual.values, week_spread_pred
            )

            print(
                f"Week {week_num}: Bias={week_spread_metrics['bias']:+.2f}, "
                f"RMSE={week_spread_metrics['rmse']:.2f} ({len(week_data)} games)"
            )

    print("\n=== RECOMMENDATIONS ===\n")

    # Generate recommendations based on findings
    if abs(spread_metrics["bias"]) > 0.5:
        print(
            f"📊 Consider recalibration: Spread bias is {spread_metrics['bias']:+.2f} points"
        )

    if abs(total_metrics["bias"]) > 0.5:
        print(
            f"📊 Consider recalibration: Total bias is {total_metrics['bias']:+.2f} points"
        )

    if not spread_alerts and not total_alerts and abs(spread_metrics["bias"]) < 0.5:
        print("✅ Models are well-calibrated. No action needed.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Monitor model calibration")
    parser.add_argument("--year", type=int, default=2024, help="Year to analyze")
    parser.add_argument("--start-week", type=int, default=1, help="Start week")
    parser.add_argument(
        "--end-week", type=int, default=None, help="End week (default: 16)"
    )

    args = parser.parse_args()

    main(args.year, args.start_week, args.end_week)
