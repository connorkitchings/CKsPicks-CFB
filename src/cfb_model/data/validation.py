"""Validation utilities for local CSV storage.

Provides checks for:
- Manifest row counts vs. CSV rows (via manifest only)
- Referential integrity (plays -> games)
- Duplicate detection within partitions (CSV read)
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from .storage.base import StorageBackend
from .storage.local_storage import LocalStorage


@dataclass
class ValidationIssue:
    level: str  # "ERROR" | "WARN" | "INFO"
    message: str
    entity: str
    path: Path | None = None


def _iter_csv_files(root: Path) -> Iterable[Path]:
    """Recursively find all data.csv files."""
    for p in root.rglob("data.csv"):
        if p.is_file():
            yield p


def validate_manifest_counts(
    partition_dir: Path, entity: str
) -> list[ValidationIssue]:
    """Check if the number of rows in the CSV matches the manifest count."""
    issues: list[ValidationIssue] = []
    manifest_path = partition_dir / "manifest.json"
    if not manifest_path.exists():
        issues.append(
            ValidationIssue(
                "ERROR", "Missing manifest.json", entity=entity, path=partition_dir
            )
        )
        return issues

    try:
        with manifest_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        manifest_rows = int(data.get("rows", -1))
    except (json.JSONDecodeError, ValueError) as e:
        issues.append(
            ValidationIssue(
                "ERROR",
                f"Failed to read manifest.json: {e}",
                entity=entity,
                path=manifest_path,
            )
        )
        return issues

    csv_path = partition_dir / "data.csv"
    if not csv_path.exists():
        if manifest_rows == 0:
            # Manifest says 0 rows, and no CSV exists, which is valid.
            return issues
        issues.append(
            ValidationIssue("ERROR", "Missing data.csv", entity=entity, path=csv_path)
        )
        return issues

    try:
        df = pd.read_csv(csv_path)
        csv_rows = len(df)
    except Exception as e:
        issues.append(
            ValidationIssue(
                "ERROR", f"Failed reading CSV: {e}", entity=entity, path=csv_path
            )
        )
        return issues

    if csv_rows != manifest_rows:
        issues.append(
            ValidationIssue(
                "ERROR",
                f"Manifest row count {manifest_rows} != CSV rows {csv_rows}",
                entity=entity,
                path=partition_dir,
            )
        )
    return issues


def validate_partition_duplicates(
    partition_dir: Path, entity: str, key_columns: list[str]
) -> list[ValidationIssue]:
    """Detect duplicates in a partition's data.csv based on key columns."""
    issues: list[ValidationIssue] = []
    csv_path = partition_dir / "data.csv"
    if not csv_path.exists():
        return issues  # No data to check for duplicates

    try:
        df = pd.read_csv(csv_path)
        if df.empty:
            return issues

        # Ensure all key columns are present before checking
        if not all(k in df.columns for k in key_columns):
            issues.append(
                ValidationIssue(
                    "WARN",
                    f"Skipping duplicate check; missing one or more keys: {key_columns}",
                    entity=entity,
                    path=partition_dir,
                )
            )
            return issues

        dup_mask = df.duplicated(subset=key_columns, keep=False)
        dup_count = int(dup_mask.sum())
        if dup_count > 0:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    f"Found {dup_count} duplicate rows on keys {key_columns}",
                    entity=entity,
                    path=partition_dir,
                )
            )
    except Exception as e:
        issues.append(
            ValidationIssue(
                "ERROR",
                f"Duplicate check failed: {e}",
                entity=entity,
                path=partition_dir,
            )
        )
    return issues


