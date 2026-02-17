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
    """Calculate turnover luck factor (turnovers gained minus turnovers lost).

    Fumble recoveries are roughly 50/50 by chance, so net turnover margin
    is a meaningful proxy for game-level luck. Positive values indicate
    the team benefited from turnover luck.
    """
    team_game_df = team_game_df.copy()
    if "turnover" not in byplay_df.columns:
        team_game_df["luck_factor"] = 0.0
        return team_game_df

    if "luck_factor" in team_game_df.columns:
        team_game_df = team_game_df.drop(columns=["luck_factor"])

    off_to = (
        byplay_df.groupby(["game_id", "offense"])["turnover"]
        .sum()
        .reset_index()
        .rename(columns={"offense": "team", "turnover": "turnovers_lost"})
    )
    def_to = (
        byplay_df.groupby(["game_id", "defense"])["turnover"]
        .sum()
        .reset_index()
        .rename(columns={"defense": "team", "turnover": "turnovers_gained"})
    )
    luck = off_to.merge(def_to, on=["game_id", "team"], how="outer").fillna(0)
    luck["luck_factor"] = luck["turnovers_gained"] - luck["turnovers_lost"]

    team_game_df = team_game_df.merge(
        luck[["game_id", "team", "luck_factor"]],
        on=["game_id", "team"],
        how="left",
    )
    team_game_df["luck_factor"] = team_game_df["luck_factor"].fillna(0)
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
        team_game = merge_situational_features(team_game, games_df, teams_df, venues_df)

    # Merge weather features if available
    if weather_df is not None:
        team_game = merge_weather_features(team_game, weather_df)

    # Add simple luck factor calculation if needed
    team_game = calculate_luck_factor(team_game, byplay)
    team_season = aggregate_team_season(team_game)
    return byplay, drives, team_game, team_season
