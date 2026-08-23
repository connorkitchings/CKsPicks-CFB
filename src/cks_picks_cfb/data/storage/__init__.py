"""Storage abstraction layer for CFB model data.

Provides a unified interface for reading/writing data from local or cloud storage.
Supports:
- Local filesystem (external drive)
- Cloudflare R2 (S3-compatible)
- AWS S3
"""

from cks_picks_cfb.data.storage.base import (
    Partition,
    StorageBackend,
    StorageError,
    StorageSettings,
)
from cks_picks_cfb.data.storage.factory import get_source_storage, get_storage
from cks_picks_cfb.data.storage.local import LocalStorage
from cks_picks_cfb.data.storage.r2 import R2Storage, ReadOnlyStorage, S3Storage

__all__ = [
    "Partition",
    "StorageBackend",
    "StorageError",
    "StorageSettings",
    "LocalStorage",
    "R2Storage",
    "ReadOnlyStorage",
    "S3Storage",
    "get_source_storage",
    "get_storage",
]
