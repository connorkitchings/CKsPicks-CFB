"""
Analyzes the effect and impact of iterative opponent-adjustment.
"""

import argparse
import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

# Add project root to path to allow importing from src
sys.path.append(os.getcwd())
from cks_picks_cfb.utils.local_storage import LocalStorage


def plot_convergence(data: pd.DataFrame, metric: str, teams: list[str]):
    """
    Plots the value of a metric across adjustment iterations for a list of teams.
    """
    print(
        f"Plotting convergence for metric '{metric}' for teams: {', '.join(teams)}..."
    )

    plot_df = data[data["team"].isin(teams)].copy()

    if plot_df.empty:
        print(f"Warning: No data found for the specified teams: {', '.join(teams)}")
        return

    if metric not in plot_df.columns:
        print(
            f"Error: Metric '{metric}' not found in the dataset. Available metrics start with 'adj_'."
        )
        return

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(12, 8))

    sns.lineplot(data=plot_df, x="iteration", y=metric, hue="team", marker="o", ax=ax)

    ax.set_title(f"Opponent-Adjustment Convergence for '{metric}'", fontsize=16)
    ax.set_xlabel("Iteration", fontsize=12)
    ax.set_ylabel(metric, fontsize=12)
    ax.legend(title="Team")

    output_dir = Path("artifacts/analysis")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"adjustment_convergence_{metric}.png"

    print(f"Saving plot to {output_path}")
    fig.savefig(output_path)
    plt.close(fig)


def run_performance_analysis(year: int, iterations: list[int]):
    """
    Runs training experiments for each adjustment iteration and compares performance.
    """
    print(
        f"Running performance analysis for year {year} across iterations: {iterations}..."
    )
    print("Placeholder: Performance analysis would happen here.")
    print(
        "This would involve programmatically calling the training script and analyzing mlflow results."
    )


def main():
    """Main function to parse arguments and dispatch to the correct analysis mode."""
    parser = argparse.ArgumentParser(
        description="Analyze the effect of iterative opponent-adjustment.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--year", type=int, required=True, help="The season year to analyze."
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["visual", "performance"],
        required=True,
        help=(
            "Analysis mode:\n"
            "'visual': Plot metric convergence for a set of teams.\n"
            "'performance': Run experiments to find the best iteration level."
        ),
    )
    parser.add_argument(
        "--metric",
        type=str,
        help="The metric to plot in 'visual' mode (e.g., 'adj_off_epa_pp').",
    )
    parser.add_argument(
        "--teams",
        nargs="+",
        help="A list of team names to plot in 'visual' mode (e.g., 'Alabama' 'Georgia').",
    )

    args = parser.parse_args()

    if args.mode == "visual":
        if not args.metric or not args.teams:
            parser.error("'visual' mode requires --metric and --teams arguments.")

        try:
            storage = LocalStorage(file_format="csv", data_type="processed")
            records = storage.read_index(
                "team_season_adj_iterations", {"year": str(args.year)}
            )
            if not records:
                raise FileNotFoundError(
                    f"No adjustment iteration data found for year {args.year}. Please run the data pipeline first."
                )

            df = pd.DataFrame.from_records(records)
            print(f"Successfully loaded {len(df)} records for {args.year}.")

            plot_convergence(df, args.metric, args.teams)
        except Exception as e:
            print(f"An error occurred during visual analysis: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.mode == "performance":
        iterations_to_test = list(range(7))  # Test iterations 0 through 6
        run_performance_analysis(args.year, iterations_to_test)


if __name__ == "__main__":
    main()
