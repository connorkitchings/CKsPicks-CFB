#!/usr/bin/env python3
"""
Extract and analyze predictions from recent iteration-2 experiments.
Performs comprehensive calibration analysis on 2024 test data.

Train: 2019, 2021-2023 (skip 2020)
Test: 2024
"""

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import pearsonr
from sklearn.metrics import mean_absolute_error, mean_squared_error

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Set matplotlib style
plt.rcParams["font.size"] = 10
plt.rcParams["figure.facecolor"] = "white"


def load_experiment_predictions(
    artifacts_dir: Path = Path("artifacts"),
) -> pd.DataFrame:
    """Load all predictions from recent experiments."""
    predictions_dir = artifacts_dir / "predictions"

    if not predictions_dir.exists():
        log.warning(f"Predictions directory not found: {predictions_dir}")
        return pd.DataFrame()

    all_predictions = []

    # Iterate through experiment directories
    for exp_dir in predictions_dir.iterdir():
        if not exp_dir.is_dir():
            continue

        for run_dir in exp_dir.iterdir():
            if not run_dir.is_dir():
                continue

            # Load 2024 predictions
            pred_file = run_dir / "2024_predictions.csv"
            if pred_file.exists():
                df = pd.read_csv(pred_file)
                df["experiment"] = exp_dir.name
                df["run_id"] = run_dir.name
                all_predictions.append(df)
                log.info(
                    f"Loaded {len(df)} predictions from {exp_dir.name}/{run_dir.name[:8]}"
                )

    if not all_predictions:
        log.warning("No prediction files found")
        return pd.DataFrame()

    combined = pd.concat(all_predictions, ignore_index=True)
    log.info(
        f"Total predictions loaded: {len(combined)} from {len(all_predictions)} runs"
    )

    return combined


def analyze_residuals(
    predictions: np.ndarray,
    actuals: np.ndarray,
    output_dir: Path,
    target_name: str = "spread",
) -> dict:
    """Compute comprehensive residual statistics."""
    residuals = actuals - predictions

    stats = {
        "count": len(residuals),
        "mean": float(np.mean(residuals)),
        "median": float(np.median(residuals)),
        "std": float(np.std(residuals)),
        "min": float(np.min(residuals)),
        "max": float(np.max(residuals)),
        "rmse": float(np.sqrt(mean_squared_error(actuals, predictions))),
        "mae": float(mean_absolute_error(actuals, predictions)),
        "skew": float(pd.Series(residuals).skew()),
        "kurtosis": float(pd.Series(residuals).kurt()),
    }

    # Plot residual distribution
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Histogram
    axes[0].hist(residuals, bins=30, edgecolor="black", alpha=0.7)
    axes[0].axvline(0, color="red", linestyle="--", linewidth=2, label="Zero")
    axes[0].axvline(
        np.mean(residuals),
        color="blue",
        linestyle="--",
        linewidth=2,
        label=f"Mean: {np.mean(residuals):.2f}",
    )
    axes[0].set_xlabel("Residual (Actual - Predicted)")
    axes[0].set_ylabel("Frequency")
    axes[0].set_title(f"{target_name.title()} Residual Distribution (2024)")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    # Q-Q plot
    from scipy.stats import probplot

    probplot(residuals, dist="norm", plot=axes[1])
    axes[1].set_title("Q-Q Plot (Normality Check)")
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    plot_path = output_dir / f"residuals_{target_name}_2024.png"
    plot_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(plot_path, dpi=150, bbox_inches="tight")
    log.info(f"Saved residual plot to {plot_path}")
    plt.close()

    return stats


def plot_calibration_curve(
    predictions: np.ndarray,
    actuals: np.ndarray,
    output_dir: Path,
    target_name: str = "spread",
    n_bins: int = 10,
) -> None:
    """Generate calibration curve (binned actual vs predicted)."""
    # Create bins based on predicted values
    bin_edges = np.percentile(predictions, np.linspace(0, 100, n_bins + 1))
    bin_indices = np.digitize(predictions, bin_edges[:-1]) - 1

    bin_data = []
    for i in range(n_bins):
        mask = bin_indices == i
        if mask.sum() > 0:
            bin_data.append(
                {
                    "bin": i,
                    "pred_mean": predictions[mask].mean(),
                    "actual_mean": actuals[mask].mean(),
                    "count": mask.sum(),
                    "pred_std": predictions[mask].std(),
                    "actual_std": actuals[mask].std(),
                }
            )

    bin_df = pd.DataFrame(bin_data)

    # Plot
    plt.figure(figsize=(8, 8))
    plt.scatter(
        bin_df["pred_mean"],
        bin_df["actual_mean"],
        s=bin_df["count"] * 3,
        alpha=0.6,
        c="blue",
    )

    # Perfect calibration line
    min_val = min(bin_df["pred_mean"].min(), bin_df["actual_mean"].min())
    max_val = max(bin_df["pred_mean"].max(), bin_df["actual_mean"].max())
    plt.plot(
        [min_val, max_val],
        [min_val, max_val],
        "r--",
        linewidth=2,
        label="Perfect Calibration",
    )

    # Add correlation
    corr, p_value = pearsonr(bin_df["pred_mean"], bin_df["actual_mean"])
    plt.text(
        0.05,
        0.95,
        f"r = {corr:.3f} (p = {p_value:.3e})",
        transform=plt.gca().transAxes,
        fontsize=12,
        verticalalignment="top",
        bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
    )

    plt.xlabel("Mean Predicted Value (per bin)")
    plt.ylabel("Mean Actual Value (per bin)")
    plt.title(f"{target_name.title()} Calibration Curve (2024)")
    plt.legend()
    plt.grid(True, alpha=0.3)

    plot_path = output_dir / f"calibration_{target_name}_2024.png"
    plt.savefig(plot_path, dpi=150, bbox_inches="tight")
    log.info(f"Saved calibration curve to {plot_path}")
    plt.close()

    return bin_df


