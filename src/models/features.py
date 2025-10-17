"""Shared helpers for building features and merged datasets for modeling."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import get_data_root
from src.features.core import (
    aggregate_team_season,
    apply_iterative_opponent_adjustment,
)
from src.utils.local_storage import LocalStorage


def prepare_team_features(team_season_adj_df: pd.DataFrame) -> pd.DataFrame:
    """Build one-row-per-team features combining adjusted offense/defense and extras.

    Args:
        team_season_adj_df: Season aggregates with off_/def_ and adj_* columns when available.

    Returns:
        DataFrame with season, team, games_played and consolidated metrics to be joined
        to games for home/away features.
    """
    base_cols = ["season", "team", "games_played"]

    off_metric_cols = [
        c
        for c in team_season_adj_df.columns
        if c.startswith("adj_off_") or c.startswith("off_")
    ]
    def_metric_cols = [
        c
        for c in team_season_adj_df.columns
        if c.startswith("adj_def_") or c.startswith("def_")
    ]

    off_df = team_season_adj_df[base_cols + off_metric_cols].copy()
    if off_metric_cols:
        off_df = off_df.dropna(subset=off_metric_cols, how="all")

    def_df = team_season_adj_df[base_cols + def_metric_cols].copy()
    if def_metric_cols:
        def_df = def_df.dropna(subset=def_metric_cols, how="all")

    combined = off_df.merge(
        def_df, on=["season", "team"], how="outer", suffixes=("", "_defside")
    )

    if "games_played_x" in combined.columns or "games_played_y" in combined.columns:
        combined["games_played"] = combined[
            [c for c in ["games_played_x", "games_played_y"] if c in combined.columns]
        ].max(axis=1, skipna=True)
        combined = combined.drop(
            columns=[
                c for c in ["games_played_x", "games_played_y"] if c in combined.columns
            ]
        )

    # Include pace and opportunity metrics if present (excluding timing metrics like sec_per_play)
    pace_cols = [
        "plays_per_game",
        "drives_per_game",
        "avg_scoring_opps_per_game",
    ]
    present_pace = [c for c in pace_cols if c in team_season_adj_df.columns]
    if present_pace:
        pace_df = (
            team_season_adj_df[["season", "team"] + present_pace].drop_duplicates(
                subset=["season", "team"]
            )  # safety
        )
        combined = combined.merge(pace_df, on=["season", "team"], how="left")

    return combined


def build_feature_list(df: pd.DataFrame) -> list[str]:
    """Construct the list of modeling features present for both home and away.

    Args:
        df: Merged games+features DataFrame with home_/away_ prefixes.

    Returns:
        List of column names to use as model inputs.
    """
    adjusted_metrics = [
        "epa_pp",
        "sr",
        "ypp",
        "expl_rate_overall_10",
        "expl_rate_overall_20",
        "expl_rate_overall_30",
        "expl_rate_rush",
        "expl_rate_pass",
    ]
    features: list[str] = []
    momentum_suffixes = ["_last_3", "_last_1"]
    for side in ["home", "away"]:
        for prefix in ["adj_off_", "adj_def_", "off_", "def_"]:
            for metric in adjusted_metrics:
                col = f"{side}_{prefix}{metric}"
                if col in df.columns:
                    features.append(col)
                for suffix in momentum_suffixes:
                    col_momentum = f"{col}{suffix}"
                    if col_momentum in df.columns:
                        features.append(col_momentum)
        for extra in [
            "off_eckel_rate",
            "off_finish_pts_per_opp",
            "stuff_rate",
            "havoc_rate",
        ]:
            col = f"{side}_{extra}"
            if col in df.columns:
                features.append(col)
        # Pace/opportunity features (exclude sec_per_play as requested)
        for pace in [
            "plays_per_game",
            "drives_per_game",
            "avg_scoring_opps_per_game",
        ]:
            col = f"{side}_{pace}"
            if col in df.columns:
                features.append(col)

    # Global game context features
    for global_feat in ["neutral_site", "same_conference"]:
        if global_feat in df.columns:
            features.append(global_feat)

    return features


def build_differential_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    From a merged dataframe with home_ and away_ prefixes, create new
    differential/matchup features.
    """
    # Define which stats are zero-centered (use subtraction) vs. positive (use ratio)
    zero_centered_metrics = ["epa_pp"]
    positive_metrics = [
        "sr", "ypp", "expl_rate_overall_10", "expl_rate_overall_20",
        "expl_rate_overall_30", "expl_rate_rush", "expl_rate_pass",
        "eckel_rate", "finish_pts_per_opp", "stuff_rate", "havoc_rate",
        "plays_per_game", "drives_per_game", "avg_scoring_opps_per_game"
    ]
    
    base_metrics = zero_centered_metrics + positive_metrics
    momentum_suffixes = ["_last_3", "_last_1"]
    
    new_df = df.copy()

    for metric in base_metrics:
        for suffix in [""] + momentum_suffixes:
            full_metric_name = f"{metric}{suffix}"
            
            # Define the four columns for the matchup
            home_off_col = f"home_adj_off_{full_metric_name}"
            away_def_col = f"away_adj_def_{full_metric_name}"
            away_off_col = f"away_adj_off_{full_metric_name}"
            home_def_col = f"home_adj_def_{full_metric_name}"

            # Check if all necessary columns exist
            required_cols = [home_off_col, away_def_col, away_off_col, home_def_col]
            if not all(col in new_df.columns for col in required_cols):
                continue

            # Define new differential column names
            matchup_home_off_col = f"matchup_home_off_vs_away_def_{full_metric_name}"
            matchup_away_off_col = f"matchup_away_off_vs_home_def_{full_metric_name}"

            if metric in zero_centered_metrics:
                # Use subtraction for zero-centered stats
                new_df[matchup_home_off_col] = new_df[home_off_col] - new_df[away_def_col]
                new_df[matchup_away_off_col] = new_df[away_off_col] - new_df[home_def_col]
            elif metric in positive_metrics:
                # Use safe ratio for positive-only stats
                # Adding a small epsilon to avoid division by zero
                epsilon = 1e-6
                new_df[matchup_home_off_col] = new_df[home_off_col] / (new_df[away_def_col] + epsilon)
                new_df[matchup_away_off_col] = new_df[away_off_col] / (new_df[home_def_col] + epsilon)

    return new_df


