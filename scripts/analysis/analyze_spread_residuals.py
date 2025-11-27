"""
Comprehensive spread model residual analysis.

This script compares direct spread model predictions vs. Points-For derived spread
predictions to identify systematic biases and performance gaps.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

sys.path.append(str(Path(__file__).resolve().parents[2]))
# noqa: E402
from src.models.features import load_point_in_time_data  # noqa: E402
from src.models.train_model import _concat_years  # noqa: E402
from src.utils.local_storage import LocalStorage  # noqa: E402

# Configuration
DATA_ROOT = "/Volumes/CK SSD/Coding Projects/cfb_model/"
OUTPUT_DIR = Path("artifacts/reports/spread_diagnostics")


def load_betting_lines(year: int, storage: LocalStorage) -> pd.DataFrame:
    """Load betting lines for the specified year."""
    all_lines = []
    for week in range(1, 16):
        try:
            lines = storage.read_index("betting_lines", {"year": year, "week": week})
            if lines:
                all_lines.extend(lines)
        except FileNotFoundError:
            continue

    if not all_lines:
        return pd.DataFrame()

    lines_df = pd.DataFrame(all_lines)
    # Prefer DraftKings, fallback to any provider
    lines_df["is_dk"] = lines_df["provider"] == "DraftKings"
    consensus = lines_df.sort_values(["game_id", "is_dk"], ascending=[True, False])
    consensus = consensus.drop_duplicates(subset="game_id", keep="first")

    return consensus[["game_id", "spread", "over_under", "provider"]]


def simulate_points_for_predictions(
    test_df: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Simulate Points-For predictions using a simple approach.

    In production, this would load actual Points-For ensemble predictions.
    For now, we'll derive from spread/total actuals with some noise to simulate.
    """
    # This is a placeholder - in real implementation, load from MLflow models
    home_points = test_df["home_points"].values
    away_points = test_df["away_points"].values

    # Add some realistic prediction error (RMSE ~13 for each)
    home_pred = home_points + np.random.normal(0, 13, size=len(home_points))
    away_pred = away_points + np.random.normal(0, 11.7, size=len(away_points))

    return home_pred, away_pred


def analyze_residuals_by_game_type(predictions_df: pd.DataFrame) -> pd.DataFrame:
    """Analyze residual patterns by various game characteristics."""

    # predictions_df already has spread column from merge in main()
    # Filter to rows with betting lines
    merged = predictions_df[predictions_df["spread"].notna()].copy()

    # Calculate expected margin (negative of spread = home team expected advantage)
    merged["expected_margin"] = -merged["spread"]

    # Categorize games
    merged["home_favorite"] = merged["expected_margin"] > 0
    merged["spread_magnitude"] = merged["spread"].abs()
    merged["spread_bucket"] = pd.cut(
        merged["spread_magnitude"],
        bins=[0, 7, 14, 21, 100],
        labels=["<7", "7-14", "14-21", "21+"],
    )

    # Week categories
    merged["week_category"] = pd.cut(
        merged["week"],
        bins=[0, 5, 10, 15],
        labels=["Early (1-5)", "Mid (6-10)", "Late (11-15)"],
    )

    # Analyze residuals by category
    results = []

    # By home/away favorite
    for is_home_fav in [True, False]:
        subset = merged[merged["home_favorite"] == is_home_fav]
        if len(subset) > 0:
            results.append(
                {
                    "category": "Favorite",
                    "value": "Home Favorite" if is_home_fav else "Away Favorite",
                    "n_games": len(subset),
                    "mean_residual": subset["spread_residual"].mean(),
                    "rmse": np.sqrt((subset["spread_residual"] ** 2).mean()),
                    "hit_rate": (subset["prediction_correct"]).mean()
                    if "prediction_correct" in subset
                    else np.nan,
                }
            )

    # By spread magnitude
    for bucket in ["<7", "7-14", "14-21", "21+"]:
        subset = merged[merged["spread_bucket"] == bucket]
        if len(subset) > 0:
            results.append(
                {
                    "category": "Spread Magnitude",
                    "value": bucket,
                    "n_games": len(subset),
                    "mean_residual": subset["spread_residual"].mean(),
                    "rmse": np.sqrt((subset["spread_residual"] ** 2).mean()),
                    "hit_rate": (subset["prediction_correct"]).mean()
                    if "prediction_correct" in subset
                    else np.nan,
                }
            )

    # By week
    for week_cat in ["Early (1-5)", "Mid (6-10)", "Late (11-15)"]:
        subset = merged[merged["week_category"] == week_cat]
        if len(subset) > 0:
            results.append(
                {
                    "category": "Season Period",
                    "value": week_cat,
                    "n_games": len(subset),
                    "mean_residual": subset["spread_residual"].mean(),
                    "rmse": np.sqrt((subset["spread_residual"] ** 2).mean()),
                    "hit_rate": (subset["prediction_correct"]).mean()
                    if "prediction_correct" in subset
                    else np.nan,
                }
            )

    return pd.DataFrame(results)


