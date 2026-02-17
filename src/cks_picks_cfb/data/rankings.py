"""Rankings data ingestion from CFBD API.

Fetches AP and Coaches poll rankings for teams.
"""

from typing import Any

import cfbd

from .base import BaseIngester


class RankingsIngester(BaseIngester):
    """Ingester for college football rankings data (AP, Coaches polls)."""

    def __init__(
        self,
        year: int = 2024,
        week: int | None = None,
        *,
        data_root: str | None = None,
        storage=None,
    ):
        """Initialize the rankings ingester.

        Args:
            year: The year to ingest data for (default: 2024)
            week: Optional specific week to ingest data for
            data_root: Root path for local data storage
            storage: Custom storage backend
        """
        super().__init__(year, data_root=data_root, storage=storage)
        self.week = week

    @property
    def entity_name(self) -> str:
        """The logical entity name for storage."""
        return "rankings"

    @property
    def partition_keys(self) -> list[str]:
        """Partition keys for rankings data."""
        if self.week is not None:
            return ["year", "week"]
        return ["year"]

    def fetch_data(self) -> list[Any]:
        """Fetch rankings data from the CFBD API.

        Returns:
            List of ranking objects from CFBD API
        """
        rankings_api = cfbd.RankingsApi(cfbd.ApiClient(self.cfbd_config))

        if self.week is not None:
            all_rankings = rankings_api.get_rankings(year=self.year, week=self.week)
        else:
            all_rankings = rankings_api.get_rankings(year=self.year)

        print(f"Found {len(all_rankings)} ranking weeks for {self.year}")
        return all_rankings

    def transform_data(self, data: list[Any]) -> list[dict[str, Any]]:
        """Transform rankings data into storage format.

        Args:
            data: List of ranking week objects from CFBD API

        Returns:
            List of dictionaries ready for storage
        """
        records = []

        for ranking_week in data:
            week = self.safe_getattr(ranking_week, "week", None)
            season = self.safe_getattr(ranking_week, "season", self.year)

            polls = self.safe_getattr(ranking_week, "polls", [])
            for poll in polls:
                poll_name = self.safe_getattr(poll, "poll", None)
                ranks = self.safe_getattr(poll, "ranks", [])

                for rank_entry in ranks:
                    records.append(
                        {
                            "season": season,
                            "week": week,
                            "poll": poll_name,
                            "rank": self.safe_getattr(rank_entry, "rank", None),
                            "team": self.safe_getattr(rank_entry, "school", None),
                            "conference": self.safe_getattr(
                                rank_entry, "conference", None
                            ),
                            "first_place_votes": self.safe_getattr(
                                rank_entry, "first_place_votes", None
                            ),
                            "points": self.safe_getattr(rank_entry, "points", None),
                            "year": self.year,
                        }
                    )

        return records


def ingest_rankings(
    year: int, week: int | None = None, data_root: str | None = None
) -> int:
    """Convenience function to ingest rankings data.

    Args:
        year: Year to ingest
        week: Optional specific week
        data_root: Root path for data storage

    Returns:
        Number of records written
    """
    ingester = RankingsIngester(year=year, week=week, data_root=data_root)
    data = ingester.fetch_data()
    transformed = ingester.transform_data(data)
    ingester.ingest_data(transformed)
    return len(transformed)
