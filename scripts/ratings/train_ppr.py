import argparse
import os
import sys

import arviz as az
import pandas as pd
import pymc as pm

# Add project root to path
sys.path.append(os.getcwd())
# noqa: E402
from src.config import ARTIFACTS_DIR, DATA_ROOT


def load_data(year: int) -> pd.DataFrame:
    """Load game data for a specific year."""
    # The data is partitioned: raw/games/year=2024/data.csv
    # DATA_ROOT is imported from src.config
    raw_games_dir = DATA_ROOT / "raw" / "games" / f"year={year}"
    csv_path = raw_games_dir / "data.csv"

    if csv_path.exists():
        try:
            df = pd.read_csv(csv_path)

            # Ensure columns exist
            req_cols = [
                "home_team",
                "away_team",
                "home_points",
                "away_points",
                "neutral_site",
                "week",
                "start_date",
            ]
            if not all(c in df.columns for c in req_cols):
                # Check if columns are present but maybe different case or missing
                missing = [c for c in req_cols if c not in df.columns]
                raise ValueError(f"Missing columns in {csv_path}: {missing}")

            # Filter to completed games
            df = df.dropna(subset=["home_points", "away_points"])

            # Filter for FBS vs FBS games only
            if (
                "home_classification" in df.columns
                and "away_classification" in df.columns
            ):
                print(f"Filtering for FBS vs FBS games. Before: {len(df)}")
                df = df[
                    (df["home_classification"] == "fbs")
                    & (df["away_classification"] == "fbs")
                ]
                print(f"After FBS filter: {len(df)}")
            else:
                print(
                    "Warning: 'home_classification' or 'away_classification' columns missing. Skipping FBS filter."
                )

            # Sort by date/week
            df = df.sort_values(["week", "start_date"])
            return df
        except Exception as e:
            print(f"Failed to read CSV from {csv_path}: {e}")
            pass

    raise FileNotFoundError(f"Could not find game data for {year} at {csv_path}")


def train_model(
    df: pd.DataFrame,
    year: int,
    draws: int = 1000,
    tune: int = 1000,
    sigma_drift_prior: float = 1.0,
    hfa_mu_prior: float = 2.5,
):
    """Train a dynamic Bayesian Hierarchical Model (Gaussian Random Walk)."""

    # Prepare data
    teams = sorted(list(set(df["home_team"]).union(set(df["away_team"]))))
    team_map = {team: i for i, team in enumerate(teams)}

    # Map weeks to 0..T-1
    min_week = df["week"].min()
    max_week = df["week"].max()
    weeks = list(range(min_week, max_week + 1))
    week_map = {w: i for i, w in enumerate(weeks)}
    n_weeks = len(weeks)

    home_idx = df["home_team"].map(team_map).values
    away_idx = df["away_team"].map(team_map).values
    week_idx = df["week"].map(week_map).values

    # Score differential: Home - Away
    score_diff = df["home_points"].values - df["away_points"].values

    # Neutral site adjustment
    is_neutral = df["neutral_site"].astype(int).values
    not_neutral = 1 - is_neutral

    coords = {"team": teams, "match": df.index, "week": weeks}

    print(
        f"Training Dynamic PPR model for {year} with {len(teams)} teams, {n_weeks} weeks, and {len(df)} games..."
    )

    with pm.Model(coords=coords) as model:
        # Hyperparameters
        # Initial rating distribution
        sigma_rating_init = pm.HalfNormal("sigma_rating_init", sigma=10)

        # Random walk drift (volatility)
        sigma_drift = pm.HalfNormal("sigma_drift", sigma=sigma_drift_prior)

        # Dynamic Ratings: (n_weeks, n_teams)
        # We use a Gaussian Random Walk across weeks for each team
        # init_dist defines the distribution at t=0
        ratings = pm.GaussianRandomWalk(
            "ratings",
            sigma=sigma_drift,
            init_dist=pm.Normal.dist(0, sigma_rating_init),
            dims=("week", "team"),
        )

        # Home Field Advantage (static for now, could be dynamic)
        hfa = pm.Normal("hfa", mu=hfa_mu_prior, sigma=1)

        # Model error
        sigma_score = pm.HalfNormal("sigma_score", sigma=10)
        nu_score = pm.Gamma("nu_score", alpha=2, beta=0.1)

        # Expected score differential
        # ratings is (n_weeks, n_teams)
        # We index by [week_idx, team_idx]
        mu_diff = (
            ratings[week_idx, home_idx]
            - ratings[week_idx, away_idx]
            + hfa * not_neutral
        )

        # Likelihood
        pm.StudentT(
            "diff_obs",
            nu=nu_score,
            mu=mu_diff,
            sigma=sigma_score,
            observed=score_diff,
            dims="match",
        )

        # Sampling
        trace = pm.sample(draws=draws, tune=tune, chains=2, target_accept=0.9)

    return model, trace, teams, weeks


