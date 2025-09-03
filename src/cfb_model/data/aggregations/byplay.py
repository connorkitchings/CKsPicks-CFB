from __future__ import annotations

import numpy as np
import pandas as pd


def update_yards_gained(row: pd.Series) -> int | float:
    """Standardize yards_gained for fumble plays to ensure offensive stats are consistent."""
    play_type = str(row.get("play_type", ""))
    yards_gained = row.get("yards_gained", 0)
    if "fumble recovery (touchdown)" in play_type.lower() and yards_gained != 0:
        return 0
    if "fumble recovery (opponent)" in play_type.lower():
        return 0
    return yards_gained


def calculate_explosive(row: pd.Series) -> int | None:
    """Flag explosive plays based on rush/pass yard thresholds."""
    play_type = row.get("play_type")
    yards_gained = row.get("yards_gained", 0)
    rush_result = row.get("rush_result", 0)
    pass_attempt = row.get("pass_attempt", 0)

    if play_type in [
        "Rush",
        "Rushing Touchdown",
        "Fumble Recovery (Own)",
        "Pass",
        "Pass Reception",
        "Pass Incompletion",
        "Passing Touchdown",
        "Sack",
        "Safety",
    ]:
        if rush_result == 1 and yards_gained >= 15:
            return 1
        if pass_attempt == 1 and yards_gained >= 20:
            return 1
        return 0
    if play_type in [
        "Fumble Recovery (Opponent)",
        "Fumble Return Touchdown",
        "Pass Interception Return",
        "Interception Return Touchdown",
        "Safety",
        "Interception",
    ]:
        return 0
    return None


def calculate_play_success(row: pd.Series) -> int | None:
    """Determine success by down-and-distance criteria."""
    down = row.get("down", 0)
    yards_gained = row.get("yards_gained", 0)
    yards_to_first = row.get("yards_to_first", 0)
    play_type = row.get("play_type")
    turnover = row.get("turnover", 0)
    penalty = row.get("penalty", 0)

    if play_type in [
        "Rush",
        "Rushing Touchdown",
        "Fumble Recovery (Own)",
        "Pass",
        "Pass Reception",
        "Pass Incompletion",
        "Passing Touchdown",
        "Sack",
        "Safety",
    ]:
        if yards_to_first == 0:
            if down == 1 and yards_gained >= (0.5 * row.get("yards_to_goal", 0)):
                return 1
            if down == 2 and yards_gained >= (0.7 * row.get("yards_to_goal", 0)):
                return 1
            if down in (3, 4) and yards_gained >= row.get("yards_to_goal", 0):
                return 1
            return 0
        if yards_to_first > 0:
            if down == 1 and yards_gained >= (0.5 * yards_to_first):
                return 1
            if down == 2 and yards_gained >= (0.7 * yards_to_first):
                return 1
            if down in (3, 4) and yards_gained >= yards_to_first:
                return 1
            if down == 1 and yards_gained >= (0.5 * row.get("yards_to_goal", 0)):
                return 1
            if down == 2 and yards_gained >= (0.7 * row.get("yards_to_goal", 0)):
                return 1
            if down in (3, 4) and yards_gained >= row.get("yards_to_goal", 0):
                return 1
            return 0
        return 0
    if turnover == 1:
        return 0
    if penalty == 1:
        return None
    return None


