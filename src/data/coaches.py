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
        data_root: str | None = None,
        storage=None,
    ):
        """Initialize the coaches ingester.

        Args:
            year: The year to ingest data for (default: 2024)
            classification: Team classification filter (default: "fbs")
            min_year: Minimum year for coach history (default: None)
            max_year: Maximum year for coach history (default: None)
            limit_teams: Limit number of teams for testing (default: None)
        """
        super().__init__(year, classification, data_root=data_root, storage=storage)
        self.min_year = min_year
        self.max_year = max_year
        self.limit_teams = limit_teams

    @property
    def entity_name(self) -> str:
        """The logical entity name for storage."""
        return "coaches"

    def get_fbs_teams(self) -> list[str]:
        """Get list of FBS team names from local storage."""
        teams_index = self.storage.read_index(
            "teams",
            filters={"year": str(self.year)},
            columns=["school"],
        )
        if not teams_index:
            raise RuntimeError(
                f"Teams index not found for year {self.year}. Please run the teams ingester first."
            )
        return [team["school"] for team in teams_index]

    def fetch_data(self) -> list[Any]:
        """Fetch coaches data from the CFBD API.

        Returns:
            List of coach objects from CFBD API
        """
        coaches_api = cfbd.CoachesApi(cfbd.ApiClient(self.cfbd_config))

        print(f"Getting FBS teams from local storage for {self.year}...")
        fbs_teams = self.get_fbs_teams()

        if self.limit_teams:
            fbs_teams = fbs_teams[: self.limit_teams]
            print(f"Limited to first {self.limit_teams} teams for testing.")

        print(f"Found {len(fbs_teams)} FBS teams to process.")

        all_coaches_data = coaches_api.get_coaches(
            year=self.year,
            min_year=self.min_year,
            max_year=self.max_year,
        )
        print(f"Fetched {len(all_coaches_data)} total coaches from API.")

        # Filter to only coaches associated with the specified FBS teams
        fbs_coaches = []
        fbs_teams_set = set(fbs_teams)
        for coach in all_coaches_data:
            for season in self.safe_getattr(coach, "seasons", []):
                if self.safe_getattr(season, "school") in fbs_teams_set:
                    fbs_coaches.append(coach)
                    break  # Add coach once and move to the next

        print(f"Filtered to {len(fbs_coaches)} coaches with FBS experience.")
        return fbs_coaches

    def transform_data(self, data: list[Any]) -> list[dict[str, Any]]:
        """Transform coaches data into storage format.

        Args:
            data: List of coach objects from CFBD API

        Returns:
            List of dictionaries ready for storage
        """
        coaches_to_insert = []

        for coach in data:
            # Handle seasons array - convert to JSON format
            seasons = self.safe_getattr(coach, "seasons", None)
            if seasons:
                seasons_data = [s.to_dict() for s in seasons]
                seasons = seasons_data

            coaches_to_insert.append(
                {
                    "first_name": self.safe_getattr(coach, "first_name", None),
                    "last_name": self.safe_getattr(coach, "last_name", None),
                    "hire_date": self.safe_getattr(coach, "hire_date", None),
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
