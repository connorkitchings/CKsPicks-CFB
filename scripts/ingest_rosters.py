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

teams_api = cfbd.TeamsApi(cfbd.ApiClient(configuration))


def get_fbs_teams(year=2024):
    """Get list of FBS team names and IDs from our teams table."""
    response = (
        supabase.table("teams")
        .select("id, school")
        .eq("year", year)
        .eq("classification", "fbs")
        .execute()
    )
    return {team["school"]: team["id"] for team in response.data}


def ingest_rosters(year=2024, limit_teams=None):
    """Fetches rosters from FBS teams and ingests them into the Supabase 'rosters' table."""
    try:
        print(f"Getting FBS teams from database for {year}...")
        fbs_teams_dict = get_fbs_teams(year)
        fbs_teams = list(fbs_teams_dict.keys())

        if limit_teams:
            fbs_teams = fbs_teams[:limit_teams]
            print(f"Limited to first {limit_teams} teams for testing.")

        print(f"Found {len(fbs_teams)} FBS teams to process.")

        try:
            # OPTIMIZATION: Use single bulk API call instead of 130+ individual calls
            print(f"Fetching all rosters for {year} in single API call...")
            all_rosters = teams_api.get_roster(year=year)

            print(f"Fetched {len(all_rosters)} total players from API.")

            # Filter to only FBS teams and add team metadata
            players_to_insert = []
            for player in all_rosters:
                player_team = getattr(player, "team", None)
                if player_team in fbs_teams_dict:
                    players_to_insert.append(
                        {
                            "team_id": fbs_teams_dict[player_team],
                            "year": year,
                            "id": getattr(player, "id", None),
                            "first_name": getattr(player, "first_name", None),
                            "last_name": getattr(player, "last_name", None),
                            "jersey": getattr(player, "jersey", None),
                            "weight": getattr(player, "weight", None),
                            "height": getattr(player, "height", None),
                            "position": getattr(player, "position", None),
                            "home_city": getattr(player, "home_city", None),
                            "home_state": getattr(player, "home_state", None),
                            "home_country": getattr(player, "home_country", None),
                            "home_latitude": getattr(player, "home_latitude", None),
                            "home_longitude": getattr(player, "home_longitude", None),
                            "home_county_fips": getattr(
                                player, "home_county_fips", None
                            ),
                            "recruit_ids": getattr(player, "recruit_ids", None),
                        }
                    )

            print(f"Filtered to {len(players_to_insert)} FBS players.")

            # Insert all players at once
            total_players = 0
            if players_to_insert:
                print(f"Ingesting {len(players_to_insert)} players...")
                response = supabase.table("rosters").upsert(players_to_insert).execute()
                total_players = len(response.data)
                print(f"Successfully ingested {total_players} players.")

        except Exception as e:
            print(f"Error with bulk roster fetch: {e}")
            print("Falling back to individual team calls...")

            # Fallback to original method if bulk call fails
            total_players = 0
            batch_size = (
                10  # Process teams in smaller batches since roster API can be heavy
            )

            for i in range(0, len(fbs_teams), batch_size):
                batch_teams = fbs_teams[i : i + batch_size]
                print(
                    f"Processing teams {i + 1}-{min(i + batch_size, len(fbs_teams))} of {len(fbs_teams)}..."
                )

                players_to_insert = []

                for team in batch_teams:
                    try:
                        # Get roster for this team
                        team_roster = teams_api.get_roster(team=team, year=year)

                        for player in team_roster:
                            players_to_insert.append(
                                {
                                    "team_id": fbs_teams_dict[team],
                                    "year": year,
                                    "id": getattr(player, "id", None),
                                    "first_name": getattr(player, "first_name", None),
                                    "last_name": getattr(player, "last_name", None),
                                    "jersey": getattr(player, "jersey", None),
                                    "weight": getattr(player, "weight", None),
                                    "height": getattr(player, "height", None),
                                    "position": getattr(player, "position", None),
                                    "home_city": getattr(player, "home_city", None),
                                    "home_state": getattr(player, "home_state", None),
                                    "home_country": getattr(
                                        player, "home_country", None
                                    ),
                                    "home_latitude": getattr(
                                        player, "home_latitude", None
                                    ),
                                    "home_longitude": getattr(
                                        player, "home_longitude", None
                                    ),
                                    "home_county_fips": getattr(
                                        player, "home_county_fips", None
                                    ),
                                    "recruit_ids": getattr(player, "recruit_ids", None),
                                }
                            )

                    except Exception as e:
                        print(f"Error processing team {team}: {e}")
                        continue

                # Insert this batch of players
                if players_to_insert:
                    print(f"Ingesting {len(players_to_insert)} players from batch...")
                    response = (
                        supabase.table("rosters").upsert(players_to_insert).execute()
                    )
                    batch_count = len(response.data)
                    total_players += batch_count
                    print(
                        f"Successfully ingested {batch_count} players. Total so far: {total_players}"
                    )

        print(f"Completed! Total players ingested: {total_players}")

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    # Start with a limited number of teams for testing
    ingest_rosters(limit_teams=3)