def calculate_time_features(data: pd.DataFrame) -> pd.DataFrame:
    """Compute time-remaining features and play durations; mask noisy contexts."""
    df = data.copy()
    df = df.sort_values(
        by=["season", "week", "game_id", "quarter", "drive_number", "play_number"],
        ascending=[True, True, True, True, True, True],
    ).reset_index(drop=True)

    if (
        df.get("clock_minutes", pd.Series([0])).max() > 15
        or df.get("clock_seconds", pd.Series([0])).max() >= 60
    ):
        print("Warning: Some clock values seem to be out of range.")

    df["clock_minutes_in_secs"] = np.where(
        df["quarter"] <= 4,
        (4 - df["quarter"]) * 15 * 60 + (df["clock_minutes"] * 60),
        0,
    )
    df["time_remaining_after"] = df["clock_minutes_in_secs"] + df["clock_seconds"]
    df["time_remaining_before"] = df.groupby("game_id")["time_remaining_after"].shift(1)
    df.loc[
        (df["drive_number"] == 1) & (df["play_number"] == 1), "time_remaining_before"
    ] = 3600

    df["play_duration"] = (
        pd.to_numeric(df["time_remaining_before"], errors="coerce")
        - pd.to_numeric(df["time_remaining_after"], errors="coerce")
    ).astype(float)

    min_dur = pd.Series(df["play_duration"], dtype="float64").min(skipna=True)
    if pd.notna(min_dur) and min_dur < 0:
        print(
            "Warning: Some play durations are negative. This might indicate an issue with the time calculation."
        )

    mask_invalid_context = (
        (df.get("penalty", 0) == 1)
        | (df.get("st", 0) == 1)
        | (df.get("twopoint", 0) == 1)
    )
    df.loc[mask_invalid_context, "play_duration"] = np.nan
    df.loc[df["play_duration"] <= 0, "play_duration"] = np.nan
    df.loc[df["play_duration"] >= 60, "play_duration"] = np.nan
    return df


def assign_drive_numbers(
    df: pd.DataFrame,
    kickoff_types: list[str],
    end_of_drive_types: list[str],
) -> pd.DataFrame:
    """Assign drive numbers using possession changes and end-of-drive events."""
    required_cols = [
        "game_id",
        "offense",
        "defense",
        "play_type",
        "quarter",
        "play_number",
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"assign_drive_numbers missing required columns: {missing}")

    df = df.sort_values(by=["game_id", "quarter", "play_number"]).copy()
    df["drive_number"] = np.nan

    def _assign(group: pd.DataFrame) -> pd.DataFrame:
        current_drive = 0
        last_offense = None
        last_end_of_drive = True
        rows = []
        for _, row in group.iterrows():
            play_type = row["play_type"]
            offense = row["offense"]
            start_new = False
            if last_offense is None:
                start_new = True
            elif offense != last_offense:
                start_new = True
            elif last_end_of_drive:
                start_new = True
            elif play_type in kickoff_types:
                start_new = True
            if start_new:
                current_drive += 1
            row_out = row.copy()
            row_out["drive_number"] = current_drive
            last_end_of_drive = (
                (play_type in end_of_drive_types)
                or bool(row.get("scoring", False))
                or bool(row.get("turnover", 0))
            )
            last_offense = offense
            rows.append(row_out)
        return pd.DataFrame(rows)

    df = df.groupby("game_id").apply(_assign, include_groups=False).reset_index()
    df["drive_number"] = df["drive_number"].astype(int)
    return df


