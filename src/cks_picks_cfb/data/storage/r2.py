"""Cloud storage backends: Cloudflare R2, AWS S3, and ReadOnlyStorage wrapper."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from cks_picks_cfb.data.storage.base import Partition, StorageBackend, StorageError


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
