"""Storage base types: error, partition, settings, and abstract backend.

This module is intentionally import-free of boto3 / pyarrow so that it
can be used in environments where only the abstract interface is needed.
"""

from __future__ import annotations

import json
import os
import re
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pandas as pd


class StorageError(RuntimeError):
    """Raised when storage operations fail."""


@dataclass(frozen=True)
class Partition:
    """A logical partition descriptor used for directory layout.

    Example for plays: {"season": "2024", "week": "1", "game_id": "401525416"}
    """

    values: Mapping[str, str]

    def path_suffix(self) -> Path:
        parts = [f"{k}={v}" for k, v in self.values.items()]
        return Path(*parts)


@dataclass(frozen=True)
class StorageSettings:
    """Explicit storage configuration for cross-environment pipeline operations."""

    backend: str
    environment: str = "production"
    data_root: str | None = None
    bucket: str | None = None
    account_id: str | None = None
    access_key: str | None = None
    secret_key: str | None = None
    endpoint: str | None = None
    region: str = "us-east-1"
    read_only: bool = False

    @classmethod
    def from_env(cls, *, environment: str | None = None) -> "StorageSettings":
        backend = os.getenv("CFB_STORAGE_BACKEND", "local").lower()
        selected = (environment or os.getenv("CFB_ARTIFACT_ENV", "production")).lower()
        if backend == "local":
            return cls(
                backend=backend,
                environment=selected,
                data_root=os.getenv("CFB_MODEL_DATA_ROOT"),
            )
        if backend == "r2":
            prefix = "CFB_R2_PREVIEW" if selected == "preview" else "CFB_R2"
            return cls(
                backend=backend,
                environment=selected,
                bucket=os.getenv(f"{prefix}_BUCKET"),
                account_id=os.getenv(f"{prefix}_ACCOUNT_ID"),
                access_key=os.getenv(f"{prefix}_ACCESS_KEY"),
                secret_key=os.getenv(f"{prefix}_SECRET_KEY"),
                endpoint=os.getenv(f"{prefix}_ENDPOINT"),
            )
        if backend == "s3":
            return cls(
                backend=backend,
                environment=selected,
                bucket=os.getenv("CFB_S3_BUCKET"),
                access_key=os.getenv("AWS_ACCESS_KEY_ID"),
                secret_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                region=os.getenv("CFB_S3_REGION", "us-east-1"),
            )
        return cls(backend=backend, environment=selected)

    @classmethod
    def source_from_env(cls) -> "StorageSettings":
        """Load the separately scoped, read-only historical R2 source."""
        return cls(
            backend="r2",
            environment="source",
            bucket=os.getenv("CFB_R2_SOURCE_BUCKET"),
            account_id=os.getenv("CFB_R2_SOURCE_ACCOUNT_ID"),
            access_key=os.getenv("CFB_R2_SOURCE_ACCESS_KEY"),
            secret_key=os.getenv("CFB_R2_SOURCE_SECRET_KEY"),
            endpoint=os.getenv("CFB_R2_SOURCE_ENDPOINT"),
            read_only=True,
        )


