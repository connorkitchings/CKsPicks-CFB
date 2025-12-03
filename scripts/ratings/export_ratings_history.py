import os
import sys

import pandas as pd

# Add project root to path
sys.path.append(os.getcwd())

from src.config import ARTIFACTS_DIR


def export_ratings():
    """
    Reads all backtest CSVs from artifacts/backtest/ppr/
    and consolidates them into a single parquet file for feature injection.

    Output Schema:
    - year: int
    - week: int
    - team: str
    - ppr_rating: float
    """
    output_path = ARTIFACTS_DIR / "features" / "ppr_ratings.parquet"

    # Define years to process (could be dynamic, but explicit is safer for now)
    years = [2019, 2021, 2022, 2023, 2024, 2025]
    all_ratings = []

    for year in years:
        history_path = ARTIFACTS_DIR / "ratings" / str(year) / "ratings_history.csv"
        if not history_path.exists():
            print(f"Warning: No ratings history found for {year} at {history_path}")
            continue

        print(f"Processing {year} from {history_path}...")
        df = pd.read_csv(history_path)

        # Schema: week, team, rating
        # We need: year, week, team, ppr_rating

        df["year"] = year
        df = df.rename(columns={"rating": "ppr_rating"})

        # Select columns
        df = df[["year", "week", "team", "ppr_rating"]]

        all_ratings.append(df)

    if not all_ratings:
        print("No ratings extracted.")
        return

    final_df = pd.concat(all_ratings, ignore_index=True)

    # --- Handle Bye Weeks (Forward Fill) ---
    # 1. Create full grid of year/week/team
    years = final_df["year"].unique()
    dfs = []

    for y in years:
        year_df = final_df[final_df["year"] == y].copy()
        teams = year_df["team"].unique()
        # Extend weeks to cover postseason (up to 16)
        max_week = max(year_df["week"].max(), 16)
        weeks = range(year_df["week"].min(), max_week + 1)

        # Create MultiIndex grid
        idx = pd.MultiIndex.from_product([weeks, teams], names=["week", "team"])
        grid = pd.DataFrame(index=idx).reset_index()
        grid["year"] = y

        # Merge with actual ratings
        merged = grid.merge(year_df, on=["year", "week", "team"], how="left")

        # Sort for filling
        merged = merged.sort_values(["team", "week"])

        # Forward fill ratings per team
        merged["ppr_rating"] = merged.groupby("team")["ppr_rating"].ffill()

        # Fill remaining NaNs (start of season) with 0.0 (prior mean)
        merged["ppr_rating"] = merged["ppr_rating"].fillna(0.0)

        dfs.append(merged)

    final_df = pd.concat(dfs, ignore_index=True)

    # Sort
    final_df = final_df.sort_values(["year", "week", "team"])

    # Save
    final_df.to_parquet(output_path, index=False)
    print(
        f"Successfully exported {len(final_df)} ratings to {output_path} (with forward fill)"
    )
    print(final_df.head())


if __name__ == "__main__":
    export_ratings()