def analyze_by_edge_bins(
    predictions: np.ndarray,
    actuals: np.ndarray,
    output_dir: Path,
    target_name: str = "spread",
) -> pd.DataFrame:
    """Analyze residuals by absolute edge magnitude bins."""
    residuals = actuals - predictions
    abs_predictions = np.abs(predictions)

    # Define edge bins
    bins = [(0, 5), (5, 10), (10, 15), (15, 100)]
    bin_stats = []

    for low, high in bins:
        mask = (abs_predictions >= low) & (abs_predictions < high)
        if mask.sum() == 0:
            continue

        bin_residuals = residuals[mask]
        bin_stats.append(
            {
                "edge_bin": f"{low}-{high}",
                "count": mask.sum(),
                "mean_residual": bin_residuals.mean(),
                "std_residual": bin_residuals.std(),
                "rmse": np.sqrt(mean_squared_error(actuals[mask], predictions[mask])),
                "mae": mean_absolute_error(actuals[mask], predictions[mask]),
                "median_abs_residual": np.median(np.abs(bin_residuals)),
            }
        )

    bin_df = pd.DataFrame(bin_stats)

    # Save to CSV
    csv_path = output_dir / f"residuals_by_edge_{target_name}_2024.csv"
    bin_df.to_csv(csv_path, index=False)
    log.info(f"Saved edge bin analysis to {csv_path}")

    # Plot
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    axes[0].bar(bin_df["edge_bin"], bin_df["rmse"], alpha=0.7, color="steelblue")
    axes[0].set_xlabel("Absolute Edge Bin")
    axes[0].set_ylabel("RMSE")
    axes[0].set_title(f"{target_name.title()} RMSE by Edge Magnitude")
    axes[0].grid(True, alpha=0.3, axis="y")

    axes[1].scatter(bin_df["count"], bin_df["rmse"], s=100, alpha=0.7, color="coral")
    axes[1].set_xlabel("Number of Samples")
    axes[1].set_ylabel("RMSE")
    axes[1].set_title("Sample Size vs. RMSE")
    axes[1].grid(True, alpha=0.3)

    for i, row in bin_df.iterrows():
        axes[1].annotate(
            row["edge_bin"],
            (row["count"], row["rmse"]),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=9,
        )

    plt.tight_layout()
    plot_path = output_dir / f"edge_analysis_{target_name}_2024.png"
    plt.savefig(plot_path, dpi=150, bbox_inches="tight")
    log.info(f"Saved edge analysis plot to {plot_path}")
    plt.close()

    return bin_df


def main():
    output_dir = Path("artifacts/reports/calibration")
    output_dir.mkdir(parents=True, exist_ok=True)

    log.info("=" * 60)
    log.info("Starting Calibration Analysis on 2024 Test Data")
    log.info("Train: 2019, 2021-2023 | Test: 2024")
    log.info("=" * 60 + "\n")

    # Load predictions
    log.info("[1/5] Loading experiment predictions...")
    df = load_experiment_predictions()

    if df.empty:
        log.error("No predictions found. Exiting.")
        return

    # Filter to most recent spread/total experiments
    # Group by experiment name and use latest run
    log.info("[2/5] Analyzing latest runs per experiment...")

    for exp_name in df["experiment"].unique():
        exp_df = df[df["experiment"] == exp_name]
        latest_run = exp_df.sort_values("run_id").iloc[
            -len(exp_df) // len(exp_df["run_id"].unique()) :
        ]

        log.info(f"\n{'=' * 60}")
        log.info(f"Experiment: {exp_name}")
        log.info(f"Run: {latest_run['run_id'].iloc[0][:8]}...")
        log.info(f"Samples: {len(latest_run)}")
        log.info(f"{'=' * 60}")

        predictions = latest_run["prediction"].values
        actuals = latest_run["actual"].values

        # Infer target type from experiment name
        target_type = "spread" if "spread" in exp_name.lower() else "total"

        # [3/5] Residual analysis
        log.info(f"\n[3/5] Analyzing residuals for {target_type}...")
        residual_stats = analyze_residuals(
            predictions, actuals, output_dir, target_type
        )

        log.info(f"  RMSE: {residual_stats['rmse']:.4f}")
        log.info(f"  MAE: {residual_stats['mae']:.4f}")
        log.info(f"  Mean Residual: {residual_stats['mean']:.4f}")
        log.info(f"  Std Residual: {residual_stats['std']:.4f}")
        log.info(f"  Skew: {residual_stats['skew']:.4f}")

        # [4/5] Calibration curve
        log.info(f"\n[4/5] Generating calibration curve for {target_type}...")
        plot_calibration_curve(predictions, actuals, output_dir, target_type)

        # [5/5] Edge bin analysis
        log.info(f"\n[5/5] Analyzing by edge bins for {target_type}...")
        edge_df = analyze_by_edge_bins(predictions, actuals, output_dir, target_type)

        log.info("\nEdge Bin Results:")
        print(edge_df.to_string(index=False))

    log.info("\n" + "=" * 60)
    log.info("Calibration Analysis Complete!")
    log.info(f"All outputs saved to: {output_dir}")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
