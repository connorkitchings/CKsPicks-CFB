"""Rosters data ingestion from CFBD API."""

from typing import Any

import cfbd

from .base import BaseIngester


class RostersIngester(BaseIngester):
    """Ingester for college football rosters data."""

    def __init__(
        self, year: int = 2024, classification: str = "fbs", limit_teams: int = None
    ):
        """Initialize the rosters ingester.

        Args:
            year: The year to ingest data for (default: 2024)
            classification: Team classification filter (default: "fbs")
            limit_teams: Limit number of teams for testing (default: None)
        """
        super().__init__(year, classification)
        self.limit_teams = limit_teams

    @property
    def table_name(self) -> str:
        """The name of the Supabase table to ingest data into."""
        return "rosters"

    def get_fbs_teams(self) -> dict[str, int]:
        """Get list of FBS team names and IDs from our teams table.

        Returns:
            Dictionary mapping team names to team IDs
        """
        response = (
            self.supabase.table("teams")
            .select("id, school")
            .eq("year", self.year)
            .eq("classification", self.classification)
            .execute()
        )
        return {team["school"]: team["id"] for team in response.data}

    def fetch_data(self) -> list[Any]:
        """Fetch rosters data from the CFBD API using optimized bulk calls.

        Returns:
            List of player objects from CFBD API
        """
        teams_api = cfbd.TeamsApi(cfbd.ApiClient(self.cfbd_config))

        print(f"Getting FBS teams from database for {self.year}...")
        fbs_teams_dict = self.get_fbs_teams()
        fbs_teams = list(fbs_teams_dict.keys())

        if self.limit_teams:
            fbs_teams = fbs_teams[: self.limit_teams]
            print(f"Limited to first {self.limit_teams} teams for testing.")

        print(f"Found {len(fbs_teams)} FBS teams to process.")

        try:
            # OPTIMIZATION: Use single bulk API call instead of 130+ individual calls
            print(f"Fetching all rosters for {self.year} in single API call...")
            all_rosters = teams_api.get_roster(year=self.year)

            print(f"Fetched {len(all_rosters)} total players from API.")

            # Filter to only FBS teams and store team metadata
            fbs_players = []
            self.team_metadata = {}  # Store team info for transform_data

            for player in all_rosters:
                player_team = self.safe_getattr(player, "team", None)
                if player_team in fbs_teams_dict:
                    fbs_players.append(player)
                    # Store team metadata for this player
                    player_id = self.safe_getattr(player, "id", None)
                    if player_id:
                        self.team_metadata[player_id] = {
                            "team": player_team,
                            "team_id": fbs_teams_dict[player_team],
                        }

            print(f"Filtered to {len(fbs_players)} FBS players.")

            # Log team distribution for verification
            team_counts = {}
            for player in fbs_players:
                team = self.safe_getattr(player, "team", None)
                team_counts[team] = team_counts.get(team, 0) + 1

            print(f"Players distributed across {len(team_counts)} FBS teams.")
            return fbs_players

        except Exception as e:
            print(f"Error with bulk roster fetch: {e}")
            print("Falling back to individual team calls...")

            # Fallback to original method if bulk call fails
            all_players = []
            batch_size = 10  # Process teams in smaller batches

            for i in range(0, len(fbs_teams), batch_size):
                batch_teams = fbs_teams[i : i + batch_size]
                print(
                    f"Processing teams {i + 1}-{min(i + batch_size, len(fbs_teams))} of {len(fbs_teams)}..."
                )

                for team in batch_teams:
                    try:
                        # Get roster for this team
                        team_roster = teams_api.get_roster(team=team, year=self.year)

                        for player in team_roster:
                            # Add team info to player data
                            player.team = team
                            player.team_id = fbs_teams_dict[team]
                            all_players.append(player)

                        print(f"  {team}: {len(team_roster)} players")

                    except Exception as e:
                        print(f"  Error fetching roster for {team}: {e}")
                        continue

            print(f"Total players collected: {len(all_players)}")
            return all_players

    def transform_data(self, data: list[Any]) -> list[dict[str, Any]]:
        """Transform rosters data into Supabase table format.

        Args:
            data: List of player objects from CFBD API

        Returns:
            List of dictionaries ready for Supabase insertion
        """
        players_to_insert = []

        for player in data:
            player_id = self.safe_getattr(player, "id", None)

            # Get team metadata from stored mapping
            team_info = getattr(self, "team_metadata", {}).get(player_id, {})
            team_id = team_info.get("team_id")

            players_to_insert.append(
                {
                    "id": player_id,
                    "team_id": team_id,
                    "first_name": self.safe_getattr(player, "first_name", None),
                    "last_name": self.safe_getattr(player, "last_name", None),
                    "jersey": self.safe_getattr(player, "jersey", None),
                    "year": self.year,
                    "position": self.safe_getattr(player, "position", None),
                    "height": self.safe_getattr(player, "height", None),
                    "weight": self.safe_getattr(player, "weight", None),
                    "home_city": self.safe_getattr(player, "home_city", None),
                    "home_state": self.safe_getattr(player, "home_state", None),
                    "home_country": self.safe_getattr(player, "home_country", None),
                    "home_latitude": self.safe_getattr(player, "home_latitude", None),
                    "home_longitude": self.safe_getattr(player, "home_longitude", None),
                    "home_county_fips": self.safe_getattr(
                        player, "home_county_fips", None
                    ),
                    "recruit_ids": self.safe_getattr(player, "recruit_ids", None),
                }
            )

        return players_to_insert


def main() -> None:
    """CLI entry point for rosters ingestion."""
    ingester = RostersIngester()
    ingester.run()


if __name__ == "__main__":
    main()
