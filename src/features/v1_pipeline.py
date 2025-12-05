import pandas as pd

from src.config import get_data_root
from src.utils.local_storage import LocalStorage


def load_v1_data(year: int):
    """
    Load raw game data and team season stats for a given year.
    Returns a merged DataFrame with home/away features and targets.
    """
    data_root = get_data_root()
    raw_storage = LocalStorage(data_root=data_root, file_format="csv", data_type="raw")
    processed_storage = LocalStorage(
        data_root=data_root, file_format="csv", data_type="processed"
    )

    # Load Games
    games = raw_storage.read_index("games", {"year": year})
    if not games:
        print(f"No games found for {year}")
        return None
    games_df = pd.DataFrame(games)

    # Load Team Season Stats (Adjusted or Raw)
    # For v1 baseline, we'll use the 'team_season_adj' which contains EPA/SR
    team_stats = processed_storage.read_index("team_season_adj", {"year": year})
    if not team_stats:
        print(f"No team stats found for {year}")
        return None
    stats_df = pd.DataFrame(team_stats)

    # Select only baseline features
    cols_to_keep = [
        "season",
        "team",
        "adj_off_epa_pp",
        "adj_def_epa_pp",
        "adj_off_sr",
        "adj_def_sr",
    ]
    # Check if columns exist
    available_cols = [c for c in cols_to_keep if c in stats_df.columns]
    stats_df = stats_df[available_cols]

    # Merge Home
    merged = games_df.merge(
        stats_df.add_prefix("home_"),
        left_on=["season", "home_team"],
        right_on=["home_season", "home_team"],
        how="inner",
    )

    # Merge Away
    merged = merged.merge(
        stats_df.add_prefix("away_"),
        left_on=["season", "away_team"],
        right_on=["away_season", "away_team"],
        how="inner",
    )

    # Calculate Target (Home - Away Score)
    merged["spread_target"] = merged["home_points"].astype(float) - merged[
        "away_points"
    ].astype(float)

    # Drop rows with missing targets
    merged = merged.dropna(subset=["spread_target"])

    return merged
