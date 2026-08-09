"""Storage abstraction layer for CFB model data.

Provides a unified interface for reading/writing data from local or cloud storage.
Supports:
- Local filesystem (external drive)
- Cloudflare R2 (S3-compatible)
- AWS S3

Usage:
    from cks_picks_cfb.data.storage import get_storage

    # Get storage instance (auto-detects backend from environment)
    storage = get_storage()

    # Read data (path-based API)
    df = storage.read_parquet("processed/team_game/2024.parquet")

    # Read data (entity/partition API for feature pipeline)
    records = storage.read_index("games", {"season": "2024", "week": "1"})

    # Write data
    storage.write_parquet(df, "processed/team_game/2024.parquet")

    # List files
    files = storage.list_files("raw/games/")

Configuration:
    Set in .env file:
    - CFB_STORAGE_BACKEND: 'local', 'r2', or 's3'
    - CFB_MODEL_DATA_ROOT: Path to local data (for local backend)
    - CFB_R2_*: R2 configuration (for r2 backend)
    - CFB_S3_*: S3 configuration (for s3 backend)
"""

import json
import os
import re
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


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
    def read_parquet(self, path: str) -> pd.DataFrame:
        """Read a parquet file."""
        pass

    @abstractmethod
    def write_parquet(self, df: pd.DataFrame, path: str) -> None:
        """Write a parquet file."""
        pass

    @abstractmethod
    def read_csv(self, path: str, **kwargs) -> pd.DataFrame:
        """Read a CSV file."""
        pass

    @abstractmethod
    def write_csv(self, df: pd.DataFrame, path: str, **kwargs) -> None:
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


