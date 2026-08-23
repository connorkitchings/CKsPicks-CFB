"""Local filesystem storage backend."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from cks_picks_cfb.data.storage.base import Partition, StorageBackend, StorageError


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
