"""Pre-aggregation pipeline orchestration.

Runs the full chain: plays → byplay → drives → team-game → team-season and
adds simple derived signals used in modeling/reporting.
"""

from __future__ import annotations

import pandas as pd

from .byplay import allplays_to_byplay
from .core import aggregate_drives, aggregate_team_game, aggregate_team_season
from .situational import merge_situational_features
from .weather import merge_weather_features


def calculate_luck_factor(
    team_game_df: pd.DataFrame, byplay_df: pd.DataFrame
) -> pd.DataFrame:
    """Calculate luck factor as actual margin minus expected margin from PPA."""
    # For MVP, we'll add a simple placeholder luck factor
    # In the future, this could compare actual vs expected score based on PPA
    team_game_df = team_game_df.copy()
    team_game_df["luck_factor"] = 0.0  # Placeholder for now
    return team_game_df


def build_preaggregation_pipeline(
    plays_raw_df: pd.DataFrame,
    games_df: pd.DataFrame | None = None,
    teams_df: pd.DataFrame | None = None,
    venues_df: pd.DataFrame | None = None,
    weather_df: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Run plays → byplay → drives → team-game → team-season pipeline.

    Args:
        plays_raw_df: Raw plays DataFrame containing at minimum season and week.
            If season is missing but a constant year column exists, season is derived.
        games_df: Optional DataFrame containing raw game data for situational features.
        teams_df: Optional DataFrame containing raw team data for situational features.
        venues_df: Optional DataFrame containing raw venue data for situational features.
        weather_df: Optional DataFrame containing game-level weather data.

    Returns:
        Tuple of (byplay_df, drives_df, team_game_df, team_season_df), suitable for
        persistence or downstream modeling features.

    Raises:
        ValueError: If season/week cannot be determined on inputs.
    """
    if "season" not in plays_raw_df.columns:
        if "year" in plays_raw_df.columns and plays_raw_df["year"].nunique() == 1:
            plays_raw_df["season"] = plays_raw_df["year"]
        else:
            raise ValueError(
                "Input DataFrame to pipeline is missing required 'season' column."
            )

    if "week" not in plays_raw_df.columns:
        # The 'week' column is essential for partitioning and aggregations.
        # Unlike 'season', it's harder to infer, so we fail if it's missing.
        raise ValueError(
            "Input DataFrame to pipeline is missing required 'week' column."
        )

    byplay = allplays_to_byplay(plays_raw_df)
    drives = aggregate_drives(byplay)
    if "season" not in drives.columns or "week" not in drives.columns:
        drives = drives.merge(
            byplay[["game_id", "season", "week"]].drop_duplicates(),
            on="game_id",
            how="left",
        )
    team_game = aggregate_team_game(byplay, drives)

    # Merge situational features if available
    if games_df is not None and not games_df.empty:
        team_game = merge_situational_features(
            team_game, games_df, teams_df, venues_df
        )

    # Merge weather features if available
    if weather_df is not None:
        team_game = merge_weather_features(team_game, weather_df)

    # Add simple luck factor calculation if needed
    team_game = calculate_luck_factor(team_game, byplay)
    team_season = aggregate_team_season(team_game)
    return byplay, drives, team_game, team_season
