#!/usr/bin/env python3
"""Resume partial migration by continuing from last uploaded file.

This script reads the migration log and continues uploading only files
that weren't successfully copied.

Usage:
    python scripts/migration/resume_migration.py --log migration_raw_20260213_135345.log
"""

import argparse
import logging
import os
import sys
from pathlib import Path


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Set up logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )
    return logging.getLogger(__name__)


def get_uploaded_files(log_file: str) -> set:
    """Extract list of successfully uploaded files from log."""
    uploaded = set()
    with open(log_file, "r") as f:
        for line in f:
            if "✅ Copied" in line:
                # Extract filename after "✅ Copied "
                file_path = line.split("✅ Copied ")[-1].strip()
                uploaded.add(file_path)
    return uploaded


def resume_migration(
    log_file: str,
    include_patterns: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
    verbose: bool = False,
) -> dict:
    """Resume migration from where it left off.

    Args:
        log_file: Path to the previous migration log
        include_patterns: List of path patterns to include
        exclude_patterns: List of path patterns to exclude
        verbose: Enable verbose logging

    Returns:
        Dictionary with migration statistics
    """
    logger = setup_logging(verbose)
    project_root = Path(__file__).parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from cks_picks_cfb.data.storage import LocalStorage, get_storage

    # Get already uploaded files
    logger.info(f"📖 Reading uploaded files from {log_file}...")
    uploaded_files = get_uploaded_files(log_file)
    logger.info(f"✅ Found {len(uploaded_files)} already uploaded files")

    # Setup storage
    backend = os.getenv("CFB_STORAGE_BACKEND", "local").lower()
    if backend == "local":
        raise ValueError("CFB_STORAGE_BACKEND must be 'r2' or 's3'")

    local_root = os.getenv("CFB_MODEL_DATA_ROOT")
    if not local_root:
        raise ValueError("CFB_MODEL_DATA_ROOT must be set")

    logger.info(f"🚀 Resuming migration to {backend.upper()}")
    logger.info(f"Source: {local_root}")

    local_storage = LocalStorage(local_root)
    cloud_storage = get_storage()

    # Get list of all files
    logger.info("📋 Scanning local files...")
    all_files = local_storage.list_files("")

    # Filter files
    files_to_process = []
    for f in all_files:
        if include_patterns:
            if not any(pattern in f for pattern in include_patterns):
                continue
        if exclude_patterns:
            if any(pattern in f for pattern in exclude_patterns):
                continue
        files_to_process.append(f)

    # Separate into uploaded and remaining
    remaining_files = [f for f in files_to_process if f not in uploaded_files]
    already_done = [f for f in files_to_process if f in uploaded_files]

    logger.info(f"📊 Total files to process: {len(files_to_process)}")
    logger.info(f"✅ Already uploaded: {len(already_done)}")
    logger.info(f"📤 Remaining to upload: {len(remaining_files)}")

    if not remaining_files:
        logger.info("🎉 All files already uploaded!")
        return {
            "copied": 0,
            "skipped": len(already_done),
            "errors": 0,
            "total_bytes": 0,
        }

    # Upload remaining files
    stats = {"copied": 0, "skipped": 0, "errors": 0, "total_bytes": 0}

    for i, file_path in enumerate(remaining_files, 1):
        try:
            local_full_path = Path(local_storage.get_full_path(file_path))
            file_size = local_full_path.stat().st_size
            size_mb = file_size / (1024 * 1024)

            logger.info(
                f"📄 [{i}/{len(remaining_files)}] Copying {file_path} ({size_mb:.2f} MB)"
            )

            # Copy based on file type
            if file_path.endswith(".parquet"):
                df = local_storage.read_parquet(file_path)
                cloud_storage.write_parquet(df, file_path)
            elif file_path.endswith(".csv"):
                df = local_storage.read_csv(file_path)
                cloud_storage.write_csv(df, file_path, index=False)
            else:
                logger.warning(f"⚠️  Skipping non-standard file: {file_path}")
                stats["skipped"] += 1
                continue

            logger.info(f"✅ Copied {file_path}")
            stats["copied"] += 1
            stats["total_bytes"] += file_size

        except Exception as e:
            logger.error(f"❌ Error copying {file_path}: {e}")
            stats["errors"] += 1

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 Resume Migration Summary")
    logger.info("=" * 60)
    logger.info(f"Previously uploaded: {len(already_done)}")
    logger.info(f"Newly copied: {stats['copied']}")
    logger.info(f"Skipped: {stats['skipped']}")
    logger.info(f"Errors: {stats['errors']}")
    logger.info(f"Total data: {stats['total_bytes'] / (1024**3):.2f} GB")
    logger.info(f"Total files in cloud: {len(already_done) + stats['copied']}")

    return stats


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Resume a partial migration from log file"
    )
    parser.add_argument(
        "--log",
        required=True,
        help="Path to the migration log file to resume from",
    )
    parser.add_argument(
        "--include",
        action="append",
        help="Include only files matching these patterns",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        help="Exclude files matching these patterns",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    try:
        stats = resume_migration(
            log_file=args.log,
            include_patterns=args.include,
            exclude_patterns=args.exclude,
            verbose=args.verbose,
        )

        if stats["errors"] > 0:
            sys.exit(1)

    except Exception as e:
        logging.error(f"Resume failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
