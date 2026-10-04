"""CLI: ``python -m cks_picks_cfb.quality --stage silver --year 2026``.

Runs the registered checks for a stage, writes a receipt under ``--output`` (local
directory) and exits 1 when any blocking check fails, 2 on usage errors.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from cks_picks_cfb.quality.checks import REGISTRY, STAGES, registry_problems, run_stage
from cks_picks_cfb.quality.loaders import (
    load_ingest_context,
    load_silver_context,
    parse_pins,
)
from cks_picks_cfb.quality.receipt import build_receipt, write_receipt_local


def _code_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=STAGES)
    parser.add_argument("--year", type=int)
    parser.add_argument("--environment", choices=("preview", "production"))
    parser.add_argument("--output", type=Path, default=Path("artifacts"))
    parser.add_argument(
        "--pin",
        action="append",
        metavar="DATASET=VERSION_ID",
        help="Pin a Silver dataset version for the run (repeatable)",
    )
    parser.add_argument("--list", action="store_true", help="List registered checks")
    parser.add_argument(
        "--verify-registry", action="store_true", help="Check registry integrity only"
    )
    args = parser.parse_args(argv)

    if args.verify_registry:
        problems = registry_problems()
        print(json.dumps({"checks": len(REGISTRY), "problems": problems}, indent=2))
        return 1 if problems else 0
    if args.list:
        for spec in sorted(REGISTRY.values(), key=lambda s: (s.stage, s.check_id)):
            print(
                f"{spec.stage:8} {spec.severity:5} {spec.check_id}  {spec.description}"
            )
        return 0
    if args.stage is None:
        parser.error("--stage is required unless --list or --verify-registry is used")

    context: dict = {"year": args.year, "environment": args.environment}
    pins = parse_pins(args.pin)
    if args.environment and args.year:
        loader = {"ingest": load_ingest_context, "silver": load_silver_context}.get(
            args.stage
        )
        if loader is not None:
            context.update(loader(args.environment, args.year, pins=pins))
    run = run_stage(args.stage, context)
    receipt = build_receipt(
        run,
        identity={"year": args.year, "environment": args.environment, "pins": pins},
        code_sha=_code_sha(),
        inputs=context.get("inputs"),
    )
    path = write_receipt_local(receipt, args.output)
    print(
        json.dumps(
            {
                "stage": args.stage,
                "checks": receipt["summary"]["checks"],
                "failed": receipt["summary"]["failed"],
                "skipped": receipt["summary"]["skipped"],
                "blocked": receipt["blocked"],
                "receipt": str(path),
            },
            indent=2,
        )
    )
    return 1 if run.blocked else 0


if __name__ == "__main__":
    sys.exit(main())
