"""Local Parquet storage backend implementation.

Writes entity records to partitioned Parquet files with Snappy compression and
creates a small manifest.json per partition for validation. Timestamps are
expected to already be timezone-normalized by the caller.
"""

from __future__ import annotations

import json
import os
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
        3. A default `data/raw` directory inside the current working directory.

        Args:
            data_root: An optional, explicit path to the data storage root.
        """
        # Determine the root path from argument, environment variable, or default
        root_path = data_root or os.getenv("CFB_MODEL_DATA_ROOT") or Path.cwd() / "data" / "raw"
        root = Path(root_path).resolve()

        # Create the directory if it doesn't exist to ensure it's available for writing
        try:
            root.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise StorageError(f"Failed to create data root directory at {root}: {e}")

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
        overwrite: bool = True,
    ) -> int:
        part_dir = self._entity_partition_dir(entity, partition)
        if overwrite and part_dir.exists():
            # remove existing partition directory contents
            for p in sorted(part_dir.glob("**/*"), reverse=True):
                if p.is_file():
                    p.unlink(missing_ok=True)  # type: ignore[arg-type]
            # remove empty dirs from bottom up
            for p in sorted(part_dir.glob("**/*"), reverse=True):
                if p.is_dir():
                    try:
                        p.rmdir()
                    except OSError:
                        pass
        part_dir.mkdir(parents=True, exist_ok=True)

        if not records:
            # still write an empty manifest to record the attempt
            self._write_manifest(part_dir, rows=0, schema=None)
            return 0

        try:
            # Convert sequence of mappings to Arrow Table
            batch = pa.Table.from_pylist(list(records))
        except Exception as e:
            raise StorageError(f"Failed to create pyarrow Table from records: {e}")

        # Write a single parquet file per call (can be split by caller per partition)
        file_path = part_dir / "part-0001.parquet"
        pq.write_table(batch, file_path, compression="snappy")

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

        if not base_dir.exists():
            return []

        files = sorted(base_dir.rglob("*.parquet"))
        if not files:
            return []

        # Determine the actual columns to read from the first file's schema
        # to avoid errors if a column doesn't exist.
        try:
            schema = pq.read_schema(files[0])
            if columns:
                read_columns = [col for col in columns if col in schema.names]
            else:
                read_columns = schema.names
        except Exception:
            # If schema reading fails, the directory might be empty or contain no valid files
            return []

        if not read_columns:
            # If no desired columns are in the schema, we can't return anything useful.
            return []

        # Read all parquet files within this partition
        try:
            table = pq.read_table(files, columns=read_columns)
            return table.to_pylist()
        except Exception as e:
            raise StorageError(f"Failed to read Parquet files from {base_dir}: {e}")
