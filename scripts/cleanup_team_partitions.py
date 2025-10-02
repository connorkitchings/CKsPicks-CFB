#!/usr/bin/env python3
"""
Team Partition Directory Cleanup Script

Standardizes team partition directories from tuple format ('TeamName',)
to key=value format (team=TeamName) with proper side partitioning.

Usage:
    python scripts/cleanup_team_partitions.py --entity team_season --year 2017 --dry-run
    python scripts/cleanup_team_partitions.py --entity team_season_adj --year 2014-2018 --execute
"""

import argparse
import os
import shutil
import subprocess
from pathlib import Path
from typing import List


class TeamPartitionCleanup:
    def __init__(self, data_root: str):
        self.data_root = Path(data_root)
        self.processed_root = self.data_root / "data" / "processed"

    def get_tuple_dirs(self, entity: str, year: int) -> List[Path]:
        """Get all tuple-format directories for a given entity/year."""
        entity_year_path = self.processed_root / entity / f"year={year}"
        if not entity_year_path.exists():
            print(f"Warning: {entity_year_path} does not exist")
            return []

        tuple_dirs = []
        for item in entity_year_path.iterdir():
            if item.is_dir() and item.name.startswith("(") and item.name.endswith(",)"):
                tuple_dirs.append(item)

        return sorted(tuple_dirs)

    def extract_team_name(self, tuple_dir_name: str) -> str:
        """Extract team name from tuple format directory name."""
        # Remove ('...') wrapper and trailing comma
        team_name = tuple_dir_name.strip("()").strip("',").strip('"')
        return team_name

    def check_enhanced_schema(self, standardized_dir: Path) -> bool:
        """Check if standardized format has enhanced schema (more columns)."""
        try:
            offense_file = standardized_dir / "side=offense" / "data.csv"
            if not offense_file.exists():
                return False

            # Read the header line to check for enhanced columns
            with open(offense_file, "r") as f:
                header = f.readline().strip()
                # Enhanced schema includes off_rush_ypp and off_pass_ypp columns
                return "off_rush_ypp" in header and "off_pass_ypp" in header
        except Exception:
            return False

    def _remove_tuple_directory(self, tuple_dir: Path) -> bool:
        """Robustly remove a tuple directory, handling macOS metadata files."""
        try:
            # Clear extended attributes that might prevent deletion
            subprocess.run(
                ["xattr", "-c", str(tuple_dir)], capture_output=True, check=False
            )

            # Remove any macOS metadata files first
            for root, dirs, files in os.walk(tuple_dir, topdown=False):
                for file in files:
                    file_path = Path(root) / file
                    try:
                        if file.startswith("._"):
                            # Force remove macOS metadata files
                            subprocess.run(["rm", "-f", str(file_path)], check=False)
                        else:
                            file_path.unlink()
                    except Exception:
                        # Try force removal if regular unlink fails
                        subprocess.run(["rm", "-f", str(file_path)], check=False)

                # Remove directories
                for dir_name in dirs:
                    dir_path = Path(root) / dir_name
                    try:
                        dir_path.rmdir()
                    except Exception:
                        # Try force removal
                        subprocess.run(["rmdir", str(dir_path)], check=False)

            # Finally remove the main directory
            try:
                tuple_dir.rmdir()
            except Exception:
                # Last resort force removal
                subprocess.run(["rm", "-rf", str(tuple_dir)], check=False)

            # Verify removal
            if tuple_dir.exists():
                print(f"  ❌ Failed to completely remove {tuple_dir}")
                return False
            else:
                return True

        except Exception as e:
            print(f"  ❌ Failed to remove tuple directory: {e}")
            return False

    def validate_data_consistency(self, old_dir: Path, new_dir: Path) -> bool:
        """Compare data files between old and new directory structures."""
        try:
            # Check if both directories have the expected structure
            old_sides = ["offense", "defense"]
            new_sides = ["side=offense", "side=defense"]

            for old_side, new_side in zip(old_sides, new_sides):
                old_data = old_dir / old_side / "data.csv"
                new_data = new_dir / new_side / "data.csv"

                if not old_data.exists() or not new_data.exists():
                    print(
                        f"  ❌ Missing data files: {old_data.exists()=}, {new_data.exists()=}"
                    )
                    return False

                # Compare file sizes
                old_size = old_data.stat().st_size
                new_size = new_data.stat().st_size

                if old_size != new_size:
                    print(
                        f"  ❌ Size mismatch for {old_side}: {old_size} vs {new_size}"
                    )
                    return False

                # Compare line counts
                old_lines = subprocess.run(
                    ["wc", "-l", str(old_data)], capture_output=True, text=True
                ).stdout.split()[0]
                new_lines = subprocess.run(
                    ["wc", "-l", str(new_data)], capture_output=True, text=True
                ).stdout.split()[0]

                if old_lines != new_lines:
                    print(
                        f"  ❌ Line count mismatch for {old_side}: {old_lines} vs {new_lines}"
                    )
                    return False

            print("  ✅ Data consistency validated")
            return True

        except Exception as e:
            print(f"  ❌ Validation error: {e}")
            return False

    def convert_team_directory(
        self, entity: str, year: int, tuple_dir: Path, dry_run: bool = True
    ) -> bool:
        """Convert a single tuple-format directory to standardized format."""
        team_name = self.extract_team_name(tuple_dir.name)

        # Create target directory path
        entity_year_path = self.processed_root / entity / f"year={year}"
        target_dir = entity_year_path / f"team={team_name}"

        print(f"\n🔄 Processing: {tuple_dir.name} → team={team_name}")

        # Check if target already exists
        if target_dir.exists():
            print(f"  ℹ️  Target directory already exists: {target_dir}")

            # Check if the standardized version has more columns (newer schema)
            has_enhanced_schema = self.check_enhanced_schema(target_dir)

            if has_enhanced_schema:
                print("  📈 Standardized format has enhanced schema - prioritizing it")
                if not dry_run:
                    print(f"  🗑️  Removing older tuple directory: {tuple_dir}")
                    if self._remove_tuple_directory(tuple_dir):
                        return True
                    else:
                        return False
                else:
                    print(
                        "  🧪 DRY RUN: Would remove older tuple format (enhanced schema detected)"
                    )
                    return True
            else:
                # Same schema - validate consistency
                if not dry_run:
                    if self.validate_data_consistency(tuple_dir, target_dir):
                        print(f"  🗑️  Removing duplicate tuple directory: {tuple_dir}")
                        if self._remove_tuple_directory(tuple_dir):
                            return True
                        else:
                            return False
                    else:
                        print("  ⚠️  Data inconsistency detected - skipping removal")
                        return False
                else:
                    print(f"  🧪 DRY RUN: Would validate and remove {tuple_dir}")
                    return True

        # Convert tuple format to standardized format
        if not dry_run:
            try:
                target_dir.mkdir(parents=True, exist_ok=True)

                # Copy offense and defense directories with new naming
                for old_side, new_side in [
                    ("offense", "side=offense"),
                    ("defense", "side=defense"),
                ]:
                    old_side_dir = tuple_dir / old_side
                    new_side_dir = target_dir / new_side

                    if old_side_dir.exists():
                        shutil.copytree(old_side_dir, new_side_dir, dirs_exist_ok=True)
                        print(f"    📁 Copied {old_side} → {new_side}")

                # Validate the conversion
                if self.validate_data_consistency(tuple_dir, target_dir):
                    # Remove old tuple directory
                    if self._remove_tuple_directory(tuple_dir):
                        print(
                            f"  ✅ Successfully converted and removed {tuple_dir.name}"
                        )
                        return True
                    else:
                        # Rollback on validation failure
                        shutil.rmtree(target_dir)
                        print(
                            "  ❌ Failed to remove tuple directory - rolled back conversion"
                        )
                        return False
                else:
                    # Rollback on validation failure
                    shutil.rmtree(target_dir)
                    print("  ❌ Validation failed - rolled back conversion")
                    return False

            except Exception as e:
                print(f"  ❌ Conversion error: {e}")
                return False
        else:
            print(f"  🧪 DRY RUN: Would convert {tuple_dir.name} → team={team_name}")
            return True

    def cleanup_entity_year(self, entity: str, year: int, dry_run: bool = True) -> dict:
        """Clean up all team directories for a specific entity/year."""
        print(f"\n🎯 Processing {entity} year={year}")

        tuple_dirs = self.get_tuple_dirs(entity, year)
        if not tuple_dirs:
            print(f"  ℹ️  No tuple directories found for {entity} year={year}")
            return {"processed": 0, "successful": 0, "failed": 0}

        print(f"  📊 Found {len(tuple_dirs)} tuple directories to process")

        results = {"processed": 0, "successful": 0, "failed": 0}

        for tuple_dir in tuple_dirs:
            results["processed"] += 1
            if self.convert_team_directory(entity, year, tuple_dir, dry_run):
                results["successful"] += 1
            else:
                results["failed"] += 1

        return results

    def cleanup_multiple_years(
        self, entity: str, years: List[int], dry_run: bool = True
    ) -> dict:
        """Clean up multiple years for an entity."""
        total_results = {"processed": 0, "successful": 0, "failed": 0}

        for year in years:
            year_results = self.cleanup_entity_year(entity, year, dry_run)
            for key in total_results:
                total_results[key] += year_results[key]

        return total_results


