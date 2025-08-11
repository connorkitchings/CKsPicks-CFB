"""Local Parquet storage backend implementation.

Writes entity records to partitioned Parquet files with Snappy compression and
creates a small manifest.json per partition for validation. Timestamps are
expected to already be timezone-normalized by the caller.
"""

from __future__ import annotations

import json
import os
import shutil
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from .base import Partition, StorageBackend, StorageError


class LocalParquetStorage(StorageBackend):
    def __init__(self, data_root: str | Path | None = None) -> None:
        """Initializes the local Parquet storage backend.

        The data root path is determined with the following priority:
        1. The `data_root` argument provided to the constructor.
        2. The `CFB_MODEL_DATA_ROOT` environment variable.
        3. A default `data` directory inside the current working directory.

        Args:
            data_root: An optional, explicit path to the data storage root.
        """
        # Determine the root path from argument, environment variable, or default
        base_root = data_root or os.getenv("CFB_MODEL_DATA_ROOT") or Path.cwd() / "data"
        root_path = Path(base_root) / "raw_data"
        root = root_path.resolve()

        # Create the directory if it doesn't exist to ensure it's available for writing
        try:
            root.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise StorageError(f"Failed to create data root directory at {root}: {e}") from e

        if not root.is_dir():
            raise StorageError(
                f"Data root path is not a directory: {root}. Please check the path."
            )
        self._root = root

    def root(self) -> Path:
        return self._root

    def _entity_partition_dir(self, entity: str, partition: Partition) -> Path:
        return self._root / entity / partition.path_suffix()

    def write(
        self,
        entity: str,
        records: Sequence[Mapping[str, Any]],
        partition: Partition,
        *,
        partition_cols: list[str] | None = None,
        overwrite: bool = True,
    ) -> int:
        part_dir = self._entity_partition_dir(entity, partition)
        if overwrite and part_dir.exists():
            try:
                shutil.rmtree(part_dir, ignore_errors=True)
            except OSError as e:
                raise StorageError(f"Failed to remove existing partition directory {part_dir}: {e}") from e
        part_dir.mkdir(parents=True, exist_ok=True)

        if not records:
            # still write an empty manifest to record the attempt
            self._write_manifest(part_dir, rows=0, schema=None)
            return 0

        try:
            # Convert sequence of mappings to Arrow Table
            batch = pa.Table.from_pylist(list(records))
        except Exception as e:
            raise StorageError(f"Failed to create pyarrow Table from records: {e}") from e

        # Use write_to_dataset to handle partitioning and file naming
        pq.write_to_dataset(
            batch,
            root_path=part_dir,
            partition_cols=partition_cols,
            compression="snappy",
            basename_template="part-{i}.parquet",
        )

        # Write manifest for validation
        self._write_manifest(part_dir, rows=batch.num_rows, schema=batch.schema)
        return batch.num_rows

    def _write_manifest(
        self, part_dir: Path, *, rows: int, schema: pa.Schema | None
    ) -> None:
        manifest = {
            "rows": rows,
            "write_time": datetime.now().isoformat(timespec="seconds"),
            "schema": None,
        }
        if schema is not None:
            manifest["schema"] = {
                "fields": [
                    {
                        "name": f.name,
                        "type": str(f.type),
                        "nullable": f.nullable,
                    }
                    for f in schema
                ]
            }
        with (part_dir / "manifest.json").open("w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

    def read_index(
        self,
        entity: str,
        filters: Mapping[str, Any],
        columns: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Reads a lightweight index for an entity, filtered by partition values.

        Args:
            entity: The entity name (e.g., "games", "teams").
            filters: A mapping of partition keys to values (e.g., {"season": "2024"}).
            columns: Optional list of columns to read. If None, reads all.

        Returns:
            A list of dictionaries representing the read data.
        """
        partition_values = {k: str(v) for k, v in filters.items() if v is not None}
        partition = Partition(partition_values)
        base_dir = self._root / entity / partition.path_suffix()

        print(f"    [read_index] Checking for index at: {base_dir}")
        dir_exists = base_dir.exists()
        print(f"    [read_index] Directory exists: {dir_exists}")

        if not dir_exists:
            print(f"    [read_index] Directory does not exist: {base_dir}")
            return []

        files = sorted([p for p in base_dir.rglob("*.parquet") if not p.name.startswith("._")])
        print(f"    [read_index] Found {len(files)} parquet files in {base_dir}")
        if not files:
            print(f"    [read_index] No parquet files found in {base_dir}")
            return []

        # Read all parquet files within this partition, letting pyarrow handle schema
        try:
            dataset = pq.ParquetDataset(files)
            table = dataset.read(columns=columns)
            return table.to_pylist()
        except Exception as e:
            # Gracefully handle empty directories or non-parquet files
            if "No files found" in str(e) or "is not a Parquet file" in str(e):
                return []
            raise StorageError(f"Failed to read Parquet files from {base_dir}: {e}") from e
