"""Base class for CFBD data ingestion."""

import os
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import cfbd
from dotenv import load_dotenv

from ..storage.base import Partition, StorageBackend
from ..storage.local_storage import LocalStorage

load_dotenv()


class BaseIngester(ABC):
    """Base class for CFBD data ingestion with common functionality.

    Provides shared configuration, error handling, and utility methods
    for all data ingestion classes.
    """

    def __init__(
        self,
        year: int = 2024,
        classification: str = "fbs",
        *,
        data_root: str | None = None,
        storage: StorageBackend | None = None,
    ):
        """Initialize the ingester with common configuration.

        Args:
            year: The year to ingest data for (default: 2024)
            classification: Team classification filter (default: "fbs")
            data_root: Root path for local data storage (optional; placeholder used if None)
            storage: Custom storage backend (optional)
        """
        self.year = year
        self.classification = classification.lower()

        # Environment
        self.cfbd_api_key = os.getenv("CFBD_API_KEY")
        if not self.cfbd_api_key:
            raise ValueError("Missing required environment variable: CFBD_API_KEY")

        # Initialize clients
        self.cfbd_config = cfbd.Configuration(access_token=self.cfbd_api_key)

        # Initialize storage backend (hard-fail if path inaccessible)
        self.storage: StorageBackend = storage or LocalStorage(
            data_root=data_root, file_format="csv", data_type="raw"
        )

        # Timezone for normalization (US/Eastern)
        self._eastern = ZoneInfo("America/New_York")

    @property
    @abstractmethod
    def entity_name(self) -> str:
        """The logical entity name for storage (e.g., 'games', 'plays')."""
        pass

    @abstractmethod
    def fetch_data(self) -> list[Any]:
        """Fetch data from the CFBD API.

        Returns:
            List of data objects from the CFBD API
        """
        pass

    @abstractmethod
    def transform_data(self, data: list[Any]) -> list[dict[str, Any]]:
        """Transform CFBD API data into a dict-ready storage format.

        Args:
            data: Raw data from CFBD API

        Returns:
            List of dictionaries ready for storage
        """
        pass

    def filter_fbs_teams(self, teams: list[Any]) -> list[Any]:
        """Filter teams to only include FBS classification.

        Args:
            teams: List of team objects from CFBD API

        Returns:
            Filtered list containing only FBS teams
        """
        return [
            team
            for team in teams
            if getattr(team, "classification", "").lower() == self.classification
        ]

    def safe_getattr(self, obj: Any, attr: str, default: Any = None) -> Any:
        """Safely get attribute from object with default fallback.

        Args:
            obj: Object to get attribute from
            attr: Attribute name
            default: Default value if attribute doesn't exist

        Returns:
            Attribute value or default
        """
        return getattr(obj, attr, default)

    def normalize_to_eastern(self, dt: Any) -> datetime | None:
        """Normalize a datetime to US/Eastern timezone.

        Accepts datetime or ISO-like string; returns aware datetime in Eastern.
        Returns None if input is falsy.
        """
        if not dt:
            return None
        if isinstance(dt, str):
            try:
                # Attempt fromisoformat; if it fails, return None
                parsed = datetime.fromisoformat(dt)
            except ValueError:
                return None
        else:
            parsed = dt
        if parsed.tzinfo is None:
            # Assume UTC if tz-naive; CFBD typically provides tz-aware, but be safe
            parsed = parsed.replace(tzinfo=ZoneInfo("UTC"))
        return parsed.astimezone(self._eastern)

    @property
    def partition_keys(self) -> list[str]:
        """The keys to use for partitioning the data."""
        return ["year"]

    def ingest_data(self, data: list[dict[str, Any]]) -> None:
        """Default ingestion: write all rows into a partition based on partition_keys.

        Subclasses with finer-grained partitioning (e.g., plays) should override.
        """
        if not data:
            print("No data to ingest.")
            return

        partition_values = {key: str(getattr(self, key)) for key in self.partition_keys}
        partition = Partition(partition_values)
        written = self.storage.write(
            self.entity_name, data, partition, overwrite=True
        )
        print(
            f"Wrote {written} records to {self.entity_name}/{partition.path_suffix()}."
        )

        # --- DEBUGGING TEST: Read back immediately ---
        try:
            filters = {key: str(getattr(self, key)) for key in self.partition_keys}
            read_back_data = self.storage.read_index(
                self.entity_name, filters
            )
            print(f"DEBUG: Successfully read back {len(read_back_data)} records immediately after writing.")
        except Exception as e:
            print(f"DEBUG: FAILED to read back data immediately after writing: {e}")
        # --- END DEBUGGING TEST ---

    def run(self) -> None:
        """Execute the complete ingestion process using local storage."""
        try:
            print(f"Starting {self.__class__.__name__} for {self.year}...")
            print(f"  - Using data root: {self.storage.root()}")

            # Fetch data from CFBD API
            raw_data = self.fetch_data()
            print(f"Fetched {len(raw_data)} records from CFBD API.")

            # Transform data for storage
            transformed_data = self.transform_data(raw_data)
            print(f"Transformed {len(transformed_data)} records for ingestion.")

            # Diagnostic check
            if transformed_data:
                print(f"First transformed record: {transformed_data[0]}")

            # Persist locally
            self.ingest_data(transformed_data)

            print(f"Completed {self.__class__.__name__} successfully.")

        except Exception as e:
            print(f"Error in {self.__class__.__name__}: {e}")
            raise
