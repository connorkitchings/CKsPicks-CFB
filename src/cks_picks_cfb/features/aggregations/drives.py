"""Drive-level aggregation from play-by-play data."""

from __future__ import annotations

import numpy as np
import pandas as pd


def aggregate_drives(plays_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate play-level rows into drive-level metrics.

    Args:
        plays_df: Enriched play-level DataFrame. Must include columns:
            - game_id, drive_number, offense, defense
            - yards_gained, quarter
            - eckel (indicator for scoring opp window), yards_to_goal, scoring, turnover
            - play_type (string), is_drive_play (optional; inferred if missing)

    Returns:
        DataFrame with one row per (game_id, drive_number, offense, defense) and columns:
            - drive_plays, drive_yards
            - drive_start_period, drive_end_period
            - start_yards_to_goal, end_yards_to_goal
            - is_eckel_drive, had_scoring_opportunity, points, turnovers
            - is_successful_drive, is_busted_drive, is_explosive_drive

    Raises:
        ValueError: If required columns are missing from plays_df.
    """
    required = [
        "game_id",
        "drive_number",
        "offense",
        "defense",
        "yards_gained",
        "quarter",
        "eckel",
        "yards_to_goal",
        "scoring",
    ]
    for c in required:
        if c not in plays_df.columns:
            raise ValueError(f"aggregate_drives requires column '{c}' in plays_df")

    plays_df = plays_df.copy()
    if "is_drive_play" not in plays_df.columns:
        approx_non_count = ["Timeout", "Uncategorized", "placeholder", "End Period"]
        plays_df["is_drive_play"] = (
            (plays_df.get("st", 0) == 0)
            & (plays_df.get("penalty", 0) == 0)
            & (plays_df.get("twopoint", 0) == 0)
            & (~plays_df["play_type"].isin(approx_non_count))
        ).astype(int)
    agg = (
        plays_df.sort_values(["game_id", "drive_number", "quarter", "play_number"])
        .groupby(["game_id", "drive_number", "offense", "defense"], as_index=False)
        .agg(
            drive_plays=("is_drive_play", "sum"),
            drive_yards=("yards_gained", "sum"),
            drive_start_period=("quarter", "min"),
            drive_end_period=("quarter", "max"),
            start_yards_to_goal=("yards_to_goal", "first"),
            end_yards_to_goal=("yards_to_goal", "last"),
            is_eckel_drive=("eckel", "max"),
            # Use a column to anchor the custom function; reference other columns by index
            had_scoring_opportunity=(
                "yards_to_goal",
                lambda s: 1 if (plays_df.loc[s.index, "eckel"] == 1).any() else 0,
            ),
            points=("scoring", "sum"),
            turnovers=("turnover", "sum"),
        )
    )

    # Define drive outcomes based on aggregated stats
    agg["is_successful_drive"] = (agg["points"] > 0).astype(int)
    agg["is_busted_drive"] = (agg["turnovers"] > 0).astype(int)

    # For explosive drive, calculate YPP and set a threshold (e.g., 10 YPP)
    drive_ypp = agg["drive_yards"] / agg["drive_plays"].replace(
        0, 1
    )  # Avoid division by zero
    agg["is_explosive_drive"] = (drive_ypp > 10).astype(int)

    agg["points_on_opps"] = np.where(
        agg["had_scoring_opportunity"] == 1, agg["points"], 0
    )
    return agg