def build_differential_feature_list(df: pd.DataFrame) -> list[str]:
    """
    Construct the list of modeling features after differential transformation.
    """
    features = [col for col in df.columns if col.startswith("matchup_")]
    
    # Add global game context features
    for global_feat in ["neutral_site", "same_conference"]:
        if global_feat in df.columns:
            features.append(global_feat)
            
    return features


def generate_point_in_time_features(
    year: int, week: int, data_root: str | None
) -> pd.DataFrame:
    """Generate season-to-date features for all games in a specific week, using only data from prior weeks."""
    resolved_root = data_root or get_data_root()
    processed_storage = LocalStorage(
        data_root=resolved_root, file_format="csv", data_type="processed"
    )
    raw_storage = LocalStorage(
        data_root=resolved_root, file_format="csv", data_type="raw"
    )

    # 1. Load all team_game data for the season up to the target week
    all_team_game_records = []
    for w in range(1, week):
        weekly_records = processed_storage.read_index("team_game", {"year": year, "week": w})
        if weekly_records:
            all_team_game_records.extend(weekly_records)

    if not all_team_game_records:
        raise ValueError(f"No team_game data found for year {year} up to week {week}")
    team_game_df = pd.DataFrame.from_records(all_team_game_records)

    # 2. Filter to data *before* the target week for feature calculation (already done by loop)
    feature_data = team_game_df.copy()

    if feature_data.empty:
        raise ValueError(f"No historical data found before week {week} for year {year}")

    # 3. Calculate season-to-date stats using only past data
    team_season_pre_week = aggregate_team_season(feature_data)

    # 4. Perform opponent adjustment on the point-in-time data
    team_season_adj_pre_week = apply_iterative_opponent_adjustment(
        team_season_pre_week, feature_data
    )

    # 5. Prepare the features for merging
    team_features = prepare_team_features(team_season_adj_pre_week)

    # 6. Load the actual games for the target week
    game_records = raw_storage.read_index("games", {"year": year})
    if not game_records:
        raise ValueError(f"No raw game data found for year {year}")
    games_df = pd.DataFrame.from_records(game_records)
    week_games_df = games_df[games_df["week"] == week].copy()

    # 7. Merge the point-in-time features into the target week's games
    home_features = team_features.add_prefix("home_")
    away_features = team_features.add_prefix("away_")

    merged_df = week_games_df.merge(
        home_features,
        left_on=["season", "home_team"],
        right_on=["home_season", "home_team"],
        how="left",
    )
    merged_df = merged_df.merge(
        away_features,
        left_on=["season", "away_team"],
        right_on=["away_season", "away_team"],
        how="left",
    )

    # Add targets for training/evaluation if scores are available
    if "home_points" in merged_df.columns and "away_points" in merged_df.columns:
        merged_df["spread_target"] = merged_df["home_points"].astype(float) - merged_df[
            "away_points"
        ].astype(float)
        merged_df["total_target"] = merged_df["home_points"].astype(float) + merged_df[
            "away_points"
        ].astype(float)

    # Derive conference indicator with fallbacks
    if (
        "home_conference" in merged_df.columns
        and "away_conference" in merged_df.columns
    ):
        merged_df["same_conference"] = (
            merged_df["home_conference"].astype(str)
            == merged_df["away_conference"].astype(str)
        ).astype(int)
    elif "conference_game" in merged_df.columns:
        # CFBD provides conference_game boolean for many records
        try:
            merged_df["same_conference"] = merged_df["conference_game"].astype(int)
        except Exception:
            merged_df["same_conference"] = 0
    else:
        # Last-resort default (no leakage, conservative)
        merged_df["same_conference"] = 0

    merged_df = merged_df.drop(columns=["home_season", "away_season"], errors="ignore")
    return merged_df


