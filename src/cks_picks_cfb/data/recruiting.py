"""Recruiting data ingestion from CFBD API.

Fetches team recruiting rankings from 247Sports composite.
"""

from typing import Any

import cfbd

from .base import BaseIngester


class RecruitingIngester(BaseIngester):
    """Ingester for college football recruiting rankings data."""

    def __init__(
        self,
        year: int = 2024,
        *,
        data_root: str | None = None,
        storage=None,
    ):
        """Initialize the recruiting ingester.

        Args:
            year: The recruiting class year to ingest data for (default: 2024)
            data_root: Root path for local data storage
            storage: Custom storage backend
        """
        super().__init__(year, data_root=data_root, storage=storage)

    @property
    def entity_name(self) -> str:
        """The logical entity name for storage."""
        return "recruiting"

    @property
    def partition_keys(self) -> list[str]:
        """Partition keys for recruiting data."""
        return ["year"]

    def fetch_data(self) -> list[Any]:
        """Fetch recruiting rankings data from the CFBD API.

        Returns:
            List of team recruiting ranking objects from CFBD API
        """
        recruiting_api = cfbd.RecruitingApi(cfbd.ApiClient(self.cfbd_config))

        all_rankings = recruiting_api.get_team_recruiting_rankings(year=self.year)

        print(f"Found {len(all_rankings)} team recruiting rankings for {self.year}")
        return all_rankings

    def transform_data(self, data: list[Any]) -> list[dict[str, Any]]:
        """Transform recruiting rankings data into storage format.

        Args:
            data: List of team recruiting ranking objects from CFBD API

        Returns:
            List of dictionaries ready for storage
        """
        records = []

        for ranking in data:
            records.append(
                {
                    "season": self.year,
                    "rank": self.safe_getattr(ranking, "rank", None),
                    "team": self.safe_getattr(ranking, "team", None),
                    "points": self.safe_getattr(ranking, "points", None),
                    "year": self.year,
                }
            )

        return records


def ingest_recruiting(year: int, data_root: str | None = None) -> int:
    """Convenience function to ingest recruiting data.

    Args:
        year: Recruiting class year to ingest
        data_root: Root path for data storage

    Returns:
        Number of records written
    """
    ingester = RecruitingIngester(year=year, data_root=data_root)
    data = ingester.fetch_data()
    transformed = ingester.transform_data(data)
    ingester.ingest_data(transformed)
    return len(transformed)
