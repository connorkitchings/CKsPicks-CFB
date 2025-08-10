import os

import cfbd
from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

# Load environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
CFBD_API_KEY = os.getenv("CFBD_API_KEY")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Configure CFBD API
configuration = cfbd.Configuration(access_token=CFBD_API_KEY)

drives_api = cfbd.DrivesApi(cfbd.ApiClient(configuration))


def get_fbs_game_ids(year=2024):
    """Get list of FBS game IDs and weeks from our games table."""
    response = supabase.table("games").select("id, week").eq("season", year).execute()
    return [(game["id"], game["week"]) for game in response.data]


def ingest_drives(year=2024, season_type="regular", limit_games=None):
    """Fetches drives from FBS games and ingests them into the Supabase 'drives' table."""
    try:
        print(f"Getting FBS game IDs from database for {year} {season_type} season...")
        fbs_games_data = get_fbs_game_ids(year)

        if limit_games:
            fbs_games_data = fbs_games_data[:limit_games]
            print(f"Limited to first {limit_games} games for testing.")

        print(f"Found {len(fbs_games_data)} FBS games to process.")

        total_drives = 0
        batch_size = 50  # Process games in batches to avoid overwhelming the API

        for i in range(0, len(fbs_games_data), batch_size):
            batch_games_data = fbs_games_data[i : i + batch_size]
            print(
                f"Processing games {i + 1}-{min(i + batch_size, len(fbs_games_data))} of {len(fbs_games_data)}..."
            )

            drives_to_insert = []

            # Group games by week to minimize API calls
            games_by_week = {}
            for game_id, week in batch_games_data:
                if week not in games_by_week:
                    games_by_week[week] = []
                games_by_week[week].append(game_id)

            for week, game_ids_in_week in games_by_week.items():
                try:
                    # Get all drives for this week
                    week_drives = drives_api.get_drives(
                        year=year, season_type=season_type, week=week
                    )

                    # Filter drives for our specific FBS games
                    for drive in week_drives:
                        drive_game_id = getattr(drive, "game_id", None)
                        if drive_game_id in game_ids_in_week:
                            drives_to_insert.append(
                                {
                                    "id": getattr(drive, "id", None),
                                    "game_id": drive_game_id,
                                    "drive_number": getattr(
                                        drive, "drive_number", None
                                    ),
                                    "scoring": getattr(drive, "scoring", None),
                                    "offense": getattr(drive, "offense", None),
                                    "offense_conference": getattr(
                                        drive, "offense_conference", None
                                    ),
                                    "defense": getattr(drive, "defense", None),
                                    "defense_conference": getattr(
                                        drive, "defense_conference", None
                                    ),
                                    "plays": getattr(drive, "plays", None),
                                    "yards": getattr(drive, "yards", None),
                                    "drive_result": getattr(
                                        drive, "drive_result", None
                                    ),
                                    "is_home_offense": getattr(
                                        drive, "is_home_offense", None
                                    ),
                                    "start_period": getattr(
                                        drive, "start_period", None
                                    ),
                                    "start_yardline": getattr(
                                        drive, "start_yardline", None
                                    ),
                                    "start_yards_to_goal": getattr(
                                        drive, "start_yards_to_goal", None
                                    ),
                                    "start_time_minutes": getattr(
                                        getattr(drive, "start_time", None),
                                        "minutes",
                                        None,
                                    )
                                    if getattr(drive, "start_time", None)
                                    else None,
                                    "start_time_seconds": getattr(
                                        getattr(drive, "start_time", None),
                                        "seconds",
                                        None,
                                    )
                                    if getattr(drive, "start_time", None)
                                    else None,
                                    "start_offense_score": getattr(
                                        drive, "start_offense_score", None
                                    ),
                                    "start_defense_score": getattr(
                                        drive, "start_defense_score", None
                                    ),
                                    "end_period": getattr(drive, "end_period", None),
                                    "end_yardline": getattr(
                                        drive, "end_yardline", None
                                    ),
                                    "end_yards_to_goal": getattr(
                                        drive, "end_yards_to_goal", None
                                    ),
                                    "end_time_minutes": getattr(
                                        getattr(drive, "end_time", None),
                                        "minutes",
                                        None,
                                    )
                                    if getattr(drive, "end_time", None)
                                    else None,
                                    "end_time_seconds": getattr(
                                        getattr(drive, "end_time", None),
                                        "seconds",
                                        None,
                                    )
                                    if getattr(drive, "end_time", None)
                                    else None,
                                    "end_offense_score": getattr(
                                        drive, "end_offense_score", None
                                    ),
                                    "end_defense_score": getattr(
                                        drive, "end_defense_score", None
                                    ),
                                }
                            )

                except Exception as e:
                    print(f"Error processing week {week}: {e}")
                    continue

            # Insert this batch of drives
            if drives_to_insert:
                print(f"Ingesting {len(drives_to_insert)} drives from batch...")
                response = supabase.table("drives").upsert(drives_to_insert).execute()
                batch_count = len(response.data)
                total_drives += batch_count
                print(
                    f"Successfully ingested {batch_count} drives. Total so far: {total_drives}"
                )

        print(f"Completed! Total drives ingested: {total_drives}")

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    # Start with a limited number of games for testing
    ingest_drives(limit_games=10)
