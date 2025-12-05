import subprocess
from pathlib import Path

import pandas as pd


def main():
    years = [2019, 2021, 2022, 2023, 2024]
    base_dir = Path("artifacts/validation/walk_forward")
    output_dir = Path("artifacts/reports/calibration/pruned_validation")
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []

    for year in years:
        pred_file = base_dir / f"{year}_predictions.csv"
        if not pred_file.exists():
            print(f"Skipping {year}: {pred_file} not found")
            continue

        print(f"Analyzing {year}...")
        cmd = [
            "uv",
            "run",
            "python",
            "scripts/analyze_calibration.py",
            "--predictions-file",
            str(pred_file),
            "--output-dir",
            str(output_dir),
            "--model-col",
            "spread_pred_points_for_ensemble",
            "--actual-col",
            "spread_actual",
        ]

        # Run analysis script to generate plots
        subprocess.run(cmd, check=True)

        # Load predictions to compute metrics directly for summary
        df = pd.read_csv(pred_file)
        valid = df[["spread_actual", "spread_pred_points_for_ensemble"]].dropna()
        bias = (
            valid["spread_actual"] - valid["spread_pred_points_for_ensemble"]
        ).mean()
        rmse = (
            (valid["spread_actual"] - valid["spread_pred_points_for_ensemble"]) ** 2
        ).mean() ** 0.5

        results.append({"year": year, "bias": bias, "rmse": rmse, "count": len(valid)})

    # Save summary
    summary_df = pd.DataFrame(results)
    summary_path = output_dir / "bias_summary.csv"
    summary_df.to_csv(summary_path, index=False)
    print(f"\nSummary saved to {summary_path}")
    print(summary_df)


if __name__ == "__main__":
    main()
