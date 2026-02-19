"""
Situational feature engineering.

Functions for creating features based on game-level context, such as rest, travel, etc.
"""

import pandas as pd
from geopy.distance import geodesic

# IANA timezone string → approximate standard UTC hour offset (ignores DST)
_TZ_OFFSET = {
    "America/New_York": -5,
    "America/Indiana/Indianapolis": -5,
    "America/Detroit": -5,
    "America/Kentucky/Louisville": -5,
    "America/Chicago": -6,
    "America/Menominee": -6,
    "America/Denver": -7,
    "America/Boise": -7,
    "America/Phoenix": -7,
    "America/Los_Angeles": -8,
    "America/Anchorage": -9,
    "Pacific/Honolulu": -10,
    "America/Honolulu": -10,
}


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
    merged_df["days_of_rest"] = merged_df["days_of_rest"].fillna(7.0)
    merged_df = merged_df.drop(columns=["start_date", "previous_game_date"])

    # --- Part 2: Travel Distance & Neutral Site ---
    if venues_df is None or venues_df.empty:
        merged_df["travel_distance_km"] = 0.0
        merged_df["neutral_site"] = False  # Assume not neutral if no venue data
        return merged_df

    travel_df = games_df[
        ["game_id", "venue_id", "home_team", "away_team", "neutral_site"]
    ].copy()

    # Merge this info into our main df
    merged_df = merged_df.merge(travel_df, on="game_id", how="left")

    # Derive each team's home venue
    home_venues = (
        games_df[~games_df["neutral_site"]]
        .groupby("home_team")["venue_id"]
        .agg(lambda x: x.mode().iloc[0] if not x.mode().empty else None)
        .dropna()
        .to_frame()
        .reset_index()
        .rename(columns={"home_team": "team", "venue_id": "home_venue_id"})
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
        if row["team"] == row["home_team"] or row["neutral_site"]:
            return 0.0
        if pd.notna(row["game_lat"]) and pd.notna(row["home_lat"]):
            return geodesic(
                (row["game_lat"], row["game_lon"]), (row["home_lat"], row["home_lon"])
            ).kilometers
        return 0.0  # Default to 0 if we can't calculate

    merged_df["travel_distance_km"] = merged_df.apply(calculate_distance, axis=1)

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
            merged_df["_game_tz_off"] = (
                merged_df["game_timezone"].map(_TZ_OFFSET).fillna(0)
            )
            merged_df["_home_tz_off"] = (
                merged_df["home_timezone"].map(_TZ_OFFSET).fillna(0)
            )
            merged_df["timezone_diff"] = (
                merged_df["_game_tz_off"] - merged_df["_home_tz_off"]
            )
            merged_df["eastward_travel"] = (merged_df["timezone_diff"] < 0).astype(int)
            # Home team: no timezone crossing
            home_mask = merged_df["team"] == merged_df["home_team"]
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
            # Home team plays at their home venue, no altitude differential
            home_mask = merged_df["team"] == merged_df["home_team"]
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
    ]
    for col in ["timezone_diff", "eastward_travel", "altitude_diff", "is_dome_game"]:
        if col in merged_df.columns:
            new_situational_cols.append(col)

    final_cols = list(team_game_df.columns) + new_situational_cols
    # Ensure no duplicate columns
    final_cols = list(dict.fromkeys(final_cols))

    # Drop intermediate columns and return
    return merged_df[final_cols]
