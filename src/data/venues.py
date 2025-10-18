"""Venues data ingestion from CFBD API."""

from typing import Any

import cfbd

from .base import BaseIngester


class VenuesIngester(BaseIngester):
    """Ingester for college football venues data."""

    def __init__(
        self,
        year: int = 2024,
        classification: str = "fbs",
        data_root: str | None = None,
        storage=None,
    ):
        super().__init__(year, classification, data_root=data_root, storage=storage)

    @property
    def entity_name(self) -> str:
        """The logical entity name for storage."""
        return "venues"

    def get_fbs_team_names(self) -> set[str]:
        """Deprecated: no longer used; venues derive from local games index to avoid extra calls."""
        return set()

    def get_fbs_venue_ids(self) -> set[int]:
        """Get venue IDs used by FBS games using local games index to minimize API calls."""
        games_index = self.storage.read_index(
            "games", {"year": self.year}, columns=["venue_id"]
        )
        ids: set[int] = set()
        for row in games_index:
            vid = row.get("venue_id")
            if vid is not None:
                try:
                    ids.add(int(vid))
                except Exception:
                    continue
        print(
            f"Derived {len(ids)} unique venue IDs from local games index for {self.year}."
        )
        return ids

    def fetch_data(self) -> list[Any]:
        """Fetch venues data from the CFBD API.

        Returns:
            List of venue objects from CFBD API
        """
        venues_api = cfbd.VenuesApi(cfbd.ApiClient(self.cfbd_config))
        all_venues = venues_api.get_venues()
        print(f"Found {len(all_venues)} total venues from venues API.")

        # Get venue IDs used by FBS games from local index
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
                        venue, "year_constructed", None
                    ),
                    "year": self.year,
                }
            )

        return venues_to_insert


def main() -> None:
    """CLI entry point for venues ingestion."""
    ingester = VenuesIngester()
    ingester.run()


if __name__ == "__main__":
    main()
