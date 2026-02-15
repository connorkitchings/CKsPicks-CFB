"""Storage backend abstractions for local data persistence.

This module defines the base interfaces for writing and reading locally
stored datasets used by the ingestion pipeline.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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


class StorageBackend(ABC):
    """Abstract storage backend API.

    Implementations must be safe to call repeatedly (idempotent overwrite mode).
    """

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
            entity: Top-level entity name (e.g., "plays", "games").
            records: A sequence of dict-like rows to persist.
            partition: Partition spec for directory layout.
            overwrite: If True, replace existing partition contents.

        Returns:
            Number of rows written.
        """

    @abstractmethod
    def read_index(
        self, entity: str, filters: Mapping[str, Any]
    ) -> list[dict[str, Any]]:
        """Read a lightweight index for an entity filtered by attributes.

        Intended for small lookups (e.g., games id/week by season/season_type).
        Implementations may load only necessary columns.
        """

    @abstractmethod
    def root(self) -> Path:
        """Return the root path for the storage backend."""
