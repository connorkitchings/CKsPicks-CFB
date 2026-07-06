"""Storage backend abstractions — unified entry point.

This module re-exports the canonical storage types from cks_picks_cfb.data.storage.
All new code should import directly from cks_picks_cfb.data.storage; this shim
exists for backward compatibility with existing import sites.
"""

from __future__ import annotations

from cks_picks_cfb.data.storage import Partition, StorageBackend, StorageError

__all__ = ["Partition", "StorageBackend", "StorageError"]
