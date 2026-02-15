import itertools
import os
import subprocess
import sys

import pandas as pd

# Add project root to path
sys.path.append(os.getcwd())

from cks_picks_cfb.config import ARTIFACTS_DIR


def run_tuning_sweep():
    year = 2024
    # Reduced weeks for speed during tuning, but enough to capture dynamics
    start_week = 4
    end_week = 12
    draws = 500
    tune = 500

    # Grid Search Space
    sigma_drift_priors = [0.1, 0.5, 1.0, 2.0]
    hfa_mu_priors = [2.0, 2.5, 3.0]

    results = []

    print(f"Starting Tuning Sweep for {year} (Weeks {start_week}-{end_week})...")

    for sigma, hfa in itertools.product(sigma_drift_priors, hfa_mu_priors):
        print(f"\n--- Testing Configuration: Sigma={sigma}, HFA={hfa} ---")

        # Construct command to run backtest
        # We'll parse the output to get metrics, or read the generated CSV
        # Ideally, we modify backtest_ppr to return metrics, but calling via subprocess ensures clean state

        cmd = [
            "uv",
            "run",
            "python",
            "scripts/ratings/backtest_ppr.py",
            "--year",
            str(year),
            "--start_week",
            str(start_week),
            "--end_week",
            str(end_week),
            "--draws",
            str(draws),
            "--tune",
            str(tune),
            "--sigma_drift_prior",
            str(sigma),
            "--hfa_mu_prior",
            str(hfa),
        ]

        try:
            # Run backtest
            # We need to capture stdout to parse the final metrics
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            output = result.stdout

            # Parse metrics from output
            # Look for:
            # RMSE: 19.1234
            # Win Accuracy: 0.6543

            rmse = None
            acc = None

            for line in output.splitlines():
                if "RMSE:" in line:
                    rmse = float(line.split(":")[1].strip())
                if "Win Accuracy:" in line:
                    acc = float(line.split(":")[1].strip())

            if rmse is not None and acc is not None:
                print(f"  Result: RMSE={rmse:.4f}, Acc={acc:.4%}")
                results.append(
                    {
                        "sigma_drift_prior": sigma,
                        "hfa_mu_prior": hfa,
                        "rmse": rmse,
                        "accuracy": acc,
                    }
                )
            else:
                print("  Failed to parse metrics from output.")
                print(output[-500:])  # Print tail of output for debug

        except subprocess.CalledProcessError as e:
            print(f"  Backtest failed: {e}")
            print(e.stderr)

    # Save Tuning Results
    if results:
        df = pd.DataFrame(results)
        df = df.sort_values("accuracy", ascending=False)

        output_dir = ARTIFACTS_DIR / "tuning" / "ppr"
        output_dir.mkdir(parents=True, exist_ok=True)
        csv_path = output_dir / f"tuning_results_{year}.csv"
        df.to_csv(csv_path, index=False)

        print("\n--- Tuning Complete ---")
        print(f"Results saved to {csv_path}")
        print("\nTop 5 Configurations:")
        print(df.head(5).to_markdown(index=False))
    else:
        print("\nNo results collected.")


if __name__ == "__main__":
    run_tuning_sweep()
