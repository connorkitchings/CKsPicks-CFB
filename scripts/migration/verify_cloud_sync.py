#!/usr/bin/env python3
"""Verify local vs cloud migration completeness for raw/processed data.

Compares canonical tabular files (.csv, .parquet) in CFB_MODEL_DATA_ROOT with
objects in the configured cloud storage backend (R2/S3).

Usage:
    # Verify raw + processed (default), ignoring macOS ._* metadata files
    PYTHONPATH=. uv run python scripts/migration/verify_cloud_sync.py

    # Verify only processed files
    PYTHONPATH=. uv run python scripts/migration/verify_cloud_sync.py --prefix processed

    # Include ._* metadata files in the comparison
    PYTHONPATH=. uv run python scripts/migration/verify_cloud_sync.py --include-dot-underscore
"""

import argparse
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency in runtime env
    load_dotenv = None


def is_tabular_data_file(path: str, include_dot_underscore: bool) -> bool:
    """Return True for canonical dataset files included in verification."""
    file_name = Path(path).name
    if not include_dot_underscore and file_name.startswith("._"):
        return False
    return path.endswith(".csv") or path.endswith(".parquet")


def build_local_inventory(
    data_root: Path, prefix: str, include_dot_underscore: bool
) -> set[str]:
    """Build local file inventory for the given prefix."""
    base = data_root / prefix
    if not base.exists():
        return set()

    files: set[str] = set()
    for file_path in base.rglob("*"):
        if not file_path.is_file():
            continue
        rel_path = file_path.relative_to(data_root).as_posix()
        if is_tabular_data_file(rel_path, include_dot_underscore):
            files.add(rel_path)
    return files


def build_cloud_inventory(prefix: str, include_dot_underscore: bool) -> set[str]:
    """Build cloud inventory for the given prefix using configured backend."""
    from src.data.storage import get_storage

    storage = get_storage()
    cloud_files = storage.list_files(f"{prefix}/")
    return {
        path
        for path in cloud_files
        if is_tabular_data_file(path, include_dot_underscore)
    }


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Verify local and cloud migration completeness."
    )
    parser.add_argument(
        "--prefix",
        action="append",
        choices=["raw", "processed"],
        help="Prefix to verify (can be specified multiple times). Defaults to raw+processed.",
    )
    parser.add_argument(
        "--include-dot-underscore",
        action="store_true",
        help="Include macOS ._* metadata files in comparison.",
    )
    parser.add_argument(
        "--output-dir",
        default="/tmp/cfb_cloud_sync_verify",
        help="Directory for writing reconciliation artifacts.",
    )
    args = parser.parse_args()

    if load_dotenv:
        load_dotenv(".env", override=False)

    data_root_value = os.getenv("CFB_MODEL_DATA_ROOT")
    if not data_root_value:
        raise ValueError("CFB_MODEL_DATA_ROOT must be set")

    data_root = Path(data_root_value)
    if not data_root.exists():
        raise ValueError(f"CFB_MODEL_DATA_ROOT not found: {data_root}")

    backend = os.getenv("CFB_STORAGE_BACKEND", "local").lower()
    if backend == "local":
        raise ValueError("Cloud verification requires CFB_STORAGE_BACKEND='r2' or 's3'")

    prefixes = args.prefix or ["raw", "processed"]
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Using backend: {backend}")
    print(f"Data root: {data_root}")
    print(f"Comparing prefixes: {', '.join(prefixes)}")
    print(f"Include dot-underscore metadata files: {args.include_dot_underscore}")

    has_diff = False
    for prefix in prefixes:
        local_files = build_local_inventory(
            data_root=data_root,
            prefix=prefix,
            include_dot_underscore=args.include_dot_underscore,
        )
        cloud_files = build_cloud_inventory(
            prefix=prefix,
            include_dot_underscore=args.include_dot_underscore,
        )

        missing_in_cloud = sorted(local_files - cloud_files)
        extra_in_cloud = sorted(cloud_files - local_files)

        (output_dir / f"local_{prefix}.txt").write_text(
            "\n".join(sorted(local_files)) + ("\n" if local_files else "")
        )
        (output_dir / f"cloud_{prefix}.txt").write_text(
            "\n".join(sorted(cloud_files)) + ("\n" if cloud_files else "")
        )
        (output_dir / f"missing_{prefix}_in_cloud.txt").write_text(
            "\n".join(missing_in_cloud) + ("\n" if missing_in_cloud else "")
        )
        (output_dir / f"extra_{prefix}_in_cloud.txt").write_text(
            "\n".join(extra_in_cloud) + ("\n" if extra_in_cloud else "")
        )

        print(
            f"{prefix}: local={len(local_files)} cloud={len(cloud_files)} "
            f"missing_in_cloud={len(missing_in_cloud)} extra_in_cloud={len(extra_in_cloud)}"
        )

        if missing_in_cloud:
            print(f"Sample missing ({prefix}): {missing_in_cloud[:5]}")
            has_diff = True
        if extra_in_cloud:
            print(f"Sample extra ({prefix}): {extra_in_cloud[:5]}")
            has_diff = True

    print(f"Artifacts written to: {output_dir}")
    return 1 if has_diff else 0


if __name__ == "__main__":
    raise SystemExit(main())
