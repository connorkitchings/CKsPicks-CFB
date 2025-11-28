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
            ]
            if not all(c in df.columns for c in req_cols):
                # Check if columns are present but maybe different case or missing
                missing = [c for c in req_cols if c not in df.columns]
                raise ValueError(f"Missing columns in {csv_path}: {missing}")

            # Filter to completed games
            df = df.dropna(subset=["home_points", "away_points"])
            return df
        except Exception as e:
            print(f"Failed to read CSV from {csv_path}: {e}")
            pass

    raise FileNotFoundError(f"Could not find game data for {year} at {csv_path}")


def train_model(df: pd.DataFrame, year: int, draws: int = 1000, tune: int = 1000):
    """Train a static Bayesian Hierarchical Model."""

    # Prepare data
    teams = sorted(list(set(df["home_team"]).union(set(df["away_team"]))))
    team_map = {team: i for i, team in enumerate(teams)}

    home_idx = df["home_team"].map(team_map).values
    away_idx = df["away_team"].map(team_map).values

    # Score differential: Home - Away
    score_diff = df["home_points"].values - df["away_points"].values

    # Neutral site adjustment: 1 if neutral, 0 otherwise
    # If neutral, home field advantage should be 0 (or reduced)
    # We'll model HFA as a parameter, multiplied by (1 - neutral_site)
    is_neutral = df["neutral_site"].astype(int).values
    not_neutral = 1 - is_neutral

    coords = {"team": teams, "match": df.index}

    print(
        f"Training PPR model for {year} with {len(teams)} teams and {len(df)} games..."
    )

    with pm.Model(coords=coords) as model:
        # Hyperparameters for team ratings
        # Global rating mean (should be 0) and sd
        mu_rating = pm.Normal("mu_rating", mu=0, sigma=1)
        sigma_rating = pm.HalfNormal("sigma_rating", sigma=10)

        # Team ratings (centered parameterization for now)
        ratings = pm.Normal("ratings", mu=mu_rating, sigma=sigma_rating, dims="team")

        # Home Field Advantage
        hfa = pm.Normal("hfa", mu=2.5, sigma=1)

        # Model error (Student T for robust regression)
        sigma_score = pm.HalfNormal("sigma_score", sigma=10)
        nu_score = pm.Gamma("nu_score", alpha=2, beta=0.1)

        # Expected score differential
        # diff = rating_home - rating_away + hfa * not_neutral
        mu_diff = ratings[home_idx] - ratings[away_idx] + hfa * not_neutral

        # Likelihood
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

    return model, trace, teams


def save_artifacts(trace, teams, year):
    """Save the trace and team ratings."""
    output_dir = ARTIFACTS_DIR / "ratings" / str(year)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save trace
    trace_path = output_dir / "trace.nc"
    az.to_netcdf(trace, trace_path)
    print(f"Saved trace to {trace_path}")

    # Extract mean ratings
    # Extract mean ratings
    # summary = az.summary(trace, var_names=["ratings", "hfa"], hdi_prob=0.95)

    # Map back to team names
    # summary index for ratings is ratings[TeamName] or ratings[0] depending on arviz version/dims
    # With dims="team", it usually uses the coord names if available.
    # Let's check if index contains team names or indices.

    # Create a clean DataFrame
    ratings_df = pd.DataFrame(index=teams)

    # Extract means from posterior
    post = trace.posterior
    mean_ratings = post["ratings"].mean(dim=["chain", "draw"]).values
    hdi_lower = post["ratings"].quantile(0.025, dim=["chain", "draw"]).values
    hdi_upper = post["ratings"].quantile(0.975, dim=["chain", "draw"]).values

    ratings_df["rating"] = mean_ratings
    ratings_df["hdi_lower"] = hdi_lower
    ratings_df["hdi_upper"] = hdi_upper
    ratings_df = ratings_df.sort_values("rating", ascending=False)

    csv_path = output_dir / "team_ratings.csv"
    ratings_df.to_csv(csv_path)
    print(f"Saved ratings to {csv_path}")

    # Print top 10
    print("\nTop 10 Teams:")
    print(ratings_df.head(10))

    # Print HFA
    mean_hfa = post["hfa"].mean().item()
    print(f"\nEstimated Home Field Advantage: {mean_hfa:.2f} points")


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

    args = parser.parse_args()

    try:
        df = load_data(args.year)
        model, trace, teams = train_model(df, args.year, args.draws, args.tune)
        save_artifacts(trace, teams, args.year)

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
