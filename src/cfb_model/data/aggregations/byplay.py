from __future__ import annotations

import numpy as np
import pandas as pd


def apply_manual_data_fixes(df: pd.DataFrame) -> pd.DataFrame:
    """Apply a list of hardcoded data corrections for known errors in raw data."""
    conditions_and_updates = [
        ((400937467, 1, 5), {"yards_gained": 15, "play_type": "Penalty"}),
        ((400547851, 11, 6), {"yards_gained": 15, "play_type": "Penalty"}),
        ((400547737, 9, 1), {"yards_to_first": 1}),
        (
            (400547737, 9, 2),
            {
                "yard_line": 2,
                "yards_to_goal": 98,
                "yards_to_first": 9,
                "yards_gained": -1,
                "adj_yd_line": 98,
            },
        ),
        ((400547737, 9, 3), {"yards_to_first": 10}),
        ((400547739, 11, 14), {"yards_gained": -5}),
        (
            (400547739, 11, 15),
            {"yard_line": 82, "yards_to_goal": 18, "yards_to_first": 18, "adj_yd_line": 18},
        ),
        (
            (400547739, 11, 16),
            {"yard_line": 82, "yards_to_goal": 18, "yards_to_first": 18, "adj_yd_line": 18},
        ),
        ((400869843, 27, 9), {"yards_gained": -5}),
        ((400869843, 27, 10), {"yard_line": 78, "yards_to_goal": 22}),
        ((401237102, 4), {"offense": "Texas A&M", "defense": "Florida"}),
        ((401237102, 4, 8), {"play_number": 5}),
        ((401237102, 4, 9), {"play_number": 6}),
        ((401237102, 4, 10), {"play_number": 7}),
        ((401237102, 4, 11), {"play_number": 8}),
        ((401237102, 4, 12), {"play_number": 9}),
        ((401237102, 4, 13), {"play_number": 10}),
        ((401237102, 4, 14), {"play_number": 11}),
        ((401237102, 4, 15), {"play_number": 12}),
        ((401237102, 4, 16), {"play_number": 13}),
        ((401237102, 4, 17), {"play_number": 14}),
        ((401237102, 4, 18), {"play_number": 15}),
        ((401237102, 4, 29), {"play_number": 16}),
        ((400869850, 26, 15), {"yards_gained": -5}),
        ((401013353, 23, 4), {"yards_gained": -5}),
        ((400869264, 9, 1), {"yards_gained": -5}),
        ((401114260, 11, 5), {"yards_gained": -5}),
        ((401282206, 9, 6), {"yards_gained": -15}),
        ((401405102, 14, 4), {"yards_gained": -15}),
        ((401282189, 6, 7), {"yards_gained": -15}),
        ((401309577, 22, 1), {"yards_gained": -15}),
        ((400548020, 16, 10), {"yards_gained": -5}),
        ((401403927, 9, 3), {"yards_gained": -15}),
        ((400787353, 3, 5), {"yards_gained": -5}),
        ((400869721, 19, 5), {"yards_gained": -15}),
        ((401310733, 6, 8), {"yards_gained": 0}),
        ((401287949, 4, 3), {"yards_gained": -9}),
        ((401309639, 19, 5), {"yards_gained": 0}),
        ((401282215, 26, 10), {"yards_gained": 0}),
        ((401119278, 26, 7), {"yards_gained": 0}),
        ((401121957, 28, 4), {"yards_gained": -10}),
        ((400941829, 25, 2), {"play_type": "Penalty", "yards_gained": -10}),
        ((400869041, 18, 8), {"yards_gained": -9}),
        ((400547743, 21, 3), {"yards_gained": 15}),
        ((401117876, 8, 5), {"yards_gained": 0}),
        ((401022561, 20, 11), {"yards_gained": 15}),
        (
            (401643724, 22, 15),
            {"yard_line": 25, "yards_to_goal": 25, "yards_to_first": 25, "adj_yd_line": 25},
        ),
    ]
    for condition, updates in conditions_and_updates:
        game_id, drive_number, *play_number_list = condition
        play_number = play_number_list[0] if play_number_list else None

        if play_number is None:
            condition_mask = (df["game_id"] == game_id) & (df["drive_number"] == drive_number)
        else:
            condition_mask = (
                (df["game_id"] == game_id)
                & (df["drive_number"] == drive_number)
                & (df["play_number"] == play_number)
            )
        if condition_mask.any():
            for col, value in updates.items():
                df.loc[condition_mask, col] = value
    return df


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

    # Calculate total time remaining in the game after this play
    # Time = (quarters remaining after this one) * 15 minutes + current quarter time remaining
    df["time_remaining_after"] = np.where(
        df["quarter"] <= 4,
        # Quarters remaining after current quarter * 15 minutes + time left in current quarter
        (4 - df["quarter"]) * 15 * 60 + (df["clock_minutes"] * 60 + df["clock_seconds"]),
        # For overtime, just use the clock time (assuming 15 minute OT periods)
        df["clock_minutes"] * 60 + df["clock_seconds"]
    )
    # Calculate time_remaining_before with quarter boundary awareness
    df["time_remaining_before"] = np.nan
    # Process each game separately to handle quarter transitions properly
    for game_id, game_group in df.groupby("game_id"):
        game_df = game_group.copy().reset_index(drop=True)
        for idx in range(len(game_df)):
            if idx == 0:
                # First play of the game
                df.loc[game_df.index[idx], "time_remaining_before"] = 3600  # 60 minutes
            else:
                current_quarter = game_df.iloc[idx]["quarter"]
                prev_quarter = game_df.iloc[idx - 1]["quarter"]
                if current_quarter == prev_quarter:
                    # Same quarter: use previous play's time_remaining_after
                    df.loc[game_df.index[idx], "time_remaining_before"] = (
                        game_df.iloc[idx - 1]["time_remaining_after"]
                    )
                else:
                    # Quarter changed: use time at end of previous quarter (which is 0:00)
                    # For CFB, quarters end at 0:00, so time remaining = minutes left in game
                    if prev_quarter == 1:
                        # End of 1st quarter = start of 2nd = 45 minutes left in game
                        quarter_end_time = 3 * 15 * 60  # 2700 seconds
                    elif prev_quarter == 2:
                        # End of 2nd quarter (halftime) = start of 3rd = 30 minutes left
                        quarter_end_time = 2 * 15 * 60  # 1800 seconds
                    elif prev_quarter == 3:
                        # End of 3rd quarter = start of 4th = 15 minutes left
                        quarter_end_time = 1 * 15 * 60  # 900 seconds
                    elif prev_quarter == 4:
                        # End of regulation = start of OT = 0 seconds
                        quarter_end_time = 0
                    else:
                        # End of OT periods = 0 seconds
                        quarter_end_time = 0
                    df.loc[game_df.index[idx], "time_remaining_before"] = quarter_end_time

    df["play_duration"] = (
        pd.to_numeric(df["time_remaining_before"], errors="coerce")
        - pd.to_numeric(df["time_remaining_after"], errors="coerce")
    ).astype(float)

    # Check for negative durations and provide detailed warning
    min_dur = pd.Series(df["play_duration"], dtype="float64").min(skipna=True)
    if pd.notna(min_dur) and min_dur < 0:
        neg_count = (df["play_duration"] < 0).sum()
        # Count quarter transitions that may cause negative durations
        quarter_changes = 0
        for game_id, game_group in df.groupby("game_id"):
            game_df = game_group.sort_values(["quarter", "play_number"]).reset_index(drop=True)
            quarter_changes += (game_df["quarter"].diff() > 0).sum()
        print(
            f"Warning: {neg_count} play durations are negative (min: {min_dur:.1f}s). "
            f"This includes {quarter_changes} quarter transitions and clock management inconsistencies "
            "in the raw CFB data. Negative durations will be set to NaN."
        )

    # Create masks for invalid contexts - only mask if columns exist and values are 1
    # This preserves play durations for plays that don't have these special context flags
    if "penalty" in df.columns:
        df.loc[df["penalty"] == 1, "play_duration"] = np.nan
    if "st" in df.columns:
        df.loc[df["st"] == 1, "play_duration"] = np.nan
    if "twopoint" in df.columns:
        df.loc[df["twopoint"] == 1, "play_duration"] = np.nan
    # Set negative and extreme durations to NaN
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

    result_df = df.sort_values(by=["game_id", "quarter", "play_number"]).copy()
    result_df["drive_number"] = np.nan
    # Process each game separately to avoid issues with groupby.apply
    all_games = []
    for game_id, game_group in result_df.groupby("game_id"):
        game_df = game_group.copy().reset_index(drop=True)
        current_drive = 0
        last_offense = None
        last_end_of_drive = True
        for idx in range(len(game_df)):
            row = game_df.iloc[idx]
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
            game_df.loc[idx, "drive_number"] = current_drive
            last_end_of_drive = (
                (play_type in end_of_drive_types)
                or bool(row.get("scoring", False))
                or bool(row.get("turnover", 0))
            )
            last_offense = offense
        all_games.append(game_df)
    final_df = pd.concat(all_games, ignore_index=True)
    final_df["drive_number"] = final_df["drive_number"].astype(int)
    return final_df