class LocalStorage(StorageBackend):
    """Local filesystem storage (external drive)."""

    def __init__(self, root_path: str):
        """Initialize local storage.

        Args:
            root_path: Root directory for data storage
        """
        self.root_path = Path(root_path)
        if not self.root_path.exists():
            raise ValueError(f"Data root does not exist: {self.root_path}")

    def _get_path(self, path: str) -> Path:
        """Get full local path."""
        return self.root_path / path

    def read_parquet(self, path: str) -> pd.DataFrame:
        """Read a parquet file."""
        full_path = self._get_path(path)
        return pd.read_parquet(full_path)

    def write_parquet(self, df: pd.DataFrame, path: str) -> None:
        """Write a parquet file."""
        full_path = self._get_path(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(full_path)

    def read_csv(self, path: str, **kwargs) -> pd.DataFrame:
        """Read a CSV file."""
        full_path = self._get_path(path)
        return pd.read_csv(full_path, **kwargs)

    def write_csv(self, df: pd.DataFrame, path: str, **kwargs) -> None:
        """Write a CSV file."""
        full_path = self._get_path(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(full_path, **kwargs)

    def read_bytes(self, path: str) -> bytes:
        """Read bytes from local storage."""
        return self._get_path(path).read_bytes()

    def write_bytes(self, data: bytes, path: str) -> None:
        """Write bytes to local storage."""
        full_path = self._get_path(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(data)

    def exists(self, path: str) -> bool:
        """Check if a file exists."""
        return self._get_path(path).exists()

    def list_files(self, prefix: str) -> list[str]:
        """List files with given prefix."""
        prefix_path = self._get_path(prefix)
        if not prefix_path.exists():
            return []

        if prefix_path.is_file():
            return [prefix]

        # List all files recursively under prefix
        files = []
        for file_path in prefix_path.rglob("*"):
            if file_path.is_file():
                # Get relative path from root
                rel_path = file_path.relative_to(self.root_path)
                files.append(str(rel_path))
        return files

    def get_full_path(self, path: str) -> str:
        """Get the full local path."""
        return str(self._get_path(path))

    def object_metadata(self, path: str) -> Mapping[str, Any]:
        stat = self._get_path(path).stat()
        return {
            "size": stat.st_size,
            "last_modified": datetime.fromtimestamp(stat.st_mtime)
            .astimezone()
            .isoformat(),
        }

    def _get_entity_partition_path(self, entity: str, partition: Partition) -> Path:
        """Get path for entity partition."""
        return self._get_path(entity) / partition.path_suffix()

    def read_index(
        self, entity: str, filters: Mapping[str, Any], columns: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Read records by entity and partition filters."""
        partition_values = {k: str(v) for k, v in filters.items() if v is not None}
        partition = Partition(partition_values)
        base_dir = self._get_entity_partition_path(entity, partition)

        if not base_dir.exists():
            return []

        # Look for parquet files first, then CSV
        parquet_files = sorted(
            [p for p in base_dir.rglob("*.parquet") if not p.name.startswith("._")]
        )

        if parquet_files:
            rows: list[dict[str, Any]] = []
            for fpath in parquet_files:
                try:
                    table = pq.read_table(fpath, columns=columns)
                    rows.extend(table.to_pylist())
                except Exception as e:
                    relative = str(fpath.relative_to(self.root_path))
                    self.quarantine_object(relative, e)
                    raise StorageError(f"Unreadable parquet object: {fpath}") from e
            return rows

        # Fall back to CSV
        csv_files = sorted(
            [
                p
                for p in base_dir.rglob("data.csv")
                if p.is_file() and not p.name.startswith("._")
            ]
        )

        if csv_files:
            frames: list[pd.DataFrame] = []
            for fpath in csv_files:
                try:
                    df = pd.read_csv(fpath)
                    if columns:
                        df = df[columns]
                    frames.append(df)  # type: ignore[arg-type]
                except Exception as e:
                    relative = str(fpath.relative_to(self.root_path))
                    self.quarantine_object(relative, e)
                    raise StorageError(f"Unreadable CSV object: {fpath}") from e
            if not frames:
                return []
            df_all = pd.concat(frames, ignore_index=True)
            return df_all.to_dict(orient="records")

        return []

    def write(
        self,
        entity: str,
        records: Sequence[Mapping[str, Any]],
        partition: Partition,
        *,
        overwrite: bool = True,
    ) -> int:
        """Write records for an entity to a specific partition."""
        import shutil

        part_dir = self._get_entity_partition_path(entity, partition)

        if overwrite and part_dir.exists():
            try:
                shutil.rmtree(part_dir, ignore_errors=True)
            except OSError as e:
                raise ValueError(
                    f"Failed to remove existing partition directory {part_dir}: {e}"
                ) from e

        part_dir.mkdir(parents=True, exist_ok=True)

        if not records:
            # Write empty manifest
            manifest = {
                "rows": 0,
                "write_time": datetime.now().isoformat(timespec="seconds"),
                "entity": entity,
                "schema_version": "cloud_v1",
                "schema": None,
            }
            with (part_dir / "manifest.json").open("w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)
            return 0

        # Write as parquet
        try:
            table = pa.Table.from_pylist(list(records))
        except Exception as e:
            raise ValueError(f"Failed to create pyarrow Table from records: {e}") from e

        pq.write_to_dataset(
            table,
            root_path=part_dir,
            compression="snappy",
            basename_template="part-{i}.parquet",
        )
        num_rows = table.num_rows
        schema = table.schema

        # Write manifest
        manifest = {
            "rows": num_rows,
            "write_time": datetime.now().isoformat(timespec="seconds"),
            "entity": entity,
            "schema_version": "cloud_v1",
            "schema": {
                "fields": [
                    {
                        "name": f.name,
                        "type": str(f.type),
                        "nullable": f.nullable,
                    }
                    for f in schema
                ]
            }
            if schema
            else None,
        }
        with (part_dir / "manifest.json").open("w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        return num_rows

    def root(self) -> Path:
        """Return the root path for the storage backend."""
        return self.root_path

    def describe(self) -> str:
        return f"local:{self.root_path}"


class R2Storage(StorageBackend):
    """Cloudflare R2 storage (S3-compatible) with local caching and parallel downloads."""

    def __init__(
        self,
        bucket: str,
        account_id: str,
        access_key: str,
        secret_key: str,
        endpoint: Optional[str] = None,
        cache_dir: Optional[str] = None,
        max_workers: int = 8,
    ):
        """Initialize R2 storage.

        Args:
            bucket: R2 bucket name
            account_id: Cloudflare account ID
            access_key: R2 API access key
            secret_key: R2 API secret key
            endpoint: Optional custom endpoint URL
            cache_dir: Local cache directory (default: ~/.cache/cfb_model/r2/)
            max_workers: Max parallel download workers (default: 8)
        """
        try:
            import boto3
        except ImportError:
            raise ImportError(
                "boto3 required for R2 storage. Install with: uv add boto3"
            )

        self.bucket = bucket
        if endpoint is None:
            endpoint = f"https://{account_id}.r2.cloudflarestorage.com"

        self.s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="auto",  # R2 uses 'auto' region
        )

        # Setup local cache
        if cache_dir is None:
            cache_dir = os.path.expanduser("~/.cache/cfb_model/r2")
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_workers = max_workers
        self._cache_hits = 0
        self._cache_misses = 0

        # Setup memory cache for read_index (LRU cache with TTL)

        self._memory_cache = {}
        self._memory_cache_ttl = 300  # 5 minutes TTL
        self._memory_cache_timestamps = {}

    def read_parquet(self, path: str) -> pd.DataFrame:
        """Read a parquet file from R2."""
        import io

        obj = self.s3_client.get_object(Bucket=self.bucket, Key=path)
        buffer = io.BytesIO(obj["Body"].read())
        return pd.read_parquet(buffer)

    def write_parquet(self, df: pd.DataFrame, path: str) -> None:
        """Write a parquet file to R2."""
        import io

        buffer = io.BytesIO()
        df.to_parquet(buffer)
        buffer.seek(0)
        self.s3_client.put_object(Bucket=self.bucket, Key=path, Body=buffer.getvalue())
        self._invalidate_cache(path)

    def read_csv(self, path: str, **kwargs) -> pd.DataFrame:
        """Read a CSV file from R2."""
        obj = self.s3_client.get_object(Bucket=self.bucket, Key=path)
        return pd.read_csv(obj["Body"], **kwargs)

    def write_csv(self, df: pd.DataFrame, path: str, **kwargs) -> None:
        """Write a CSV file to R2."""
        import io

        buffer = io.StringIO()
        df.to_csv(buffer, **kwargs)
        self.s3_client.put_object(Bucket=self.bucket, Key=path, Body=buffer.getvalue())
        self._invalidate_cache(path)

    def read_bytes(self, path: str) -> bytes:
        """Read bytes from R2."""
        obj = self.s3_client.get_object(Bucket=self.bucket, Key=path)
        return obj["Body"].read()

    def write_bytes(self, data: bytes, path: str) -> None:
        """Write bytes to R2."""
        self.s3_client.put_object(Bucket=self.bucket, Key=path, Body=data)
        self._invalidate_cache(path)

    def _invalidate_cache(self, path: str | None = None) -> None:
        """Invalidate disk and query caches after a write.

        Immutable lake objects normally never change, but legacy partitions still do.
        A write must therefore never leave a stale local object or stale ``read_index``
        result visible to a subsequent pipeline step.
        """
        self._memory_cache.clear()
        self._memory_cache_timestamps.clear()
        if path is not None:
            self._get_cache_path(path).unlink(missing_ok=True)

    def exists(self, path: str) -> bool:
        """Check if a file exists in R2."""
        try:
            self.s3_client.head_object(Bucket=self.bucket, Key=path)
            return True
        except Exception:
            return False

    def list_files(self, prefix: str) -> list[str]:
        """List files with given prefix in R2."""
        return list(self.list_object_metadata(prefix))

    def list_object_metadata(self, prefix: str) -> Mapping[str, Mapping[str, Any]]:
        """List R2 keys using metadata already present in ListObjectsV2 pages."""
        objects: dict[str, Mapping[str, Any]] = {}
        continuation_token: Optional[str] = None

        while True:
            kwargs = {"Bucket": self.bucket, "Prefix": prefix}
            if continuation_token:
                kwargs["ContinuationToken"] = continuation_token

            response = self.s3_client.list_objects_v2(**kwargs)
            for obj in response.get("Contents", []):
                modified = obj.get("LastModified")
                objects[str(obj["Key"])] = {
                    "size": int(obj.get("Size", 0)),
                    "etag": str(obj.get("ETag", "")).strip('"') or None,
                    "last_modified": modified.isoformat() if modified else None,
                    "storage_class": obj.get("StorageClass"),
                }

            if response.get("IsTruncated"):
                continuation_token = response.get("NextContinuationToken")
            else:
                break

        return objects

    def get_full_path(self, path: str) -> str:
        """Get the S3 URI for a file."""
        return f"s3://{self.bucket}/{path}"

    def object_metadata(self, path: str) -> Mapping[str, Any]:
        response = self.s3_client.head_object(Bucket=self.bucket, Key=path)
        modified = response.get("LastModified")
        return {
            "size": int(response.get("ContentLength", 0)),
            "etag": str(response.get("ETag", "")).strip('"') or None,
            "last_modified": modified.isoformat() if modified else None,
            "version_id": response.get("VersionId"),
            "content_type": response.get("ContentType"),
        }

    def _get_entity_partition_prefix(self, entity: str, partition: Partition) -> str:
        """Get S3 prefix for entity partition."""
        return f"{entity}/{partition.path_suffix()}"

    def _get_cache_path(self, file_key: str) -> Path:
        """Get local cache path for an S3 file key."""
        safe_name = file_key.replace("/", "__")
        return self.cache_dir / safe_name

    def _download_file(self, file_key: str, use_cache: bool = True) -> bytes:
        """Download a file from R2 with caching support."""
        cache_path = self._get_cache_path(file_key)
        if use_cache and cache_path.exists():
            self._cache_hits += 1
            return cache_path.read_bytes()
        obj = self.s3_client.get_object(Bucket=self.bucket, Key=file_key)
        data = obj["Body"].read()
        if use_cache:
            cache_path.write_bytes(data)
            self._cache_misses += 1
        return data

    def _download_files_parallel(
        self, file_keys: list[str], use_cache: bool = True
    ) -> dict[str, bytes]:
        """Download multiple files in parallel."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results: dict[str, bytes] = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_key = {
                executor.submit(self._download_file, key, use_cache): key
                for key in file_keys
            }
            for future in as_completed(future_to_key):
                key = future_to_key[future]
                try:
                    results[key] = future.result()
                except Exception as e:
                    raise StorageError(f"Failed to download object: {key}") from e
        return results

    def read_index(
        self,
        entity: str,
        filters: Mapping[str, Any],
        columns: list[str] | None = None,
        *,
        use_cache: bool = True,
        parallel: bool = True,
    ) -> list[dict[str, Any]]:
        """Read records by entity and partition filters with caching and parallel downloads."""
        import io
        import time

        # Memory cache key
        cache_key = (
            entity,
            tuple(sorted(filters.items())),
            tuple(columns) if columns else None,
        )

        # Check memory cache
        if cache_key in self._memory_cache:
            cache_time = self._memory_cache_timestamps.get(cache_key, 0)
            if time.time() - cache_time < self._memory_cache_ttl:
                return self._memory_cache[cache_key]
            else:
                # Expired, remove from cache
                del self._memory_cache[cache_key]
                del self._memory_cache_timestamps[cache_key]

        partition_values = {k: str(v) for k, v in filters.items() if v is not None}
        partition = Partition(partition_values)
        prefix = self._get_entity_partition_prefix(entity, partition)
        files = self.list_files(prefix)
        if not files:
            return []

        result: list[dict[str, Any]] = []

        parquet_files = [f for f in files if f.endswith(".parquet")]
        if parquet_files:
            rows: list[dict[str, Any]] = []
            if parallel and len(parquet_files) > 1:
                file_contents = self._download_files_parallel(
                    parquet_files, use_cache=use_cache
                )
                for file_key, data in file_contents.items():
                    try:
                        buffer = io.BytesIO(data)
                        table = pq.read_table(buffer, columns=columns)
                        rows.extend(table.to_pylist())
                    except Exception as e:
                        self.quarantine_object(file_key, e)
                        raise StorageError(
                            f"Unreadable parquet object: {file_key}"
                        ) from e
            else:
                for file_key in parquet_files:
                    try:
                        data = self._download_file(file_key, use_cache=use_cache)
                        buffer = io.BytesIO(data)
                        table = pq.read_table(buffer, columns=columns)
                        rows.extend(table.to_pylist())
                    except Exception as e:
                        self.quarantine_object(file_key, e)
                        raise StorageError(
                            f"Unreadable parquet object: {file_key}"
                        ) from e
            result = rows
        else:
            csv_files = [f for f in files if f.endswith("data.csv")]
            if csv_files:
                frames: list[pd.DataFrame] = []
                if parallel and len(csv_files) > 1:
                    file_contents = self._download_files_parallel(
                        csv_files, use_cache=use_cache
                    )
                    for file_key, data in file_contents.items():
                        try:
                            df = pd.read_csv(io.BytesIO(data))
                            if columns:
                                df = df[columns]
                            frames.append(df)
                        except Exception as e:
                            self.quarantine_object(file_key, e)
                            raise StorageError(
                                f"Unreadable CSV object: {file_key}"
                            ) from e
                else:
                    for file_key in csv_files:
                        try:
                            data = self._download_file(file_key, use_cache=use_cache)
                            df = pd.read_csv(io.BytesIO(data))
                            if columns:
                                df = df[columns]
                            frames.append(df)
                        except Exception as e:
                            self.quarantine_object(file_key, e)
                            raise StorageError(
                                f"Unreadable CSV object: {file_key}"
                            ) from e
                if frames:
                    df_all = pd.concat(frames, ignore_index=True)
                    result = df_all.to_dict(orient="records")

        # Store in memory cache
        self._memory_cache[cache_key] = result
        self._memory_cache_timestamps[cache_key] = time.time()

        return result

    def write(
        self,
        entity: str,
        records: Sequence[Mapping[str, Any]],
        partition: Partition,
        *,
        overwrite: bool = True,
    ) -> int:
        """Write records for an entity to a specific partition."""
        import io

        prefix = self._get_entity_partition_prefix(entity, partition)

        # If overwrite, delete existing files in this partition
        if overwrite:
            existing_files = self.list_files(prefix)
            for file_key in existing_files:
                try:
                    self.s3_client.delete_object(Bucket=self.bucket, Key=file_key)
                except Exception as e:
                    print(f"Warning: Failed to delete {file_key}: {e}")

        if not records:
            # Write empty manifest
            manifest_key = f"{prefix}/manifest.json"
            manifest = {
                "rows": 0,
                "write_time": datetime.now().isoformat(timespec="seconds"),
                "entity": entity,
                "schema_version": "cloud_v1",
                "schema": None,
            }
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=manifest_key,
                Body=json.dumps(manifest, indent=2).encode("utf-8"),
            )
            return 0

        # Convert records to DataFrame then to parquet
        try:
            table = pa.Table.from_pylist(list(records))
        except Exception as e:
            raise ValueError(f"Failed to create pyarrow Table from records: {e}") from e

        # Write parquet file
        buffer = io.BytesIO()
        pq.write_table(table, buffer, compression="snappy")
        buffer.seek(0)

        file_key = f"{prefix}/part-0.parquet"
        self.s3_client.put_object(
            Bucket=self.bucket, Key=file_key, Body=buffer.getvalue()
        )

        num_rows = table.num_rows
        schema = table.schema

        # Write manifest
        manifest_key = f"{prefix}/manifest.json"
        manifest = {
            "rows": num_rows,
            "write_time": datetime.now().isoformat(timespec="seconds"),
            "entity": entity,
            "schema_version": "cloud_v1",
            "schema": {
                "fields": [
                    {"name": f.name, "type": str(f.type), "nullable": f.nullable}
                    for f in schema
                ]
            }
            if schema
            else None,
        }
        self.s3_client.put_object(
            Bucket=self.bucket,
            Key=manifest_key,
            Body=json.dumps(manifest, indent=2).encode("utf-8"),
        )

        return num_rows

    def root(self) -> str:
        """Return the root path for the storage backend."""
        return f"s3://{self.bucket}"

    def describe(self) -> str:
        return f"r2:{self.bucket}"


class S3Storage(StorageBackend):
    """AWS S3 storage."""

    def __init__(
        self,
        bucket: str,
        region: str = "us-east-1",
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
    ):
        """Initialize S3 storage.

        Args:
            bucket: S3 bucket name
            region: AWS region
            access_key: Optional AWS access key (uses default credentials if not provided)
            secret_key: Optional AWS secret key
        """
        try:
            import boto3
        except ImportError:
            raise ImportError(
                "boto3 required for S3 storage. Install with: uv add boto3"
            )

        if access_key and secret_key:
            self.s3_client = boto3.client(
                "s3",
                region_name=region,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
            )
        else:
            # Use default credentials from environment/config
            self.s3_client = boto3.client("s3", region_name=region)

        self.bucket = bucket

    def read_parquet(self, path: str) -> pd.DataFrame:
        """Read a parquet file from S3."""
        obj = self.s3_client.get_object(Bucket=self.bucket, Key=path)
        return pd.read_parquet(obj["Body"])

    def write_parquet(self, df: pd.DataFrame, path: str) -> None:
        """Write a parquet file to S3."""
        import io

        buffer = io.BytesIO()
        df.to_parquet(buffer)
        buffer.seek(0)
        self.s3_client.put_object(Bucket=self.bucket, Key=path, Body=buffer.getvalue())

    def read_csv(self, path: str, **kwargs) -> pd.DataFrame:
        """Read a CSV file from S3."""
        obj = self.s3_client.get_object(Bucket=self.bucket, Key=path)
        return pd.read_csv(obj["Body"], **kwargs)

    def write_csv(self, df: pd.DataFrame, path: str, **kwargs) -> None:
        """Write a CSV file to S3."""
        import io

        buffer = io.StringIO()
        df.to_csv(buffer, **kwargs)
        self.s3_client.put_object(Bucket=self.bucket, Key=path, Body=buffer.getvalue())

    def read_bytes(self, path: str) -> bytes:
        """Read bytes from S3."""
        obj = self.s3_client.get_object(Bucket=self.bucket, Key=path)
        return obj["Body"].read()

    def write_bytes(self, data: bytes, path: str) -> None:
        """Write bytes to S3."""
        self.s3_client.put_object(Bucket=self.bucket, Key=path, Body=data)

    def exists(self, path: str) -> bool:
        """Check if a file exists in S3."""
        try:
            self.s3_client.head_object(Bucket=self.bucket, Key=path)
            return True
        except Exception:
            return False

    def list_files(self, prefix: str) -> list[str]:
        """List files with given prefix in S3."""
        return list(self.list_object_metadata(prefix))

    def list_object_metadata(self, prefix: str) -> Mapping[str, Mapping[str, Any]]:
        """List S3 keys using metadata already present in ListObjectsV2 pages."""
        objects: dict[str, Mapping[str, Any]] = {}
        continuation_token: Optional[str] = None

        while True:
            kwargs = {"Bucket": self.bucket, "Prefix": prefix}
            if continuation_token:
                kwargs["ContinuationToken"] = continuation_token

            response = self.s3_client.list_objects_v2(**kwargs)
            for obj in response.get("Contents", []):
                modified = obj.get("LastModified")
                objects[str(obj["Key"])] = {
                    "size": int(obj.get("Size", 0)),
                    "etag": str(obj.get("ETag", "")).strip('"') or None,
                    "last_modified": modified.isoformat() if modified else None,
                    "storage_class": obj.get("StorageClass"),
                }

            if response.get("IsTruncated"):
                continuation_token = response.get("NextContinuationToken")
            else:
                break

        return objects

    def get_full_path(self, path: str) -> str:
        """Get the S3 URI for a file."""
        return f"s3://{self.bucket}/{path}"

    def _get_entity_partition_prefix(self, entity: str, partition: Partition) -> str:
        """Get S3 prefix for entity partition."""
        return f"{entity}/{partition.path_suffix()}"

    def read_index(
        self, entity: str, filters: Mapping[str, Any], columns: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Read records by entity and partition filters."""
        import io

        partition_values = {k: str(v) for k, v in filters.items() if v is not None}
        partition = Partition(partition_values)
        prefix = self._get_entity_partition_prefix(entity, partition)

        # List all files under this prefix
        files = self.list_files(prefix)

        if not files:
            return []

        # Look for parquet files first
        parquet_files = [f for f in files if f.endswith(".parquet")]

        if parquet_files:
            rows: list[dict[str, Any]] = []
            for file_key in parquet_files:
                try:
                    obj = self.s3_client.get_object(Bucket=self.bucket, Key=file_key)
                    buffer = io.BytesIO(obj["Body"].read())
                    table = pq.read_table(buffer, columns=columns)
                    rows.extend(table.to_pylist())
                except Exception as e:
                    self.quarantine_object(file_key, e)
                    raise StorageError(f"Unreadable parquet object: {file_key}") from e
            return rows

        # Fall back to CSV files
        csv_files = [f for f in files if f.endswith("data.csv")]

        if csv_files:
            frames: list[pd.DataFrame] = []
            for file_key in csv_files:
                try:
                    obj = self.s3_client.get_object(Bucket=self.bucket, Key=file_key)
                    df = pd.read_csv(obj["Body"])
                    if columns:
                        df = df[columns]
                    frames.append(df)  # type: ignore[arg-type]
                except Exception as e:
                    self.quarantine_object(file_key, e)
                    raise StorageError(f"Unreadable CSV object: {file_key}") from e
            if not frames:
                return []
            df_all = pd.concat(frames, ignore_index=True)
            return df_all.to_dict(orient="records")

        return []

    def write(
        self,
        entity: str,
        records: Sequence[Mapping[str, Any]],
        partition: Partition,
        *,
        overwrite: bool = True,
    ) -> int:
        """Write records for an entity to a specific partition."""
        import io

        prefix = self._get_entity_partition_prefix(entity, partition)

        # If overwrite, delete existing files in this partition
        if overwrite:
            existing_files = self.list_files(prefix)
            for file_key in existing_files:
                try:
                    self.s3_client.delete_object(Bucket=self.bucket, Key=file_key)
                except Exception as e:
                    print(f"Warning: Failed to delete {file_key}: {e}")

        if not records:
            # Write empty manifest
            manifest_key = f"{prefix}/manifest.json"
            manifest = {
                "rows": 0,
                "write_time": datetime.now().isoformat(timespec="seconds"),
                "entity": entity,
                "schema_version": "cloud_v1",
                "schema": None,
            }
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=manifest_key,
                Body=json.dumps(manifest, indent=2).encode("utf-8"),
            )
            return 0

        # Convert records to DataFrame then to parquet
        try:
            table = pa.Table.from_pylist(list(records))
        except Exception as e:
            raise ValueError(f"Failed to create pyarrow Table from records: {e}") from e

        # Write parquet file
        buffer = io.BytesIO()
        pq.write_table(table, buffer, compression="snappy")
        buffer.seek(0)

        file_key = f"{prefix}/part-0.parquet"
        self.s3_client.put_object(
            Bucket=self.bucket, Key=file_key, Body=buffer.getvalue()
        )

        num_rows = table.num_rows
        schema = table.schema

        # Write manifest
        manifest_key = f"{prefix}/manifest.json"
        manifest = {
            "rows": num_rows,
            "write_time": datetime.now().isoformat(timespec="seconds"),
            "entity": entity,
            "schema_version": "cloud_v1",
            "schema": {
                "fields": [
                    {"name": f.name, "type": str(f.type), "nullable": f.nullable}
                    for f in schema
                ]
            }
            if schema
            else None,
        }
        self.s3_client.put_object(
            Bucket=self.bucket,
            Key=manifest_key,
            Body=json.dumps(manifest, indent=2).encode("utf-8"),
        )

        return num_rows

    def root(self) -> str:
        """Return the root path for the storage backend."""
        return f"s3://{self.bucket}"

    def describe(self) -> str:
        return f"s3:{self.bucket}"


class ReadOnlyStorage(StorageBackend):
    """Capability wrapper that prevents source-bucket mutation in process."""

    def __init__(self, backend: StorageBackend) -> None:
        self.backend = backend

    def read_parquet(self, path: str) -> pd.DataFrame:
        return self.backend.read_parquet(path)

    def read_csv(self, path: str, **kwargs) -> pd.DataFrame:
        return self.backend.read_csv(path, **kwargs)

    def read_bytes(self, path: str) -> bytes:
        return self.backend.read_bytes(path)

    def exists(self, path: str) -> bool:
        return self.backend.exists(path)

    def list_files(self, prefix: str) -> list[str]:
        return self.backend.list_files(prefix)

    def list_object_metadata(self, prefix: str) -> Mapping[str, Mapping[str, Any]]:
        return self.backend.list_object_metadata(prefix)

    def get_full_path(self, path: str) -> str:
        return self.backend.get_full_path(path)

    def object_metadata(self, path: str) -> Mapping[str, Any]:
        return self.backend.object_metadata(path)

    def root(self) -> Path | str:
        return self.backend.root()

    def describe(self) -> str:
        return f"read-only:{self.backend.describe()}"

    def read_index(
        self, entity: str, filters: Mapping[str, Any], columns: list[str] | None = None
    ) -> list[dict[str, Any]]:
        raise StorageError(
            "read_index is disabled for read-only sources because legacy error "
            "handling can quarantine into the source bucket; read objects directly"
        )

    @staticmethod
    def _deny() -> None:
        raise StorageError("read-only source storage cannot be mutated")

    def write_parquet(self, df: pd.DataFrame, path: str) -> None:
        self._deny()

    def write_csv(self, df: pd.DataFrame, path: str, **kwargs) -> None:
        self._deny()

    def write_bytes(self, data: bytes, path: str) -> None:
        self._deny()

    def write(
        self,
        entity: str,
        records: Sequence[Mapping[str, Any]],
        partition: Partition,
        *,
        overwrite: bool = True,
    ) -> int:
        self._deny()
        return 0


def get_source_storage() -> ReadOnlyStorage:
    """Return the separately configured historical source as read-only."""
    settings = StorageSettings.source_from_env()
    missing = [
        name
        for name, value in {
            "CFB_R2_SOURCE_BUCKET": settings.bucket,
            "CFB_R2_SOURCE_ACCOUNT_ID": settings.account_id,
            "CFB_R2_SOURCE_ACCESS_KEY": settings.access_key,
            "CFB_R2_SOURCE_SECRET_KEY": settings.secret_key,
        }.items()
        if not value
    ]
    if missing:
        raise ValueError(f"Historical source storage requires: {', '.join(missing)}")
    backend = get_storage(settings)
    return ReadOnlyStorage(backend)


def get_storage(
    settings: StorageSettings | None = None, *, environment: str | None = None
) -> StorageBackend:
    """Get storage instance based on environment configuration.

    Returns:
        Configured storage backend instance

    Raises:
        ValueError: If storage backend is not configured or invalid
    """
    settings = settings or StorageSettings.from_env(environment=environment)
    backend = settings.backend.lower()

    if backend == "local":
        data_root = settings.data_root
        if not data_root:
            raise ValueError(
                "CFB_MODEL_DATA_ROOT must be set for local storage backend"
            )
        return LocalStorage(data_root)

    elif backend == "r2":
        selected = settings.environment
        prefix = (
            "CFB_R2_PREVIEW"
            if selected == "preview"
            else "CFB_R2_SOURCE"
            if selected == "source"
            else "CFB_R2"
        )
        bucket = settings.bucket
        account_id = settings.account_id
        access_key = settings.access_key
        secret_key = settings.secret_key
        endpoint = settings.endpoint

        if not all([bucket, account_id, access_key, secret_key]):
            raise ValueError(
                f"R2 {selected} storage requires: {prefix}_BUCKET, "
                f"{prefix}_ACCOUNT_ID, {prefix}_ACCESS_KEY, {prefix}_SECRET_KEY"
            )

        assert (
            bucket is not None
            and account_id is not None
            and access_key is not None
            and secret_key is not None
        )
        return R2Storage(bucket, account_id, access_key, secret_key, endpoint)

    elif backend == "s3":
        bucket = settings.bucket
        region = settings.region
        access_key = settings.access_key
        secret_key = settings.secret_key

        if not bucket:
            raise ValueError("S3 storage requires: CFB_S3_BUCKET")

        return S3Storage(bucket, region, access_key, secret_key)

    else:
        raise ValueError(
            f"Invalid storage backend: {backend}. Must be 'local', 'r2', or 's3'"
        )
