"""Core aggregation functions for plays → drives → team-game → team-season.

These utilities aggregate enriched play data to higher-level representations and
compute derived metrics (e.g., scoring opportunity indicators, explosive drives).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def aggregate_drives(plays_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate play-level rows into drive-level metrics.

    Args:
        plays_df: Enriched play-level DataFrame. Must include columns:
            - game_id, drive_number, offense, defense
            - yards_gained, play_duration, quarter
            - time_remaining_before, time_remaining_after
            - eckel (indicator for scoring opp window), yards_to_goal, scoring, turnover
            - play_type (string), is_drive_play (optional; inferred if missing)

    Returns:
        DataFrame with one row per (game_id, drive_number, offense, defense) and columns:
            - drive_plays, drive_yards, drive_time
            - drive_start_period, drive_end_period
            - start_time_remain, end_time_remain
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


def calculate_st_analytics_agg(
    plays_df: pd.DataFrame, drives_df: pd.DataFrame
) -> pd.DataFrame:
    """Aggregate special-teams play signals to game-level metrics.

    Args:
        plays_df: Play-level DataFrame containing special-teams indicators such as
            st (1 if special teams), st_punt, st_fg, kick_distance, is_fg_made.
        drives_df: Drive-level DataFrame to derive next-drive context for net punt yards.

    Returns:
        DataFrame with columns keyed by (game_id, team) for special-teams metrics.
        May be empty if no special-teams plays exist.
    """
    st_plays = plays_df[plays_df["st"] == 1].copy()
    if st_plays.empty:
        return pd.DataFrame()

    # Calculate Net Punt Yards
    punts = st_plays[st_plays["st_punt"] == 1].copy()
    if not punts.empty:
        drive_starts = (
            drives_df.groupby(["game_id", "drive_number"])["start_yards_to_goal"]
            .first()
            .reset_index()
        )
        drive_starts["next_drive_start_ytg"] = drive_starts.groupby("game_id")[
            "start_yards_to_goal"
        ].shift(-1)
        punts = punts.merge(drive_starts, on=["game_id", "drive_number"], how="left")
        punts["net_punt_yards"] = punts["yards_to_goal"] - (
            100 - punts["next_drive_start_ytg"]
        )
        punt_agg = (
            punts.groupby(["game_id", "offense"])
            .agg(off_avg_net_punt_yards=("net_punt_yards", "mean"))
            .reset_index()
        )
    else:
        punt_agg = pd.DataFrame(
            columns=["game_id", "offense", "off_avg_net_punt_yards"]
        )

    # Calculate Field Goal stats
    fg_plays = st_plays[st_plays["st_fg"] == 1].copy()
    if not fg_plays.empty:
        fg_plays["fg_bucket"] = pd.cut(
            fg_plays["kick_distance"],
            bins=[0, 39, 49, 100],
            labels=["short", "mid", "long"],
        )
        fg_agg = (
            fg_plays.groupby(["game_id", "offense", "fg_bucket"], observed=True)
            .agg(fg_attempts=("st_fg", "count"), fg_made=("is_fg_made", "sum"))
            .reset_index()
        )
        fg_agg = fg_agg.pivot_table(
            index=["game_id", "offense"],
            columns="fg_bucket",
            values=["fg_attempts", "fg_made"],
            fill_value=0,
            observed=True,
        ).reset_index()
        fg_agg.columns = [
            f"off_{col[0]}_{col[1]}" if col[1] else col[0] for col in fg_agg.columns
        ]
        # Compute FG success rates by distance buckets
        for bucket in ["short", "mid", "long"]:
            att_col = f"off_fg_attempts_{bucket}"
            made_col = f"off_fg_made_{bucket}"
            rate_col = f"off_fg_rate_{bucket}"
            if att_col in fg_agg.columns and made_col in fg_agg.columns:
                denom = fg_agg[att_col].where(fg_agg[att_col] > 0, 1)
                fg_agg[rate_col] = fg_agg[made_col].astype(float) / denom
    else:
        fg_agg = pd.DataFrame(columns=["game_id", "offense"])

    # Merge ST stats
    st_agg = punt_agg.merge(fg_agg, on=["game_id", "offense"], how="outer").rename(
        columns={"offense": "team"}
    )
    return st_agg


def aggregate_team_game(
    plays_df: pd.DataFrame, drives_df: pd.DataFrame
) -> pd.DataFrame:
    """Aggregate play- and drive-level signals into team-game metrics.

    Ensures season/week presence on both inputs (deriving from the other if needed)
    and computes offense/defense rate statistics, explosive/play splits, line yards,
    power success, and drive-level finishing efficiency.

    Args:
        plays_df: Enriched play-level DataFrame. Required columns include at least
            season, week, game_id, offense, defense, play_number, rush_attempt,
            pass_attempt, success, yards_gained, ppa. Optional columns used when present:
            havoc, line_yards, second_level_yards, open_field_yards,
            is_power_situation, power_success_converted.
        drives_df: Drive-level DataFrame with at minimum game_id, drive_number and
            (season, week) either present or derivable; plus indicators used for
            eckel, successful/explosive/busted drive rates.

    Returns:
        DataFrame with one row per (season, week, game_id, team) containing offense
        and defense rate stats, split YPP, explosive rates, power success, and various
        drive-level rates. Includes special-teams aggregates when available.

    Raises:
        ValueError: If neither plays_df nor drives_df provide season/week to derive mapping.
    """
    # Ensure season/week are present on plays_df; if missing, derive from drives_df mapping
    if ("season" not in plays_df.columns) or ("week" not in plays_df.columns):
        season_week_map = (
            drives_df[["game_id", "season", "week"]].drop_duplicates()
            if ("season" in drives_df.columns and "week" in drives_df.columns)
            else pd.DataFrame(columns=["game_id", "season", "week"])
        )
        if not season_week_map.empty:
            plays_df = plays_df.merge(season_week_map, on="game_id", how="left")
        else:
            raise ValueError(
                "aggregate_team_game requires 'season' and 'week' columns on plays_df or drives_df"
            )

    # Ensure season/week also present on drives_df
    if ("season" not in drives_df.columns) or ("week" not in drives_df.columns):
        season_week_map = (
            plays_df[["game_id", "season", "week"]].drop_duplicates()
            if ("season" in plays_df.columns and "week" in plays_df.columns)
            else pd.DataFrame(columns=["game_id", "season", "week"])
        )
        if not season_week_map.empty:
            drives_df = drives_df.merge(season_week_map, on="game_id", how="left")
        else:
            raise ValueError(
                "aggregate_team_game requires 'season' and 'week' columns on drives_df or plays_df"
            )

    off_grp = plays_df.groupby(["season", "week", "game_id", "offense"], as_index=False)
    off_agg = off_grp.agg(
        n_off_plays=("play_number", "count"),
        n_rush_plays=("rush_attempt", "sum"),
        n_pass_plays=("pass_attempt", "sum"),
        off_sr=("success", "mean"),
        off_ypp=("yards_gained", "mean"),
        off_epa_pp=("ppa", "mean"),
        _off_rush_yards=(
            "yards_gained",
            lambda s: (
                plays_df.loc[s.index, "yards_gained"].where(
                    plays_df.loc[s.index, "rush_attempt"] == 1, 0
                ).sum()
            ),
        ),
        _off_pass_yards=(
            "yards_gained",
            lambda s: (
                plays_df.loc[s.index, "yards_gained"].where(
                    plays_df.loc[s.index, "pass_attempt"] == 1, 0
                ).sum()
            ),
        ),
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
                & (plays_df.loc[s.index, "yards_gained"] >= 15)
            ).mean(),
        ),
        off_expl_rate_pass=(
            "pass_attempt",
            lambda s: (
                (plays_df.loc[s.index, "pass_attempt"] == 1)
                & (plays_df.loc[s.index, "yards_gained"] >= 20)
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
# Compute split YPP safely
    off_denom_rush = off_agg["n_rush_plays"].where(off_agg["n_rush_plays"] > 0, 1)
    off_denom_pass = off_agg["n_pass_plays"].where(off_agg["n_pass_plays"] > 0, 1)
    off_agg["off_rush_ypp"] = off_agg["_off_rush_yards"].astype(float) / off_denom_rush
    off_agg["off_pass_ypp"] = off_agg["_off_pass_yards"].astype(float) / off_denom_pass
    off_agg = off_agg.drop(columns=["_off_rush_yards", "_off_pass_yards"]).rename(columns={"offense": "team"})

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
                & (plays_df.loc[s.index, "yards_gained"] >= 15)
            ).mean(),
        ),
        def_expl_rate_pass=(
            "pass_attempt",
            lambda s: (
                (plays_df.loc[s.index, "pass_attempt"] == 1)
                & (plays_df.loc[s.index, "yards_gained"] >= 20)
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
        off_avg_start_position=("start_yards_to_goal", "mean"),
    ).rename(columns={"offense": "team"})

    # Compute finish points per scoring opportunity safely
    denom = drv_agg["_sum_opp"].where(drv_agg["_sum_opp"] > 0, 1)
    drv_agg["off_finish_pts_per_opp"] = drv_agg["_sum_pts_on_opps"] / denom
    drv_agg = drv_agg.drop(columns=["_sum_pts_on_opps", "_sum_opp"])

    # Calculate Power Success Rate safely
    off_denom = off_agg["_power_success_situations"].where(
        off_agg["_power_success_situations"] > 0, 1
    )
    off_agg["off_power_success_rate"] = (
        off_agg["_power_success_conversions"] / off_denom
    )
    off_agg = off_agg.drop(
        columns=["_power_success_situations", "_power_success_conversions"]
    )

    def_denom = def_agg["_def_power_success_situations"].where(
        def_agg["_def_power_success_situations"] > 0, 1
    )
    def_agg["def_power_success_rate_allowed"] = (
        def_agg["_def_power_success_conversions"] / def_denom
    )
    def_agg = def_agg.drop(
        columns=["_def_power_success_situations", "_def_power_success_conversions"]
    )

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
        def_avg_start_position_allowed=("start_yards_to_goal", "mean"),
    ).rename(columns={"defense": "team"})

    # Compute defensive finish points per scoring opportunity safely
    def_denom = def_drv_agg["_def_sum_opp_allowed"].where(
        def_drv_agg["_def_sum_opp_allowed"] > 0, 1
    )
    def_drv_agg["def_finish_pts_per_opp_allowed"] = (
        def_drv_agg["_def_sum_pts_on_opps_allowed"] / def_denom
    )
    def_drv_agg = def_drv_agg.drop(
        columns=["_def_sum_pts_on_opps_allowed", "_def_sum_opp_allowed"]
    )

    # Merge all team-game aggregations
    team_game = off_agg.merge(
        def_agg, on=["season", "week", "game_id", "team"], how="outer"
    )
    team_game = team_game.merge(
        drv_agg, on=["season", "week", "game_id", "team"], how="left"
    )
    team_game = team_game.merge(
        def_drv_agg, on=["season", "week", "game_id", "team"], how="left"
    )

    # Add special teams if available
    st_agg = calculate_st_analytics_agg(plays_df, drives_df)
    if not st_agg.empty:
        team_game = team_game.merge(st_agg, on=["game_id", "team"], how="left")

# Merge defensive split YPP computed from plays
    def_denom_rush = plays_df.groupby(["season", "week", "game_id", "defense"], as_index=False)["rush_attempt"].sum()
    def_denom_pass = plays_df.groupby(["season", "week", "game_id", "defense"], as_index=False)["pass_attempt"].sum()
    def_yards_rush = plays_df.assign(rush_yards=plays_df["yards_gained"].where(plays_df["rush_attempt"] == 1, 0)).groupby(["season", "week", "game_id", "defense"], as_index=False)["rush_yards"].sum()
    def_yards_pass = plays_df.assign(pass_yards=plays_df["yards_gained"].where(plays_df["pass_attempt"] == 1, 0)).groupby(["season", "week", "game_id", "defense"], as_index=False)["pass_yards"].sum()
    def_split = def_denom_rush.merge(def_denom_pass, on=["season", "week", "game_id", "defense"], how="outer", suffixes=("_rush", "_pass"))
    def_split = def_split.merge(def_yards_rush, on=["season", "week", "game_id", "defense"], how="left")
    def_split = def_split.merge(def_yards_pass, on=["season", "week", "game_id", "defense"], how="left")
    def_split = def_split.rename(columns={"defense": "team"})
    def_split["def_rush_ypp"] = def_split["rush_yards"].astype(float) / def_split["rush_attempt"].where(def_split["rush_attempt"] > 0, 1)
    def_split["def_pass_ypp"] = def_split["pass_yards"].astype(float) / def_split["pass_attempt"].where(def_split["pass_attempt"] > 0, 1)
    team_game = team_game.merge(def_split[["season", "week", "game_id", "team", "def_rush_ypp", "def_pass_ypp"]], on=["season", "week", "game_id", "team"], how="left")
    return team_game

def aggregate_team_season(team_game_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate team-game metrics to season-to-date with recency weighting.

    Uses weights 3, 2, 1 for the last three games (most recent highest), and 1 for
    all earlier games. Aggregates a curated list of offense/defense and drive-level
    metrics when present.

    Args:
        team_game_df: Team-game DataFrame with at least season, week, team columns and
            metric columns output by aggregate_team_game.

    Returns:
        DataFrame with one row per (season, team) containing weighted averages and
        games_played. Includes cumulative_luck_factor when present.

    Raises:
        ValueError: If required identity columns are missing.
    """
    required = ["season", "week", "team"]
    for c in required:
        if c not in team_game_df.columns:
            raise ValueError(f"aggregate_team_season requires column '{c}'")

    if team_game_df.empty:
        return pd.DataFrame()

    def _apply_weights(g: pd.DataFrame) -> pd.DataFrame:
        g = g.sort_values("week").copy()
        weights = np.ones(len(g), dtype=float)
        # Assign 3,2,1 to last three games (most recent highest), earlier = 1
        for i, w in enumerate([1.0, 2.0, 3.0], start=1):
            if len(g) - i >= 0:
                weights[-i] = w
        g["recency_weight"] = weights
        return g

    # Process each season/team separately to avoid groupby.apply column loss issues
    all_weighted = []
    for (season, team), group in team_game_df.groupby(["season", "team"]):
        weighted_group = _apply_weights(group)
        all_weighted.append(weighted_group)
    weighted = pd.concat(all_weighted, ignore_index=True)

    metric_cols = [
        "off_sr",
"off_ypp",
        "off_rush_ypp",
        "off_pass_ypp",
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
        "def_rush_ypp",
        "def_pass_ypp",
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

        # Add momentum features
        last_3 = g.tail(3)
        for col in present_metric_cols:
            out[f"{col}_last_3"] = last_3[col].mean()

        last_1 = g.tail(1)
        for col in present_metric_cols:
            out[f"{col}_last_1"] = last_1[col].mean()

        out["games_played"] = float(len(g))
        if "luck_factor" in g.columns:
            out["cumulative_luck_factor"] = g["luck_factor"].sum()
        return pd.Series(out)

    season_agg = (
        weighted.groupby(["season", "team"], as_index=False)
        .apply(_agg_group, include_groups=False)
        .reset_index(drop=True)
    )
    return season_agg

def aggregate_team_season(team_game_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate team-game metrics to season-to-date with recency weighting.

    Uses weights 3, 2, 1 for the last three games (most recent highest), and 1 for
    all earlier games. Aggregates a curated list of offense/defense and drive-level
    metrics when present.

    Args:
        team_game_df: Team-game DataFrame with at least season, week, team columns and
            metric columns output by aggregate_team_game.

    Returns:
        DataFrame with one row per (season, team) containing weighted averages and
        games_played. Includes cumulative_luck_factor when present.

    Raises:
        ValueError: If required identity columns are missing.
    """
    required = ["season", "week", "team"]
    for c in required:
        if c not in team_game_df.columns:
            raise ValueError(f"aggregate_team_season requires column '{c}'")

    if team_game_df.empty:
        return pd.DataFrame()

    def _apply_weights(g: pd.DataFrame) -> pd.DataFrame:
        g = g.sort_values("week").copy()
        weights = np.ones(len(g), dtype=float)
        # Assign 3,2,1 to last three games (most recent highest), earlier = 1
        for i, w in enumerate([1.0, 2.0, 3.0], start=1):
            if len(g) - i >= 0:
                weights[-i] = w
        g["recency_weight"] = weights
        return g

    # Process each season/team separately to avoid groupby.apply column loss issues
    all_weighted = []
    for (season, team), group in team_game_df.groupby(["season", "team"]):
        weighted_group = _apply_weights(group)
        all_weighted.append(weighted_group)
    weighted = pd.concat(all_weighted, ignore_index=True)

    metric_cols = [
        "off_sr",
"off_ypp",
        "off_rush_ypp",
        "off_pass_ypp",
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
        "def_rush_ypp",
        "def_pass_ypp",
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

        # Add momentum features
        last_3 = g.tail(3)
        for col in present_metric_cols:
            out[f"{col}_last_3"] = last_3[col].mean()

        last_1 = g.tail(1)
        for col in present_metric_cols:
            out[f"{col}_last_1"] = last_1[col].mean()

        out["games_played"] = float(len(g))
        if "luck_factor" in g.columns:
            out["cumulative_luck_factor"] = g["luck_factor"].sum()
        return pd.Series(out)

    season_agg = (
        weighted.groupby(["season", "team"], as_index=False)
        .apply(_agg_group, include_groups=False)
        .reset_index(drop=True)
    )
    return season_agg


def apply_iterative_opponent_adjustment(
    team_season_df: pd.DataFrame, team_game_df: pd.DataFrame, iterations: int = 4
) -> pd.DataFrame:
    """Apply iterative opponent adjustment to season-to-date metrics.

    For each iteration, adjusts team season metrics by subtracting opponent average
    strengths (centered by league means) weighted by game recency.

    Args:
        team_season_df: Season-to-date per-team metrics (output of aggregate_team_season).
        team_game_df: Team-game metrics with recency_weight and per-game opponents.
        iterations: Number of adjustment passes (default 4 as per MVP spec).

    Returns:
        DataFrame with added adj_off_* and adj_def_* columns for metrics present in
        the inputs, leaving original off_/def_ metrics unchanged.
    """
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

    # Build recency weights (3 for most recent game, then 2, then 1; earlier = 1)
    # Avoid groupby.apply to ensure grouping columns remain intact across pandas versions
    team_game_sorted = team_game_df.sort_values(["season", "team", "week"]).copy()
    g = team_game_sorted.groupby(["season", "team"], as_index=False)
    team_game_sorted["_gsize"] = g["week"].transform("size")
    team_game_sorted["_ord"] = g["week"].cumcount()
    team_game_sorted["recency_weight"] = 1.0
    team_game_sorted.loc[
        team_game_sorted["_ord"] == team_game_sorted["_gsize"] - 1, "recency_weight"
    ] = 3.0
    team_game_sorted.loc[
        team_game_sorted["_ord"] == team_game_sorted["_gsize"] - 2, "recency_weight"
    ] = 2.0
    # third most recent remains 1.0 by default; earlier already 1.0
    team_game_weighted = team_game_sorted.drop(columns=["_gsize", "_ord"]).reset_index(drop=True)

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
                    league_means[f"off_{metric}"] = adjusted_df[
                        f"adj_off_{metric}"
                    ].mean()
                if f"adj_def_{metric}" in adjusted_df.columns:
                    league_means[f"def_{metric}"] = adjusted_df[
                        f"adj_def_{metric}"
                    ].mean()

            for metric in metrics_to_adjust:
                # Skip metrics that don't have both offensive and required columns
                off_col_name = f"off_{metric}"
                if metric in defensive_allowed_metrics:
                    def_col_name = f"def_{metric}_allowed"
                else:
                    def_col_name = f"def_{metric}"

                # Skip if required columns don't exist
                if (
                    off_col_name not in row.index
                    or def_col_name not in row.index
                    or f"off_{metric}" not in league_means
                    or f"def_{metric}" not in league_means
                ):
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
                if (
                    def_col not in team_games_with_opp_adj.columns
                    or off_col not in team_games_with_opp_adj.columns
                ):
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
