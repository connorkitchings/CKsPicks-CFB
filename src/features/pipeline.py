"""Pre-aggregation pipeline orchestration.

Runs the full chain: plays → byplay → drives → team-game → team-season and
adds simple derived signals used in modeling/reporting.
"""

from __future__ import annotations

import pandas as pd

from .byplay import allplays_to_byplay
from .core import aggregate_drives, aggregate_team_game, aggregate_team_season


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
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Run plays → byplay → drives → team-game → team-season pipeline.

    Args:
        plays_raw_df: Raw plays DataFrame containing at minimum season and week.
            If season is missing but a constant year column exists, season is derived.

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
    # Add simple luck factor calculation if needed
    team_game = calculate_luck_factor(team_game, byplay)
    team_season = aggregate_team_season(team_game)
    return byplay, drives, team_game, team_season
