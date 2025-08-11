import os
from pprint import pprint

import cfbd
from cfbd.rest import ApiException
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def print_schema(label, obj):
    print(f"\n{'='*60}\n{label} Schema\n{'='*60}")
    if hasattr(obj, 'to_dict'):
        pprint(obj.to_dict())
    else:
        pprint(obj)


def fetch_and_print_schemas():
    """
    Fetch and print schemas for all relevant CFBD data types.
    """
    api_key = os.getenv("CFBD_API_KEY")
    if not api_key:
        print("Error: CFBD_API_KEY not found in environment variables.")
        print("Please add it to your .env file.")
        return

    configuration = cfbd.Configuration(access_token=api_key)
    print("Fetching data from CFBD API...")

    try:
        with cfbd.ApiClient(configuration) as api_client:
            # 1. Games
            games_api = cfbd.GamesApi(api_client)
            games = games_api.get_games(year=2023, season_type="regular", week=1)
            if games:
                print_schema("Game", games[0])

            # 2. Plays
            plays_api = cfbd.PlaysApi(api_client)
            plays = plays_api.get_plays(year=2023, week=1, season_type="regular")
            if plays:
                print_schema("Play", plays[0])


            # 4. Betting Lines
            betting_api = cfbd.BettingApi(api_client)
            lines = betting_api.get_lines(year=2023, week=1, season_type="regular")
            if lines and hasattr(lines[0], 'lines') and lines[0].lines:
                print_schema("BettingLine (Game)", lines[0])
                print_schema("BettingLine (Line)", lines[0].lines[0])

            # 5. Team Info by Season
            teams_api = cfbd.TeamsApi(api_client)
            teams = teams_api.get_teams(year=2023)
            if teams:
                print_schema("TeamInfo", teams[0])

            # 6. Roster Info by Season
            try:
                roster = teams_api.get_roster(year=2023, team=teams[0].school if teams else None)
                if roster:
                    print_schema("RosterInfo", roster[0])
            except AttributeError:
                print("TeamsApi.get_roster not available in this cfbd-python version.")
            except Exception as e:
                print(f"Error fetching roster info: {e}")

            # 7. Advanced Game Stats
            stats_api = cfbd.StatsApi(api_client)
            adv_stats = stats_api.get_advanced_game_stats(year=2023, week=1)
            if adv_stats:
                print_schema("AdvancedGameStat", adv_stats[0])

            # 8. Coaches
            try:
                coaches_api = cfbd.CoachesApi(api_client)
                coaches = coaches_api.get_coaches(year=2023)
                if coaches:
                    print_schema("Coach", coaches[0])
            except AttributeError:
                print("CoachesApi or get_coaches not available in this cfbd-python version.")
            except Exception as e:
                print(f"Error fetching coaches: {e}")

            # 9. Metrics (Team/Advanced)
            try:
                metrics = stats_api.get_metrics(year=2023, week=1)
                if metrics:
                    print_schema("Metrics", metrics[0])
            except AttributeError:
                print("get_metrics not available in this cfbd-python version.")
            except Exception as e:
                print(f"Error fetching metrics: {e}")
            try:
                adv_team_metrics = stats_api.get_advanced_team_metrics(year=2023, week=1)
                if adv_team_metrics:
                    print_schema("AdvancedTeamMetrics", adv_team_metrics[0])
            except AttributeError:
                print("get_advanced_team_metrics not available in this cfbd-python version.")
            except Exception as e:
                print(f"Error fetching advanced team metrics: {e}")

            # 10. Ratings
            try:
                ratings = stats_api.get_ratings(year=2023, week=1)
                if ratings:
                    print_schema("Ratings", ratings[0])
            except AttributeError:
                print("get_ratings not available in this cfbd-python version.")
            except Exception as e:
                print(f"Error fetching ratings: {e}")

            # 11. Recruiting
            try:
                recruiting_api = cfbd.RecruitingApi(api_client)
                recruits = recruiting_api.get_recruiting_players(year=2023)
                if recruits:
                    print_schema("RecruitingPlayer", recruits[0])
            except AttributeError:
                print("RecruitingApi or get_recruiting_players not available in this cfbd-python version.")
            except Exception as e:
                print(f"Error fetching recruiting data: {e}")

    except ApiException as e:
        print(f"Exception when calling CFBD API: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    fetch_and_print_schemas()
