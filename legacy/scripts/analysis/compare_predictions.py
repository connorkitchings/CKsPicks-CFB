"""Script to compare prototype predictions vs walk-forward predictions."""

from pathlib import Path

import pandas as pd


def main():
    # 1. Load Prototype Predictions
    proto_dir = Path("artifacts/predictions/points_for_prototype")
    proto_files = list(proto_dir.glob("*_predictions.csv"))
    if not proto_files:
        print("No prototype files found.")
        return
    proto_file = max(proto_files, key=lambda p: p.stat().st_mtime)
    print(f"Prototype File: {proto_file}")
    proto_df = pd.read_csv(proto_file)

    # 2. Load Walk-Forward Predictions
    wf_file = Path("artifacts/validation/walk_forward/2024_predictions.csv")
    if not wf_file.exists():
        print("No walk-forward file found.")
        return
    print(f"Walk-Forward File: {wf_file}")
    wf_df = pd.read_csv(wf_file)

    # 3. Compare Columns
    print("\n--- Prototype Columns ---")
    print(proto_df.columns.tolist())
    print("\n--- Walk-Forward Columns ---")
    print(wf_df.columns.tolist())

    # 4. Merge and Compare Values
    # Proto: id, pred_spread
    # WF: id, spread_pred_points_for_ensemble

    # Ensure ID match
    proto_df["id"] = proto_df["id"].astype(int)
    wf_df["id"] = wf_df["id"].astype(int)

    merged = pd.merge(
        proto_df[["id", "pred_spread", "pred_total"]],
        wf_df[
            ["id", "spread_pred_points_for_ensemble", "total_pred_points_for_ensemble"]
        ],
        on="id",
        how="inner",
        suffixes=("_proto", "_wf"),
    )

    print(f"\nMerged {len(merged)} games.")

    # Calculate Correlation
    spread_corr = merged["pred_spread"].corr(merged["spread_pred_points_for_ensemble"])
    total_corr = merged["pred_total"].corr(merged["total_pred_points_for_ensemble"])

    print(f"Spread Correlation: {spread_corr:.4f}")
    print(f"Total Correlation: {total_corr:.4f}")

    # Calculate Mean Absolute Difference
    merged["spread_diff"] = (
        merged["pred_spread"] - merged["spread_pred_points_for_ensemble"]
    ).abs()
    print(f"Mean Abs Spread Diff: {merged['spread_diff'].mean():.4f}")

    # Check if they are identical
    if merged["spread_diff"].max() < 0.001:
        print("Predictions are IDENTICAL.")
    else:
        print("Predictions are DIFFERENT.")

    # Sample differences
    print("\n--- Sample Differences ---")
    print(
        merged[
            ["id", "pred_spread", "spread_pred_points_for_ensemble", "spread_diff"]
        ].head(10)
    )


if __name__ == "__main__":
    main()
