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

coaches_api = cfbd.CoachesApi(cfbd.ApiClient(configuration))


def get_fbs_teams(year=2024):
    """Get list of FBS team names from our teams table."""
    response = (
        supabase.table("teams")
        .select("school")
        .eq("year", year)
        .eq("classification", "fbs")
        .execute()
    )
    return [team["school"] for team in response.data]


def ingest_coaches(year=2024, min_year=None, max_year=None, limit_teams=None):
    """Fetches coaches from FBS teams and ingests them into the Supabase 'coaches' table."""
    try:
        print(f"Getting FBS teams from database for {year}...")
        fbs_teams = get_fbs_teams(year)

        if limit_teams:
            fbs_teams = fbs_teams[:limit_teams]
            print(f"Limited to first {limit_teams} teams for testing.")

        print(f"Found {len(fbs_teams)} FBS teams to process.")

        total_coaches = 0
        batch_size = 10  # Process teams in smaller batches

        for i in range(0, len(fbs_teams), batch_size):
            batch_teams = fbs_teams[i : i + batch_size]
            print(
                f"Processing teams {i + 1}-{min(i + batch_size, len(fbs_teams))} of {len(fbs_teams)}..."
            )

            coaches_to_insert = []

            for team in batch_teams:
                try:
                    # Get coaches for this team
                    team_coaches = coaches_api.get_coaches(
                        team=team, year=year, min_year=min_year, max_year=max_year
                    )

                    for coach in team_coaches:
                        # Convert seasons to JSONB format
                        seasons_data = []
                        for season in getattr(coach, "seasons", []):
                            season_dict = {
                                "year": getattr(season, "year", None),
                                "school": getattr(season, "school", None),
                                "games": getattr(season, "games", None),
                                "wins": getattr(season, "wins", None),
                                "losses": getattr(season, "losses", None),
                                "ties": getattr(season, "ties", None),
                                "preseason_rank": getattr(
                                    season, "preseason_rank", None
                                ),
                                "postseason_rank": getattr(
                                    season, "postseason_rank", None
                                ),
                                "srs": getattr(season, "srs", None),
                                "sp_overall": getattr(season, "sp_overall", None),
                                "sp_offense": getattr(season, "sp_offense", None),
                                "sp_defense": getattr(season, "sp_defense", None),
                            }
                            seasons_data.append(season_dict)

                        # Handle datetime serialization for hire_date
                        hire_date = getattr(coach, "hire_date", None)
                        if hire_date and hasattr(hire_date, "isoformat"):
                            hire_date = hire_date.isoformat()

                        coaches_to_insert.append(
                            {
                                "first_name": getattr(coach, "first_name", None),
                                "last_name": getattr(coach, "last_name", None),
                                "hire_date": hire_date,
                                "seasons": seasons_data,
                            }
                        )

                except Exception as e:
                    print(f"Error processing team {team}: {e}")
                    continue

            # Insert this batch of coaches
            if coaches_to_insert:
                print(f"Ingesting {len(coaches_to_insert)} coaches from batch...")
                response = supabase.table("coaches").upsert(coaches_to_insert).execute()
                batch_count = len(response.data)
                total_coaches += batch_count
                print(
                    f"Successfully ingested {batch_count} coaches. Total so far: {total_coaches}"
                )

        print(f"Completed! Total coaches ingested: {total_coaches}")

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    # Start with a limited number of teams for testing
    ingest_coaches(limit_teams=3)
