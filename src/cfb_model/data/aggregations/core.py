from __future__ import annotations

import numpy as np
import pandas as pd


def aggregate_drives(plays_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregates play-level data to drive-level metrics.

    Returns a DataFrame with one row per (game_id, drive_number, offense, defense).
    """
    required = [
        "game_id",
        "drive_number",
        "offense",
        "defense",
        "yards_gained",
        "play_duration",
        "quarter",
        "time_remaining_after",
        "time_remaining_before",
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
    plays_df["counted_play_duration"] = np.where(
        plays_df["is_drive_play"] == 1, plays_df["play_duration"], 0
    )

    agg = (
        plays_df.sort_values(["game_id", "drive_number", "quarter", "play_number"])
        .groupby(["game_id", "drive_number", "offense", "defense"], as_index=False)
        .agg(
            drive_plays=("is_drive_play", "sum"),
            drive_yards=("yards_gained", "sum"),
            drive_time=("counted_play_duration", "sum"),
            drive_start_period=("quarter", "min"),
            drive_end_period=("quarter", "max"),
            start_time_remain=("time_remaining_before", "max"),
            end_time_remain=("time_remaining_after", "min"),
            start_yards_to_goal=("yards_to_goal", "first"),
            end_yards_to_goal=("yards_to_goal", "last"),
            is_eckel_drive=("eckel", "max"),
            # Use a column to anchor the custom function; reference other columns by index
            had_scoring_opportunity=(
                "yards_to_goal",
                lambda s: 1
                if (
                    (
                        plays_df.loc[s.index, "eckel"]
                        & (plays_df.loc[s.index, "down"] == 1)
                        & (plays_df.loc[s.index, "yards_to_goal"] <= 40)
                    ).any()
                )
                else 0,
            ),
            points=("scoring", "sum"),
            turnovers=("turnover", "sum"),
        )
    )

    # Define drive outcomes based on aggregated stats
    agg["is_successful_drive"] = (agg["points"] > 0).astype(int)
    agg["is_busted_drive"] = (agg["turnovers"] > 0).astype(int)
    
    # For explosive drive, calculate YPP and set a threshold (e.g., 10 YPP)
    drive_ypp = agg["drive_yards"] / agg["drive_plays"].replace(0, 1) # Avoid division by zero
    agg["is_explosive_drive"] = (drive_ypp > 10).astype(int)

    agg["points_on_opps"] = np.where(
        agg["had_scoring_opportunity"] == 1, agg["points"], 0
    )
    return agg


def calculate_st_analytics_agg(plays_df: pd.DataFrame, drives_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregates special teams analytics to the game level."""
    st_plays = plays_df[plays_df['st'] == 1].copy()
    if st_plays.empty:
        return pd.DataFrame()

    # Calculate Net Punt Yards
    punts = st_plays[st_plays['st_punt'] == 1].copy()
    if not punts.empty:
        drive_starts = drives_df.groupby(['game_id', 'drive_number'])['start_yards_to_goal'].first().reset_index()
        drive_starts['next_drive_start_ytg'] = drive_starts.groupby('game_id')['start_yards_to_goal'].shift(-1)
        punts = punts.merge(drive_starts, on=['game_id', 'drive_number'], how='left')
        punts['net_punt_yards'] = punts['yards_to_goal'] - (100 - punts['next_drive_start_ytg'])
        punt_agg = punts.groupby(['game_id', 'offense']).agg(off_avg_net_punt_yards=('net_punt_yards', 'mean')).reset_index()
    else:
        punt_agg = pd.DataFrame(columns=['game_id', 'offense', 'off_avg_net_punt_yards'])

    # Calculate Field Goal stats
    fg_plays = st_plays[st_plays['st_fg'] == 1].copy()
    if not fg_plays.empty:
        fg_plays['fg_bucket'] = pd.cut(fg_plays['kick_distance'], bins=[0, 39, 49, 100], labels=['short', 'mid', 'long'])
        fg_agg = fg_plays.groupby(['game_id', 'offense', 'fg_bucket']).agg(fg_attempts=('st_fg', 'count'), fg_made=('is_fg_made', 'sum')).reset_index()
        fg_agg = fg_agg.pivot_table(index=['game_id', 'offense'], columns='fg_bucket', values=['fg_attempts', 'fg_made'], fill_value=0).reset_index()
        fg_agg.columns = [f'off_{col[0]}_{col[1]}' if col[1] else col[0] for col in fg_agg.columns]
    else:
        fg_agg = pd.DataFrame(columns=['game_id', 'offense'])

    # Merge ST stats
    st_agg = punt_agg.merge(fg_agg, on=['game_id', 'offense'], how='outer').rename(columns={"offense": "team"})
    return st_agg


def aggregate_team_game(
    plays_df: pd.DataFrame, drives_df: pd.DataFrame
) -> pd.DataFrame:
    """Aggregates to team-game features combining play- and drive-level signals.

    Returns one row per (game_id, team), with `home/away` available from plays_df.
    """
    off_grp = plays_df.groupby(["season", "week", "game_id", "offense"], as_index=False)
    off_agg = off_grp.agg(
        n_off_plays=("play_number", "count"),
        n_rush_plays=("rush_attempt", "sum"),
        n_pass_plays=("pass_attempt", "sum"),
        off_sr=("success", "mean"),
        off_ypp=("yards_gained", "mean"),
        off_epa_pp=("ppa", "mean"),
        off_expl_rate_overall_10=(
            "yards_gained",
            lambda s: (plays_df.loc[s.index, "yards_gained"] >= 10).mean(),
        ),
        off_expl_rate_overall_20=(
            "yards_gained",
            lambda s: (plays_df.loc[s.index, "yards_gained"] >= 20).mean(),
        ),
        off_expl_rate_overall_30=(
            "yards_gained",
            lambda s: (plays_df.loc[s.index, "yards_gained"] >= 30).mean(),
        ),
        off_expl_rate_rush=(
            "rush_attempt",
            lambda s: (
                (plays_df.loc[s.index, "rush_attempt"] == 1)
                & (plays_df.loc[s.index, "yards_gained"] >= 10)
            ).mean(),
        ),
        off_expl_rate_pass=(
            "pass_attempt",
            lambda s: (
                (plays_df.loc[s.index, "pass_attempt"] == 1)
                & (plays_df.loc[s.index, "yards_gained"] >= 15)
            ).mean(),
        ),
        stuff_rate=(
            "rush_attempt",
            lambda s: (
                (plays_df.loc[s.index, "rush_attempt"] == 1)
                & (plays_df.loc[s.index, "yards_gained"] <= 0)
            ).mean(),
        ),
        havoc_rate=("havoc", "mean"),
        off_avg_line_yards=("line_yards", "mean"),
        off_avg_second_level_yards=("second_level_yards", "mean"),
        off_avg_open_field_yards=("open_field_yards", "mean"),
        _power_success_situations=("is_power_situation", "sum"),
        _power_success_conversions=("power_success_converted", "sum"),
    )
    off_agg = off_agg.rename(columns={"offense": "team"})

    def_grp = plays_df.groupby(["season", "week", "game_id", "defense"], as_index=False)
    def_agg = def_grp.agg(
        def_sr=("success", "mean"),
        def_ypp=("yards_gained", "mean"),
        def_epa_pp=("ppa", "mean"),
        def_expl_rate_overall_10=(
            "yards_gained",
            lambda s: (plays_df.loc[s.index, "yards_gained"] >= 10).mean(),
        ),
        def_expl_rate_overall_20=(
            "yards_gained",
            lambda s: (plays_df.loc[s.index, "yards_gained"] >= 20).mean(),
        ),
        def_expl_rate_overall_30=(
            "yards_gained",
            lambda s: (plays_df.loc[s.index, "yards_gained"] >= 30).mean(),
        ),
        def_expl_rate_rush=(
            "rush_attempt",
            lambda s: (
                (plays_df.loc[s.index, "rush_attempt"] == 1)
                & (plays_df.loc[s.index, "yards_gained"] >= 10)
            ).mean(),
        ),
        def_expl_rate_pass=(
            "pass_attempt",
            lambda s: (
                (plays_df.loc[s.index, "pass_attempt"] == 1)
                & (plays_df.loc[s.index, "yards_gained"] >= 15)
            ).mean(),
        ),
        def_avg_line_yards_allowed=("line_yards", "mean"),
        def_avg_second_level_yards_allowed=("second_level_yards", "mean"),
        def_avg_open_field_yards_allowed=("open_field_yards", "mean"),
        _def_power_success_situations=("is_power_situation", "sum"),
        _def_power_success_conversions=("power_success_converted", "sum"),
    ).rename(columns={"defense": "team"})

    drv_grp = drives_df.groupby(
        ["season", "week", "game_id", "offense"], as_index=False
    )
    drv_agg = drv_grp.agg(
        off_drives=("drive_number", "count"),
        off_eckel_rate=("is_eckel_drive", "mean"),
        off_successful_drive_rate=("is_successful_drive", "mean"),
        off_busted_drive_rate=("is_busted_drive", "mean"),
        off_explosive_drive_rate=("is_explosive_drive", "mean"),
        _sum_pts_on_opps=("points_on_opps", "sum"),
        _sum_opp=("had_scoring_opportunity", "sum"),
    ).rename(columns={"offense": "team"})

    # Compute finish points per scoring opportunity safely
    denom = drv_agg["_sum_opp"].where(drv_agg["_sum_opp"] > 0, 1)
    drv_agg["off_finish_pts_per_opp"] = drv_agg["_sum_pts_on_opps"] / denom
    drv_agg = drv_agg.drop(columns=["_sum_pts_on_opps", "_sum_opp"])

    # Calculate Power Success Rate safely
    off_denom = off_agg["_power_success_situations"].where(off_agg["_power_success_situations"] > 0, 1)
    off_agg["off_power_success_rate"] = off_agg["_power_success_conversions"] / off_denom
    off_agg = off_agg.drop(columns=["_power_success_situations", "_power_success_conversions"])

    def_denom = def_agg["_def_power_success_situations"].where(def_agg["_def_power_success_situations"] > 0, 1)
    def_agg["def_power_success_rate_allowed"] = def_agg["_def_power_success_conversions"] / def_denom
    def_agg = def_agg.drop(columns=["_def_power_success_situations", "_def_power_success_conversions"])

    # Create defensive drives aggregation  
    def_drv_grp = drives_df.groupby(
        ["season", "week", "game_id", "defense"], as_index=False
    )
    def_drv_agg = def_drv_grp.agg(
        def_drives_allowed=("drive_number", "count"),
        def_eckel_rate_allowed=("is_eckel_drive", "mean"),
        def_successful_drive_rate_allowed=("is_successful_drive", "mean"),
        def_busted_drive_rate_allowed=("is_busted_drive", "mean"),
        def_explosive_drive_rate_allowed=("is_explosive_drive", "mean"),
        _def_sum_pts_on_opps_allowed=("points_on_opps", "sum"),
        _def_sum_opp_allowed=("had_scoring_opportunity", "sum"),
    ).rename(columns={"defense": "team"})
    
    # Compute defensive finish points per scoring opportunity safely
    def_denom = def_drv_agg["_def_sum_opp_allowed"].where(def_drv_agg["_def_sum_opp_allowed"] > 0, 1)
    def_drv_agg["def_finish_pts_per_opp_allowed"] = def_drv_agg["_def_sum_pts_on_opps_allowed"] / def_denom
    def_drv_agg = def_drv_agg.drop(columns=["_def_sum_pts_on_opps_allowed", "_def_sum_opp_allowed"])

    # Merge all team-game aggregations
    team_game = off_agg.merge(def_agg, on=["season", "week", "game_id", "team"], how="outer")
    team_game = team_game.merge(drv_agg, on=["season", "week", "game_id", "team"], how="left")
    team_game = team_game.merge(def_drv_agg, on=["season", "week", "game_id", "team"], how="left")
    
    # Add special teams if available
    st_agg = calculate_st_analytics_agg(plays_df, drives_df)
    if not st_agg.empty:
        team_game = team_game.merge(st_agg, on=["game_id", "team"], how="left")

    return team_game


def aggregate_team_season(team_game_df: pd.DataFrame) -> pd.DataFrame:
    """Season-to-date team aggregates using recency weights (3/2/1; earlier=1)."""
    required = ["season", "week", "team"]
    for c in required:
        if c not in team_game_df.columns:
            raise ValueError(f"aggregate_team_season requires column '{c}'")

    def _apply_weights(g: pd.DataFrame) -> pd.DataFrame:
        g = g.sort_values("week").copy()
        weights = np.ones(len(g), dtype=float)
        # Assign 3,2,1 to last three games (most recent highest), earlier = 1
        for i, w in enumerate([1.0, 2.0, 3.0], start=1):
            if len(g) - i >= 0:
                weights[-i] = w
        g["recency_weight"] = weights
        return g

    weighted = team_game_df.groupby(
        ["season", "team"], as_index=False, group_keys=False
    ).apply(_apply_weights)

    metric_cols = [
        "off_sr",
        "off_ypp",
        "off_epa_pp",
        "off_expl_rate_overall_10",
        "off_expl_rate_overall_20",
        "off_expl_rate_overall_30",
        "off_expl_rate_rush",
        "off_expl_rate_pass",
        "stuff_rate",
        "havoc_rate",
        "def_sr",
        "def_ypp",
        "def_epa_pp",
        "def_expl_rate_overall_10",
        "def_expl_rate_overall_20",
        "def_expl_rate_overall_30",
        "def_expl_rate_rush",
        "def_expl_rate_pass",
        "off_eckel_rate",
        "off_finish_pts_per_opp",
        "off_power_success_rate",
        "off_avg_line_yards",
        "off_avg_second_level_yards",
        "off_avg_open_field_yards",
        "def_power_success_rate_allowed",
        "def_avg_line_yards_allowed",
        "def_avg_second_level_yards_allowed",
        "def_avg_open_field_yards_allowed",
        # Drive-level metrics
        "off_successful_drive_rate",
        "off_busted_drive_rate",
        "off_explosive_drive_rate",
        "def_successful_drive_rate_allowed",
        "def_busted_drive_rate_allowed",
        "def_explosive_drive_rate_allowed",
        # Special teams metrics (if available)
        "off_avg_net_punt_yards",
    ]
    present_metric_cols = [c for c in metric_cols if c in weighted.columns]

    def _agg_group(g: pd.DataFrame) -> pd.Series:
        out: dict[str, float] = {}
        w = g["recency_weight"].astype(float)
        wsum = w.sum() if w.sum() > 0 else 1.0
        for col in present_metric_cols:
            vals = g[col].astype(float)
            out[col] = float((vals * w).sum() / wsum)
        out["games_played"] = float(len(g))
        if "luck_factor" in g.columns:
            out["cumulative_luck_factor"] = g["luck_factor"].sum()
        return pd.Series(out)

    season_agg = (
        weighted.groupby(["season", "team"], as_index=False)
        .apply(_agg_group)
        .reset_index(drop=True)
    )
    return season_agg


def apply_iterative_opponent_adjustment(
    team_season_df: pd.DataFrame, team_game_df: pd.DataFrame, iterations: int = 4
) -> pd.DataFrame:
    """Applies iterative opponent adjustment to season-to-date team aggregates."""
    adjusted_df = team_season_df.copy()

    metrics_to_adjust = [
        "epa_pp",
        "sr",
        "ypp",
        "expl_rate_overall_10",
        "expl_rate_overall_20",
        "expl_rate_overall_30",
        "expl_rate_rush",
        "expl_rate_pass",
        "power_success_rate",
        "avg_line_yards",
        "avg_second_level_yards",
        "avg_open_field_yards",
        "successful_drive_rate",
        "busted_drive_rate",
        "explosive_drive_rate",
        "avg_net_punt_yards",
        "fg_rate_short",
        "fg_rate_mid",
        "fg_rate_long",
    ]

    # Define defensive metrics that use '_allowed' suffix
    defensive_allowed_metrics = {
        "power_success_rate",
        "avg_line_yards", 
        "avg_second_level_yards",
        "avg_open_field_yards",
        "successful_drive_rate",
        "busted_drive_rate",
        "explosive_drive_rate",
        "avg_net_punt_yards",
    }
    
    for metric in metrics_to_adjust:
        # Offensive metric - only add if column exists
        off_col = f"off_{metric}"
        if off_col in adjusted_df.columns:
            adjusted_df[f"adj_off_{metric}"] = adjusted_df[off_col]
        
        # Defensive metric - handle metrics that use '_allowed' suffix, only add if column exists
        if metric in defensive_allowed_metrics:
            def_col = f"def_{metric}_allowed"
        else:
            def_col = f"def_{metric}"
            
        if def_col in adjusted_df.columns:
            adjusted_df[f"adj_def_{metric}"] = adjusted_df[def_col]

    def _apply_weights_to_games(g: pd.DataFrame) -> pd.DataFrame:
        g = g.sort_values("week").copy()
        weights = np.ones(len(g), dtype=float)
        for i, w in enumerate([1.0, 2.0, 3.0], start=1):
            if len(g) - i >= 0:
                weights[-i] = w
        g["recency_weight"] = weights
        return g

    team_game_weighted = team_game_df.groupby(
        ["season", "team"], as_index=False, group_keys=False
    ).apply(_apply_weights_to_games)
    games_with_opponents = team_game_weighted.merge(
        team_game_weighted,
        left_on=["season", "week", "game_id"],
        right_on=["season", "week", "game_id"],
        suffixes=("", "_opp"),
    )
    games_with_opponents = games_with_opponents[
        games_with_opponents["team"] != games_with_opponents["team_opp"]
    ]

    for _ in range(iterations):
        # Only include columns that actually exist in the DataFrame
        adj_cols = ["season", "team"]
        for m in metrics_to_adjust:
            if f"adj_off_{m}" in adjusted_df.columns:
                adj_cols.append(f"adj_off_{m}")
            if f"adj_def_{m}" in adjusted_df.columns:
                adj_cols.append(f"adj_def_{m}")
        
        current_adjusted_metrics = adjusted_df[adj_cols].copy()
        current_adjusted_metrics = current_adjusted_metrics.set_index(
            ["season", "team"]
        )  # type: ignore[assignment]

        new_adjusted_df = adjusted_df.copy()

        for index, row in adjusted_df.iterrows():
            season = row["season"]
            team = row["team"]

            team_games = games_with_opponents[
                (games_with_opponents["season"] == season)
                & (games_with_opponents["team"] == team)
            ]
            if team_games.empty:
                continue

            team_games_with_opp_adj = team_games.merge(
                current_adjusted_metrics,
                left_on=["season", "team_opp"],
                right_index=True,
                how="left",
                suffixes=("", "_opp_adj"),
            )

            league_means = {}
            for metric in metrics_to_adjust:
                if f"adj_off_{metric}" in adjusted_df.columns:
                    league_means[f"off_{metric}"] = adjusted_df[f"adj_off_{metric}"].mean()
                if f"adj_def_{metric}" in adjusted_df.columns:
                    league_means[f"def_{metric}"] = adjusted_df[f"adj_def_{metric}"].mean()

            for metric in metrics_to_adjust:
                # Skip metrics that don't have both offensive and required columns
                off_col_name = f"off_{metric}"
                if metric in defensive_allowed_metrics:
                    def_col_name = f"def_{metric}_allowed"
                else:
                    def_col_name = f"def_{metric}"
                
                # Skip if required columns don't exist
                if (off_col_name not in row.index or 
                    def_col_name not in row.index or
                    f"off_{metric}" not in league_means or
                    f"def_{metric}" not in league_means):
                    continue
                
                off_base_metric = row[off_col_name]
                def_base_metric = row[def_col_name]

                # Handle column names with or without the merge suffix
                def_col = (
                    f"adj_def_{metric}_opp_adj"
                    if f"adj_def_{metric}_opp_adj" in team_games_with_opp_adj.columns
                    else f"adj_def_{metric}"
                )
                off_col = (
                    f"adj_off_{metric}_opp_adj"
                    if f"adj_off_{metric}_opp_adj" in team_games_with_opp_adj.columns
                    else f"adj_off_{metric}"
                )
                
                # Skip if required adjusted columns don't exist
                if (def_col not in team_games_with_opp_adj.columns or
                    off_col not in team_games_with_opp_adj.columns):
                    continue

                opp_def_metrics = team_games_with_opp_adj[def_col]
                opp_off_metrics = team_games_with_opp_adj[off_col]
                weights = team_games_with_opp_adj["recency_weight"]

                weighted_opp_def_mean = (
                    ((opp_def_metrics - league_means[f"def_{metric}"]) * weights).sum()
                    / weights.sum()
                    if weights.sum() > 0
                    else 0
                )

                weighted_opp_off_mean = (
                    ((opp_off_metrics - league_means[f"off_{metric}"]) * weights).sum()
                    / weights.sum()
                    if weights.sum() > 0
                    else 0
                )

                if f"adj_off_{metric}" in new_adjusted_df.columns:
                    new_adjusted_df.loc[index, f"adj_off_{metric}"] = (
                        off_base_metric - weighted_opp_def_mean
                    )
                if f"adj_def_{metric}" in new_adjusted_df.columns:
                    new_adjusted_df.loc[index, f"adj_def_{metric}"] = (
                        def_base_metric - weighted_opp_off_mean
                    )

        adjusted_df = new_adjusted_df

    return adjusted_df
