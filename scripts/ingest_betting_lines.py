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

betting_api = cfbd.BettingApi(cfbd.ApiClient(configuration))


def get_fbs_game_ids(year=2024):
    """Get list of FBS game IDs from our games table."""
    response = supabase.table("games").select("id").eq("season", year).execute()
    return [game["id"] for game in response.data]


def ingest_betting_lines(year=2024, season_type="regular", limit_games=None):
    """Fetches betting lines from FBS games and ingests them into the Supabase 'betting_lines' table."""
    try:
        print(f"Getting FBS game IDs from database for {year} {season_type} season...")
        fbs_game_ids = get_fbs_game_ids(year)

        if limit_games:
            fbs_game_ids = fbs_game_ids[:limit_games]
            print(f"Limited to first {limit_games} games for testing.")

        print(f"Found {len(fbs_game_ids)} FBS games to process.")

        try:
            # OPTIMIZATION: Make single API call instead of multiple calls in loop
            print(
                f"Fetching all betting lines for {year} {season_type} season in single API call..."
            )
            year_lines = betting_api.get_lines(year=year, season_type=season_type)

            print(f"Fetched {len(year_lines)} total games with betting lines from API.")

            # Filter lines for our specific FBS games and process
            lines_to_insert = []
            fbs_game_ids_set = set(fbs_game_ids)  # Convert to set for faster lookup

            for line in year_lines:
                line_game_id = getattr(line, "id", None)
                if line_game_id in fbs_game_ids_set:
                    # Process each sportsbook's lines for this game
                    lines = getattr(line, "lines", [])
                    for sportsbook_line in lines:
                        lines_to_insert.append(
                            {
                                "game_id": line_game_id,
                                "provider": getattr(sportsbook_line, "provider", None),
                                "spread": getattr(sportsbook_line, "spread", None),
                                "formatted_spread": getattr(
                                    sportsbook_line, "formatted_spread", None
                                ),
                                "spread_open": getattr(
                                    sportsbook_line, "spread_open", None
                                ),
                                "over_under": getattr(
                                    sportsbook_line, "over_under", None
                                ),
                                "over_under_open": getattr(
                                    sportsbook_line, "over_under_open", None
                                ),
                                "home_moneyline": getattr(
                                    sportsbook_line, "home_moneyline", None
                                ),
                                "away_moneyline": getattr(
                                    sportsbook_line, "away_moneyline", None
                                ),
                            }
                        )

            # Insert all betting lines at once
            total_lines = 0
            if lines_to_insert:
                print(f"Ingesting {len(lines_to_insert)} betting lines...")
                response = (
                    supabase.table("betting_lines").upsert(lines_to_insert).execute()
                )
                total_lines = len(response.data)
                print(f"Successfully ingested {total_lines} betting lines.")

        except Exception as e:
            print(f"Error with optimized betting lines fetch: {e}")
            print("Falling back to original batched method...")

            # Fallback to original method if bulk call fails
            total_lines = 0
            batch_size = 50  # Process games in batches to avoid overwhelming the API

            for i in range(0, len(fbs_game_ids), batch_size):
                batch_game_ids = fbs_game_ids[i : i + batch_size]
                print(
                    f"Processing games {i + 1}-{min(i + batch_size, len(fbs_game_ids))} of {len(fbs_game_ids)}..."
                )

                lines_to_insert = []

                try:
                    # Get all betting lines for this year
                    year_lines = betting_api.get_lines(
                        year=year, season_type=season_type
                    )

                    # Filter lines for our specific FBS games
                    for line in year_lines:
                        line_game_id = getattr(line, "id", None)
                        if line_game_id in batch_game_ids:
                            # Process each sportsbook's lines for this game
                            lines = getattr(line, "lines", [])
                            for sportsbook_line in lines:
                                lines_to_insert.append(
                                    {
                                        "game_id": line_game_id,
                                        "provider": getattr(
                                            sportsbook_line, "provider", None
                                        ),
                                        "spread": getattr(
                                            sportsbook_line, "spread", None
                                        ),
                                        "formatted_spread": getattr(
                                            sportsbook_line, "formatted_spread", None
                                        ),
                                        "spread_open": getattr(
                                            sportsbook_line, "spread_open", None
                                        ),
                                        "over_under": getattr(
                                            sportsbook_line, "over_under", None
                                        ),
                                        "over_under_open": getattr(
                                            sportsbook_line, "over_under_open", None
                                        ),
                                        "home_moneyline": getattr(
                                            sportsbook_line, "home_moneyline", None
                                        ),
                                        "away_moneyline": getattr(
                                            sportsbook_line, "away_moneyline", None
                                        ),
                                    }
                                )

                except Exception as e:
                    print(f"Error processing batch: {e}")
                    continue

                # Insert this batch of betting lines
                if lines_to_insert:
                    print(
                        f"Ingesting {len(lines_to_insert)} betting lines from batch..."
                    )
                    response = (
                        supabase.table("betting_lines")
                        .upsert(lines_to_insert)
                        .execute()
                    )
                    batch_count = len(response.data)
                    total_lines += batch_count
                    print(
                        f"Successfully ingested {batch_count} betting lines. Total so far: {total_lines}"
                    )

        print(f"Completed! Total betting lines ingested: {total_lines}")

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    # Start with a limited number of games for testing
    ingest_betting_lines(limit_games=10)
