#!/usr/bin/env python3
"""Stage packaged prediction runs between artifact namespaces (dry run by default)."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from dotenv import load_dotenv

from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ops.v5_artifact_staging import stage_runs
from cks_picks_cfb.ratings_lab.artifacts import canonical_json


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", default="preview", choices=("preview", "production")
    )
    parser.add_argument(
        "--target", default="production", choices=("preview", "production")
    )
    parser.add_argument(
        "--run",
        action="append",
        required=True,
        metavar="WEEK=RUN_ID",
        help="repeatable",
    )
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-receipt-sha256")
    parser.add_argument("--expected-code-sha")
    args = parser.parse_args()

    runs = {int(w): r for w, r in (item.split("=", 1) for item in args.run)}
    source = get_storage(environment=args.source)
    target = get_storage(environment=args.target)
    receipt = stage_runs(
        source, target, runs, source=args.source, target=args.target, apply=False
    )
    if args.apply:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        dirty = subprocess.check_output(["git", "status", "--porcelain=v1"], text=True)
        if dirty.strip() or head != args.expected_code_sha:
            raise SystemExit("apply requires the reviewed clean committed code")
        if receipt["manifest_sha256"] != args.expected_receipt_sha256:
            raise SystemExit("dry-run plan differs from the reviewed receipt")
        receipt = stage_runs(
            source, target, runs, source=args.source, target=args.target, apply=True
        )
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_bytes(canonical_json(receipt))
    print(
        json.dumps(
            {"applied": args.apply, "receipt_sha256": receipt["manifest_sha256"]}
        )
    )


if __name__ == "__main__":
    main()