class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    def read_parquet(self, path: str) -> "pd.DataFrame":
        """Read a parquet file."""
        pass

    @abstractmethod
    def write_parquet(self, df: "pd.DataFrame", path: str) -> None:
        """Write a parquet file."""
        pass

    @abstractmethod
    def read_csv(self, path: str, **kwargs) -> "pd.DataFrame":
        """Read a CSV file."""
        pass

    @abstractmethod
    def write_csv(self, df: "pd.DataFrame", path: str, **kwargs) -> None:
        """Write a CSV file."""
        pass

    @abstractmethod
    def read_bytes(self, path: str) -> bytes:
        """Read an opaque binary object."""
        pass

    @abstractmethod
    def write_bytes(self, data: bytes, path: str) -> None:
        """Write an opaque binary object."""
        pass

    @abstractmethod
    def exists(self, path: str) -> bool:
        """Check if a file exists."""
        pass

    @abstractmethod
    def list_files(self, prefix: str) -> list[str]:
        """List files with given prefix."""
        pass

    @abstractmethod
    def get_full_path(self, path: str) -> str:
        """Get the full path/URL for a file."""
        pass

    # Entity/Partition API for feature pipeline integration
    @abstractmethod
    def read_index(
        self, entity: str, filters: Mapping[str, Any], columns: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Read records by entity and partition filters.

        Args:
            entity: Entity name (e.g., "games", "plays")
            filters: Partition filters (e.g., {"season": "2024", "week": "1"})
            columns: Optional list of columns to read

        Returns:
            List of records as dictionaries
        """
        pass

    @abstractmethod
    def write(
        self,
        entity: str,
        records: Sequence[Mapping[str, Any]],
        partition: Partition,
        *,
        overwrite: bool = True,
    ) -> int:
        """Write records for an entity to a specific partition.

        Args:
            entity: Entity name (e.g., "games", "plays")
            records: Records to write
            partition: Partition specification
            overwrite: Whether to overwrite existing data

        Returns:
            Number of rows written
        """
        pass

    @abstractmethod
    def root(self) -> Path | str:
        """Return the root path for the storage backend.

        Deprecated: prefer describe() for logging, list_partitions() for
        partition discovery, and partition_exists() for existence checks.
        """
        pass

    # --- New entity/partition discovery API (replaces storage.root() / ... calls) ---

    def list_partitions(
        self, entity: str, parent_filters: Mapping[str, Any]
    ) -> list[Partition]:
        """Discover child partitions under entity/parent_partition_path.

        For example, list_partitions("raw/plays", {"year": "2025"}) might return
        [Partition({"year": "2025", "week": "1"}), Partition({"year": "2025", "week": "2"}), ...].

        Default implementation uses list_files() + regex parsing — subclasses may override
        for efficiency (e.g., S3 delimiter-based listing).
        """
        parent_suffix = "/".join(
            f"{k}={v}" for k, v in parent_filters.items() if v is not None
        )
        prefix = f"{entity}/{parent_suffix}/" if parent_suffix else f"{entity}/"
        files = self.list_files(prefix)

        children: dict[frozenset, Partition] = {}
        for fpath in files:
            # Strip the prefix to get the relative path
            rel = fpath[len(prefix) :] if fpath.startswith(prefix) else fpath
            # Extract key=value segments
            segments = re.findall(r"(\w+)=([^/]+)", rel)
            if not segments:
                continue
            # Build partition values from parent + first child segment
            combined = {k: str(v) for k, v in parent_filters.items() if v is not None}
            key_name, key_val = segments[0]
            combined[key_name] = key_val
            key = frozenset(combined.items())
            if key not in children:
                children[key] = Partition(combined)
        return list(children.values())

    def partition_exists(self, entity: str, partition: Partition) -> bool:
        """Check if any data exists for entity/partition.

        Default implementation uses list_files() — subclasses may override for efficiency.
        """
        prefix = f"{entity}/{partition.path_suffix()}"
        return len(self.list_files(prefix)) > 0

    def describe(self) -> str:
        """Return a backend-agnostic identifier for logging (e.g., 'r2:cfb-model-data')."""
        return str(self.root())

    def object_metadata(self, path: str) -> Mapping[str, Any]:
        """Return stable source metadata when the backend exposes it."""
        payload = self.read_bytes(path)
        return {"size": len(payload)}

    def list_object_metadata(self, prefix: str) -> Mapping[str, Mapping[str, Any]]:
        """List object keys and metadata.

        The default is intentionally portable. Cloud backends override this to reuse
        metadata returned by their paginated list API instead of issuing one HEAD
        request per object.
        """
        return {path: self.object_metadata(path) for path in self.list_files(prefix)}

    def quarantine_object(self, path: str, error: Exception) -> str:
        """Copy an unreadable object and diagnostic metadata to quarantine."""
        payload = self.read_bytes(path)
        content_sha = __import__("hashlib").sha256(payload).hexdigest()
        basename = Path(path).name
        prefix = f"lake/quarantine/content_sha={content_sha}"
        object_uri = f"{prefix}/{basename}"
        metadata_uri = f"{prefix}/error.json"
        if not self.exists(object_uri):
            self.write_bytes(payload, object_uri)
        if not self.exists(metadata_uri):
            self.write_bytes(
                json.dumps(
                    {
                        "source_uri": path,
                        "content_sha": content_sha,
                        "error_type": type(error).__name__,
                        "error": str(error),
                        "quarantined_at": datetime.now().astimezone().isoformat(),
                    },
                    sort_keys=True,
                ).encode("utf-8"),
                metadata_uri,
            )
        return object_uri
