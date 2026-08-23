"""Pure, kickoff-ordered EWMA team-season aggregation."""

from __future__ import annotations

import pandas as pd


def _calculate_ewma(series: pd.Series, alpha: float) -> pd.Series:
    """Calculate an exponentially weighted moving average."""
    return series.ewm(alpha=alpha, min_periods=1).mean()


def aggregate_team_season_ewma(
    team_game_df: pd.DataFrame, alpha: float
) -> pd.DataFrame:
    """Aggregate team-game metrics using prior-game EWMA values only."""
    team_game_df = team_game_df.copy()
    date_column = next(
        (
            column
            for column in ("kickoff_utc", "start_date", "date")
            if column in team_game_df
        ),
        None,
    )
    sort_columns = ["season", "team"]
    if date_column:
        team_game_df[date_column] = pd.to_datetime(
            team_game_df[date_column], utc=True, errors="raise"
        )
        sort_columns.append(date_column)
    else:
        sort_columns.append("week")
    if "game_id" in team_game_df:
        sort_columns.append("game_id")
    team_game_df = team_game_df.sort_values(sort_columns)

    excluded = {
        "season",
        "week",
        "game_id",
        "team",
        "opponent",
        "home_away",
        "date",
    }
    metric_columns = [
        column
        for column in team_game_df.columns
        if column not in excluded
        and pd.api.types.is_numeric_dtype(team_game_df[column])
    ]
    ewma = team_game_df.groupby(["season", "team"], sort=False)[
        metric_columns
    ].transform(lambda series: _calculate_ewma(series, alpha).shift(1))
    team_season = team_game_df[["season", "week", "team", "game_id"]].copy()
    team_season[metric_columns] = ewma
    return team_season.dropna(subset=metric_columns, how="all")
