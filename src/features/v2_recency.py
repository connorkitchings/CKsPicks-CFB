import pandas as pd
from tqdm import tqdm

from src.config import get_data_root
from src.features.core import apply_iterative_opponent_adjustment
from src.utils.local_storage import LocalStorage


def _calculate_ewma(series, alpha):
    """
    Calculate Exponentially Weighted Moving Average.
    pandas ewm uses alpha=alpha, adjust=True/False.
    If adjust=True, uses weights (1-alpha)**i.
    """
    return series.ewm(alpha=alpha, min_periods=1).mean()


def _augment_with_style_metrics(df):
    # Simplified style metrics for on-the-fly generation
    # We can skip complex rolling windows for now or implement if critical
    # Just returning raw for speed, style metrics are usually secondary
    return df


def aggregate_team_season_ewma(team_game_df, alpha):
    """
    Aggregate team-game metrics using EWMA (Exponential Decay).
    """
    # Sort by date/week
    team_game_df = team_game_df.sort_values(["season", "week"])

    # Columns to aggregate (excluding identifiers)
    exclude_cols = [
        "season",
        "week",
        "game_id",
        "team",
        "opponent",
        "home_away",
        "date",
    ]
    metric_cols = [
        c
        for c in team_game_df.columns
        if c not in exclude_cols and pd.api.types.is_numeric_dtype(team_game_df[c])
    ]

    # helper for groupby apply
    def _apply_ewma(g):
        # We want the EWMA of *past* games at the start of the current week.
        # shift(1) means row[i] gets stats from 0..i-1
        # ewm().mean() calculates usage including current row.
        # So we ewm() then shift(1).

        # Note: We need to handle weeks. If a team plays multiple times (rare) or gaps.
        # Assuming one row per game per team.
        ewma = g[metric_cols].ewm(alpha=alpha, min_periods=1).mean().shift(1)
        ewma["season"] = g["season"]
        ewma["week"] = g["week"]
        ewma["team"] = g["team"]
        ewma["game_id"] = g["game_id"]  # Join key
        return ewma

    # Apply per team
    team_season = team_game_df.groupby(["season", "team"], group_keys=False).apply(
        _apply_ewma
    )

    # Drop first game (NaNs)
    team_season = team_season.dropna(subset=metric_cols, how="all")

    return team_season


def load_v2_recency_data(year, alpha=0.5, iterations=4):
    """
    Load raw team-game data, calculate EWMA stats, apply adjustment, and return training/test DF.
    """
    data_root = get_data_root()
    storage = LocalStorage(
        data_root=data_root, file_format="csv", data_type="processed"
    )

    # Load Team Game Data (Raw stats)
    # We need prior year data for early season continuity?
    # For now, let's just load the specific year. Cold start is a known issue.
    # To mitigate, maybe load year-1 and filter?
    # Let's simple start: load `year` data.
    records = storage.read_index("team_game", {"year": year})
    if not records:
        print(f"No team_game data for {year}")
        return None

    team_game_df = pd.DataFrame.from_records(records)

    # Calculate EWMA Unadjusted
    print(f"Calculating EWMA (alpha={alpha}) for {year}...")
    team_season = aggregate_team_season_ewma(team_game_df, alpha=alpha)

    # Ideally we'd augment style metrics here
    # team_season = _augment_with_style_metrics(team_season)

    # Opponent Adjustment
    # We need an iterator because `apply_iterative_opponent_adjustment`
    # expects a full season DF and prior_games_df.
    # But wait, `apply_iterative_opponent_adjustment` adjusts a SINGLE week based on PRIOR games.
    # We can batch this.

    print("Applying Opponent Adjustments (Iterative)...")
    weeks = sorted(team_season["week"].unique())
    adj_dfs = []

    for week in tqdm(weeks):
        # Stats entering this week
        current_week_stats = team_season[team_season["week"] == week]
        # Games played prior to this week (for opponent strength lookup)
        prior_games = team_game_df[team_game_df["week"] < week]

        if current_week_stats.empty:
            continue

        # Run adjustment
        adj_df = apply_iterative_opponent_adjustment(
            current_week_stats, prior_games, iterations=iterations
        )
        # Only keep the final iteration for training
        adj_df = adj_df[adj_df["iteration"] == iterations]
        adj_dfs.append(adj_df)

    full_adj_df = pd.concat(adj_dfs, ignore_index=True)

    # Merge with Targets (Merge Home/Away for training)
    # Re-use v1_pipeline merge logic or implement simpler one here
    return _merge_for_training(full_adj_df, year)


def _merge_for_training(team_stats, year):
    # Load Games (Targets)
    data_root = get_data_root()
    raw_storage = LocalStorage(data_root=data_root, file_format="csv", data_type="raw")
    games = raw_storage.read_index("games", {"year": year})
    games_df = pd.DataFrame(games)

    if "id" in games_df.columns:
        games_df = games_df.rename(columns={"id": "game_id"})

    # Betting Lines
    betting = raw_storage.read_index("betting_lines", {"year": year})
    if betting:
        betting_df = pd.DataFrame(betting)
        if "id" in betting_df.columns:
            betting_df = betting_df.rename(columns={"id": "game_id"})
        # Take mean line
        betting_df = (
            betting_df.groupby("game_id")
            .agg({"spread": "mean", "over_under": "mean"})
            .reset_index()
            .rename(columns={"spread": "spread_line", "over_under": "total_line"})
        )
        games_df = games_df.merge(betting_df, on="game_id", how="left")

    # Merge Home/Away Stats
    # team_stats has 'team' column.
    # games_df has 'home_team', 'away_team'.
    # Join on game_id is cleaner.

    # But team_stats keys are (game_id, team).
    # team_stats contains the stats *entering* the game_id.

    # NOTE: home_stats rename was unused - the merge below uses team_stats directly
    # and renames columns via the merge's suffixes and the rename_map at the end
    # Remove team name from merge key if present, but we need to match home_team?
    # Actually, if we merge on game_id and team, we need to know who is home.
    # Better:
    # 1. Merge game_df with home_stats on (game_id, home_team)
    # 2. Merge with away_stats on (game_id, away_team)

    # Need 'team' column in home_stats matching 'home_team' in games

    # Normalize names function might be needed? assuming IDs/Names align from ingestion

    # Filter valid games
    games_df = games_df[games_df["completed"]]

    # Prepare stats
    # team_stats has 'team'.

    merged = games_df.merge(
        team_stats.rename(columns={"team": "home_team"}),
        on=["game_id", "home_team"],
        how="inner",
        suffixes=("", "_home_stats"),
    )

    merged = merged.merge(
        team_stats.rename(columns={"team": "away_team"}),
        on=["game_id", "away_team"],
        how="inner",
        suffixes=("", "_away"),
    )

    # Rename collisions
    # The suffixes above handle it mostly.
    # features will be columns in team_stats.

    # Calculate Target
    merged["spread_target"] = merged["home_points"] - merged["away_points"]
    merged["total_target"] = merged["home_points"] + merged["away_points"]

    # Prefix features
    feature_cols = [
        c for c in team_stats.columns if c not in ["game_id", "season", "week", "team"]
    ]

    # Rename correctly
    # Above merge creates: {col} (for home) and {col}_away (for away).
    # We want home_{col} and away_{col}.

    rename_map = {}
    for c in feature_cols:
        rename_map[c] = f"home_{c}"
        rename_map[f"{c}_away"] = f"away_{c}"

    merged = merged.rename(columns=rename_map)

    return merged
