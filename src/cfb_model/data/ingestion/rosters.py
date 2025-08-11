"""Rosters data ingestion from CFBD API."""

from typing import Any

import cfbd

from .base import BaseIngester
from .teams import TeamsIngester


class RostersIngester(BaseIngester):
    """Ingester for college football rosters data."""

    def __init__(
        self, year: int = 2024, classification: str = "fbs", limit_teams: int = None, data_root: str | None = None, storage=None
    ):
        """Initialize the rosters ingester.

        Args:
            year: The year to ingest data for (default: 2024)
            classification: Team classification filter (default: "fbs")
            limit_teams: Limit number of teams for testing (default: None)
        """
        super().__init__(year, classification, data_root=data_root, storage=storage)
        self.limit_teams = limit_teams

    @property
    def entity_name(self) -> str:
        """The logical entity name for storage."""
        return "rosters"

    def get_fbs_teams(self) -> dict[str, int]:
        """Get FBS team names and IDs from local storage."""
        teams_index = self.storage.read_index(
            "teams",
            filters={"year": str(self.year)},
            columns=["id", "school"],
        )
        if not teams_index:
            raise RuntimeError(f"Teams index not found for year {self.year}. Please run the teams ingester first.")
        return {team["school"]: team["id"] for team in teams_index}

    def fetch_data(self) -> list[Any]:
        """Fetch rosters data from the CFBD API.

        Returns:
            List of player objects from CFBD API
        """
        teams_api = cfbd.TeamsApi(cfbd.ApiClient(self.cfbd_config))

        print(f"Getting FBS teams from local storage for {self.year}...")
        fbs_teams_dict = self.get_fbs_teams()
        fbs_teams = list(fbs_teams_dict.keys())

        if self.limit_teams:
            fbs_teams = fbs_teams[: self.limit_teams]
            print(f"Limited to first {self.limit_teams} teams for testing.")

        print(f"Found {len(fbs_teams)} FBS teams to process.")

        all_rosters = teams_api.get_roster(year=self.year)
        print(f"Fetched {len(all_rosters)} total players from API.")

        # Filter to only FBS teams and prepare for transformation
        fbs_players = []
        for player in all_rosters:
            player_team = self.safe_getattr(player, "team", None)
            if player_team in fbs_teams_dict:
                # Add team_id to the player object for use in transform_data
                player.team_id = fbs_teams_dict[player_team]
                fbs_players.append(player)

        print(f"Filtered to {len(fbs_players)} FBS players.")
        return fbs_players

    def transform_data(self, data: list[Any]) -> list[dict[str, Any]]:
        """Transform rosters data into storage format.

        Args:
            data: List of player objects from CFBD API

        Returns:
            List of dictionaries ready for storage
        """
        players_to_insert = []

        for player in data:
            players_to_insert.append(
                {
                    "id": self.safe_getattr(player, "id", None),
                    "team_id": self.safe_getattr(player, "team_id", None),
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
