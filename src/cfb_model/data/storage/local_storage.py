"""Local storage backend implementation.

Writes entity records to partitioned CSV (or Parquet) files and creates a small
manifest.json per partition for validation. Timestamps are expected to already be
timezone-normalized by the caller. CSV is the default for both raw and processed.
"""

from __future__ import annotations

import json
import os
import shutil
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .base import Partition, StorageBackend, StorageError


class LocalStorage(StorageBackend):
    def __init__(
        self,
        data_root: str | Path | None = None,
        file_format: Literal["parquet", "csv"] = "parquet",
        data_type: Literal["raw", "processed"] = "raw",
    ) -> None:
        """Initializes the local storage backend.

        The data root path is determined with the following priority:
        1. The `data_root` argument provided to the constructor.
        2. The `CFB_MODEL_DATA_ROOT` environment variable.
        3. A default `data` directory inside the current working directory.

        Args:
            data_root: An optional, explicit path to the data storage root.
            file_format: The file format to use for storage ('parquet' or 'csv').
            data_type: The type of data being stored ('raw' or 'processed').
        """
        base_root = data_root or os.getenv("CFB_MODEL_DATA_ROOT") or Path.cwd()
        root_path = Path(base_root) / "data" / f"{data_type}"
        root = root_path.resolve()

        try:
            root.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise StorageError(
                f"Failed to create data root directory at {root}: {e}"
            ) from e

        if not root.is_dir():
            raise StorageError(
                f"Data root path is not a directory: {root}. Please check the path."
            )
        self._root = root
        self.file_format = file_format
        self._data_type: Literal["raw", "processed"] = data_type

    def root(self) -> Path:
        return self._root

    def _entity_partition_dir(self, entity: str, partition: Partition) -> Path:
        # Use explicit key=value directory segments for clarity and stability
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
            try:
                shutil.rmtree(part_dir, ignore_errors=True)
            except OSError as e:
                raise StorageError(
                    f"Failed to remove existing partition directory {part_dir}: {e}"
                ) from e
        part_dir.mkdir(parents=True, exist_ok=True)

        if not records:
            self._write_manifest(part_dir, entity=entity, rows=0, schema=None)
            return 0

        if self.file_format == "parquet":
            try:
                table = pa.Table.from_pylist(list(records))
            except Exception as e:
                raise StorageError(
                    f"Failed to create pyarrow Table from raw records: {e}"
                ) from e

            pq.write_to_dataset(
                table,
                root_path=part_dir,
                compression="snappy",
                basename_template="part-{i}.parquet",
            )
            num_rows = table.num_rows
            schema = table.schema
        elif self.file_format == "csv":
            df = pd.DataFrame(list(records))
            df.to_csv(part_dir / "data.csv", index=False)
            num_rows = len(df)
            schema = pa.Schema.from_pandas(df)
        else:
            raise ValueError(f"Unsupported file format: {self.file_format}")

        self._write_manifest(part_dir, entity=entity, rows=num_rows, schema=schema)
        return num_rows

    def _write_manifest(
        self, part_dir: Path, *, entity: str, rows: int, schema: pa.Schema | None
    ) -> None:
        manifest = {
            "rows": rows,
            "write_time": datetime.now().isoformat(timespec="seconds"),
            "data_type": self._data_type,
            "file_format": self.file_format,
            "entity": entity,
            "schema_version": ("processed_v1" if self._data_type == "processed" else "raw_v1"),
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
        partition_values = {k: str(v) for k, v in filters.items() if v is not None}
        partition = Partition(partition_values)
        base_dir = self._entity_partition_dir(entity, partition)

        if not base_dir.exists():
            return []

        if self.file_format == "parquet":
            files = sorted(
                [p for p in base_dir.rglob("*.parquet") if not p.name.startswith("._")]
            )
            if not files:
                return []

            rows: list[dict[str, Any]] = []
            for fpath in files:
                try:
                    table = pq.read_table(fpath, columns=columns)
                    rows.extend(table.to_pylist())
                except Exception as e:
                    print(f"Skipping unreadable file: {fpath} -> {e}")
                    continue
            return rows
        elif self.file_format == "csv":
            # Recursively read all CSV files under the base_dir to support nested partitions
            files = sorted(
                [
                    p
                    for p in base_dir.rglob("data.csv")
                    if p.is_file() and not p.name.startswith("._")
                ]
            )
            if not files:
                return []
            frames: list[pd.DataFrame] = []
            for fpath in files:
                try:
                    df = pd.read_csv(fpath, usecols=columns)
                    frames.append(df)
                except Exception as e:
                    print(f"Skipping unreadable CSV: {fpath} -> {e}")
                    continue
            if not frames:
                return []
            df_all = pd.concat(frames, ignore_index=True)
            return df_all.to_dict(orient="records")
        else:
            raise ValueError(f"Unsupported file format: {self.file_format}")
