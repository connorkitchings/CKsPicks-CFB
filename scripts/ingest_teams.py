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

api_instance = cfbd.TeamsApi(cfbd.ApiClient(configuration))


def ingest_teams(year=2024, classification="fbs"):
    """Fetches FBS teams from cfbd for a specific year and ingests them into the Supabase 'teams' table."""
    try:
        print(f"Fetching all teams from cfbd API for {year}...")
        teams = api_instance.get_teams(year=year)

        # Filter for FBS teams only
        fbs_teams = [
            team
            for team in teams
            if getattr(team, "classification", "").lower() == classification.lower()
        ]
        print(
            f"Found {len(fbs_teams)} {classification.upper()} teams out of {len(teams)} total teams."
        )

        teams_to_insert = []
        for team in fbs_teams:
            # Handle optional fields safely
            alternate_names = getattr(team, "alt_name_1", None)
            if alternate_names:
                alternate_names = [alternate_names]  # Convert to array format

            teams_to_insert.append(
                {
                    "id": team.id,
                    "school": team.school,
                    "mascot": getattr(team, "mascot", None),
                    "abbreviation": getattr(team, "abbreviation", None),
                    "alternate_names": alternate_names,
                    "color": getattr(team, "color", None),
                    "alternate_color": getattr(team, "alt_color", None),
                    "logos": getattr(team, "logos", None),
                    "conference": getattr(team, "conference", None),
                    "division": getattr(team, "division", None),
                    "classification": getattr(team, "classification", None),
                    "twitter": getattr(team, "twitter", None),
                    "year": year,
                }
            )

        print("Ingesting teams into Supabase...")
        response = supabase.table("teams").upsert(teams_to_insert).execute()
        print(f"Successfully ingested {len(response.data)} teams.")

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    ingest_teams()
