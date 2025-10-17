"""Minimal CFBD API ingestion helpers used for raw data collection.

Note: Primary ingestion is handled elsewhere; this module provides
lightweight wrappers and cleaning for calendar/plays endpoints used in
notebooks or ad-hoc backfills.
"""

import time
import logging
from typing import Dict, List

import pandas as pd
import requests
from tqdm import tqdm as tqdm_

FBS_list = [
    "SEC",
    "American Athletic",
    "FBS Independents",
    "Big Ten",
    "Conference USA",
    "Big 12",
    "Mid-American",
    "ACC",
    "Sun Belt",
    "Pac-12",
    "Mountain West",
]


def fetch_calendar(year: int, headers: Dict[str, str]) -> List[Dict]:
    url = "https://api.collegefootballdata.com/calendar"
    params = {"year": year}

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.warning(f"Error fetching calendar data for year {year}: {e}")
        return []


def fetch_plays(year: int, week: int, headers: Dict[str, str]) -> List[Dict]:
    url = "https://api.collegefootballdata.com/plays"
    params = {"year": year, "week": week}

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.warning(f"Error fetching plays data for year {year}, week {week}: {e}")
        return []


def call_api_plays(first_year: int, last_year: int, api_key: str) -> pd.DataFrame:
    start = time.time()

    headers = {"Authorization": f"Bearer {api_key}"}

    all_plays = []

    for year in range(first_year, last_year + 1):
        calendar = fetch_calendar(year, headers)
        regular_season_weeks = [
            week["week"] for week in calendar if week["seasonType"] == "regular"
        ]

        for week in tqdm_(
            regular_season_weeks, desc=f"Fetching {year} plays", unit="week"
        ):
            plays = fetch_plays(year, week, headers)
            for play in plays:
                play["season"] = year  # Add the year to each play
                play["week"] = week  # Add the week to each play
            all_plays.extend(plays)

    plays_df = pd.DataFrame(all_plays)

    # Filter for FBS games
    cfpera_plays = plays_df[
        (plays_df["offense_conference"].isin(FBS_list))
        & (plays_df["defense_conference"].isin(FBS_list))
    ].reset_index(drop=True)

    # Rename and adjust columns
    cfpera_plays = cfpera_plays.rename(
        columns={"distance": "yards_to_first", "period": "quarter"}
    )

    # Calculate adj_yd_line
    cfpera_plays["adj_yd_line"] = cfpera_plays.apply(
        lambda row: row["yard_line"]
        if row["offense"] == row["home"]
        else 100 - row["yard_line"],
        axis=1,
    )

    # Fix turnover yards
    interception_conditions = (
        (cfpera_plays["play_type"] == "Interception")
        | (cfpera_plays["play_type"] == "Interception Return Touchdown")
        | (cfpera_plays["play_type"] == "Pass Interception Return")
    )
    cfpera_plays.loc[interception_conditions, "yards_gained"] = 0

    # Extract minutes and seconds into separate columns
    cfpera_plays["clock_minutes"] = cfpera_plays["clock"].apply(lambda x: x["minutes"])
    cfpera_plays["clock_seconds"] = cfpera_plays["clock"].apply(lambda x: x["seconds"])
    cfpera_plays = cfpera_plays.drop(columns=["clock", "wallclock"])

    # Standardize team names
    cfpera_plays.loc[cfpera_plays["offense"] == "Hawai'i", "offense"] = "Hawaii"
    cfpera_plays.loc[cfpera_plays["offense"] == "San José State", "offense"] = (
        "San Jose State"
    )
    cfpera_plays.loc[cfpera_plays["defense"] == "Hawai'i", "defense"] = "Hawaii"
    cfpera_plays.loc[cfpera_plays["defense"] == "San José State", "defense"] = (
        "San Jose State"
    )

    # Reorder columns
    columns = cfpera_plays.columns.tolist()
    columns.remove("season")
    columns.insert(0, "season")
    columns.remove("week")
    columns.insert(1, "week")
    cfpera_plays = cfpera_plays[columns]

    cfpera_plays = cfpera_plays.sort_values(
        by=["season", "game_id", "drive_number", "play_number"],
        ascending=[False, True, True, True],
    ).reset_index(drop=True)

    end = time.time()
    total_time = end - start
    total_time_per = total_time / (last_year - first_year + 1)

    minutes, seconds = divmod(int(total_time), 60)
    minutes_per, seconds_per = divmod(int(total_time_per), 60)

    logging.info(
        f"call_api_plays took {minutes} minutes and {seconds} seconds to complete."
    )
    logging.info(
        f"It took {minutes_per} minutes and {seconds_per} seconds to complete per season."
    )

    return cfpera_plays
