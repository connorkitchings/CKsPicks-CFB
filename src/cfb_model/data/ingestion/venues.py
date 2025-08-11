"""Venues data ingestion from CFBD API."""

from typing import Any

import cfbd

from .base import BaseIngester


class VenuesIngester(BaseIngester):
    """Ingester for college football venues data."""

    @property
    def entity_name(self) -> str:
        """The logical entity name for storage."""
        return "venues"

    def get_fbs_team_names(self) -> set[str]:
        """Get list of FBS team names for filtering games.

        Returns:
            Set of FBS team names
        """
        teams_api = cfbd.TeamsApi(cfbd.ApiClient(self.cfbd_config))
        teams = teams_api.get_teams(year=self.year)
        fbs_teams = [
            team.school
            for team in teams
            if getattr(team, "classification", "").lower() == self.classification
        ]
        return set(fbs_teams)

    def get_fbs_venue_ids(self) -> set[int]:
        """Get venue IDs used by FBS games.

        Returns:
            Set of venue IDs from FBS games
        """
        games_api = cfbd.GamesApi(cfbd.ApiClient(self.cfbd_config))
        fbs_team_names = self.get_fbs_team_names()

        print(f"Fetching FBS games for {self.year} to identify venues...")
        all_games = games_api.get_games(year=self.year, season_type="regular")

        # Filter for FBS games and collect venue IDs
        fbs_games = [
            game
            for game in all_games
            if (
                self.safe_getattr(game, "home_team", "") in fbs_team_names
                and self.safe_getattr(game, "away_team", "") in fbs_team_names
            )
        ]

        game_venue_ids = set()
        for game in fbs_games:
            venue_id = self.safe_getattr(game, "venue_id", None)
            if venue_id:
                game_venue_ids.add(venue_id)

        print(
            f"Found {len(game_venue_ids)} unique venue IDs from {len(fbs_games)} FBS games."
        )
        return game_venue_ids

    def fetch_data(self) -> list[Any]:
        """Fetch venues data from the CFBD API.

        Returns:
            List of venue objects from CFBD API
        """
        venues_api = cfbd.VenuesApi(cfbd.ApiClient(self.cfbd_config))
        all_venues = venues_api.get_venues()
        print(f"Found {len(all_venues)} total venues from venues API.")

        # Get venue IDs used by FBS games
        fbs_venue_ids = self.get_fbs_venue_ids()

        # Filter venues to only those used by FBS games
        fbs_venues = [
            venue
            for venue in all_venues
            if self.safe_getattr(venue, "id", None) in fbs_venue_ids
        ]

        print(f"Filtered to {len(fbs_venues)} venues used by FBS games.")
        return fbs_venues

    def transform_data(self, data: list[Any]) -> list[dict[str, Any]]:
        """Transform venues data into storage format.

        Args:
            data: List of venue objects from CFBD API

        Returns:
            List of dictionaries ready for storage
        """
        venues_to_insert = []

        for venue in data:
            venues_to_insert.append(
                {
                    "id": self.safe_getattr(venue, "id", None),
                    "name": self.safe_getattr(venue, "name", None),
                    "capacity": self.safe_getattr(venue, "capacity", None),
                    "city": self.safe_getattr(venue, "city", None),
                    "state": self.safe_getattr(venue, "state", None),
                    "zip": self.safe_getattr(venue, "zip", None),
                    "country_code": self.safe_getattr(venue, "country_code", None),
                    "timezone": self.safe_getattr(venue, "timezone", None),
                    "latitude": self.safe_getattr(venue, "latitude", None),
                    "longitude": self.safe_getattr(venue, "longitude", None),
                    "elevation": self.safe_getattr(venue, "elevation", None),
                    "grass": self.safe_getattr(venue, "grass", None),
                    "dome": self.safe_getattr(venue, "dome", None),
                    "construction_year": self.safe_getattr(
                        venue, "construction_year", None
                    ),
                }
            )

        return venues_to_insert


def main() -> None:
    """CLI entry point for venues ingestion."""
    ingester = VenuesIngester()
    ingester.run()


if __name__ == "__main__":
    main()
