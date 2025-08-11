"""Teams data ingestion from CFBD API."""

from typing import Any

import cfbd

from .base import BaseIngester


class TeamsIngester(BaseIngester):
    """Ingester for college football teams data."""

    def __init__(self, year: int = 2024, classification: str = "fbs", data_root: str | None = None):
        super().__init__(year, classification, data_root=data_root)


    @property
    def entity_name(self) -> str:
        """The logical entity name for storage."""
        return "teams"

    def fetch_data(self) -> list[Any]:
        """Fetch teams data from the CFBD API.

        Returns:
            List of team objects from CFBD API
        """
        api_instance = cfbd.TeamsApi(cfbd.ApiClient(self.cfbd_config))
        teams = api_instance.get_teams(year=self.year)

        # Filter for FBS teams only
        fbs_teams = self.filter_fbs_teams(teams)
        print(
            f"Found {len(fbs_teams)} {self.classification.upper()} teams out of {len(teams)} total teams."
        )

        return fbs_teams

    def transform_data(self, data: list[Any]) -> list[dict[str, Any]]:
        """Transform teams data into storage format.

        Args:
            data: List of team objects from CFBD API

        Returns:
            List of dictionaries ready for storage
        """
        teams_to_insert = []

        for team in data:
            # Handle optional fields safely
            alternate_names = self.safe_getattr(team, "alt_name_1", None)
            if alternate_names:
                alternate_names = [alternate_names]  # Convert to array format

            teams_to_insert.append(
                {
                    "id": team.id,
                    "school": team.school,
                    "mascot": self.safe_getattr(team, "mascot", None),
                    "abbreviation": self.safe_getattr(team, "abbreviation", None),
                    "alternate_names": alternate_names,
                    "color": self.safe_getattr(team, "color", None),
                    "alternate_color": self.safe_getattr(team, "alt_color", None),
                    "logos": self.safe_getattr(team, "logos", None),
                    "conference": self.safe_getattr(team, "conference", None),
                    "division": self.safe_getattr(team, "division", None),
                    "classification": self.safe_getattr(team, "classification", None),
                    "twitter": self.safe_getattr(team, "twitter", None),
                    "year": self.year,
                }
            )

        return teams_to_insert


def main() -> None:
    """CLI entry point for teams ingestion."""
    ingester = TeamsIngester()
    ingester.run()


if __name__ == "__main__":
    main()
