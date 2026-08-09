"""
Situational feature engineering.

Functions for creating features based on game-level context, such as rest, travel, etc.
"""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd
from geopy.distance import geodesic


def merge_situational_features(
    team_game_df: pd.DataFrame,
    games_df: pd.DataFrame,
    teams_df: pd.DataFrame | None = None,
    venues_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Merge situational features derived from raw data into the team-game DataFrame.

    Args:
        team_game_df: DataFrame with team-game level stats.
        games_df: DataFrame with raw game metadata.
        teams_df: Optional DataFrame with raw team data.
        venues_df: Optional DataFrame with raw venue data.

    Returns:
        DataFrame with situational features merged in.
    """
    if games_df.empty:
        return team_game_df

    if "id" in games_df.columns:
        games_df = games_df.rename(columns={"id": "game_id"})

    # --- Part 1: Days of Rest ---
    rest_df = games_df[["game_id", "start_date"]].copy()
    rest_df["start_date"] = pd.to_datetime(
        rest_df["start_date"], utc=True, errors="coerce"
    )

    merged_df = team_game_df.merge(rest_df, on="game_id", how="left")
    merged_df = merged_df.sort_values(by=["team", "start_date"])
    merged_df["previous_game_date"] = merged_df.groupby("team")["start_date"].shift(1)

    merged_df["start_date"] = pd.to_datetime(
        merged_df["start_date"], utc=True, errors="coerce"
    )
    merged_df["previous_game_date"] = pd.to_datetime(
        merged_df["previous_game_date"], utc=True, errors="coerce"
    )

    merged_df["days_of_rest"] = (
        merged_df["start_date"] - merged_df["previous_game_date"]
    ).dt.days
    merged_df["days_of_rest_missing"] = merged_df["days_of_rest"].isna()
    merged_df["days_of_rest"] = merged_df["days_of_rest"].fillna(7.0)
    merged_df = merged_df.drop(columns=["previous_game_date"])

    # --- Part 2: Travel Distance & Neutral Site ---
    if venues_df is None or venues_df.empty:
        merged_df["travel_distance_km"] = 0.0
        merged_df["travel_distance_missing"] = True
        merged_df["neutral_site"] = False  # Assume not neutral if no venue data
        merged_df["neutral_site_missing"] = True
        merged_df = merged_df.drop(columns=["start_date"], errors="ignore")
        return merged_df

    travel_df = games_df[
        ["game_id", "venue_id", "home_team", "away_team", "neutral_site"]
    ].copy()

    # Merge this info into our main df
    merged_df = merged_df.merge(travel_df, on="game_id", how="left")

    # Team metadata is the authority for a home venue. Inferring it from the
    # season schedule leaks venue changes and mishandles neutral-site slates.
    home_venues = pd.DataFrame(columns=["team", "home_venue_id"])
    if teams_df is not None and not teams_df.empty:
        team_column = next(
            (column for column in ("team", "school") if column in teams_df), None
        )
        venue_column = next(
            (column for column in ("home_venue_id", "venue_id") if column in teams_df),
            None,
        )
        if team_column and venue_column:
            home_venues = (
                teams_df[[team_column, venue_column]]
                .dropna()
                .drop_duplicates(team_column, keep="last")
                .rename(columns={team_column: "team", venue_column: "home_venue_id"})
            )
    merged_df = merged_df.merge(home_venues, on="team", how="left")

    # Get venue coordinates
    venues_locations = venues_df[["id", "latitude", "longitude"]].rename(
        columns={"id": "venue_id"}
    )
    venues_locations = venues_locations.dropna(subset=["latitude", "longitude"])

    # Merge game venue and home venue coordinates
    merged_df = merged_df.merge(venues_locations, on="venue_id", how="left").rename(
        columns={"latitude": "game_lat", "longitude": "game_lon"}
    )
    merged_df = merged_df.merge(
        venues_locations,
        left_on="home_venue_id",
        right_on="venue_id",
        how="left",
        suffixes=("_game", "_home"),
    ).rename(columns={"latitude": "home_lat", "longitude": "home_lon"})

    # Calculate distance
    def calculate_distance(row):
        if row["team"] == row["home_team"] and not bool(row["neutral_site"]):
            return 0.0
        coordinates = ("game_lat", "game_lon", "home_lat", "home_lon")
        if all(pd.notna(row[column]) for column in coordinates):
            return geodesic(
                (row["game_lat"], row["game_lon"]), (row["home_lat"], row["home_lon"])
            ).kilometers
        return float("nan")

    merged_df["travel_distance_km"] = merged_df.apply(calculate_distance, axis=1)
    merged_df["travel_distance_missing"] = merged_df["travel_distance_km"].isna()
    merged_df["travel_distance_km"] = merged_df["travel_distance_km"].fillna(0.0)
    merged_df["neutral_site_missing"] = merged_df["neutral_site"].isna()
    merged_df["neutral_site"] = merged_df["neutral_site"].fillna(False).astype(bool)

    # --- Part 3: Enhanced Venue Features (timezone, elevation, dome) ---
    extra_venue_cols = [
        c for c in ["timezone", "elevation", "dome"] if c in venues_df.columns
    ]
    if extra_venue_cols and "id" in venues_df.columns:
        venue_lookup = venues_df.set_index("id")[extra_venue_cols].to_dict("index")

        # Determine the game venue ID column (may have been suffixed in Part 2 merges)
        game_vid_col = (
            "venue_id_game" if "venue_id_game" in merged_df.columns else "venue_id"
        )

        if "timezone" in extra_venue_cols:
            merged_df["game_timezone"] = merged_df[game_vid_col].map(
                lambda vid: venue_lookup.get(vid, {}).get("timezone")
            )
            merged_df["home_timezone"] = merged_df["home_venue_id"].map(
                lambda vid: venue_lookup.get(vid, {}).get("timezone")
            )

            def utc_offset_hours(row, column):
                timezone_name = row.get(column)
                kickoff = row.get("start_date")
                if not timezone_name or pd.isna(kickoff):
                    return float("nan")
                try:
                    timestamp = pd.Timestamp(kickoff).to_pydatetime()
                    return (
                        timestamp.astimezone(ZoneInfo(str(timezone_name)))
                        .utcoffset()
                        .total_seconds()
                        / 3600
                    )
                except (ZoneInfoNotFoundError, ValueError, AttributeError):
                    return float("nan")

            merged_df["_game_tz_off"] = merged_df.apply(
                lambda row: utc_offset_hours(row, "game_timezone"), axis=1
            )
            merged_df["_home_tz_off"] = merged_df.apply(
                lambda row: utc_offset_hours(row, "home_timezone"), axis=1
            )
            merged_df["timezone_missing"] = (
                merged_df[["_game_tz_off", "_home_tz_off"]].isna().any(axis=1)
            )
            merged_df["timezone_diff"] = (
                merged_df["_game_tz_off"] - merged_df["_home_tz_off"]
            )
            merged_df["eastward_travel"] = (merged_df["timezone_diff"] > 0).astype(int)
            merged_df["timezone_diff"] = merged_df["timezone_diff"].fillna(0.0)
            # Home team: no timezone crossing
            home_mask = (merged_df["team"] == merged_df["home_team"]) & ~merged_df[
                "neutral_site"
            ]
            merged_df.loc[home_mask, "timezone_diff"] = 0.0
            merged_df.loc[home_mask, "eastward_travel"] = 0
            merged_df = merged_df.drop(
                columns=[
                    "_game_tz_off",
                    "_home_tz_off",
                    "game_timezone",
                    "home_timezone",
                ],
                errors="ignore",
            )

        if "elevation" in extra_venue_cols:
            merged_df["game_elevation"] = merged_df[game_vid_col].map(
                lambda vid: venue_lookup.get(vid, {}).get("elevation")
            )
            merged_df["home_elevation"] = merged_df["home_venue_id"].map(
                lambda vid: venue_lookup.get(vid, {}).get("elevation")
            )
            merged_df["altitude_diff"] = merged_df["game_elevation"].fillna(
                0
            ) - merged_df["home_elevation"].fillna(0)
            merged_df["altitude_missing"] = (
                merged_df[["game_elevation", "home_elevation"]].isna().any(axis=1)
            )
            # Home team plays at their home venue, no altitude differential
            home_mask = (merged_df["team"] == merged_df["home_team"]) & ~merged_df[
                "neutral_site"
            ]
            merged_df.loc[home_mask, "altitude_diff"] = 0.0
            merged_df = merged_df.drop(
                columns=["game_elevation", "home_elevation"], errors="ignore"
            )

        if "dome" in extra_venue_cols:
            merged_df["is_dome_game"] = (
                merged_df[game_vid_col]
                .map(lambda vid: venue_lookup.get(vid, {}).get("dome"))
                .fillna(False)
                .astype(int)
            )

    # Rest × travel fatigue interaction
    merged_df["rest_travel_fatigue"] = merged_df["travel_distance_km"] / (
        merged_df["days_of_rest"] + 1
    )

    # --- Final Cleanup ---
    # Select final columns to keep
    new_situational_cols = [
        "days_of_rest",
        "travel_distance_km",
        "neutral_site",
        "rest_travel_fatigue",
        "days_of_rest_missing",
        "travel_distance_missing",
        "neutral_site_missing",
    ]
    for col in [
        "timezone_diff",
        "eastward_travel",
        "timezone_missing",
        "altitude_diff",
        "altitude_missing",
        "is_dome_game",
    ]:
        if col in merged_df.columns:
            new_situational_cols.append(col)

    final_cols = list(team_game_df.columns) + new_situational_cols
    # Ensure no duplicate columns
    final_cols = list(dict.fromkeys(final_cols))

    # Drop intermediate columns and return
    result = merged_df.drop(columns=["start_date"], errors="ignore")
    return result[[column for column in final_cols if column in result]]
