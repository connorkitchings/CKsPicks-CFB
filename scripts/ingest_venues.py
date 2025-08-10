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

games_api = cfbd.GamesApi(cfbd.ApiClient(configuration))
teams_api = cfbd.TeamsApi(cfbd.ApiClient(configuration))
venues_api = cfbd.VenuesApi(cfbd.ApiClient(configuration))


def get_fbs_team_names(year=2024):
    """Get list of FBS team names for filtering games."""
    teams = teams_api.get_teams(year=year)
    fbs_teams = [
        team.school
        for team in teams
        if getattr(team, "classification", "").lower() == "fbs"
    ]
    return set(fbs_teams)


def ingest_venues(year=2024):
    """Fetches venue information from cfbd and ingests into the Supabase 'venues' table."""
    try:
        print("Fetching venues from cfbd API...")

        # Get all venues from the venues API
        all_venues = venues_api.get_venues()
        print(f"Found {len(all_venues)} total venues from venues API.")

        # Also get venue info from FBS games to ensure we have all venues used
        print(f"Fetching FBS games for {year} to identify additional venues...")
        fbs_team_names = get_fbs_team_names(year)
        all_games = games_api.get_games(year=year, season_type="regular")

        # Filter for FBS games and collect venue information
        fbs_games = [
            game
            for game in all_games
            if (
                getattr(game, "home_team", "") in fbs_team_names
                and getattr(game, "away_team", "") in fbs_team_names
            )
        ]

        # Extract unique venue IDs from FBS games
        game_venue_ids = set()
        for game in fbs_games:
            venue_id = getattr(game, "venue_id", None)
            if venue_id:
                game_venue_ids.add(venue_id)

        print(
            f"Found {len(game_venue_ids)} unique venue IDs from {len(fbs_games)} FBS games."
        )

        venues_to_insert = []

        # Process venues from the venues API
        for venue in all_venues:
            venue_id = getattr(venue, "id", None)
            if (
                venue_id and venue_id in game_venue_ids
            ):  # Only include venues used by FBS games
                venues_to_insert.append(
                    {
                        "id": venue_id,
                        "name": getattr(venue, "name", None),
                        "capacity": getattr(venue, "capacity", None),
                        "city": getattr(venue, "city", None),
                        "state": getattr(venue, "state", None),
                        "zip": getattr(venue, "zip", None),
                        "country_code": getattr(venue, "country_code", None),
                        "timezone": getattr(venue, "timezone", None),
                        "latitude": getattr(venue, "latitude", None),
                        "longitude": getattr(venue, "longitude", None),
                        "elevation": getattr(venue, "elevation", None),
                        "grass": getattr(venue, "grass", None),
                        "dome": getattr(venue, "dome", None),
                        "construction_year": getattr(venue, "construction_year", None),
                    }
                )

        # Handle any venue IDs from games that weren't in the venues API
        venues_api_ids = {getattr(venue, "id", None) for venue in all_venues}
        missing_venue_ids = game_venue_ids - venues_api_ids

        if missing_venue_ids:
            print(
                f"Found {len(missing_venue_ids)} venue IDs in games that aren't in venues API. Creating minimal records."
            )
            for venue_id in missing_venue_ids:
                # Find venue name from games data
                venue_name = None
                for game in fbs_games:
                    if getattr(game, "venue_id", None) == venue_id:
                        venue_name = getattr(game, "venue", None)
                        break

                venues_to_insert.append(
                    {
                        "id": venue_id,
                        "name": venue_name,
                        "capacity": None,
                        "city": None,
                        "state": None,
                        "zip": None,
                        "country_code": None,
                        "timezone": None,
                        "latitude": None,
                        "longitude": None,
                        "elevation": None,
                        "grass": None,
                        "dome": None,
                        "construction_year": None,
                    }
                )

        print(f"Ingesting {len(venues_to_insert)} venues into Supabase...")
        response = supabase.table("venues").upsert(venues_to_insert).execute()
        print(f"Successfully ingested {len(response.data)} venues.")

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    ingest_venues()
