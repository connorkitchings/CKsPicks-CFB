import argparse
import os
import sys

import numpy as np
import pandas as pd

# Add project root to path
sys.path.append(os.getcwd())
# noqa: E402
from scripts.ratings.train_ppr import load_data, train_model
from src.config import ARTIFACTS_DIR


def run_backtest(
    year: int,
    start_week: int,
    end_week: int,
    draws: int,
    tune: int,
    sigma_drift_prior: float = 1.0,
    hfa_mu_prior: float = 2.5,
):
    """Run walk-forward validation for a specific year."""
    print(f"Starting backtest for {year}, weeks {start_week}-{end_week}")

    try:
        df = load_data(year)
    except FileNotFoundError:
        print(f"Data for {year} not found. Skipping.")
        return

    results = []

    for week in range(start_week, end_week + 1):
        print(f"\n--- Processing Week {week} ---")

        # 1. Train on data BEFORE this week
        train_df = df[df["week"] < week]
        test_df = df[df["week"] == week]

        if train_df.empty:
            print("No training data available. Skipping.")
            continue

        if test_df.empty:
            print("No games this week. Skipping.")
            continue

        # Train model
        # We use fewer draws for backtesting speed if needed, but ideally should be enough for convergence
        try:
            model, trace, teams, weeks = train_model(
                train_df,
                year,
                draws=draws,
                tune=tune,
                sigma_drift_prior=sigma_drift_prior,
                hfa_mu_prior=hfa_mu_prior,
            )
        except Exception as e:
            print(f"Training failed for week {week}: {e}")
            continue

        # 2. Extract ratings from the LAST week of training data
        # The model learns ratings for weeks present in train_df
        # The prediction for 'week' (current) is based on the rating at 'week-1' (last training week)
        # Random Walk assumption: E[r_t | r_{t-1}] = r_{t-1}

        post = trace.posterior
        last_train_week_idx = len(weeks) - 1

        # Shape: (chain, draw, team)
        current_ratings = post["ratings"].isel(week=last_train_week_idx)
        mean_ratings = current_ratings.mean(dim=["chain", "draw"]).values

        # HFA
        mean_hfa = post["hfa"].mean().item()

        # Create a lookup for ratings
        rating_map = {team: r for team, r in zip(teams, mean_ratings)}

        # 3. Predict games in test_df
        for _, row in test_df.iterrows():
            home = row["home_team"]
            away = row["away_team"]
            neutral = row["neutral_site"]

            # If a team is new (not in training set), we assume 0.0 rating (prior mean)
            r_home = rating_map.get(home, 0.0)
            r_away = rating_map.get(away, 0.0)

            # Prediction
            # diff = home - away
            pred_diff = r_home - r_away + (mean_hfa if not neutral else 0.0)
            actual_diff = row["home_points"] - row["away_points"]

            results.append(
                {
                    "year": year,
                    "week": week,
                    "home_team": home,
                    "away_team": away,
                    "pred_diff": pred_diff,
                    "actual_diff": actual_diff,
                    "error": pred_diff - actual_diff,
                    "abs_error": abs(pred_diff - actual_diff),
                    "home_rating": r_home,
                    "away_rating": r_away,
                    "hfa": mean_hfa,
                }
            )

    # Save results
    if results:
        results_df = pd.DataFrame(results)
        output_dir = ARTIFACTS_DIR / "backtest" / "ppr"
        output_dir.mkdir(parents=True, exist_ok=True)

        csv_path = output_dir / f"backtest_{year}.csv"
        results_df.to_csv(csv_path, index=False)

        # Calculate metrics
        rmse = np.sqrt((results_df["error"] ** 2).mean())
        mae = results_df["abs_error"].mean()

        # Accuracy (sign match)
        # If pred > 0 (Home wins) and actual > 0, or pred < 0 and actual < 0
        correct = (
            (results_df["pred_diff"] > 0) == (results_df["actual_diff"] > 0)
        ).mean()

        print(f"\nBacktest Complete for {year}")
        print(f"RMSE: {rmse:.4f}")
        print(f"MAE: {mae:.4f}")
        print(f"Win Accuracy: {correct:.4f}")
        print(f"Results saved to {csv_path}")
    else:
        print("No results generated.")


def main():
    parser = argparse.ArgumentParser(description="Backtest PPR model.")
    parser.add_argument("--year", type=int, required=True, help="Year to backtest")
    parser.add_argument("--start_week", type=int, default=2, help="Start week")
    parser.add_argument("--end_week", type=int, default=15, help="End week")
    parser.add_argument("--draws", type=int, default=500, help="MCMC draws")
    parser.add_argument("--tune", type=int, default=500, help="MCMC tune")
    parser.add_argument(
        "--sigma_drift_prior",
        type=float,
        default=1.0,
        help="Prior sigma for random walk drift.",
    )
    parser.add_argument(
        "--hfa_mu_prior",
        type=float,
        default=2.5,
        help="Prior mean for Home Field Advantage.",
    )

    args = parser.parse_args()

    run_backtest(
        args.year,
        args.start_week,
        args.end_week,
        args.draws,
        args.tune,
        args.sigma_drift_prior,
        args.hfa_mu_prior,
    )


if __name__ == "__main__":
    main()
