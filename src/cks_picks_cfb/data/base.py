"""Base class for CFBD data ingestion."""

import os
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import cfbd
from dotenv import load_dotenv

from cks_picks_cfb.utils.base import Partition, StorageBackend

load_dotenv()


class DataUnavailableError(RuntimeError):
    """Raised when CFBD accepts a request but has not published rows yet."""

    def __init__(self, entity_name: str, year: int):
        super().__init__(
            f"CFBD returned no {entity_name} rows for {year}; "
            "treat this as source availability, not a successful ingestion."
        )
        self.entity_name = entity_name
        self.year = year


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
        self.storage_backend = os.getenv("CFB_STORAGE_BACKEND", "local").lower()
        self.capture_time = datetime.now(timezone.utc)

        # Environment
        self.cfbd_api_key = os.getenv("CFBD_API_KEY")
        if not self.cfbd_api_key:
            raise ValueError("Missing required environment variable: CFBD_API_KEY")

        # Initialize clients
        self.cfbd_config = cfbd.Configuration(access_token=self.cfbd_api_key)

        # Initialize storage backend:
        # - Use caller-provided storage if given
        # - Auto-detect from CFB_STORAGE_BACKEND env var (r2/s3/local)
        #
        # Entity names include the tier prefix (e.g., "raw/games", "raw/plays"),
        # so the storage backend root is the BASE data root — no "raw/" subdirectory
        # is appended by the storage layer.
        if storage is not None:
            self.storage = storage
        else:
            backend = self.storage_backend
            if backend != "local":
                from cks_picks_cfb.data.storage import get_storage

                self.storage = get_storage()
            else:
                from cks_picks_cfb.data.storage import LocalStorage as DataLocalStorage

                root = data_root or os.getenv("CFB_MODEL_DATA_ROOT")
                if not root:
                    raise ValueError(
                        "CFB_MODEL_DATA_ROOT must be set for local storage backend. "
                        "Set CFB_STORAGE_BACKEND=r2 for the 2026 MVP cloud path."
                    )
                self.storage = DataLocalStorage(root)

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
        if isinstance(obj, dict):
            return obj.get(attr, default)
        return getattr(obj, attr, default)

    @property
    def source_endpoint(self) -> str:
        """Provider endpoint recorded in request lineage."""
        return self.entity_name.removeprefix("raw/")

    def source_parameters(self) -> dict[str, Any]:
        """Provider-facing parameters for the default single request."""
        return {"year": self.year, "classification": self.classification}

    def source_requests(self):
        """Return independently retryable and capturable provider requests."""
        from cks_picks_cfb.data.sources import SourceRequest

        return [
            SourceRequest(
                provider="cfbd",
                entity=self.entity_name.removeprefix("raw/"),
                endpoint=self.source_endpoint,
                parameters=self.source_parameters(),
                requested_at=datetime.now(timezone.utc),
            )
        ]

    @property
    def request_timeout_seconds(self) -> float:
        """Bound one provider request so a resumable operation cannot hang."""

        value = float(os.getenv("CFB_CFBD_REQUEST_TIMEOUT_SECONDS", "60"))
        if value <= 0:
            raise ValueError("CFB_CFBD_REQUEST_TIMEOUT_SECONDS must be positive")
        return value

    def fetch_source_request(self, request: dict[str, Any]) -> list[Any]:
        """Fetch one request. Subclasses with multiple requests override this."""
        return self.fetch_data()

    def fetch_source_responses(self, requests=None):
        """Fetch every request through the canonical retrying CFBD adapter."""
        from cks_picks_cfb.data.sources import (
            CFBDSourceAdapter,
            RetryPolicy,
            fetch_with_retry,
        )

        requests = list(requests or self.source_requests())
        adapter = CFBDSourceAdapter(
            {self.entity_name.removeprefix("raw/"): self.fetch_source_request},
            api_version=getattr(cfbd, "__version__", None),
        )
        policy = RetryPolicy(
            max_attempts=int(os.getenv("CFB_SOURCE_MAX_ATTEMPTS", "4")),
            base_delay_seconds=float(os.getenv("CFB_SOURCE_RETRY_BASE_SECONDS", "0.5")),
            max_delay_seconds=float(os.getenv("CFB_SOURCE_RETRY_MAX_SECONDS", "8")),
        )

        def fetch_one(source_request):
            from cks_picks_cfb.data.sources import FailureCategory, SourceError

            try:
                response = fetch_with_retry(
                    adapter,
                    source_request.entity,
                    source_request.parameters,
                    policy=policy,
                )
            except SourceError as exc:
                if exc.category == FailureCategory.DATA_UNAVAILABLE:
                    raise DataUnavailableError(self.entity_name, self.year) from exc
                raise
            return replace(response, request=source_request.manifest())

        max_workers = max(
            1,
            min(
                len(requests),
                int(os.getenv("CFB_CFBD_MAX_CONCURRENCY", "2")),
            ),
        )
        if max_workers == 1:
            return [fetch_one(request) for request in requests]
        responses = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(fetch_one, request): request for request in requests
            }
            for future in as_completed(futures):
                responses.append(future.result())
        return sorted(
            responses,
            key=lambda response: str(response.request.get("parameters", {})),
        )

    @staticmethod
    def provider_value(value: Any) -> Any:
        """Convert a generated SDK value into canonical JSON-compatible data."""
        if hasattr(value, "to_dict"):
            return BaseIngester.provider_value(value.to_dict())
        if isinstance(value, dict):
            return {
                str(key): BaseIngester.provider_value(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [BaseIngester.provider_value(item) for item in value]
        if isinstance(value, datetime):
            return value.isoformat()
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if hasattr(value, "__dict__"):
            return BaseIngester.provider_value(vars(value))
        return str(value)

    def normalize_to_eastern(self, dt: Any) -> datetime | None:
        """Normalize a datetime to US/Eastern timezone.

        Accepts datetime or ISO-like string; returns aware datetime in Eastern.
        Missing values remain missing, but malformed timestamps fail closed.
        """
        if dt is None or dt == "":
            return None
        if isinstance(dt, str):
            try:
                parsed = datetime.fromisoformat(dt.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError(f"Invalid provider timestamp: {dt!r}") from exc
        else:
            parsed = dt
        if not isinstance(parsed, datetime):
            raise TypeError(f"Expected datetime provider timestamp, got {type(dt)!r}")
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
        written = self.storage.write(self.entity_name, data, partition, overwrite=True)
        print(
            f"Wrote {written} records to {self.entity_name}/{partition.path_suffix()}."
        )

    def run(self) -> None:
        """Fetch, capture, catalog, and finally update compatibility storage."""
        dual_write_default = (
            "1" if self.storage.describe().casefold().startswith("r2:") else "0"
        )
        dual_write = os.getenv("CFB_LAKE_DUAL_WRITE", dual_write_default) == "1"
        conn_url = os.getenv("DATABASE_URL")
        if dual_write and not conn_url and os.getenv("CFB_REQUIRE_CATALOG", "0") == "1":
            raise ValueError("DATABASE_URL is required when CFB_REQUIRE_CATALOG=1")
        requests = self.source_requests()
        ingestion_run_id = (
            (os.getenv("CFB_INGESTION_RUN_ID") or uuid4().hex)
            if dual_write and conn_url
            else None
        )
        if ingestion_run_id and conn_url:
            from cks_picks_cfb.data.catalog import begin_ingestion_run

            begin_ingestion_run(
                conn_url,
                ingestion_run_id=ingestion_run_id,
                provider="cfbd",
                entity=self.entity_name.removeprefix("raw/"),
                request={"requests": [request.manifest() for request in requests]},
            )
        try:
            print(f"Starting {self.__class__.__name__} for {self.year}...")
            print(f"  - Using storage: {self.storage.describe()}")

            responses = self.fetch_source_responses(requests)
            raw_data = [record for response in responses for record in response.records]
            self.capture_time = max(response.captured_at for response in responses)
            print(f"Fetched {len(raw_data)} records from CFBD API.")
            if not raw_data:
                raise DataUnavailableError(self.entity_name, self.year)

            # Transform data for storage
            transformed_data = self.transform_data(raw_data)
            print(f"Transformed {len(transformed_data)} records for ingestion.")
            if not transformed_data:
                raise ValueError(
                    f"{self.entity_name} produced no valid rows after transformation"
                )

            # Dual-write an immutable Bronze capture.  Repeated provider payloads
            # reuse the same Parquet object while preserving a new observation.
            if dual_write:
                from cks_picks_cfb.data.catalog import (
                    finish_ingestion_run,
                    register_source_capture,
                )
                from cks_picks_cfb.data.lake import capture_provider_records

                for response in responses:
                    capture = capture_provider_records(
                        self.storage,
                        provider=response.provider,
                        entity=response.entity,
                        records=[
                            self.provider_value(record) for record in response.records
                        ],
                        captured_at=response.captured_at,
                        effective_at=response.effective_at,
                        request=response.request,
                        provider_api_version=response.provider_api_version,
                        response_metadata=response.response_metadata,
                    )
                    if conn_url:
                        register_source_capture(
                            conn_url,
                            capture,
                            ingestion_run_id=ingestion_run_id,
                        )

            # Compatibility storage is deliberately last: failures above cannot
            # mutate the legacy projection without a durable capture/catalog row.
            self.ingest_data(transformed_data)
            if ingestion_run_id and conn_url:
                from cks_picks_cfb.data.catalog import finish_ingestion_run

                finish_ingestion_run(conn_url, ingestion_run_id, succeeded=True)

            print(f"Completed {self.__class__.__name__} successfully.")

        except Exception as e:
            if ingestion_run_id and conn_url:
                from cks_picks_cfb.data.catalog import finish_ingestion_run

                finish_ingestion_run(
                    conn_url,
                    ingestion_run_id,
                    succeeded=False,
                    error_category=type(e).__name__,
                    error_detail=str(e),
                )
            print(f"Error in {self.__class__.__name__}: {e}")
            raise
