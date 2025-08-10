"""Validation utilities for local Parquet storage.

Provides checks for:
- Manifest row counts vs. Parquet rows
- Referential integrity (plays -> games)
- Duplicate detection within partitions
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import pyarrow.parquet as pq

from .storage.base import StorageBackend


@dataclass
class ValidationIssue:
    level: str  # "ERROR" | "WARN" | "INFO"
    message: str
    path: Path | None = None


def _iter_parquet_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*.parquet"):
        if p.is_file():
            yield p


def validate_manifest_counts(partition_dir: Path) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    manifest = partition_dir / "manifest.json"
    if not manifest.exists():
        issues.append(
            ValidationIssue("ERROR", "Missing manifest.json", path=partition_dir)
        )
        return issues

    # Read manifest rows
    try:
        import json

        with manifest.open("r", encoding="utf-8") as f:
            data = json.load(f)
        manifest_rows = int(data.get("rows", -1))
    except Exception as e:
        issues.append(
            ValidationIssue(
                "ERROR", f"Failed to read manifest.json: {e}", path=partition_dir
            )
        )
        return issues

    # Sum rows across parquet files
    total_rows = 0
    for fp in _iter_parquet_files(partition_dir):
        try:
            meta = pq.read_metadata(fp)
            total_rows += meta.num_rows
        except Exception as e:
            issues.append(
                ValidationIssue(
                    "ERROR", f"Failed reading metadata for {fp.name}: {e}", path=fp
                )
            )

    if total_rows != manifest_rows:
        issues.append(
            ValidationIssue(
                "ERROR",
                f"Manifest row count {manifest_rows} != Parquet rows {total_rows}",
                path=partition_dir,
            )
        )
    else:
        issues.append(
            ValidationIssue(
                "INFO", f"Row counts match: {total_rows}", path=partition_dir
            )
        )
    return issues


def validate_plays_referential(
    storage: StorageBackend, season: int, season_type: str = "regular"
) -> list[ValidationIssue]:
    """Ensure each plays partition references an existing game in games index."""
    issues: list[ValidationIssue] = []

    # Build games index set
    games = storage.read_index("games", {"season": season, "season_type": season_type})
    game_ids = {g["id"] for g in games if "id" in g and g["id"] is not None}

    plays_root = storage.root() / "plays" / f"season={season}"
    if not plays_root.exists():
        issues.append(
            ValidationIssue("WARN", "No plays data for season", path=plays_root)
        )
        return issues

    # week partitions
    for week_dir in sorted(plays_root.glob("week=*")):
        if not week_dir.is_dir():
            continue
        for game_dir in sorted(week_dir.glob("game_id=*")):
            if not game_dir.is_dir():
                continue
            try:
                game_id = int(game_dir.name.split("=", 1)[1])
            except Exception:
                issues.append(
                    ValidationIssue(
                        "ERROR", "Malformed game_id directory name", path=game_dir
                    )
                )
                continue

            if game_id not in game_ids:
                issues.append(
                    ValidationIssue(
                        "ERROR",
                        f"Plays partition references missing game_id={game_id}",
                        path=game_dir,
                    )
                )

            # Validate manifests for each plays partition
            issues.extend(validate_manifest_counts(game_dir))

    return issues


def validate_partition_duplicates(
    partition_dir: Path, *, key_columns: list[str]
) -> list[ValidationIssue]:
    """Detect duplicates in a partition Parquet files based on key columns."""
    issues: list[ValidationIssue] = []
    # Read all parquet files into a single table (columns subset)
    files = list(_iter_parquet_files(partition_dir))
    if not files:
        return issues

    try:
        # Read overlapping subset of columns present
        from pyarrow import concat_tables

        subset_cols = None
        tables = []
        for fp in files:
            schema = pq.read_schema(fp)
            available = [c for c in key_columns if c in schema.names]
            if not available:
                continue
            t = pq.read_table(fp, columns=available)
            tables.append(t)
            subset_cols = available if subset_cols is None else subset_cols
        if not tables or subset_cols is None:
            return issues
        table = concat_tables(tables, promote=True)
        df = table.to_pandas(types_mapper=None)
        dup_mask = df.duplicated(subset=subset_cols, keep=False)
        dup_count = int(dup_mask.sum())
        if dup_count > 0:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    f"Found {dup_count} duplicate rows on keys {subset_cols}",
                    path=partition_dir,
                )
            )
        else:
            issues.append(
                ValidationIssue("INFO", "No duplicates found", path=partition_dir)
            )
    except Exception as e:
        issues.append(
            ValidationIssue("ERROR", f"Duplicate check failed: {e}", path=partition_dir)
        )
    return issues


def validate_season(
    storage: StorageBackend, season: int, season_type: str = "regular"
) -> list[ValidationIssue]:
    """Run core validations for a season across games and plays."""
    issues: list[ValidationIssue] = []

    # Games partition presence and manifests
    games_dir = (
        storage.root() / "games" / f"season={season}" / f"season_type={season_type}"
    )
    if games_dir.exists():
        issues.extend(validate_manifest_counts(games_dir))
    else:
        issues.append(
            ValidationIssue(
                "WARN", "No games data for season/season_type", path=games_dir
            )
        )

    # Plays referential and manifests
    issues.extend(validate_plays_referential(storage, season, season_type))

    # Plays duplicate detection per game partition on (id) if present, else (game_id, play_number)
    plays_root = storage.root() / "plays" / f"season={season}"
    if plays_root.exists():
        for week_dir in sorted(plays_root.glob("week=*")):
            for game_dir in sorted(week_dir.glob("game_id=*")):
                # Prefer primary key 'id' if present
                issues.extend(
                    validate_partition_duplicates(
                        game_dir, key_columns=["id", "game_id", "play_number"]
                    )
                )

    return issues


def main() -> None:
    import argparse

    from .storage.local_parquet import LocalParquetStorage

    parser = argparse.ArgumentParser(
        description="Validate local Parquet data for a season."
    )
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--season_type", type=str, default="regular")
    parser.add_argument("--data-root", type=str, default=None)
    args = parser.parse_args()

    storage = LocalParquetStorage(args.data_root)
    issues = validate_season(storage, args.season, args.season_type)
    if not issues:
        print("No issues found.")
        return

    # Print summary
    for iss in issues:
        loc = f" [{iss.path}]" if iss.path else ""
        print(f"{iss.level}: {iss.message}{loc}")


if __name__ == "__main__":
    main()
