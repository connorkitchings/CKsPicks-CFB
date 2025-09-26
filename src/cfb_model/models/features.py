"""Shared helpers for building features and merged datasets for modeling."""

from __future__ import annotations

import pandas as pd

from cfb_model.config import get_data_root
from cfb_model.data.storage.local_storage import LocalStorage


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
        c for c in team_season_adj_df.columns if c.startswith("adj_off_")
    ]
    for extra in [
        "off_eckel_rate",
        "off_finish_pts_per_opp",
        "stuff_rate",
        "havoc_rate",
    ]:
        if extra in team_season_adj_df.columns:
            off_metric_cols.append(extra)

    def_metric_cols = [
        c for c in team_season_adj_df.columns if c.startswith("adj_def_")
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
    for side in ["home", "away"]:
        for prefix in ["adj_off_", "adj_def_"]:
            for metric in adjusted_metrics:
                col = f"{side}_{prefix}{metric}"
                if col in df.columns:
                    features.append(col)
        for extra in [
            "off_eckel_rate",
            "off_finish_pts_per_opp",
            "stuff_rate",
            "havoc_rate",
        ]:
            col = f"{side}_{extra}"
            if col in df.columns:
                features.append(col)
    return features


from cfb_model.data.aggregations.core import (
    aggregate_team_season,
    apply_iterative_opponent_adjustment,
)


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

    # 1. Load all team_game data for the season
    team_game_records = processed_storage.read_index("team_game", {"year": year})
    if not team_game_records:
        raise ValueError(f"No team_game data found for year {year}")
    team_game_df = pd.DataFrame.from_records(team_game_records)

    # 2. Filter to data *before* the target week for feature calculation
    feature_data = team_game_df[team_game_df["week"] < week].copy()

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
