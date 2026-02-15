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
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


@dataclass(frozen=True)
class Partition:
    """A logical partition descriptor used for directory layout.

    Example for plays: {"season": "2024", "week": "1", "game_id": "401525416"}
    """

    values: Mapping[str, str]

    def path_suffix(self) -> Path:
        parts = [f"{k}={v}" for k, v in self.values.items()]
        return Path(*parts)


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
        """Return the root path for the storage backend."""
        pass


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
                    print(f"Skipping unreadable file: {fpath} -> {e}")
                    continue
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
                    print(f"Skipping unreadable CSV: {fpath} -> {e}")
                    continue
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


class R2Storage(StorageBackend):
    """Cloudflare R2 storage (S3-compatible)."""

    def __init__(
        self,
        bucket: str,
        account_id: str,
        access_key: str,
        secret_key: str,
        endpoint: Optional[str] = None,
    ):
        """Initialize R2 storage.

        Args:
            bucket: R2 bucket name
            account_id: Cloudflare account ID
            access_key: R2 API access key
            secret_key: R2 API secret key
            endpoint: Optional custom endpoint URL
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

    def exists(self, path: str) -> bool:
        """Check if a file exists in R2."""
        try:
            self.s3_client.head_object(Bucket=self.bucket, Key=path)
            return True
        except Exception:
            return False

    def list_files(self, prefix: str) -> list[str]:
        """List files with given prefix in R2."""
        files: list[str] = []
        continuation_token: Optional[str] = None

        while True:
            kwargs = {"Bucket": self.bucket, "Prefix": prefix}
            if continuation_token:
                kwargs["ContinuationToken"] = continuation_token

            response = self.s3_client.list_objects_v2(**kwargs)
            files.extend(obj["Key"] for obj in response.get("Contents", []))

            if response.get("IsTruncated"):
                continuation_token = response.get("NextContinuationToken")
            else:
                break

        return files

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
                    print(f"Skipping unreadable file: {file_key} -> {e}")
                    continue
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
                    print(f"Skipping unreadable CSV: {file_key} -> {e}")
                    continue
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

    def exists(self, path: str) -> bool:
        """Check if a file exists in S3."""
        try:
            self.s3_client.head_object(Bucket=self.bucket, Key=path)
            return True
        except Exception:
            return False

    def list_files(self, prefix: str) -> list[str]:
        """List files with given prefix in S3."""
        files: list[str] = []
        continuation_token: Optional[str] = None

        while True:
            kwargs = {"Bucket": self.bucket, "Prefix": prefix}
            if continuation_token:
                kwargs["ContinuationToken"] = continuation_token

            response = self.s3_client.list_objects_v2(**kwargs)
            files.extend(obj["Key"] for obj in response.get("Contents", []))

            if response.get("IsTruncated"):
                continuation_token = response.get("NextContinuationToken")
            else:
                break

        return files

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
                    print(f"Skipping unreadable file: {file_key} -> {e}")
                    continue
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
                    print(f"Skipping unreadable CSV: {file_key} -> {e}")
                    continue
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


def get_storage() -> StorageBackend:
    """Get storage instance based on environment configuration.

    Returns:
        Configured storage backend instance

    Raises:
        ValueError: If storage backend is not configured or invalid
    """
    backend = os.getenv("CFB_STORAGE_BACKEND", "local").lower()

    if backend == "local":
        data_root = os.getenv("CFB_MODEL_DATA_ROOT")
        if not data_root:
            raise ValueError(
                "CFB_MODEL_DATA_ROOT must be set for local storage backend"
            )
        return LocalStorage(data_root)

    elif backend == "r2":
        bucket = os.getenv("CFB_R2_BUCKET")
        account_id = os.getenv("CFB_R2_ACCOUNT_ID")
        access_key = os.getenv("CFB_R2_ACCESS_KEY")
        secret_key = os.getenv("CFB_R2_SECRET_KEY")
        endpoint = os.getenv("CFB_R2_ENDPOINT")

        if not all([bucket, account_id, access_key, secret_key]):
            raise ValueError(
                "R2 storage requires: CFB_R2_BUCKET, CFB_R2_ACCOUNT_ID, "
                "CFB_R2_ACCESS_KEY, CFB_R2_SECRET_KEY"
            )

        assert (
            bucket is not None
            and account_id is not None
            and access_key is not None
            and secret_key is not None
        )
        return R2Storage(bucket, account_id, access_key, secret_key, endpoint)

    elif backend == "s3":
        bucket = os.getenv("CFB_S3_BUCKET")
        region = os.getenv("CFB_S3_REGION", "us-east-1")
        access_key = os.getenv("AWS_ACCESS_KEY_ID")
        secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")

        if not bucket:
            raise ValueError("S3 storage requires: CFB_S3_BUCKET")

        return S3Storage(bucket, region, access_key, secret_key)

    else:
        raise ValueError(
            f"Invalid storage backend: {backend}. Must be 'local', 'r2', or 's3'"
        )
