#!/usr/bin/env python3
"""
Calibration analysis for Walk-Forward Validation results.
Analyzes residuals, calibration curves, and bias year-over-year.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error


def load_predictions(file_path: Path) -> pd.DataFrame:
    """Load predictions from CSV."""
    if not file_path.exists():
        raise FileNotFoundError(f"Predictions file not found: {file_path}")
    return pd.read_csv(file_path)


def compute_metrics(df: pd.DataFrame, actual_col: str, pred_col: str) -> dict:
    """Compute RMSE, MAE, and Bias (Mean Residual)."""
    # Drop NaNs
    valid = df[[actual_col, pred_col]].dropna()
    if valid.empty:
        return {"rmse": np.nan, "mae": np.nan, "bias": np.nan, "count": 0}

    actuals = valid[actual_col]
    preds = valid[pred_col]
    residuals = actuals - preds

    return {
        "rmse": np.sqrt(mean_squared_error(actuals, preds)),
        "mae": mean_absolute_error(actuals, preds),
        "bias": residuals.mean(),  # Positive bias = Actual > Pred (Underprediction)
        "count": len(valid),
    }


def plot_calibration_curve(
    df: pd.DataFrame,
    actual_col: str,
    pred_col: str,
    n_bins: int = 10,
    title: str = "Calibration Curve",
    output_path: Path | None = None,
) -> None:
    """Plot calibration curve."""
    valid = df[[actual_col, pred_col]].dropna()
    if valid.empty:
        return

    actuals = valid[actual_col].values
    preds = valid[pred_col].values

    # Create bins
    try:
        bin_edges = np.percentile(preds, np.linspace(0, 100, n_bins + 1))
    except IndexError:
        return

    bin_means_pred = []
    bin_means_actual = []
    bin_counts = []

    for i in range(n_bins):
        # Handle edge case where bin edges are not unique
        if bin_edges[i] == bin_edges[i + 1]:
            continue

        mask = (preds >= bin_edges[i]) & (preds < bin_edges[i + 1])
        if i == n_bins - 1:  # Include upper bound for last bin
            mask = (preds >= bin_edges[i]) & (preds <= bin_edges[i + 1])

        if mask.sum() > 0:
            bin_means_pred.append(preds[mask].mean())
            bin_means_actual.append(actuals[mask].mean())
            bin_counts.append(mask.sum())

    plt.figure(figsize=(8, 8))
    plt.scatter(
        bin_means_pred, bin_means_actual, s=[c * 2 for c in bin_counts], alpha=0.6
    )

    # Perfect calibration line
    if bin_means_pred and bin_means_actual:
        min_val = min(min(bin_means_pred), min(bin_means_actual))
        max_val = max(max(bin_means_pred), max(bin_means_actual))
        plt.plot(
            [min_val, max_val], [min_val, max_val], "r--", label="Perfect Calibration"
        )

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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze calibration from predictions CSV"
    )
    parser.add_argument(
        "--predictions-file",
        type=Path,
        required=True,
        help="Path to predictions CSV file",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/reports/calibration"),
        help="Output directory",
    )
    parser.add_argument(
        "--model-col",
        type=str,
        default="spread_pred_points_for_ensemble",
        help="Column name for model predictions",
    )
    parser.add_argument(
        "--actual-col",
        type=str,
        default="spread_actual",
        help="Column name for actual values",
    )
    args = parser.parse_args()

    print(f"Analyzing {args.predictions_file}...")
    df = load_predictions(args.predictions_file)

    metrics = compute_metrics(df, args.actual_col, args.model_col)

    print("\nMetrics:")
    print(f"  Count: {metrics['count']}")
    print(f"  RMSE:  {metrics['rmse']:.4f}")
    print(f"  MAE:   {metrics['mae']:.4f}")
    print(f"  Bias:  {metrics['bias']:.4f} (Actual - Pred)")

    # Plot
    plot_name = args.predictions_file.stem
    plot_calibration_curve(
        df,
        args.actual_col,
        args.model_col,
        title=f"Calibration: {plot_name}",
        output_path=args.output_dir / f"calibration_{plot_name}.png",
    )


if __name__ == "__main__":
    main()