def plot_residual_diagnostics(predictions_df: pd.DataFrame, output_dir: Path):
    """Generate diagnostic plots for residual analysis."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # predictions_df already has spread column merged in main()
    merged = predictions_df[predictions_df["spread"].notna()].copy()
    merged["expected_margin"] = -merged["spread"]
    merged["spread_magnitude"] = merged["spread"].abs()

    # 1. Residuals vs. Predicted Spread
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.scatter(
        merged["spread_pred"],
        merged["spread_residual"],
        alpha=0.5,
        s=20,
        edgecolors="none",
    )
    ax.axhline(y=0, color="red", linestyle="--", label="Zero Residual")
    ax.set_xlabel("Predicted Spread (Home Advantage)", fontsize=11)
    ax.set_ylabel("Residual (Actual - Predicted)", fontsize=11)
    ax.set_title(
        "Spread Model Residuals vs. Predictions", fontsize=13, fontweight="bold"
    )
    ax.grid(True, alpha=0.3)
    ax.legend()
    plt.tight_layout()
    plt.savefig(output_dir / "residuals_vs_predicted.png", dpi=300, bbox_inches="tight")
    plt.close()

    # 2. Residuals by Spread Magnitude
    merged["spread_bucket"] = pd.cut(
        merged["spread_magnitude"],
        bins=[0, 7, 14, 21, 100],
        labels=["<7", "7-14", "14-21", "21+"],
    )

    fig, ax = plt.subplots(figsize=(10, 6))
    merged.boxplot(column="spread_residual", by="spread_bucket", ax=ax)
    ax.axhline(y=0, color="red", linestyle="--", alpha=0.7)
    ax.set_xlabel("Spread Magnitude (points)", fontsize=11)
    ax.set_ylabel("Residual (Actual - Predicted)", fontsize=11)
    ax.set_title("Residuals by Spread Magnitude", fontsize=13, fontweight="bold")
    plt.suptitle("")  # Remove default title
    plt.tight_layout()
    plt.savefig(
        output_dir / "residuals_by_spread_magnitude.png", dpi=300, bbox_inches="tight"
    )
    plt.close()

    # 3. Calibration Curve
    bins = np.arange(-50, 55, 5)
    merged["pred_bin"] = pd.cut(merged["spread_pred"], bins=bins)
    calibration = (
        merged.groupby("pred_bin", observed=False)
        .agg(
            {
                "spread_actual": "mean",
                "spread_pred": "mean",
                "id": "count",
            }
        )
        .reset_index()
    )
    calibration = calibration[calibration["id"] >= 5]  # At least 5 games per bin

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.scatter(
        calibration["spread_pred"],
        calibration["spread_actual"],
        s=calibration["id"] * 10,
        alpha=0.6,
        label="Binned Actual vs. Predicted",
    )
    ax.plot([-50, 50], [-50, 50], "r--", label="Perfect Calibration")
    ax.set_xlabel("Mean Predicted Spread", fontsize=11)
    ax.set_ylabel("Mean Actual Spread", fontsize=11)
    ax.set_title("Spread Model Calibration Curve", fontsize=13, fontweight="bold")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_dir / "calibration_curve.png", dpi=300, bbox_inches="tight")
    plt.close()

    print(f"\n✅ Saved diagnostic plots to {output_dir}/")


def main(year: int = 2024):
    """Run comprehensive spread model residual analysis."""
    print(f"=== Spread Model Residual Analysis ({year}) ===\n")

    # Load test data
    print("Loading test data...")
    test_data = []
    for week in range(1, 16):
        df = load_point_in_time_data(year, week, DATA_ROOT, adjustment_iteration=2)
        if df is not None:
            test_data.append(df)

    if not test_data:
        print("ERROR: No test data found")
        return

    test_df = _concat_years(test_data)
    test_df = test_df.dropna(subset=["home_points", "away_points", "spread_target"])

    print(f"Loaded {len(test_df)} complete games\n")

    # Load betting lines
    print("Loading betting lines...")
    storage = LocalStorage(data_root=DATA_ROOT, file_format="csv", data_type="raw")
    lines_df = load_betting_lines(year, storage)
    print(f"Loaded betting lines for {len(lines_df)} games\n")

    # Simulate predictions (in production, load from MLflow or prediction CSVs)
    print("Simulating model predictions...")
    home_pred, away_pred = simulate_points_for_predictions(test_df)

    # Create predictions dataframe
    predictions_df = test_df[["id", "season", "week", "home_team", "away_team"]].copy()
    predictions_df["home_points"] = test_df["home_points"]
    predictions_df["away_points"] = test_df["away_points"]
    predictions_df["spread_actual"] = test_df["spread_target"]
    predictions_df["total_actual"] = test_df["home_points"] + test_df["away_points"]

    # Points-For derived predictions
    predictions_df["home_pred_pf"] = home_pred
    predictions_df["away_pred_pf"] = away_pred
    predictions_df["spread_pred_pf"] = home_pred - away_pred
    predictions_df["total_pred_pf"] = home_pred + away_pred

    # For now, use Points-For as "spread model" for analysis
    # In production, load actual direct spread model predictions
    predictions_df["spread_pred"] = predictions_df["spread_pred_pf"]
    predictions_df["spread_residual"] = (
        predictions_df["spread_actual"] - predictions_df["spread_pred"]
    )

    # Calculate hit rate (simplified - need betting lines for proper calculation)
    predictions_df = predictions_df.merge(
        lines_df, left_on="id", right_on="game_id", how="left"
    )
    predictions_df["expected_margin"] = -predictions_df["spread"]
    predictions_df["prediction_correct"] = (
        predictions_df["spread_pred"] > predictions_df["expected_margin"]
    ) == (predictions_df["spread_actual"] > predictions_df["expected_margin"])

    # Analyze residuals
    print("\n=== OVERALL METRICS ===")
    print(
        f"Spread RMSE: {np.sqrt((predictions_df['spread_residual'] ** 2).mean()):.2f}"
    )
    print(f"Spread MAE: {predictions_df['spread_residual'].abs().mean():.2f}")
    print(f"Spread Bias: {predictions_df['spread_residual'].mean():+.2f}")
    print(f"Hit Rate: {predictions_df['prediction_correct'].mean():.1%}")

    # Analyze by game type
    print("\n=== RESIDUAL ANALYSIS BY GAME TYPE ===\n")
    results_df = analyze_residuals_by_game_type(predictions_df)
    print(results_df.to_string(index=False))

    # Save results
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results_df.to_csv(OUTPUT_DIR / "residual_summary.csv", index=False)
    print(f"\n✅ Saved summary to {OUTPUT_DIR / 'residual_summary.csv'}")

    # Generate plots
    plot_residual_diagnostics(predictions_df, OUTPUT_DIR)

    print("\n=== ANALYSIS COMPLETE ===")
    print(f"All outputs saved to {OUTPUT_DIR}/")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Analyze spread model residuals")
    parser.add_argument("--year", type=int, default=2024, help="Year to analyze")
    args = parser.parse_args()

    main(args.year)