def save_artifacts(trace, teams, weeks, year):
    """Save the trace and team ratings."""
    output_dir = ARTIFACTS_DIR / "ratings" / str(year)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save trace
    trace_path = output_dir / "trace.nc"
    az.to_netcdf(trace, trace_path)
    print(f"Saved trace to {trace_path}")

    # Extract mean ratings for the FINAL week
    post = trace.posterior
    # ratings shape: (chain, draw, week, team)

    # Get ratings for the last week
    last_week_idx = len(weeks) - 1
    final_ratings = post["ratings"].isel(week=last_week_idx)

    mean_ratings = final_ratings.mean(dim=["chain", "draw"]).values
    hdi_lower = final_ratings.quantile(0.025, dim=["chain", "draw"]).values
    hdi_upper = final_ratings.quantile(0.975, dim=["chain", "draw"]).values

    ratings_df = pd.DataFrame(index=teams)
    ratings_df["rating"] = mean_ratings
    ratings_df["hdi_lower"] = hdi_lower
    ratings_df["hdi_upper"] = hdi_upper
    ratings_df = ratings_df.sort_values("rating", ascending=False)

    csv_path = output_dir / "team_ratings.csv"
    ratings_df.to_csv(csv_path)
    print(f"Saved final ratings to {csv_path}")

    # Print top 10
    print("\nTop 10 Teams (Final Week):")
    print(ratings_df.head(10))

    # Print HFA
    mean_hfa = post["hfa"].mean().item()
    print(f"\nEstimated Home Field Advantage: {mean_hfa:.2f} points")

    # Save full history
    # We want a CSV with: team, week, rating, hdi_lower, hdi_upper
    history_rows = []
    mean_ratings_all = (
        post["ratings"].mean(dim=["chain", "draw"]).values
    )  # (week, team)

    for w_idx, week in enumerate(weeks):
        for t_idx, team in enumerate(teams):
            history_rows.append(
                {"week": week, "team": team, "rating": mean_ratings_all[w_idx, t_idx]}
            )

    history_df = pd.DataFrame(history_rows)
    history_path = output_dir / "ratings_history.csv"
    history_df.to_csv(history_path, index=False)
    print(f"Saved ratings history to {history_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Train Probabilistic Power Ratings (PPR) model."
    )
    parser.add_argument(
        "--year", type=int, required=True, help="Season year to train on."
    )
    parser.add_argument("--draws", type=int, default=1000, help="Number of MCMC draws.")
    parser.add_argument(
        "--tune", type=int, default=1000, help="Number of tuning steps."
    )
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

    try:
        df = load_data(args.year)
        model, trace, teams, weeks = train_model(
            df,
            args.year,
            args.draws,
            args.tune,
            sigma_drift_prior=args.sigma_drift_prior,
            hfa_mu_prior=args.hfa_mu_prior,
        )
        save_artifacts(trace, teams, weeks, args.year)

    except Exception as e:
        print(f"Error: {e}")
        # Print full traceback for debugging
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