def calculate_rushing_analytics(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate advanced rushing metrics like Line Yards, Power Success, etc."""
    df_copy = df.copy()

    # Define conditions for rushing plays
    is_rush = df_copy['rush_attempt'] == 1

    # --- Line Yards ---
    # Apply the formula only to rushing plays
    yards_gained = df_copy.loc[is_rush, 'yards_gained']
    line_yards = pd.Series(np.nan, index=df_copy.index)

    # Conditions for line yards calculation
    cond_loss = yards_gained < 0
    cond_0_4 = (yards_gained >= 0) & (yards_gained <= 4)
    cond_5_10 = (yards_gained > 4) & (yards_gained <= 10)
    cond_gt_10 = yards_gained > 10

    # Apply calculations
    line_yards.loc[is_rush & cond_loss] = yards_gained * 1.2
    line_yards.loc[is_rush & cond_0_4] = yards_gained
    line_yards.loc[is_rush & cond_5_10] = 4 + (yards_gained - 4) * 0.5
    line_yards.loc[is_rush & cond_gt_10] = 7
    
    df_copy['line_yards'] = line_yards

    # --- Power Success ---
    is_power_situation = (df_copy['down'].isin([3, 4])) & (df_copy['yards_to_first'] <= 2)
    df_copy['is_power_situation'] = is_power_situation & is_rush
    
    is_converted = df_copy['success'] == 1
    df_copy['power_success_converted'] = df_copy['is_power_situation'] & is_converted

    # --- Second Level & Open Field Yards ---
    second_level_yards = pd.Series(np.nan, index=df_copy.index)
    open_field_yards = pd.Series(np.nan, index=df_copy.index)

    second_level_yards.loc[is_rush] = (df_copy.loc[is_rush, 'yards_gained'].clip(lower=5, upper=10) - 5)
    open_field_yards.loc[is_rush] = (df_copy.loc[is_rush, 'yards_gained'].clip(lower=10) - 10)
    
    df_copy['second_level_yards'] = second_level_yards
    df_copy['open_field_yards'] = open_field_yards

    return df_copy

def calculate_st_analytics(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate advanced special teams metrics."""
    df_copy = df.copy()

    # --- Field Goal Analytics ---
    is_fg = df_copy['st_fg'] == 1
    df_copy['kick_distance'] = np.nan
    df_copy.loc[is_fg, 'kick_distance'] = df_copy.loc[is_fg, 'yard_line'] + 17
    df_copy['is_fg_made'] = (df_copy['play_type'] == 'Field Goal Good').astype(int)

    return df_copy


def allplays_to_byplay(data: pd.DataFrame) -> pd.DataFrame:
    """Transform raw plays into enriched by-play dataset."""
    df = data.copy()

    # --- Normalize column names first ---
    if "yards_to_first" not in df.columns and "distance" in df.columns:
        df["yards_to_first"] = df["distance"]
    if "quarter" not in df.columns and "period" in df.columns:
        df["quarter"] = df["period"]
    if "yard_line" not in df.columns and "yardline" in df.columns:
        df["yard_line"] = df["yardline"]

    # --- Pre-computation Checks ---
    required_cols = ["season", "week", "game_id", "quarter", "play_number"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(
            f"Input DataFrame is missing required columns for sorting and time features: {missing_cols}"
        )



    df["play_type"] = (
        df.get("play_type", "Uncategorized").fillna("Uncategorized").astype(str)
    )
    for col in [
        "yards_gained",
        "yards_to_first",
        "yards_to_goal",
        "yard_line",
        "offense_score",
        "defense_score",
        "ppa",
        "down",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    for col in ["season", "week", "game_id", "quarter", "play_number"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    st_kickoffs = ["Kickoff", "Kickoff Return (Offense)", "Kickoff Return Touchdown"]
    st_punts = [
        "Punt",
        "Blocked Punt",
        "Punt Return Touchdown",
        "Blocked Punt Touchdown",
    ]
    st_fg = [
        "Field Goal Good",
        "Field Goal Missed",
        "Blocked Field Goal",
        "Missed Field Goal Return",
        "Missed Field Goal Return Touchdown",
        "Blocked Field Goal Touchdown",
    ]
    st_extrapoint = ["Extra Point Good", "Extra Point Missed"]
    twopoint_list = ["Two Point Pass", "Two Point Rush", "Defensive 2pt Conversion"]
    st_list = st_kickoffs + st_punts + st_fg + st_extrapoint
    endofdrive = [
        "Punt",
        "Field Goal Good",
        "Field Goal Missed",
        "Blocked Field Goal",
        "Blocked Punt",
        "Punt Return Touchdown",
        "Blocked Punt Touchdown",
        "Missed Field Goal Return",
        "Blocked Field Goal Touchdown",
        "Missed Field Goal Return Touchdown",
    ]
    turnover_list = [
        "Interception",
        "Interception Return Touchdown",
        "Pass Interception Return",
        "Fumble Recovery (Opponent)",
        "Fumble Return Touchdown",
    ]
    rushattempt_list = ["Rush", "Rushing Touchdown"]
    rushresult_list = ["Rush", "Rushing Touchdown", "Sack", "Safety"]
    dropback_list = [
        "Pass",
        "Interception",
        "Interception Return Touchdown",
        "Pass Interception Return",
        "Passing Touchdown",
        "Pass Incompletion",
        "Pass Reception",
        "Sack",
    ]
    passattempt_list = [
        "Pass",
        "Pass Completion",
        "Interception",
        "Interception Return Touchdown",
        "Pass Interception Return",
        "Passing Touchdown",
        "Pass Incompletion",
        "Pass Reception",
    ]
    completion_list = ["Pass Reception", "Pass Completion", "Pass", "Passing Touchdown"]
    playtype_delete = ["Timeout", "Uncategorized", "placeholder", "End Period"]
    havoc_list = [
        "Fumble Recovery (Opponent)",
        "Fumble Return Touchdown",
        "Fumble Recovery (Own)",
        "Pass Incompletion",
        "Interception",
        "Interception Return Touchdown",
        "Pass Interception Return",
    ]

    df["relative_score"] = df["offense_score"] - df["defense_score"]
    df["half"] = np.select(
        [df["quarter"].isin([1, 2]), df["quarter"].isin([3, 4])], [1, 2], default=3
    )
    df["home_away"] = np.where(
        df["offense"] == df.get("home", df["offense"]), "home", "away"
    )

    df["penalty"] = (df["play_type"] == "Penalty").astype(int)
    df["defensive_penalty"] = (
        (df["play_type"] == "Penalty") & (df["yards_gained"] > 0)
    ).astype(int)
    df["offensive_penalty"] = (
        (df["play_type"] == "Penalty") & (df["yards_gained"] < 0)
    ).astype(int)

    binary_columns = {
        "st_kickoff": st_kickoffs,
        "st_punt": st_punts,
        "st_fg": st_fg,
        "st": st_list,
        "endofdrive": endofdrive,
        "twopoint": twopoint_list,
        "turnover": turnover_list,
        "rush_attempt": rushattempt_list,
        "rush_result": rushresult_list,
        "dropback": dropback_list,
        "pass_attempt": passattempt_list,
    }
    for col, play_types in binary_columns.items():
        df[col] = df["play_type"].isin(play_types).astype(int)

    if "drive_number" not in df.columns or df["drive_number"].isna().any():
        df = assign_drive_numbers(
            df, kickoff_types=st_kickoffs, end_of_drive_types=endofdrive
        )
    if "drive_id" not in df.columns:
        df["drive_id"] = (
            df["game_id"].astype(str) + "-" + df["drive_number"].astype(int).astype(str)
        )

    df["red_zone"] = (df["yards_to_goal"] <= 20).astype(int)
    df["eckel"] = ((df["yards_to_goal"] < 40) & (df["down"] == 1)).astype(int)

    df["updated_yards_gained"] = df.apply(update_yards_gained, axis=1)
    df["TFL"] = ((df["penalty"] == 0) & (df["updated_yards_gained"] < 0)).astype(int)
    df["sack"] = (df["play_type"] == "Sack").astype(int)
    df["completion"] = (df["play_type"].isin(completion_list)).astype(int)

    df["success"] = df.apply(calculate_play_success, axis=1)
    df["explosive"] = df.apply(calculate_explosive, axis=1)
    df["success_yards"] = np.where(df["success"] == 1, df["updated_yards_gained"], 0)
    df["explosive_yards"] = np.where(
        df["explosive"] == 1, df["updated_yards_gained"], 0
    )
    df = calculate_rushing_analytics(df)
    df = calculate_st_analytics(df)
    df["stuff"] = (
        (df["rush_attempt"] == 1) & (df["updated_yards_gained"] <= 0)
    ).astype(int)

    df["havoc"] = (
        df["play_type"].isin(havoc_list) | (df["updated_yards_gained"] < 0)
    ).astype(int)
    df.loc[df["penalty"] == 1, "havoc"] = 0

    df["thirddown_conversion"] = np.where(
        df["down"] == 3, np.where(df["success"] == 1, 1, 0), None
    )
    df["fourthdown_conversion"] = np.where(
        df["down"] == 4, np.where(df["success"] == 1, 1, 0), None
    )

    non_count_types = ["Timeout", "Uncategorized", "placeholder", "End Period"]
    df["is_drive_play"] = (
        (df["st"] == 0)
        & (df["penalty"] == 0)
        & (df["twopoint"] == 0)
        & (~df["play_type"].isin(non_count_types))
    ).astype(int)

    if "adj_yd_line" not in df.columns:
        df["adj_yd_line"] = df.get("yards_to_goal", df.get("yard_line"))

    df = df.drop(columns=["yards_gained"]).rename(
        columns={"updated_yards_gained": "yards_gained"}
    )
    df = df.sort_values(
        by=["season", "week", "game_id", "quarter", "drive_number", "play_number"]
    )
    df = calculate_time_features(df)

    def calculate_garbage_time(df_inner: pd.DataFrame) -> pd.Series:
        df_inner["garbage"] = False
        second_half = df_inner["quarter"] > 2
        df_inner.loc[
            second_half
            & (df_inner["quarter"] == 3)
            & (abs(df_inner["relative_score"]) >= 35),
            "garbage",
        ] = True
        fourth_quarter = second_half & (df_inner["quarter"] == 4)
        df_inner.loc[
            fourth_quarter & (abs(df_inner["relative_score"]) >= 27), "garbage"
        ] = True
        return df_inner["garbage"].astype(int)

    df["garbage"] = calculate_garbage_time(df)

    df["field_position_bin"] = pd.cut(
        df["yard_line"],
        bins=[0, 20, 50, 80, 100],
        labels=["Own Red Zone", "Own", "Opponent", "Red Zone"],
    )
    df["passing_down"] = np.where(
        ((df["down"] == 2) & (df["yards_to_first"] >= 8))
        | ((df["down"].isin([3, 4])) & (df["yards_to_first"] >= 5)),
        1,
        0,
    )

    column_order = [
        "season",
        "week",
        "game_id",
        "offense",
        "defense",
        "home_away",
        "relative_score",
        "offense_score",
        "defense_score",
        "half",
        "quarter",
        "offense_timeouts",
        "defense_timeouts",
        "drive_id",
        "drive_number",
        "play_number",
        "garbage",
        "yard_line",
        "yards_to_goal",
        "adj_yd_line",
        "field_position_bin",
        "down",
        "yards_to_first",
        "passing_down",
        "red_zone",
        "eckel",
        "scoring",
        "play_type",
        "play_text",
        "penalty",
        "offensive_penalty",
        "defensive_penalty",
        "st",
        "st_kickoff",
        "st_punt",
        "st_fg",
        "endofdrive",
        "twopoint",
        "turnover",
        "rush_attempt",
        "rush_result",
        "dropback",
        "pass_attempt",
        "yards_gained",
        "ppa",
        "TFL",
        "sack",
        "completion",
        "success",
        "success_yards",
        "explosive",
        "explosive_yards",
        "stuff",
        "havoc",
        "thirddown_conversion",
        "fourthdown_conversion",
        "clock_minutes",
        "clock_minutes_in_secs",
        "clock_seconds",
        "time_remaining_after",
        "time_remaining_before",
        "play_duration",
        "line_yards",
        "is_power_situation",
        "power_success_converted",
        "second_level_yards",
        "open_field_yards",
        "kick_distance",
        "is_fg_made",
    ]
    df = df[column_order].copy()
    df = df[~df["play_type"].isin(playtype_delete)].copy()
    df["ppa"] = pd.to_numeric(df["ppa"], errors="coerce")

    df.loc[
        df["play_type"].isin(["Fumble Recovery (Own)", "Fumble Recovery (Opponent)"]),
        "rush_attempt",
    ] = 1
    df.loc[
        df["play_type"].isin(["Fumble Recovery (Own)", "Fumble Recovery (Opponent)"]),
        "rush_result",
    ] = 1
    df.loc[df["play_type"].isin(["Fumble Recovery (Opponent)"]), "yards_gained"] = 0
    return df
