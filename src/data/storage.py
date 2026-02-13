"""Storage abstraction layer for CFB model data.

Provides a unified interface for reading/writing data from local or cloud storage.
Supports:
- Local filesystem (external drive)
- Cloudflare R2 (S3-compatible)
- AWS S3

Usage:
    from src.data.storage import get_storage

    # Get storage instance (auto-detects backend from environment)
    storage = get_storage()

    # Read data
    df = storage.read_parquet("processed/team_game/2024.parquet")

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

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

import pandas as pd


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
        )

    def read_parquet(self, path: str) -> pd.DataFrame:
        """Read a parquet file from R2."""
        obj = self.s3_client.get_object(Bucket=self.bucket, Key=path)
        return pd.read_parquet(obj["Body"])

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
        response = self.s3_client.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
        if "Contents" not in response:
            return []
        return [obj["Key"] for obj in response["Contents"]]

    def get_full_path(self, path: str) -> str:
        """Get the S3 URI for a file."""
        return f"s3://{self.bucket}/{path}"


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
        response = self.s3_client.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
        if "Contents" not in response:
            return []
        return [obj["Key"] for obj in response["Contents"]]

    def get_full_path(self, path: str) -> str:
        """Get the S3 URI for a file."""
        return f"s3://{self.bucket}/{path}"


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
