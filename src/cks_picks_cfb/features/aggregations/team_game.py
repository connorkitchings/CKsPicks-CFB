"""Team-game level aggregations and special teams analytics."""

from __future__ import annotations

import pandas as pd


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
        punts = punts.dropna(subset=["net_punt_yards"])
        if punts.empty:
            punt_agg = pd.DataFrame(
                columns=["game_id", "offense", "off_avg_net_punt_yards"]
            )
        else:
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

    # Build optional aggregation specs based on available columns
    _off_optional: dict = {}
    if "turnover" in plays_df.columns:
        _off_optional["off_turnover_rate"] = ("turnover", "mean")
    if "fumble_turnover" in plays_df.columns:
        _off_optional["off_fumble_rate"] = ("fumble_turnover", "mean")
    if "interception_turnover" in plays_df.columns:
        _off_optional["off_interception_rate"] = ("interception_turnover", "mean")
    if "penalty" in plays_df.columns:
        _off_optional["off_penalty_rate"] = ("penalty", "mean")
    if "offensive_penalty" in plays_df.columns:
        _off_optional["off_offensive_penalty_rate"] = ("offensive_penalty", "mean")
    if "sack" in plays_df.columns and "dropback" in plays_df.columns:
        _off_optional["_off_sacks"] = ("sack", "sum")
        _off_optional["_off_dropbacks"] = ("dropback", "sum")
    if "fourthdown_conversion" in plays_df.columns:
        _off_optional["off_fourth_down_conversion_rate"] = (
            "fourthdown_conversion",
            lambda x: x.mean() if not x.empty else 0,
        )
    if "down" in plays_df.columns:
        _off_optional["_off_fourth_down_attempts"] = (
            "down",
            lambda s: (plays_df.loc[s.index, "down"] == 4).sum(),
        )
    if "red_zone" in plays_df.columns and "success" in plays_df.columns:
        _off_optional["off_red_zone_sr"] = (
            "red_zone",
            lambda s: (
                plays_df.loc[s.index, "success"]
                .where(plays_df.loc[s.index, "red_zone"] == 1)
                .mean()
            ),
        )
    if "garbage" in plays_df.columns and "success" in plays_df.columns:
        _off_optional["off_non_garbage_sr"] = (
            "garbage",
            lambda s: (
                plays_df.loc[s.index, "success"]
                .where(plays_df.loc[s.index, "garbage"] == 0)
                .mean()
            ),
        )
    if "garbage" in plays_df.columns and "ppa" in plays_df.columns:
        _off_optional["off_non_garbage_epa"] = (
            "garbage",
            lambda s: (
                plays_df.loc[s.index, "ppa"]
                .where(plays_df.loc[s.index, "garbage"] == 0)
                .mean()
            ),
        )
    if "fourth_quarter" in plays_df.columns and "success" in plays_df.columns:
        _off_optional["off_fourth_quarter_sr"] = (
            "fourth_quarter",
            lambda s: (
                plays_df.loc[s.index, "success"]
                .where(plays_df.loc[s.index, "fourth_quarter"] == 1)
                .mean()
            ),
        )
    if "close_game" in plays_df.columns and "success" in plays_df.columns:
        _off_optional["off_close_game_sr"] = (
            "close_game",
            lambda s: (
                plays_df.loc[s.index, "success"]
                .where(plays_df.loc[s.index, "close_game"] == 1)
                .mean()
            ),
        )
    if "td_play" in plays_df.columns:
        _off_optional["off_td_rate"] = ("td_play", "mean")
    if "big_play_40" in plays_df.columns:
        _off_optional["off_40_plus_yard_rate"] = ("big_play_40", "mean")
    if "kickoff_touchback" in plays_df.columns and "st_kickoff" in plays_df.columns:
        _off_optional["_off_kickoffs"] = ("st_kickoff", "sum")
        _off_optional["_off_touchbacks"] = ("kickoff_touchback", "sum")
    if "kickoff_return" in plays_df.columns and "yards_gained" in plays_df.columns:
        _off_optional["_off_kickoff_return_yards"] = (
            "kickoff_return",
            lambda s: (
                plays_df.loc[s.index, "yards_gained"]
                .where(plays_df.loc[s.index, "kickoff_return"] == 1)
                .sum()
            ),
        )
        _off_optional["_off_kickoff_returns"] = ("kickoff_return", "sum")

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
                plays_df.loc[s.index, "yards_gained"]
                .where(plays_df.loc[s.index, "rush_attempt"] == 1, 0)
                .sum()
            ),
        ),
        _off_pass_yards=(
            "yards_gained",
            lambda s: (
                plays_df.loc[s.index, "yards_gained"]
                .where(plays_df.loc[s.index, "pass_attempt"] == 1, 0)
                .sum()
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
        off_third_down_conversion_rate=(
            "thirddown_conversion",
            lambda x: x.mean() if not x.empty else 0,
        ),
        **_off_optional,
    )
    # Compute split YPP safely
    off_denom_rush = off_agg["n_rush_plays"].where(off_agg["n_rush_plays"] > 0, 1)
    off_denom_pass = off_agg["n_pass_plays"].where(off_agg["n_pass_plays"] > 0, 1)
    off_agg["off_rush_ypp"] = off_agg["_off_rush_yards"].astype(float) / off_denom_rush
    off_agg["off_pass_ypp"] = off_agg["_off_pass_yards"].astype(float) / off_denom_pass

    # Compute sack rate (sacks per dropback) and fourth down attempt rate
    _drop_cols = ["_off_rush_yards", "_off_pass_yards"]
    if "_off_sacks" in off_agg.columns and "_off_dropbacks" in off_agg.columns:
        off_agg["off_sack_rate"] = off_agg["_off_sacks"].astype(float) / off_agg[
            "_off_dropbacks"
        ].where(off_agg["_off_dropbacks"] > 0, 1)
        _drop_cols += ["_off_sacks", "_off_dropbacks"]
    if "_off_fourth_down_attempts" in off_agg.columns:
        total_plays = off_agg["n_off_plays"].where(off_agg["n_off_plays"] > 0, 1)
        off_agg["off_fourth_down_attempt_rate"] = (
            off_agg["_off_fourth_down_attempts"].astype(float) / total_plays
        )
        _drop_cols.append("_off_fourth_down_attempts")

    if "_off_kickoffs" in off_agg.columns and "_off_touchbacks" in off_agg.columns:
        off_agg["off_touchback_rate"] = off_agg["_off_touchbacks"].astype(
            float
        ) / off_agg["_off_kickoffs"].where(off_agg["_off_kickoffs"] > 0, 1)
        _drop_cols += ["_off_kickoffs", "_off_touchbacks"]
    if "_off_kickoff_return_yards" in off_agg.columns:
        off_returns = off_agg["_off_kickoff_returns"].where(
            off_agg["_off_kickoff_returns"] > 0, 1
        )
        off_agg["off_kick_return_avg_yards"] = (
            off_agg["_off_kickoff_return_yards"].astype(float) / off_returns
        )
        _drop_cols += ["_off_kickoff_return_yards", "_off_kickoff_returns"]

    off_agg = off_agg.drop(columns=_drop_cols).rename(columns={"offense": "team"})

    _def_optional: dict = {}
    if "turnover" in plays_df.columns:
        _def_optional["def_turnover_rate"] = ("turnover", "mean")
    if "penalty" in plays_df.columns:
        _def_optional["def_penalty_rate"] = ("penalty", "mean")
    if "defensive_penalty" in plays_df.columns:
        _def_optional["def_defensive_penalty_rate"] = ("defensive_penalty", "mean")
    if "sack" in plays_df.columns and "dropback" in plays_df.columns:
        _def_optional["_def_sacks"] = ("sack", "sum")
        _def_optional["_def_dropbacks"] = ("dropback", "sum")
    if "red_zone" in plays_df.columns and "success" in plays_df.columns:
        _def_optional["def_red_zone_sr"] = (
            "red_zone",
            lambda s: (
                plays_df.loc[s.index, "success"]
                .where(plays_df.loc[s.index, "red_zone"] == 1)
                .mean()
            ),
        )
    if "garbage" in plays_df.columns and "success" in plays_df.columns:
        _def_optional["def_non_garbage_sr"] = (
            "garbage",
            lambda s: (
                plays_df.loc[s.index, "success"]
                .where(plays_df.loc[s.index, "garbage"] == 0)
                .mean()
            ),
        )
    if "fourth_quarter" in plays_df.columns and "success" in plays_df.columns:
        _def_optional["def_fourth_quarter_sr"] = (
            "fourth_quarter",
            lambda s: (
                plays_df.loc[s.index, "success"]
                .where(plays_df.loc[s.index, "fourth_quarter"] == 1)
                .mean()
            ),
        )
    if "td_play" in plays_df.columns:
        _def_optional["def_td_rate_allowed"] = ("td_play", "mean")
    if "big_play_40" in plays_df.columns:
        _def_optional["def_40_plus_yard_rate_allowed"] = ("big_play_40", "mean")

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
        def_third_down_conversion_rate=(
            "thirddown_conversion",
            lambda x: x.mean() if not x.empty else 0,
        ),
        **_def_optional,
    )

    # Compute defensive sack rate
    _def_drop_cols: list[str] = []
    if "_def_sacks" in def_agg.columns and "_def_dropbacks" in def_agg.columns:
        def_agg["def_sack_rate"] = def_agg["_def_sacks"].astype(float) / def_agg[
            "_def_dropbacks"
        ].where(def_agg["_def_dropbacks"] > 0, 1)
        _def_drop_cols += ["_def_sacks", "_def_dropbacks"]
    if _def_drop_cols:
        def_agg = def_agg.drop(columns=_def_drop_cols)
    def_agg = def_agg.rename(columns={"defense": "team"})

    drv_grp = drives_df.groupby(
        ["season", "week", "game_id", "offense"], as_index=False
    )
    drv_agg_kwargs = dict(
        off_drives=("drive_number", "count"),
        off_eckel_rate=("is_eckel_drive", "mean"),
        off_successful_drive_rate=("is_successful_drive", "mean"),
        off_busted_drive_rate=("is_busted_drive", "mean"),
        off_explosive_drive_rate=("is_explosive_drive", "mean"),
        _sum_pts_on_opps=("points_on_opps", "sum"),
        _sum_opp=("had_scoring_opportunity", "sum"),
        off_avg_start_position=("start_yards_to_goal", "mean"),
    )
    if "points" in drives_df.columns:
        drv_agg_kwargs["off_points_scored"] = ("points", "sum")
    drv_agg = drv_grp.agg(**drv_agg_kwargs).rename(columns={"offense": "team"})

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
    def_drv_agg_kwargs = dict(
        def_drives_allowed=("drive_number", "count"),
        def_eckel_rate_allowed=("is_eckel_drive", "mean"),
        def_successful_drive_rate_allowed=("is_successful_drive", "mean"),
        def_busted_drive_rate_allowed=("is_busted_drive", "mean"),
        def_explosive_drive_rate_allowed=("is_explosive_drive", "mean"),
        _def_sum_pts_on_opps_allowed=("points_on_opps", "sum"),
        _def_sum_opp_allowed=("had_scoring_opportunity", "sum"),
        def_avg_start_position_allowed=("start_yards_to_goal", "mean"),
    )
    if "points" in drives_df.columns:
        def_drv_agg_kwargs["def_points_allowed"] = ("points", "sum")
    def_drv_agg = def_drv_grp.agg(**def_drv_agg_kwargs).rename(
        columns={"defense": "team"}
    )

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
    st_cols = [
        c
        for c in team_game.columns
        if c.startswith("off_fg_")
        or c.startswith("off_avg_net_punt_yards")
        or c.startswith("off_avg_net_kick_")
    ]
    if st_cols:
        team_game[st_cols] = team_game[st_cols].fillna(0)

    # Merge defensive split YPP computed from plays
    def_denom_rush = plays_df.groupby(
        ["season", "week", "game_id", "defense"], as_index=False
    )["rush_attempt"].sum()
    def_denom_pass = plays_df.groupby(
        ["season", "week", "game_id", "defense"], as_index=False
    )["pass_attempt"].sum()
    def_yards_rush = (
        plays_df.assign(
            rush_yards=plays_df["yards_gained"].where(plays_df["rush_attempt"] == 1, 0)
        )
        .groupby(["season", "week", "game_id", "defense"], as_index=False)["rush_yards"]
        .sum()
    )
    def_yards_pass = (
        plays_df.assign(
            pass_yards=plays_df["yards_gained"].where(plays_df["pass_attempt"] == 1, 0)
        )
        .groupby(["season", "week", "game_id", "defense"], as_index=False)["pass_yards"]
        .sum()
    )
    def_split = def_denom_rush.merge(
        def_denom_pass,
        on=["season", "week", "game_id", "defense"],
        how="outer",
        suffixes=("_rush", "_pass"),
    )
    def_split = def_split.merge(
        def_yards_rush, on=["season", "week", "game_id", "defense"], how="left"
    )
    def_split = def_split.merge(
        def_yards_pass, on=["season", "week", "game_id", "defense"], how="left"
    )
    def_split = def_split.rename(columns={"defense": "team"})
    def_split["def_rush_ypp"] = def_split["rush_yards"].astype(float) / def_split[
        "rush_attempt"
    ].where(def_split["rush_attempt"] > 0, 1)
    def_split["def_pass_ypp"] = def_split["pass_yards"].astype(float) / def_split[
        "pass_attempt"
    ].where(def_split["pass_attempt"] > 0, 1)
    team_game = team_game.merge(
        def_split[
            ["season", "week", "game_id", "team", "def_rush_ypp", "def_pass_ypp"]
        ],
        on=["season", "week", "game_id", "team"],
        how="left",
    )

    # Derived drive/field-position features (safe divisions)
    if "off_points_scored" in team_game.columns and "off_drives" in team_game.columns:
        team_game["off_points_per_drive"] = team_game["off_points_scored"].astype(
            float
        ) / team_game["off_drives"].replace(0, 1)
    if (
        "def_points_allowed" in team_game.columns
        and "def_drives_allowed" in team_game.columns
    ):
        team_game["def_points_per_drive_allowed"] = team_game[
            "def_points_allowed"
        ].astype(float) / team_game["def_drives_allowed"].replace(0, 1)

    if "off_avg_start_position" in team_game.columns:
        team_game["off_avg_start_field_position"] = 100 - team_game[
            "off_avg_start_position"
        ].astype(float)
    if "def_avg_start_position_allowed" in team_game.columns:
        team_game["def_avg_start_field_position_allowed"] = 100 - team_game[
            "def_avg_start_position_allowed"
        ].astype(float)
    if (
        "off_avg_start_field_position" in team_game.columns
        and "def_avg_start_field_position_allowed" in team_game.columns
    ):
        team_game["net_field_position_delta"] = (
            team_game["off_avg_start_field_position"]
            - team_game["def_avg_start_field_position_allowed"]
        )
    return team_game
