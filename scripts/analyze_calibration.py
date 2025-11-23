#!/usr/bin/env python3
"""
Calibration analysis for CatBoost models (Iteration 2).
Analyzes residuals, calibration curves, and uncertainty validation.

Train: 2019, 2021-2023 (skip 2020)
Test: 2024
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

from src.config import get_data_root
from src.utils.local_storage import LocalStorage


def load_predictions_and_actuals(
    year: int,
    target: str,
    data_root: str | None = None,
    iteration: int = 2,
) -> pd.DataFrame:
    """
    Load predictions and actual results for a given year and target.

    Args:
        year: Test year (typically 2024)
        target: 'spread_target' or 'total_target'
        data_root: Path to data root
        iteration: Adjustment iteration depth

    Returns:
        DataFrame with columns: predicted, actual, residual, game_id, week, etc.
    """
    storage = LocalStorage(
        data_root=data_root, file_format="csv", data_type="processed"
    )

    # Load team_week_adj data for the test year
    records = storage.read_index(
        "team_week_adj", filters={"iteration": iteration, "year": year}
    )

    if not records:
        raise ValueError(f"No data found for year={year}, iteration={iteration}")

    df = pd.DataFrame.from_records(records)

    # TODO: This needs to be hooked up to actual model predictions
    # For now, return structure only
    print(f"Loaded {len(df)} records for {year} at iteration={iteration}")
    print(f"Available columns: {list(df.columns)[:10]}...")

    return df


def compute_residual_bins(
    predictions: pd.Series,
    actuals: pd.Series,
    bin_by: pd.Series,
    bin_labels: list[str],
) -> pd.DataFrame:
    """
    Compute residual statistics by bins.

    Args:
        predictions: Model predictions
        actuals: Actual outcomes
        bin_by: Series to bin by (e.g., edge size, week)
        bin_labels: Labels for bins

    Returns:
        DataFrame with mean, std, count per bin
    """
    residuals = actuals - predictions

    results = []
    for label in bin_labels:
        mask = bin_by == label
        if mask.sum() == 0:
            continue

        bin_residuals = residuals[mask]
        results.append(
            {
                "bin": label,
                "count": len(bin_residuals),
                "mean_residual": bin_residuals.mean(),
                "std_residual": bin_residuals.std(),
                "rmse": np.sqrt(mean_squared_error(actuals[mask], predictions[mask])),
                "mae": mean_absolute_error(actuals[mask], predictions[mask]),
            }
        )

    return pd.DataFrame(results)


def plot_calibration_curve(
    predictions: np.ndarray,
    actuals: np.ndarray,
    n_bins: int = 10,
    title: str = "Calibration Curve",
    output_path: Path | None = None,
) -> None:
    """
    Plot calibration curve (binned actual vs predicted).

    Args:
        predictions: Model predictions
        actuals: Actual outcomes
        n_bins: Number of bins for calibration
        title: Plot title
        output_path: Where to save plot (optional)
    """
    # Create bins based on predicted values
    bin_edges = np.percentile(predictions, np.linspace(0, 100, n_bins + 1))
    bin_indices = np.digitize(predictions, bin_edges[:-1]) - 1

    bin_means_pred = []
    bin_means_actual = []
    bin_counts = []

    for i in range(n_bins):
        mask = bin_indices == i
        if mask.sum() > 0:
            bin_means_pred.append(predictions[mask].mean())
            bin_means_actual.append(actuals[mask].mean())
            bin_counts.append(mask.sum())

    # Plot
    plt.figure(figsize=(8, 8))
    plt.scatter(
        bin_means_pred, bin_means_actual, s=[c * 2 for c in bin_counts], alpha=0.6
    )

    # Perfect calibration line
    min_val = min(min(bin_means_pred), min(bin_means_actual))
    max_val = max(max(bin_means_pred), max(bin_means_actual))
    plt.plot([min_val, max_val], [min_val, max_val], "r--", label="Perfect Calibration")

    plt.xlabel("Mean Predicted Value")
    plt.ylabel("Mean Actual Value")
    plt.title(title)
    plt.legend()
    plt.grid(True, alpha=0.3)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        print(f"Saved calibration curve to {output_path}")
    else:
        plt.show()

    plt.close()


def plot_residuals_by_bins(
    residuals: pd.Series,
    bin_by: pd.Series,
    bin_labels: list[str],
    title: str = "Residuals by Bin",
    output_path: Path | None = None,
) -> None:
    """
    Plot box plots of residuals by bins.

    Args:
        residuals: Prediction residuals
        bin_by: Series to bin by
        bin_labels: Labels for bins
        title: Plot title
        output_path: Where to save plot (optional)
    """
    data = []
    labels = []

    for label in bin_labels:
        mask = bin_by == label
        if mask.sum() > 0:
            data.append(residuals[mask].values)
            labels.append(f"{label} (n={mask.sum()})")

    plt.figure(figsize=(12, 6))
    plt.boxplot(data, labels=labels)
    plt.axhline(y=0, color="r", linestyle="--", alpha=0.5)
    plt.ylabel("Residual (Actual - Predicted)")
    plt.title(title)
    plt.xticks(rotation=45, ha="right")
    plt.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        print(f"Saved residual plot to {output_path}")
    else:
        plt.show()

    plt.close()


def compute_feature_vif(
    df: pd.DataFrame, output_path: Path | None = None
) -> pd.DataFrame:
    """
    Compute Variance Inflation Factor for all numeric features.

    Args:
        df: DataFrame with features
        output_path: Where to save VIF results (optional)

    Returns:
        DataFrame with feature names and VIF values
    """
    from statsmodels.stats.outliers_influence import variance_inflation_factor

    # Select numeric columns only
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    # Remove ID columns and target columns
    exclude = ["season", "week", "before_week", "team", "game_id"]
    feature_cols = [c for c in numeric_cols if c not in exclude]

    # Drop any rows with NaN
    df_clean = df[feature_cols].dropna()

    if len(df_clean) == 0:
        print("Warning: No complete cases for VIF computation")
        return pd.DataFrame()

    print(
        f"Computing VIF for {len(feature_cols)} features on {len(df_clean)} samples..."
    )

    vif_data = []
    for i, col in enumerate(feature_cols):
        if i % 20 == 0:
            print(f"  Progress: {i}/{len(feature_cols)}")
        try:
            vif = variance_inflation_factor(df_clean.values, i)
            vif_data.append({"feature": col, "vif": vif})
        except Exception as e:
            print(f"  Warning: Could not compute VIF for {col}: {e}")
            vif_data.append({"feature": col, "vif": np.nan})

    vif_df = pd.DataFrame(vif_data).sort_values("vif", ascending=False)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        vif_df.to_csv(output_path, index=False)
        print(f"Saved VIF results to {output_path}")

    return vif_df


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run calibration analysis on CatBoost models (Iteration 2)"
    )
    parser.add_argument(
        "--year", type=int, default=2024, help="Test year (default: 2024)"
    )
    parser.add_argument(
        "--target",
        type=str,
        choices=["spread_target", "total_target", "both"],
        default="both",
        help="Target to analyze",
    )
    parser.add_argument(
        "--iteration",
        type=int,
        default=2,
        help="Adjustment iteration depth (default: 2)",
    )
    parser.add_argument(
        "--data-root", type=str, default=str(get_data_root()), help="Data root path"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/reports/calibration"),
        help="Output directory for reports and plots",
    )
    parser.add_argument(
        "--compute-vif",
        action="store_true",
        help="Compute VIF (slow for many features)",
    )

    args = parser.parse_args()

    print(f"\n{'=' * 60}")
    print(f"Calibration Analysis: Iteration {args.iteration}, Test Year {args.year}")
    print(f"{'=' * 60}\n")

    # Load data
    df = load_predictions_and_actuals(
        year=args.year,
        target=args.target if args.target != "both" else "spread_target",
        data_root=args.data_root,
        iteration=args.iteration,
    )

    # Compute VIF if requested
    if args.compute_vif:
        print("\n[1/3] Computing feature collinearity (VIF)...")
        vif_df = compute_feature_vif(
            df,
            output_path=args.output_dir
            / f"feature_vif_iter{args.iteration}_year{args.year}.csv",
        )
        print("\nTop 10 highest VIF features:")
        print(vif_df.head(10).to_string(index=False))
        print(f"\nFeatures with VIF > 10: {(vif_df['vif'] > 10).sum()}")

    print("\n" + "=" * 60)
    print("NOTE: Full calibration analysis requires model predictions.")
    print("This script demonstrates the framework. Integration with")
    print("run_experiment.py or MLflow artifacts is needed for complete analysis.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
