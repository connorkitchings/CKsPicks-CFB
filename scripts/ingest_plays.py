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
configuration = cfbd.Configuration(
    access_token=CFBD_API_KEY
)

plays_api = cfbd.PlaysApi(cfbd.ApiClient(configuration))


def get_fbs_game_ids(year=2024):
    """Get list of FBS game IDs and weeks from our games table."""
    response = supabase.table("games").select("id, week").eq("season", year).execute()
    return [(game["id"], game["week"]) for game in response.data]


def ingest_plays(year=2024, season_type="regular", limit_games=None):
    """Fetches plays from FBS games and ingests them into the Supabase 'plays' table."""
    try:
        print(f"Getting FBS game IDs from database for {year} {season_type} season...")
        fbs_games_data = get_fbs_game_ids(year)
        
        if limit_games:
            fbs_games_data = fbs_games_data[:limit_games]
            print(f"Limited to first {limit_games} games for testing.")
        
        print(f"Found {len(fbs_games_data)} FBS games to process.")

        total_plays = 0
        batch_size = 50  # Process games in batches to avoid overwhelming the API
        
        for i in range(0, len(fbs_games_data), batch_size):
            batch_games_data = fbs_games_data[i:i+batch_size]
            print(f"Processing games {i+1}-{min(i+batch_size, len(fbs_games_data))} of {len(fbs_games_data)}...")
            
            plays_to_insert = []
            
            # Group games by week to minimize API calls
            games_by_week = {}
            for game_id, week in batch_games_data:
                if week not in games_by_week:
                    games_by_week[week] = []
                games_by_week[week].append(game_id)
            
            for week, game_ids_in_week in games_by_week.items():
                try:
                    # Get all plays for this week
                    week_plays = plays_api.get_plays(year=year, season_type=season_type, week=week)
                    
                    # Filter plays for our specific FBS games
                    for play in week_plays:
                        play_game_id = getattr(play, 'game_id', None)
                        if play_game_id in game_ids_in_week:
                            plays_to_insert.append(
                                {
                                    "id": getattr(play, "id", None),
                                    "game_id": play_game_id,
                                    "drive_id": getattr(play, "drive_id", None),
                                    "play_number": getattr(play, "play_number", None),
                                    "period": getattr(play, "period", None),
                                    "clock_minutes": getattr(play, "clock", {}).get("minutes", None) if getattr(play, "clock", None) else None,
                                    "clock_seconds": getattr(play, "clock", {}).get("seconds", None) if getattr(play, "clock", None) else None,
                                    "wallclock": getattr(play, "wallclock", None),
                                    "offense": getattr(play, "offense", None),
                                    "offense_conference": getattr(play, "offense_conference", None),
                                    "offense_score": getattr(play, "offense_score", None),
                                    "offense_timeouts": getattr(play, "offense_timeouts", None),
                                    "defense": getattr(play, "defense", None),
                                    "defense_conference": getattr(play, "defense_conference", None),
                                    "defense_score": getattr(play, "defense_score", None),
                                    "defense_timeouts": getattr(play, "defense_timeouts", None),
                                    "home": getattr(play, "home", None),
                                    "away": getattr(play, "away", None),
                                    "down": getattr(play, "down", None),
                                    "distance": getattr(play, "distance", None),
                                    "yardline": getattr(play, "yard_line", None),
                                    "yards_to_goal": getattr(play, "yards_to_goal", None),
                                    "yards_gained": getattr(play, "yards_gained", None),
                                    "play_type": getattr(play, "play_type", None),
                                    "play_text": getattr(play, "play_text", None),
                                    "ppa": getattr(play, "ppa", None),
                                    "scoring": getattr(play, "scoring", None),
                                }
                            )
                
                                "offense_score": getattr(play, "offense_score", None),
                                "offense_timeouts": getattr(
                                    play, "offense_timeouts", None
                                ),
                                "defense": getattr(play, "defense", None),
                                "defense_conference": getattr(
                                    play, "defense_conference", None
                                ),
                                "defense_score": getattr(play, "defense_score", None),
                                "defense_timeouts": getattr(
                                    play, "defense_timeouts", None
                                ),
                                "home": getattr(play, "home", None),
                                "away": getattr(play, "away", None),
                                "down": getattr(play, "down", None),
                                "distance": getattr(play, "distance", None),
                                "yardline": getattr(play, "yard_line", None),
                                "yards_to_goal": getattr(play, "yards_to_goal", None),
                                "yards_gained": getattr(play, "yards_gained", None),
                                "play_type": getattr(play, "play_type", None),
                                "play_text": getattr(play, "play_text", None),
                                "ppa": getattr(play, "ppa", None),
                                "scoring": getattr(play, "scoring", None),
                            }
                        )

                except Exception as e:
                    print(f"Error processing game {game_id}: {e}")
                    continue

            # Insert this batch of plays
            if plays_to_insert:
                print(f"Ingesting {len(plays_to_insert)} plays from batch...")
                response = supabase.table("plays").upsert(plays_to_insert).execute()
                batch_count = len(response.data)
                total_plays += batch_count
                print(
                    f"Successfully ingested {batch_count} plays. Total so far: {total_plays}"
                )

        print(f"Completed! Total plays ingested: {total_plays}")

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    # Start with a limited number of games for testing
    ingest_plays(limit_games=10)
