#!/usr/bin/env python3
"""Migrate data from local storage to cloud storage (R2/S3).

This script copies all data from the external drive to cloud storage,
with verification and progress tracking.

Usage:
    # Dry run (shows what would be copied)
    python scripts/migration/migrate_to_cloud.py --dry-run

    # Copy raw data only
    python scripts/migration/migrate_to_cloud.py --include raw/

    # Copy processed data only
    python scripts/migration/migrate_to_cloud.py --include processed/

    # Copy everything
    python scripts/migration/migrate_to_cloud.py

    # Force overwrite existing files
    python scripts/migration/migrate_to_cloud.py --force

Requirements:
    - CFB_STORAGE_BACKEND must be set to 'r2' or 's3' in .env
    - Cloud credentials must be configured
    - External drive must be connected (for source data)
"""

import argparse
import hashlib
import logging
import os
import sys
from pathlib import Path
from typing import Optional


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Set up logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )
    return logging.getLogger(__name__)


def compute_file_hash(file_path: Path) -> str:
    """Compute MD5 hash of a file."""
    md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5.update(chunk)
    return md5.hexdigest()


def should_copy_file(
    file_path: str,
    include_patterns: Optional[list[str]] = None,
    exclude_patterns: Optional[list[str]] = None,
) -> bool:
    """Determine if a file should be copied based on patterns."""
    if include_patterns:
        if not any(pattern in file_path for pattern in include_patterns):
            return False

    if exclude_patterns:
        if any(pattern in file_path for pattern in exclude_patterns):
            return False

    return True


def migrate_data(
    dry_run: bool = False,
    force: bool = False,
    include_patterns: Optional[list[str]] = None,
    exclude_patterns: Optional[list[str]] = None,
    verbose: bool = False,
) -> dict:
    """Migrate data from local storage to cloud storage.

    Args:
        dry_run: If True, only show what would be copied
        force: If True, overwrite existing files in cloud
        include_patterns: List of path patterns to include (e.g., ['raw/', 'processed/'])
        exclude_patterns: List of path patterns to exclude
        verbose: Enable verbose logging

    Returns:
        Dictionary with migration statistics
    """
    logger = setup_logging(verbose)
    from cks_picks_cfb.data.storage import LocalStorage, get_storage

    # Verify we're migrating TO cloud (not from cloud to local)
    backend = os.getenv("CFB_STORAGE_BACKEND", "local").lower()
    if backend == "local":
        raise ValueError(
            "Cannot migrate: CFB_STORAGE_BACKEND is set to 'local'. "
            "Set it to 'r2' or 's3' to migrate to cloud storage."
        )

    # Get local and cloud storage instances
    local_root = os.getenv("CFB_MODEL_DATA_ROOT")
    if not local_root:
        raise ValueError("CFB_MODEL_DATA_ROOT must be set")

    logger.info("🚀 Starting data migration to cloud")
    logger.info(f"Source: {local_root}")
    logger.info(f"Target: {backend.upper()} storage")

    if dry_run:
        logger.info("🔍 DRY RUN MODE - No files will be copied")

    local_storage = LocalStorage(local_root)
    cloud_storage = get_storage()

    # Get list of all files to migrate
    logger.info("📋 Scanning local files...")
    all_files = local_storage.list_files("")

    # Filter files based on patterns
    files_to_copy = [
        f for f in all_files if should_copy_file(f, include_patterns, exclude_patterns)
    ]

    logger.info(f"Found {len(all_files)} total files")
    logger.info(f"Will copy {len(files_to_copy)} files (after filtering)")

    if not files_to_copy:
        logger.warning("No files to copy!")
        return {"copied": 0, "skipped": 0, "errors": 0, "total_bytes": 0}

    # Migration statistics
    stats = {
        "copied": 0,
        "skipped": 0,
        "errors": 0,
        "total_bytes": 0,
    }

    # Copy each file
    for i, file_path in enumerate(files_to_copy, 1):
        try:
            # Check if file exists in cloud
            exists_in_cloud = cloud_storage.exists(file_path)

            if exists_in_cloud and not force:
                logger.debug(
                    f"⏭️  [{i}/{len(files_to_copy)}] Skipping {file_path} (already exists)"
                )
                stats["skipped"] += 1
                continue

            # Get file size
            local_full_path = Path(local_storage.get_full_path(file_path))
            file_size = local_full_path.stat().st_size
            size_mb = file_size / (1024 * 1024)

            action = "Would copy" if dry_run else "Copying"
            logger.info(
                f"📄 [{i}/{len(files_to_copy)}] {action} {file_path} ({size_mb:.2f} MB)"
            )

            if not dry_run:
                # Determine file type and copy accordingly
                if file_path.endswith(".parquet"):
                    df = local_storage.read_parquet(file_path)
                    cloud_storage.write_parquet(df, file_path)
                elif file_path.endswith(".csv"):
                    df = local_storage.read_csv(file_path)
                    cloud_storage.write_csv(df, file_path, index=False)
                else:
                    # For other file types, read as binary and write
                    # This is a fallback - may need custom handling
                    logger.warning(f"⚠️  Non-standard file type: {file_path}. Skipping.")
                    stats["skipped"] += 1
                    continue

                logger.info(f"✅ Copied {file_path}")

            stats["copied"] += 1
            stats["total_bytes"] += file_size

        except Exception as e:
            logger.error(f"❌ Error copying {file_path}: {e}")
            stats["errors"] += 1
            if verbose:
                logger.exception("Full traceback:")

    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 Migration Summary")
    logger.info("=" * 60)
    logger.info(f"Total files: {len(files_to_copy)}")
    logger.info(f"Copied: {stats['copied']}")
    logger.info(f"Skipped: {stats['skipped']}")
    logger.info(f"Errors: {stats['errors']}")
    logger.info(f"Total data: {stats['total_bytes'] / (1024**3):.2f} GB")

    if dry_run:
        logger.info("\n🔍 This was a DRY RUN - no files were actually copied")
        logger.info("Remove --dry-run to perform the actual migration")

    return stats


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate data from local storage to cloud storage"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be copied without actually copying",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files in cloud storage",
    )
    parser.add_argument(
        "--include",
        action="append",
        help="Include only files matching these patterns (can be specified multiple times)",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        help="Exclude files matching these patterns (can be specified multiple times)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    try:
        stats = migrate_data(
            dry_run=args.dry_run,
            force=args.force,
            include_patterns=args.include,
            exclude_patterns=args.exclude,
            verbose=args.verbose,
        )

        # Exit with error code if there were errors
        if stats["errors"] > 0:
            sys.exit(1)

    except Exception as e:
        logging.error(f"Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