def parse_year_range(year_str: str) -> List[int]:
    """Parse year specification (e.g., '2017', '2014-2018', '2017,2018')."""
    if "-" in year_str:
        start, end = map(int, year_str.split("-"))
        return list(range(start, end + 1))
    elif "," in year_str:
        return [int(y.strip()) for y in year_str.split(",")]
    else:
        return [int(year_str)]


def main():
    parser = argparse.ArgumentParser(description="Clean up team partition directories")
    parser.add_argument(
        "--entity",
        required=True,
        choices=["team_season", "team_season_adj", "both"],
        help="Entity to clean up",
    )
    parser.add_argument(
        "--year",
        required=True,
        help="Year(s) to process (e.g., 2017, 2014-2018, 2017,2018)",
    )
    parser.add_argument(
        "--data-root",
        default="/Volumes/CK SSD/Coding Projects/cfb_model",
        help="Data root path",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Perform dry run without making changes",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually perform the cleanup (overrides --dry-run)",
    )

    args = parser.parse_args()

    # Override dry_run if --execute is specified
    dry_run = not args.execute

    if dry_run:
        print("🧪 DRY RUN MODE - No changes will be made")
    else:
        print("⚡ EXECUTE MODE - Changes will be made")
        response = input("Are you sure you want to proceed? (yes/no): ")
        if response.lower() != "yes":
            print("Aborted.")
            return

    years = parse_year_range(args.year)
    cleanup = TeamPartitionCleanup(args.data_root)

    entities = (
        ["team_season", "team_season_adj"] if args.entity == "both" else [args.entity]
    )

    print(f"\n📋 Plan: Clean up {entities} for years {years}")
    print(f"📍 Data root: {args.data_root}")

    total_results = {"processed": 0, "successful": 0, "failed": 0}

    for entity in entities:
        print(f"\n{'=' * 60}")
        print(f"🏗️  Processing Entity: {entity}")
        print(f"{'=' * 60}")

        entity_results = cleanup.cleanup_multiple_years(entity, years, dry_run)
        for key in total_results:
            total_results[key] += entity_results[key]

        print(f"\n📊 {entity} Summary:")
        print(f"  Processed: {entity_results['processed']}")
        print(f"  Successful: {entity_results['successful']}")
        print(f"  Failed: {entity_results['failed']}")

    print(f"\n{'=' * 60}")
    print("🎯 FINAL SUMMARY")
    print(f"{'=' * 60}")
    print(f"Total Processed: {total_results['processed']}")
    print(f"Total Successful: {total_results['successful']}")
    print(f"Total Failed: {total_results['failed']}")

    if total_results["failed"] == 0:
        print("✅ All operations completed successfully!")
    else:
        print(f"⚠️  {total_results['failed']} operations failed - review output above")


if __name__ == "__main__":
    main()
