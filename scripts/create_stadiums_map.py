from pathlib import Path

import pandas as pd


def main():
    data_root = Path("./data")
    venues_path = data_root / "raw/venues/year=2024/data.csv"
    output_path = data_root / "stadiums.csv"

    print(f"Reading venues from {venues_path}...")
    # Read CSV file
    df = pd.read_csv(venues_path)

    # Select relevant columns
    cols = [
        "id",
        "name",
        "city",
        "state",
        "latitude",
        "longitude",
        "timezone",
        "elevation",
        "dome",
    ]

    # Filter to columns that exist
    cols = [c for c in cols if c in df.columns]

    stadiums = df[cols].copy()

    # Drop rows without lat/lon
    stadiums = stadiums.dropna(subset=["latitude", "longitude"])

    # Deduplicate by ID
    stadiums = stadiums.drop_duplicates(subset=["id"])

    print(f"Found {len(stadiums)} unique stadiums with coordinates.")

    # Save to CSV
    stadiums.to_csv(output_path, index=False)
    print(f"Saved stadium map to {output_path}")


if __name__ == "__main__":
    main()
