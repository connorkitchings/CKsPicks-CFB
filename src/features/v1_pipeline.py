import pandas as pd

from src.config import get_data_root
from src.utils.local_storage import LocalStorage


def load_v1_data(year: int, features: list[str] | None = None):
    """
    Load raw game data and team stats for a given year.
    Returns a merged DataFrame with home/away features and targets.

    Args:
        year: Season to load
        features: List of feature names (e.g., ['home_off_epa_pp', ...]).
                  If None, defaults to legacy adj_ features.
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

    # Standardize game_id column
    if "id" in games_df.columns and "game_id" not in games_df.columns:
        games_df = games_df.rename(columns={"id": "game_id"})

    # Filter for completed games only (Data Quality)
    if "completed" in games_df.columns:
        games_df = games_df[games_df["completed"]]

    # Also ensure scores are present (redundant but safe)
    if "home_points" in games_df.columns and "away_points" in games_df.columns:
        games_df = games_df.dropna(subset=["home_points", "away_points"])

    # Ensure week is int for merging
    if "week" in games_df.columns:
        games_df["week"] = games_df["week"].astype(int)

    # Load Betting Lines (to get spread_line for evaluation)
    betting = raw_storage.read_index("betting_lines", {"year": year})
    if betting:
        bet_df = pd.DataFrame(betting)
        # Deduplicate: prefer Bovada, then Consensus, then whatever
        # We can sort by provider priority
        if "provider" in bet_df.columns:
            provider_priority = {"Bovada": 1, "Consensus": 2}
            bet_df["priority"] = bet_df["provider"].map(provider_priority).fillna(99)
            bet_df = bet_df.sort_values("priority").drop_duplicates(subset=["game_id"])
        else:
            bet_df = bet_df.drop_duplicates(subset=["game_id"])

        if "spread" in bet_df.columns:
            bet_df = bet_df.rename(columns={"spread": "spread_line"})
        if "over_under" in bet_df.columns:
            bet_df = bet_df.rename(columns={"over_under": "total_line"})

        games_df = games_df.merge(
            bet_df[["game_id", "spread_line", "total_line"]], on="game_id", how="left"
        )
    else:
        print(f"Warning: No betting lines found for {year}")

    # Load Team Stats (Point-in-Time)
    # We use 'team_week_adj' which contains PIT stats (both raw and adjusted)
    # Note: 'team_week_adj' is partitioned by year and week.
    # We'll load all weeks for the year.
    team_stats = processed_storage.read_index("team_week_adj", {"year": year})
    if not team_stats:
        print(f"No team stats found for {year}")
        return None
    stats_df = pd.DataFrame(team_stats)

    if "week" in stats_df.columns:
        stats_df["week"] = stats_df["week"].astype(int)

    # Determine columns to keep
    if features:
        # Extract base columns (e.g. 'home_off_epa_pp' -> 'off_epa_pp')
        base_cols = set()
        for f in features:
            if f.startswith("home_"):
                base_cols.add(f.replace("home_", ""))
            elif f.startswith("away_"):
                base_cols.add(f.replace("away_", ""))

        # Add required keys for merging
        cols_to_keep = ["season", "team", "week"] + list(base_cols)

        # Filter available columns only
        available_cols = [c for c in cols_to_keep if c in stats_df.columns]
        missing_cols = set(cols_to_keep) - set(available_cols)
        if missing_cols:
            print(f"Warning: Missing columns in stats: {missing_cols}")

        stats_df = stats_df[available_cols]
    else:
        # Legacy fallback (Phase 1 default if no config)
        cols_to_keep = [
            "season",
            "team",
            "week",
            "adj_off_epa_pp",
            "adj_def_epa_pp",
            "adj_off_sr",
            "adj_def_sr",
        ]
        available_cols = [c for c in cols_to_keep if c in stats_df.columns]
        stats_df = stats_df[available_cols]

    # Merge Home
    # Match game week with stats week (PIT)
    merged = games_df.merge(
        stats_df.add_prefix("home_"),
        left_on=["season", "week", "home_team"],
        right_on=["home_season", "home_week", "home_team"],
        how="inner",
    )

    # Merge Away
    merged = merged.merge(
        stats_df.add_prefix("away_"),
        left_on=["season", "week", "away_team"],
        right_on=["away_season", "away_week", "away_team"],
        how="inner",
    )

    # Calculate Target (Home - Away Score)
    merged["spread_target"] = merged["home_points"].astype(float) - merged[
        "away_points"
    ].astype(float)
    merged["total_target"] = merged["home_points"].astype(float) + merged[
        "away_points"
    ].astype(float)

    # Drop rows with missing targets
    merged = merged.dropna(subset=["spread_target"])

    return merged
