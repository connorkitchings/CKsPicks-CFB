"""Data loading and preparation utilities for the ratings model.

This module provides functions to load and prepare game data for training
probabilistic power ratings models.
"""

from pathlib import Path
from typing import Dict, Optional, Tuple

import pandas as pd

from cks_picks_cfb.config import DATA_ROOT


def prepare_ratings_data(
    year: int,
    week: Optional[int] = None,
    min_games: int = 2,
    data_root: Optional[str] = None,
) -> Tuple[pd.DataFrame, Dict[str, int], Dict[int, str]]:
    """
    Loads games and prepares them for the ratings model.

    Args:
        year: The season to load.
        week: If provided, filter to games BEFORE this week.
        min_games: Minimum games a team must have played to be included (not strictly enforced here, but good for context).
        data_root: Path to data root.

    Returns:
        df: DataFrame with 'home_id', 'away_id', 'home_points', 'away_points', 'neutral_site'.
        team_to_idx: Mapping from team name to integer index.
        idx_to_team: Mapping from integer index to team name.
    """
    root = Path(data_root) if data_root else Path(DATA_ROOT)

    # Load games
    games_path = root / "raw" / "games" / f"year={year}" / "data.csv"
    if not games_path.exists():
        raise FileNotFoundError(f"Games data not found at {games_path}")

    df = pd.read_csv(games_path)
    if "id" in df.columns and "game_id" not in df.columns:
        df = df.rename(columns={"id": "game_id"})

    # Filter to completed games
    df = df[df["completed"]].copy()

    # Filter by week if requested (train on past, predict on current)
    if week is not None:
        df = df[df["week"] < week]

    # Filter out games with missing scores
    df = df.dropna(subset=["home_points", "away_points"])

    # Create team mapping
    # We need a consistent mapping for the whole season, ideally.
    # For now, we'll map based on the teams present in the training set.
    # NOTE: In a real production system, we might want a global team ID registry.
    all_teams = sorted(
        list(set(df["home_team"].unique()) | set(df["away_team"].unique()))
    )
    team_to_idx = {team: i for i, team in enumerate(all_teams)}
    idx_to_team = {i: team for team, i in team_to_idx.items()}

    # Map teams to indices
    df["home_id"] = df["home_team"].map(team_to_idx)
    df["away_id"] = df["away_team"].map(team_to_idx)

    # Ensure neutral_site is boolean
    df["neutral_site"] = df["neutral_site"].fillna(False).astype(bool)

    # Select relevant columns
    cols = [
        "game_id",
        "season",
        "week",
        "home_team",
        "away_team",
        "home_id",
        "away_id",
        "home_points",
        "away_points",
        "neutral_site",
    ]
    return df[cols], team_to_idx, idx_to_team