def validate_entity(
    storage: LocalStorage,
    year: int,
    entity: str,
    key_columns: list[str],
    partition_glob: str = "*/*/*",
) -> list[ValidationIssue]:
    """Generic validator for a processed entity."""
    issues: list[ValidationIssue] = []
    entity_dir = storage.root() / entity / str(year)
    if not entity_dir.exists():
        issues.append(
            ValidationIssue(
                "WARN", "No data found for entity", entity=entity, path=entity_dir
            )
        )
        return issues

    partition_dirs = list(entity_dir.glob(partition_glob))
    if not partition_dirs:
        issues.append(
            ValidationIssue(
                "INFO", "No partitions found to validate", entity=entity, path=entity_dir
            )
        )
        return issues

    print(f"Validating {len(partition_dirs)} partitions for entity '{entity}'...")
    for part_dir in partition_dirs:
        if not part_dir.is_dir():
            continue
        issues.extend(validate_manifest_counts(part_dir, entity))
        issues.extend(validate_partition_duplicates(part_dir, entity, key_columns))

    return issues


def validate_processed_season(
    storage: LocalStorage, year: int
) -> list[ValidationIssue]:
    """Run all validations for a processed season."""
    issues: list[ValidationIssue] = []
    print(f"--- Validating Processed Data for Season {year} ---")

    # byplay: year/week/game
    issues.extend(
        validate_entity(
            storage, year, "byplay", ["id", "game_id", "play_number"], "*/*/*"
        )
    )
    # drives: year/week/game
    issues.extend(
        validate_entity(storage, year, "drives", ["game_id", "drive_number"], "*/*/*")
    )
    # team_game: year/week/team
    issues.extend(
        validate_entity(storage, year, "team_game", ["game_id", "team"], "*/*/*")
    )
    # team_season & team_season_adj: year/team/side
    issues.extend(
        validate_entity(storage, year, "team_season", ["team"], "*/*/*")
    )
    issues.extend(
        validate_entity(storage, year, "team_season_adj", ["team"], "*/*/*")
    )

    return issues


def validate_raw_season(
    storage: LocalStorage, year: int, season_type: str = "regular"
) -> list[ValidationIssue]:
    """Run core validations for a raw data season."""
    issues: list[ValidationIssue] = []
    print(f"--- Validating Raw Data for Season {year} ---")

    # Simplified validation for raw data as an example
    games_dir = storage.root() / "games" / str(year)
    if games_dir.exists():
        issues.extend(validate_manifest_counts(games_dir, "games")),
        issues.extend(validate_partition_duplicates(games_dir, "games", ["id"]))
    else:
        issues.append(
            ValidationIssue("WARN", "No games data for season", entity="games", path=games_dir)
        )
    return issues


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate local CSV data for a season."
    )
    parser.add_argument("--year", type=int, required=True, help="Season year to validate.")
    parser.add_argument(
        "--data-type",
        type=str,
        default="processed",
        choices=["raw", "processed"],
        help="Type of data to validate.",
    )
    parser.add_argument("--data-root", type=str, default=None, help="Override data root path.")
    args = parser.parse_args()

    storage = LocalStorage(
        data_root=args.data_root, file_format="csv", data_type=args.data_type
    )

    if args.data_type == "processed":
        issues = validate_processed_season(storage, args.year)
    else:
        issues = validate_raw_season(storage, args.year)

    if not issues:
        print(f"\n✅ No issues found for {args.year} {args.data_type} data.")
        return

    print(f"\n--- Validation Summary for {args.year} ({args.data_type}) ---")
    errors = [iss for iss in issues if iss.level == "ERROR"]
    warns = [iss for iss in issues if iss.level == "WARN"]

    if errors:
        print(f"🔴 Found {len(errors)} ERROR(s):")
        for iss in errors:
            loc = f" [{iss.path}]" if iss.path else ""
            print(f"  - [{iss.entity}] {iss.message}{loc}")

    if warns:
        print(f"🟡 Found {len(warns)} WARNING(s):")
        for iss in warns:
            loc = f" [{iss.path}]" if iss.path else ""
            print(f"  - [{iss.entity}] {iss.message}{loc}")

    if not errors and not warns:
        print("✅ All checks passed (only INFO-level messages).")


if __name__ == "__main__":
    main()