"""Returning production data ingestion from CFBD API."""

from typing import Any

import cfbd

from .base import BaseIngester


class ReturningProductionIngester(BaseIngester):
    """Ingester for college football returning production data."""

    def __init__(
        self,
        year: int = 2024,
        *,
        data_root: str | None = None,
        storage=None,
    ):
        """Initialize the returning production ingester.

        Args:
            year: Season year to ingest data for (default: 2024)
            data_root: Root path for local data storage
            storage: Custom storage backend
        """
        super().__init__(year, data_root=data_root, storage=storage)

    @property
    def entity_name(self) -> str:
        """The logical entity name for storage."""
        return "raw/returning_production"

    @property
    def source_endpoint(self) -> str:
        return "PlayersApi.get_returning_production"

    @property
    def partition_keys(self) -> list[str]:
        """Partition keys for returning production data."""
        return ["year"]

    def fetch_data(self) -> list[Any]:
        """Fetch returning production data from the CFBD API.

        Returns:
            List of returning production objects from CFBD API
        """
        api = cfbd.PlayersApi(cfbd.ApiClient(self.cfbd_config))
        records = api.get_returning_production(
            year=self.year, _request_timeout=self.request_timeout_seconds
        )
        print(f"Found {len(records)} returning production records for {self.year}")
        return records

    def transform_data(self, data: list[Any]) -> list[dict[str, Any]]:
        """Transform returning production data into storage format.

        Args:
            data: List of returning production objects from CFBD API

        Returns:
            List of dictionaries ready for storage
        """
        records = []
        for item in data:
            records.append(
                {
                    "season": self.year,
                    "team": self.safe_getattr(item, "team", None),
                    "conference": self.safe_getattr(item, "conference", None),
                    "total_ppa": self.safe_getattr(item, "total_ppa", None),
                    "total_passing_ppa": self.safe_getattr(
                        item, "total_passing_ppa", None
                    ),
                    "total_rushing_ppa": self.safe_getattr(
                        item, "total_rushing_ppa", None
                    ),
                    "total_receiving_ppa": self.safe_getattr(
                        item, "total_receiving_ppa", None
                    ),
                    "percent_ppa": self.safe_getattr(item, "percent_ppa", None),
                    "percent_passing_ppa": self.safe_getattr(
                        item, "percent_passing_ppa", None
                    ),
                    "percent_rushing_ppa": self.safe_getattr(
                        item, "percent_rushing_ppa", None
                    ),
                    "percent_receiving_ppa": self.safe_getattr(
                        item, "percent_receiving_ppa", None
                    ),
                    "usage": self.safe_getattr(item, "usage", None),
                    "passing_usage": self.safe_getattr(item, "passing_usage", None),
                    "rushing_usage": self.safe_getattr(item, "rushing_usage", None),
                    "receiving_usage": self.safe_getattr(item, "receiving_usage", None),
                    "year": self.year,
                }
            )
        return records
