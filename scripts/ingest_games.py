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


def get_fbs_team_names(year=2024):
    """Get list of FBS team names for filtering games."""
    teams = teams_api.get_teams(year=year)
    fbs_teams = [
        team.school
        for team in teams
        if getattr(team, "classification", "").lower() == "fbs"
    ]
    return set(fbs_teams)


def ingest_games(year=2024, season_type="regular"):
    """Fetches FBS games from cfbd for a specific year and ingests them into the Supabase 'games' table."""
    try:
        print(f"Fetching {season_type} season games from cfbd API for {year}...")

        # Get FBS team names for filtering
        fbs_team_names = get_fbs_team_names(year)
        print(f"Found {len(fbs_team_names)} FBS teams for filtering.")

        # Fetch all games for the year and season type
        all_games = games_api.get_games(year=year, season_type=season_type)

        # Filter for FBS games only (games where both teams are FBS)
        fbs_games = [
            game
            for game in all_games
            if (
                getattr(game, "home_team", "") in fbs_team_names
                and getattr(game, "away_team", "") in fbs_team_names
            )
        ]

        print(f"Found {len(fbs_games)} FBS games out of {len(all_games)} total games.")

        games_to_insert = []
        for game in fbs_games:
            # Handle line scores (convert to PostgreSQL array format)
            home_line_scores = getattr(game, "home_line_scores", None)
            away_line_scores = getattr(game, "away_line_scores", None)

            # Handle datetime fields - convert to ISO format strings
            start_date = getattr(game, "start_date", None)
            if start_date:
                start_date = (
                    start_date.isoformat()
                    if hasattr(start_date, "isoformat")
                    else str(start_date)
                )

            games_to_insert.append(
                {
                    "id": game.id,
                    "season": game.season,
                    "season_type": getattr(game, "season_type", season_type),
                    "week": getattr(game, "week", None),
                    "start_date": start_date,
                    "start_time_tbd": getattr(game, "start_time_tbd", None),
                    "venue_id": getattr(game, "venue_id", None),
                    "venue": getattr(game, "venue", None),
                    "neutral_site": getattr(game, "neutral_site", None),
                    "conference_game": getattr(game, "conference_game", None),
                    "attendance": getattr(game, "attendance", None),
                    "excitement_index": getattr(game, "excitement_index", None),
                    "highlights": getattr(game, "highlights", None),
                    "notes": getattr(game, "notes", None),
                    "home_id": getattr(game, "home_id", None),
                    "home_team": getattr(game, "home_team", None),
                    "home_conference": getattr(game, "home_conference", None),
                    "home_classification": getattr(game, "home_classification", None),
                    "home_points": getattr(game, "home_points", None),
                    "home_line_scores": home_line_scores,
                    "home_pregame_elo": getattr(game, "home_pregame_elo", None),
                    "home_postgame_elo": getattr(game, "home_postgame_elo", None),
                    "home_postgame_win_probability": getattr(
                        game, "home_postgame_win_probability", None
                    ),
                    "away_id": getattr(game, "away_id", None),
                    "away_team": getattr(game, "away_team", None),
                    "away_conference": getattr(game, "away_conference", None),
                    "away_classification": getattr(game, "away_classification", None),
                    "away_points": getattr(game, "away_points", None),
                    "away_line_scores": away_line_scores,
                    "away_pregame_elo": getattr(game, "away_pregame_elo", None),
                    "away_postgame_elo": getattr(game, "away_postgame_elo", None),
                    "away_postgame_win_probability": getattr(
                        game, "away_postgame_win_probability", None
                    ),
                    "completed": getattr(game, "completed", None),
                }
            )

        print("Ingesting games into Supabase...")
        response = supabase.table("games").upsert(games_to_insert).execute()
        print(f"Successfully ingested {len(response.data)} FBS games.")

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    ingest_games()
