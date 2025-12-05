import argparse
import logging
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def fetch_weather(lat, lon, date_str):
    """
    Fetch hourly weather for a specific date from Open-Meteo Archive API.
    """
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": date_str,
        "end_date": date_str,
        "hourly": "temperature_2m,precipitation,wind_speed_10m",
        "timezone": "auto",
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching weather for {lat}, {lon}, {date_str}: {e}")
        return None


def process_year(year, data_root):
    games_path = data_root / f"raw/games/year={year}/data.csv"
    stadiums_path = data_root / "stadiums.csv"
    output_dir = data_root / f"raw/weather/year={year}"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "data.csv"

    if not games_path.exists():
        logger.warning(f"No games found for {year} at {games_path}")
        return

    logger.info(f"Processing weather for {year}...")

    # Load data
    games = pd.read_csv(games_path)
    stadiums = pd.read_csv(stadiums_path)

    # Merge games with stadiums
    # Ensure venue_id is float/int consistent
    games["venue_id"] = pd.to_numeric(games["venue_id"], errors="coerce")
    stadiums["id"] = pd.to_numeric(stadiums["id"], errors="coerce")

    merged = pd.merge(games, stadiums, left_on="venue_id", right_on="id", how="inner")

    logger.info(f"Found {len(merged)} games with stadium info for {year}")

    # weather_records will be collected from API

    # Check if we already have some data to skip
    if output_file.exists():
        existing_df = pd.read_csv(output_file)
        existing_keys = set(zip(existing_df["game_id"], existing_df["game_date"]))
    else:
        existing_keys = set()

    count = 0
    for _, row in merged.iterrows():
        game_id = row["id_x"]  # game id
        game_date = row["start_date"]

        # Parse date to YYYY-MM-DD
        try:
            dt = datetime.fromisoformat(game_date.replace("Z", "+00:00"))
            date_str = dt.strftime("%Y-%m-%d")
        except ValueError:
            logger.warning(f"Invalid date format: {game_date}")
            continue

        if (game_id, date_str) in existing_keys:
            continue

        lat = row["latitude"]
        lon = row["longitude"]

        # Fetch weather
        data = fetch_weather(lat, lon, date_str)

        if data and "hourly" in data:
            # Find the index for the game hour (approximate)
            # Open-Meteo returns 00:00 to 23:00 local time or UTC depending on timezone param
            # We used 'auto' timezone, so it should be local time?
            # Actually, let's just save the average of the game duration (e.g. 4 hours)
            # Or just save the specific hour.
            # For simplicity, let's take the average of the 4 hours starting from game time.
            # But wait, we need to align timezones.
            # The API returns 'time' array.

            # Let's just save the raw hourly data for the game start hour for now
            # Or better: save the mean of the game window (start to start+4h)

            # We need to match the game hour to the API response times.
            # API times are ISO strings.

            # Simple approach: Extract the hour from the response that matches the game hour
            # Note: API returns list of 24 hours.
            # We need to be careful with timezones.
            # Let's just take the hour index from the game_date datetime object if it's in local time?
            # The game_date from CFBD is usually UTC (Z).
            # Open-Meteo with timezone='auto' returns local time.
            # This is a mismatch.
            # Better to request UTC from Open-Meteo to match CFBD.

            # RE-IMPLEMENT fetch with timezone=GMT
            pass

        # Rate limit
        time.sleep(0.2)
        count += 1
        if count % 10 == 0:
            logger.info(f"Processed {count} games...")

    # Re-writing the fetch logic to be robust on timezones
    # We will request UTC from Open-Meteo


def fetch_weather_utc(lat, lon, date_str):
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": date_str,
        "end_date": date_str,
        "hourly": "temperature_2m,precipitation,wind_speed_10m",
        "timezone": "GMT",  # UTC
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except Exception:
        return None


def main():
    # Add src to path for imports
    import sys

    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from src.config import get_data_root

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--years", type=str, default="2024", help="Comma-separated years"
    )
    parser.add_argument(
        "--weeks",
        type=str,
        default=None,
        help="Optional comma-separated weeks to restrict (e.g., '14,15')",
    )
    parser.add_argument("--data-root", type=str, default=None)
    args = parser.parse_args()

    years = [int(y) for y in args.years.split(",")]
    weeks = None
    if args.weeks:
        weeks = {int(w) for w in args.weeks.split(",")}
    data_root = Path(args.data_root) if args.data_root else get_data_root()

    for year in years:
        process_year_robust(year, data_root, weeks=weeks)


def process_year_robust(year, data_root, weeks=None):
    games_path = data_root / f"raw/games/year={year}/data.csv"
    stadiums_path = data_root / "stadiums.csv"
    output_dir = data_root / f"raw/weather/year={year}"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "data.csv"

    if not games_path.exists():
        logger.warning(f"No games found for {year}")
        return

    logger.info(f"Processing {year}...")
    games = pd.read_csv(games_path)
    stadiums = pd.read_csv(stadiums_path)

    # Merge
    games["venue_id"] = pd.to_numeric(games["venue_id"], errors="coerce")
    stadiums["id"] = pd.to_numeric(stadiums["id"], errors="coerce")
    merged = pd.merge(games, stadiums, left_on="venue_id", right_on="id", how="inner")
    if weeks:
        merged = merged[merged["week"].isin(weeks)]

    results = []

    # Load existing if any
    if output_file.exists():
        existing_df = pd.read_csv(output_file)
        # We'll append new ones
        results = existing_df.to_dict("records")
        existing_ids = set(existing_df["game_id"])
    else:
        existing_ids = set()

    count = 0
    for _, row in merged.iterrows():
        game_id = row["id_x"]
        if game_id in existing_ids:
            continue

        start_date = row["start_date"]  # UTC ISO
        try:
            dt_utc = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            date_str = dt_utc.strftime("%Y-%m-%d")
            start_hour = dt_utc.hour
        except (ValueError, KeyError):
            continue

        lat, lon = row["latitude"], row["longitude"]

        weather = fetch_weather_utc(lat, lon, date_str)

        if weather and "hourly" in weather:
            # hourly['time'] is list of ISO strings in UTC (e.g. "2024-09-01T00:00")
            # We want the index corresponding to start_hour
            # Since we requested one day in UTC, index 0 is 00:00, index H is HH:00

            idx = start_hour
            if 0 <= idx < 24:
                temp = weather["hourly"]["temperature_2m"][idx]
                precip = weather["hourly"]["precipitation"][idx]
                wind = weather["hourly"]["wind_speed_10m"][idx]

                results.append(
                    {
                        "game_id": game_id,
                        "game_date": start_date,
                        "temperature": temp,
                        "precipitation": precip,
                        "wind_speed": wind,
                        "latitude": lat,
                        "longitude": lon,
                    }
                )
                count += 1
                if count % 10 == 0:
                    logger.info(f"Fetched {count} new weather records...")
                    # Intermediate save
                    pd.DataFrame(results).to_csv(output_file, index=False)

        time.sleep(0.1)  # 10 req/s limit roughly

    # Final save
    if results:
        pd.DataFrame(results).to_csv(output_file, index=False)
        logger.info(f"Saved {len(results)} weather records to {output_file}")


if __name__ == "__main__":
    main()
