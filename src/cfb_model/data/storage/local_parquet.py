"""Local Parquet storage backend implementation.

Writes entity records to partitioned Parquet files with Snappy compression and
creates a small manifest.json per partition for validation. Timestamps are
expected to already be timezone-normalized by the caller.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from .base import Partition, StorageBackend, StorageError

DEFAULT_DATA_ROOT = "/path/to/external/drive"  # Placeholder, replace on your machine


class LocalParquetStorage(StorageBackend):
    def __init__(self, data_root: str | Path | None = None) -> None:
        root = Path(data_root or DEFAULT_DATA_ROOT)
        if not root.exists() or not root.is_dir():
            raise StorageError(
                f"Data root is not accessible: {root}. Ensure your external SSD is mounted."
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

        # Convert sequence of mappings to Arrow Table
        batch = pa.table(
            records
        )  # Arrow infers schema; timestamps should be pa.timestamp with tz if provided

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
        self, entity: str, filters: Mapping[str, Any]
    ) -> list[dict[str, Any]]:
        """Simple index reader for small lookups.

        Currently supports games index by season and season_type, returning id and week.
        """
        if entity != "games":
            raise StorageError("read_index currently supports only 'games'.")

        season = filters.get("season")
        season_type = filters.get("season_type")
        if season is None:
            raise StorageError("'season' filter is required for games index.")

        base = self._root / "games" / f"season={season}"
        if season_type is not None:
            base = base / f"season_type={season_type}"

        # If no data exists yet, return empty to signal caller to fetch from API
        if not base.exists():
            return []

        # Read all parquet files within this partition and return minimal columns
        files = sorted(base.rglob("*.parquet"))
        out: list[dict[str, Any]] = []
        if not files:
            return out

        cols = {"id", "week"}
        for fp in files:
            table = pq.read_table(
                fp, columns=list(cols & set(pq.read_schema(fp).names))
            )
            for row in table.to_pylist():
                d = {k: row.get(k) for k in cols if k in row}
                if "id" in d:
                    out.append({"id": d.get("id"), "week": d.get("week")})
        return out
