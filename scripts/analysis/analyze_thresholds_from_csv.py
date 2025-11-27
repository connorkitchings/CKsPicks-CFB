import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def load_betting_lines(year):
    """Loads betting lines from weekly bet files."""
    lines_data = []
    reports_dir = Path(f"artifacts/reports/{year}/predictions")
    if not reports_dir.exists():
        print(f"Warning: Reports directory not found: {reports_dir}")
        return pd.DataFrame()

    for file_path in reports_dir.glob("CFB_week*_bets.csv"):
        try:
            df = pd.read_csv(file_path)
            # Keep only necessary columns
            cols = ["game_id", "home_team_spread_line", "total_line"]
            if all(c in df.columns for c in cols):
                lines_data.append(df[cols])
        except Exception as e:
            print(f"Error reading {file_path}: {e}")

    if not lines_data:
        return pd.DataFrame()

    combined_lines = pd.concat(lines_data, ignore_index=True)
    # Drop duplicates if any (though game_ids should be unique per season usually)
    combined_lines = combined_lines.drop_duplicates(subset=["game_id"])
    return combined_lines


def analyze_thresholds(df, target_type="spread"):
    # Ensure required columns exist
    required_cols = (
        ["pred_spread", "spread_line", "actual_spread"]
        if target_type == "spread"
        else ["pred_total", "total_line", "actual_total"]
    )
    if not all(col in df.columns for col in required_cols):
        print(f"Error: Missing columns. Found: {df.columns.tolist()}")
        return

    # Calculate Edge
    if target_type == "spread":
        # Edge = Pred - Line (positive means we think Home covers more/Away covers less)
        # Bet Home if Edge > 0, Bet Away if Edge < 0
        df["edge"] = df["pred_spread"] - df["spread_line"]
        df["bet_side"] = np.where(df["edge"] > 0, "Home", "Away")

        # Outcome
        # Home Win if Actual > -Line
        # e.g. Line -7. Actual 8. 8 > 7. Win.
        # e.g. Line +7. Actual -6. -6 > -7. Win.
        df["result_home"] = df["actual_spread"] + df["spread_line"]

        # Bet Result
        conditions = [
            (df["bet_side"] == "Home") & (df["result_home"] > 0),
            (df["bet_side"] == "Away") & (df["result_home"] < 0),
            (df["result_home"] == 0),  # Push
        ]
        choices = ["Win", "Win", "Push"]
        df["bet_result"] = np.select(conditions, choices, default="Loss")

    else:  # Total
        # Edge = Pred - Line
        # Bet Over if Edge > 0, Under if Edge < 0
        df["edge"] = df["pred_total"] - df["total_line"]
        df["bet_side"] = np.where(df["edge"] > 0, "Over", "Under")

        # Outcome
        conditions = [
            (df["bet_side"] == "Over") & (df["actual_total"] > df["total_line"]),
            (df["bet_side"] == "Under") & (df["actual_total"] < df["total_line"]),
            (df["actual_total"] == df["total_line"]),
        ]
        choices = ["Win", "Win", "Push"]
        df["bet_result"] = np.select(conditions, choices, default="Loss")

    # Threshold Analysis
    thresholds = [
        0.0,
        0.5,
        1.0,
        1.5,
        2.0,
        2.5,
        3.0,
        3.5,
        4.0,
        4.5,
        5.0,
        5.5,
        6.0,
        6.5,
        7.0,
        7.5,
        8.0,
        8.5,
        9.0,
        9.5,
        10.0,
    ]

    print(f"\n--- {target_type.upper()} THRESHOLD ANALYSIS ---")
    print(
        f"{'Threshold':>10} {'Count':>6} {'Wins':>6} {'Losses':>6} {'Win Rate':>8} {'ROI':>8}"
    )

    for t in thresholds:
        # Filter by absolute edge
        subset = df[df["edge"].abs() >= t].copy()

        # Exclude Pushes from Win Rate
        decided = subset[subset["bet_result"] != "Push"]
        wins = len(decided[decided["bet_result"] == "Win"])
        losses = len(decided[decided["bet_result"] == "Loss"])
        total_bets = len(subset)

        if wins + losses == 0:
            win_rate = 0.0
        else:
            win_rate = (wins / (wins + losses)) * 100

        # ROI (Assume -110 odds => bet 1.1 to win 1)
        profit = (wins * 0.90909) - losses
        risked = (wins + losses) * 1.1
        if risked == 0:
            roi = 0.0
        else:
            roi = (profit / risked) * 100

        print(
            f"{t:10.2f} {total_bets:6d} {wins:6d} {losses:6d} {win_rate:8.2f} {roi:8.2f}"
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment", required=True, help="Experiment name")
    parser.add_argument("--year", type=int, default=2024, help="Year")
    parser.add_argument("--target", default="spread", choices=["spread", "total"])
    args = parser.parse_args()

    base_dir = Path("artifacts/predictions") / args.experiment
    if not base_dir.exists():
        print(f"Error: Experiment directory not found: {base_dir}")
        return

    # Find latest run
    runs = sorted(
        [d for d in base_dir.iterdir() if d.is_dir()],
        key=lambda x: x.stat().st_mtime,
        reverse=True,
    )
    if not runs:
        print("Error: No runs found.")
        return

    latest_run = runs[0]
    csv_path = latest_run / f"{args.year}_predictions.csv"

    if not csv_path.exists():
        print(f"Error: Prediction file not found: {csv_path}")
        return

    # Load predictions
    print(f"Analyzing: {csv_path}")
    df = pd.read_csv(csv_path)

    # Load lines
    print("Loading betting lines...")
    lines_df = load_betting_lines(args.year)

    if lines_df.empty:
        print("Error: Could not load betting lines.")
        return

    # Merge
    # prediction CSV has 'id', lines_df has 'game_id'
    df = df.merge(lines_df, left_on="id", right_on="game_id", how="inner")

    # Rename for compatibility
    df = df.rename(
        columns={
            "home_team_spread_line": "spread_line",
            "prediction": "pred_spread" if args.target == "spread" else "pred_total",
            "actual": "actual_spread" if args.target == "spread" else "actual_total",
        }
    )

    # For totals, prediction is already total score?
    # In run_experiment, prediction is the model output.
    # For spread model: output is spread.
    # For total model: output is total score.

    analyze_thresholds(df, args.target)


if __name__ == "__main__":
    main()