def calculate_rushing_analytics(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate advanced rushing metrics like Line Yards, Power Success, etc."""
    df_copy = df.copy()

    # Define conditions for rushing plays
    is_rush = df_copy["rush_attempt"] == 1

    # --- Line Yards ---
    # Apply the formula only to rushing plays
    yards_gained = df_copy.loc[is_rush, "yards_gained"]
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

    df_copy["line_yards"] = line_yards

    # --- Power Success ---
    is_power_situation = (df_copy["down"].isin([3, 4])) & (
        df_copy["yards_to_first"] <= 2
    )
    df_copy["is_power_situation"] = is_power_situation & is_rush

    is_converted = df_copy["success"] == 1
    df_copy["power_success_converted"] = df_copy["is_power_situation"] & is_converted

    # --- Second Level & Open Field Yards ---
    second_level_yards = pd.Series(np.nan, index=df_copy.index)
    open_field_yards = pd.Series(np.nan, index=df_copy.index)

    second_level_yards.loc[is_rush] = (
        df_copy.loc[is_rush, "yards_gained"].clip(lower=5, upper=10) - 5
    )
    open_field_yards.loc[is_rush] = (
        df_copy.loc[is_rush, "yards_gained"].clip(lower=10) - 10
    )

    df_copy["second_level_yards"] = second_level_yards
    df_copy["open_field_yards"] = open_field_yards

    return df_copy


def calculate_st_analytics(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate advanced special teams metrics."""
    df_copy = df.copy()

    # --- Field Goal Analytics ---
    is_fg = df_copy["st_fg"] == 1
    df_copy["kick_distance"] = np.nan
    df_copy.loc[is_fg, "kick_distance"] = df_copy.loc[is_fg, "yard_line"] + 17
    df_copy["is_fg_made"] = (df_copy["play_type"] == "Field Goal Good").astype(int)

    return df_copy


def allplays_to_byplay(data: pd.DataFrame) -> pd.DataFrame:
    """Transform raw plays into enriched by-play dataset."""
    df = data.copy()
    df = apply_manual_data_fixes(df)

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

    df["clock_minutes_in_secs"] = df["clock_minutes"] * 60

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
