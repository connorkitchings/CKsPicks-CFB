#!/usr/bin/env python3
"""Promote validated Silver versions from the Preview catalog to production's.

Weekly play-by-play Silver (``byplay``, ``drives``, 2026 ``games`` and
``game_outcomes``) is built and certified in the Preview lake. Production
consumers (``publish_team_stats.py --environment production``) look in the
production catalog, which does not hold those versions. Preview and production
share one R2 bucket, so this registers the *existing* immutable objects (plus
parents and source captures) in the target catalog after re-verifying every
manifest and content hash. Nothing is copied; different buckets are refused.

Always dry run first (read-only on both catalogs and storage):

    PYTHONPATH=src:. uv run python scripts/pipeline/promote_silver_versions.py \\
        --season 2026 --dry-run

The real run writes only to the target catalog, through the restricted
production pipeline login (``scripts/ops/with_production_pipeline_env.sh`` sets
DATABASE_URL). Source is ``PREVIEW_DATABASE_URL``; use the Preview wrapper's
value, not the legacy ``.env`` one, when both are needed in one process.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from dotenv import load_dotenv

from cks_picks_cfb.data.promotion import (
    PromotionError,
    assert_same_bucket,
    promote,
    resolve_version,
)
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.data.storage.base import StorageSettings

URL_ENV = {"preview": "PREVIEW_DATABASE_URL", "production": "DATABASE_URL"}
DEFAULT_DATASETS = ("byplay", "drives", "games", "game_outcomes", "teams")


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument(
        "--from", dest="source", choices=sorted(URL_ENV), default="preview"
    )
    parser.add_argument(
        "--to", dest="target", choices=sorted(URL_ENV), default="production"
    )
    parser.add_argument(
        "--datasets",
        default=",".join(DEFAULT_DATASETS),
        help="Comma-separated Silver datasets (latest for the season unless pinned)",
    )
    parser.add_argument(
        "--version",
        action="append",
        default=[],
        metavar="DATASET=VERSION_ID",
        help="Pin a dataset to a version id (prefix ok); repeatable",
    )
    parser.add_argument("--dry-run", action="store_true", help="Verify; write nothing")
    args = parser.parse_args()
    if args.source == args.target:
        parser.error("--from and --to must differ")

    source_url = os.getenv(URL_ENV[args.source])
    target_url = os.getenv(URL_ENV[args.target])
    if not source_url or not target_url:
        print(f"Set {URL_ENV[args.source]} and {URL_ENV[args.target]}", file=sys.stderr)
        return 2
    pins = dict(item.split("=", 1) for item in args.version)
    datasets = [d.strip() for d in args.datasets.split(",") if d.strip()]

    try:
        assert_same_bucket(
            StorageSettings.from_env(environment=args.source),
            StorageSettings.from_env(environment=args.target),
        )
        roots = {
            name: resolve_version(source_url, name, args.season, pins.get(name))
            for name in datasets
        }
        print(f"Roots: {json.dumps(roots)}")
        report = promote(
            source_url=source_url,
            target_url=target_url,
            storage=get_storage(environment=args.source),
            root_versions=list(roots.values()),
            dry_run=args.dry_run,
        )
    except PromotionError as exc:
        print(f"Cannot promote: {exc}", file=sys.stderr)
        return 3

    for info in report.versions:
        flag = "present" if info["already_in_target"] else "NEW"
        print(
            f"  [{flag}] {info['dataset']} {info['version_id'][:12]} "
            f"rows={info['row_count']} bytes={info['bytes']} "
            f"parents={info['parents']} captures={info['captures']}"
        )
    print(
        f"Versions: {len(report.new_versions)} new of {len(report.versions)}; "
        f"captures: {len(report.captures_to_register)} to register, "
        f"{len(report.captures_present)} already present"
    )
    print("Dry run: nothing written." if args.dry_run else "Registered.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
