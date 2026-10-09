"""Drive-level aggregation from play-by-play data."""

from __future__ import annotations

import numpy as np
import pandas as pd

from cks_picks_cfb.data.play_identity import DRIVES_V1, DRIVES_V2


def aggregate_drives(
    plays_df: pd.DataFrame, *, schema_version: str = DRIVES_V1
) -> pd.DataFrame:
    """Aggregate play-level rows into drive-level metrics.

    ``schema_version="drives_v2"`` identifies a drive by its exact ``drive_id`` (the provider
    drive where present, else a derived drive that was admitted as unambiguous) instead of
    the displayed ``drive_number``, which a feed can reuse for a different drive. Rows keep
    v1's per-orientation split (a provider drive's kickoff and the receiving team's plays are
    separate rows), so drive counts match v1 wherever no drive number was reused.
    The default ``drives_v1`` is unchanged.

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
    if schema_version == DRIVES_V2:
        agg = _aggregate_provider_drives(plays_df)
        return _drive_outcomes(agg)
    if schema_version != DRIVES_V1:
        raise ValueError(f"unknown drives schema version: {schema_version}")
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

    return _drive_outcomes(agg)


def _aggregate_provider_drives(plays_df: pd.DataFrame) -> pd.DataFrame:
    for column in ("drive_id", "drive_id_source", "drive_ambiguous"):
        if column not in plays_df.columns:
            raise ValueError(f"drives_v2 requires column '{column}' (use byplay_v2)")
    ordered = plays_df.sort_values(
        ["game_id", "drive_id", "quarter", "drive_number", "play_number"],
        kind="mergesort",
    )
    agg = ordered.groupby(
        ["game_id", "drive_id", "offense", "defense"], as_index=False, sort=True
    ).agg(
        drive_number=("drive_number", "min"),
        drive_plays=("is_drive_play", "sum"),
        drive_yards=("yards_gained", "sum"),
        drive_start_period=("quarter", "min"),
        drive_end_period=("quarter", "max"),
        start_yards_to_goal=("yards_to_goal", "first"),
        end_yards_to_goal=("yards_to_goal", "last"),
        is_eckel_drive=("eckel", "max"),
        eckel_plays=("eckel", "sum"),
        points=("scoring", "sum"),
        turnovers=("turnover", "sum"),
        any_derived=("drive_id_source", lambda s: bool((s == "derived").any())),
        drive_ambiguous=("drive_ambiguous", "max"),
    )
    agg["had_scoring_opportunity"] = (agg["eckel_plays"] > 0).astype(int)
    agg["drive_id_source"] = agg["any_derived"].map(
        {True: "derived", False: "provider"}
    )
    agg["drive_ambiguous"] = agg["drive_ambiguous"].astype(bool)
    return agg.drop(columns=["eckel_plays", "any_derived"])


def _drive_outcomes(agg: pd.DataFrame) -> pd.DataFrame:
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
