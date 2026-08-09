import logging
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from cks_picks_cfb.data.storage import StorageBackend


def load_weather_data(
    year: int, storage: "StorageBackend | None" = None
) -> pd.DataFrame:
    """Load weather data for a specific year using cloud-compatible storage."""
    if storage is None:
        from cks_picks_cfb.data.storage import get_storage

        storage = get_storage()

    weather_path = f"raw/weather/year={year}/data.csv"
    if not storage.exists(weather_path):
        logging.warning(f"No weather data found for {year}")
        return pd.DataFrame()

    df = storage.read_csv(weather_path)
    # Ensure game_id is int
    if "game_id" in df.columns:
        df["game_id"] = pd.to_numeric(df["game_id"], errors="coerce")
    return df


def merge_weather_features(
    team_game_df: pd.DataFrame, weather_df: pd.DataFrame
) -> pd.DataFrame:
    """Merge weather features into team-game DataFrame."""
    if weather_df.empty:
        result = team_game_df.copy()
        result["weather_missing"] = True
        result["temperature_missing"] = True
        result["precipitation_missing"] = True
        result["wind_speed_missing"] = True
        result["temperature"] = 70.0
        result["precipitation"] = 0.0
        result["wind_speed"] = 0.0
        return result

    # Weather is per game, so we merge on game_id
    # We want to add weather cols to both teams in the game

    weather_cols = ["temperature", "precipitation", "wind_speed"]
    available_cols = [c for c in weather_cols if c in weather_df.columns]

    if not available_cols:
        return team_game_df

    # Select only needed columns from weather
    weather_subset = weather_df[["game_id"] + available_cols].drop_duplicates(
        subset=["game_id"]
    )

    merged = team_game_df.merge(weather_subset, on="game_id", how="left")
    for column in weather_cols:
        if column not in merged:
            merged[column] = pd.NA
        merged[f"{column}_missing"] = merged[column].isna()
    merged["weather_missing"] = merged[
        [f"{column}_missing" for column in weather_cols]
    ].all(axis=1)

    # Fill missing weather with defaults? Or leave as NaN?
    # For now, fill with mean or 0?
    # Wind=0, Precip=0 makes sense. Temp=NaN is bad.
    # Let's fill NaNs with reasonable defaults if missing
    # But strictly, if we don't have weather, maybe we shouldn't guess.
    # However, for ML, we need values.
    # Let's leave as NaN for now and let the imputer handle it, or fill with 0 for precip/wind.

    if "precipitation" in merged.columns:
        merged["precipitation"] = merged["precipitation"].fillna(0.0)
    if "wind_speed" in merged.columns:
        merged["wind_speed"] = merged["wind_speed"].fillna(0.0)
    if "temperature" in merged.columns:
        # Fill temp with average of column? Or just 70?
        # Let's fill with 70 (room temp) as a neutral prior
        merged["temperature"] = merged["temperature"].fillna(70.0)

    return merged
