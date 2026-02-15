import sys
from pathlib import Path

sys.path.append(str(Path.cwd()))
from cks_picks_cfb.config import get_data_root  # noqa: E402
from cks_picks_cfb.models.features import load_point_in_time_data  # noqa: E402


def main():
    # Load a sample week
    df = load_point_in_time_data(2023, 10, get_data_root(), adjustment_iteration=2)
    if df is None:
        print("No data found")
        return

    print("Columns:", df.columns.tolist())

    # Check for spread/line columns
    potential_cols = [
        c for c in df.columns if "spread" in c or "line" in c or "odds" in c
    ]
    print("\nPotential Line Columns:", potential_cols)

    # Check if we have what we need
    # We need the market spread to calculate residual = (Home - Away) - MarketSpread
    # Usually 'spread' in CFBD data is the market spread.

    if "spread" in df.columns:
        print("\n'spread' column found. Sample values:")
        print(
            df[
                ["home_team", "away_team", "home_points", "away_points", "spread"]
            ].head()
        )


if __name__ == "__main__":
    main()