def load_merged_dataset(year: int, data_root: str | None) -> pd.DataFrame:
    """Load adjusted team-season features and merge into games for a season.

    Args:
        year: Season to load.
        data_root: Optional data root override; falls back to config.

    Returns:
        DataFrame with per-game home/away features and spread/total targets.

    Raises:
        ValueError: If adjusted team season data or raw games are missing, or if
            required score columns are absent.
    """
    resolved_root = data_root or get_data_root()
    processed_storage = LocalStorage(
        data_root=resolved_root, file_format="csv", data_type="processed"
    )
    raw_storage = LocalStorage(
        data_root=resolved_root, file_format="csv", data_type="raw"
    )

    team_season_adj_records = processed_storage.read_index(
        "team_season_adj", {"year": year}
    )
    if not team_season_adj_records:
        raise ValueError(f"No adjusted team season data found for year {year}")
    team_season_adj_df = pd.DataFrame.from_records(team_season_adj_records)
    team_features = prepare_team_features(team_season_adj_df)

    game_records = raw_storage.read_index("games", {"year": year})
    if not game_records:
        raise ValueError(f"No raw game data found for year {year}")
    games_df = pd.DataFrame.from_records(game_records)

    home_features = team_features.add_prefix("home_")
    away_features = team_features.add_prefix("away_")

    merged_df = games_df.merge(
        home_features,
        left_on=["season", "home_team"],
        right_on=["home_season", "home_team"],
        how="left",
    )
    merged_df = merged_df.merge(
        away_features,
        left_on=["season", "away_team"],
        right_on=["away_season", "away_team"],
        how="left",
    )

    required_scores = {"home_points", "away_points"}
    if not required_scores.issubset(merged_df.columns):
        raise ValueError(
            "Games data missing required score columns: home_points, away_points"
        )

    merged_df["spread_target"] = merged_df["home_points"].astype(float) - merged_df[
        "away_points"
    ].astype(float)
    merged_df["total_target"] = merged_df["home_points"].astype(float) + merged_df[
        "away_points"
    ].astype(float)
    merged_df = merged_df.drop(columns=["home_season", "away_season"], errors="ignore")
    return merged_df
