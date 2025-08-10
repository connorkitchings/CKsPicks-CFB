"""Coaches data ingestion from CFBD API."""

from typing import Any

import cfbd

from .base import BaseIngester


class CoachesIngester(BaseIngester):
    """Ingester for college football coaches data."""

    def __init__(
        self,
        year: int = 2024,
        classification: str = "fbs",
        min_year: int = None,
        max_year: int = None,
        limit_teams: int = None,
    ):
        """Initialize the coaches ingester.

        Args:
            year: The year to ingest data for (default: 2024)
            classification: Team classification filter (default: "fbs")
            min_year: Minimum year for coach history (default: None)
            max_year: Maximum year for coach history (default: None)
            limit_teams: Limit number of teams for testing (default: None)
        """
        super().__init__(year, classification)
        self.min_year = min_year
        self.max_year = max_year
        self.limit_teams = limit_teams

    @property
    def table_name(self) -> str:
        """The name of the Supabase table to ingest data into."""
        return "coaches"

    def get_fbs_teams(self) -> list[str]:
        """Get list of FBS team names from our teams table.

        Returns:
            List of FBS team names
        """
        response = (
            self.supabase.table("teams")
            .select("school")
            .eq("year", self.year)
            .eq("classification", self.classification)
            .execute()
        )
        return [team["school"] for team in response.data]

    def fetch_data(self) -> list[Any]:
        """Fetch coaches data from the CFBD API using optimized bulk calls.

        Returns:
            List of coach objects from CFBD API
        """
        coaches_api = cfbd.CoachesApi(cfbd.ApiClient(self.cfbd_config))

        print(f"Getting FBS teams from database for {self.year}...")
        fbs_teams = self.get_fbs_teams()

        if self.limit_teams:
            fbs_teams = fbs_teams[: self.limit_teams]
            print(f"Limited to first {self.limit_teams} teams for testing.")

        print(f"Found {len(fbs_teams)} FBS teams to process.")

        try:
            # OPTIMIZATION: Use single bulk API call instead of 130+ individual calls
            print(f"Fetching all coaches for {self.year} in single API call...")
            all_coaches_data = coaches_api.get_coaches(
                year=self.year,
                min_year=self.min_year,
                max_year=self.max_year,
            )

            print(f"Fetched {len(all_coaches_data)} total coaches from API.")

            # Filter to only FBS teams and add team metadata
            fbs_coaches = []
            for coach in all_coaches_data:
                # Check if any of the coach's seasons are with FBS teams
                coach_seasons = self.safe_getattr(coach, "seasons", [])
                fbs_seasons = []

                for season in coach_seasons:
                    season_team = self.safe_getattr(season, "team", None)
                    if season_team in fbs_teams:
                        fbs_seasons.append(season)

                # If coach has FBS seasons, include them
                if fbs_seasons:
                    # Set the primary team as the most recent FBS team
                    latest_season = max(
                        fbs_seasons, key=lambda s: self.safe_getattr(s, "year", 0)
                    )
                    coach.team = self.safe_getattr(latest_season, "team", None)
                    fbs_coaches.append(coach)

            print(f"Filtered to {len(fbs_coaches)} coaches with FBS experience.")

            # Log team distribution for verification
            team_counts = {}
            for coach in fbs_coaches:
                team = getattr(coach, "team", "Unknown")
                team_counts[team] = team_counts.get(team, 0) + 1

            print(f"Coaches distributed across {len(team_counts)} FBS teams.")
            return fbs_coaches

        except Exception as e:
            print(f"Error with bulk coaches fetch: {e}")
            print("Falling back to individual team calls...")

            # Fallback to original method if bulk call fails
            all_coaches = []
            batch_size = 10  # Process teams in smaller batches

            for i in range(0, len(fbs_teams), batch_size):
                batch_teams = fbs_teams[i : i + batch_size]
                print(
                    f"Processing teams {i + 1}-{min(i + batch_size, len(fbs_teams))} of {len(fbs_teams)}..."
                )

                for team in batch_teams:
                    try:
                        # Get coaches for this team
                        team_coaches = coaches_api.get_coaches(
                            team=team,
                            year=self.year,
                            min_year=self.min_year,
                            max_year=self.max_year,
                        )

                        for coach in team_coaches:
                            # Add team info to coach data
                            coach.team = team
                            all_coaches.append(coach)

                        print(f"  {team}: {len(team_coaches)} coaches")

                    except Exception as e:
                        print(f"  Error fetching coaches for {team}: {e}")
                        continue

            print(f"Total coaches collected: {len(all_coaches)}")
            return all_coaches

    def transform_data(self, data: list[Any]) -> list[dict[str, Any]]:
        """Transform coaches data into Supabase table format.

        Args:
            data: List of coach objects from CFBD API

        Returns:
            List of dictionaries ready for Supabase insertion
        """
        coaches_to_insert = []

        for coach in data:
            # Handle seasons array - convert to JSON format
            seasons = self.safe_getattr(coach, "seasons", None)
            if seasons:
                # Convert seasons objects to dictionaries
                seasons_data = []
                for season in seasons:
                    season_dict = {
                        "year": self.safe_getattr(season, "year", None),
                        "team": self.safe_getattr(season, "team", None),
                        "games": self.safe_getattr(season, "games", None),
                        "wins": self.safe_getattr(season, "wins", None),
                        "losses": self.safe_getattr(season, "losses", None),
                        "ties": self.safe_getattr(season, "ties", None),
                        "preseason_rank": self.safe_getattr(
                            season, "preseason_rank", None
                        ),
                        "postseason_rank": self.safe_getattr(
                            season, "postseason_rank", None
                        ),
                        "srs": self.safe_getattr(season, "srs", None),
                        "sp_overall": self.safe_getattr(season, "sp_overall", None),
                        "sp_offense": self.safe_getattr(season, "sp_offense", None),
                        "sp_defense": self.safe_getattr(season, "sp_defense", None),
                    }
                    seasons_data.append(season_dict)
                seasons = seasons_data

            coaches_to_insert.append(
                {
                    "first_name": self.safe_getattr(coach, "first_name", None),
                    "last_name": self.safe_getattr(coach, "last_name", None),
                    "hire_date": self.safe_getattr(coach, "hire_date", None),
                    "team": self.safe_getattr(coach, "team", None),
                    "seasons": seasons,
                }
            )

        return coaches_to_insert


def main() -> None:
    """CLI entry point for coaches ingestion."""
    ingester = CoachesIngester()
    ingester.run()


if __name__ == "__main__":
    main()
