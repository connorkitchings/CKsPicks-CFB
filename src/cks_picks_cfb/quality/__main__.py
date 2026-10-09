"""CLI: ``python -m cks_picks_cfb.quality --stage silver --year 2026``.

Runs the registered checks for a stage, writes a receipt under ``--output`` (local
directory) and exits 1 when any blocking check fails, 2 on usage errors.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from cks_picks_cfb.quality.checks import REGISTRY, STAGES, registry_problems, run_stage
from cks_picks_cfb.quality.loaders import (
    load_gold_context,
    load_ingest_context,
    load_silver_context,
    parse_pins,
)
from cks_picks_cfb.quality.receipt import (
    build_receipt,
    write_receipt_local,
    write_receipt_storage,
)


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
        "--request-inventory",
        type=Path,
        help="Independent expected CFBD request manifest",
    )
    parser.add_argument(
        "--require-check",
        action="append",
        default=[],
        help="Fail closed on a failed or skipped check (repeatable)",
    )
    parser.add_argument(
        "--policy",
        type=Path,
        help="Versioned required-check policy (defaults to repair_v1 for a database environment)",
    )
    parser.add_argument(
        "--upload-receipt",
        action="store_true",
        help="Copy the exact receipt to configured R2; never upload by default",
    )
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
    inventory = None
    if args.request_inventory:
        if args.stage != "ingest":
            parser.error("--request-inventory is for the ingest stage")
        inventory_raw = args.request_inventory.read_bytes()
        inventory = json.loads(inventory_raw)
        if args.environment:
            from cks_picks_cfb.data.storage import get_storage
            from cks_picks_cfb.quality.request_inventory import (
                verify_expected_request_inventory,
            )

            verify_expected_request_inventory(
                get_storage(environment=args.environment), inventory
            )
    if (
        args.stage == "ingest"
        and "ingest.capture_completeness" in args.require_check
        and inventory is None
    ):
        parser.error(
            "requiring ingest.capture_completeness needs --request-inventory; "
            "the attempt ledger cannot establish completeness"
        )
    if args.upload_receipt and not args.environment:
        parser.error("--upload-receipt requires --environment")
    if args.environment and args.year:
        loader = {
            "ingest": load_ingest_context,
            "silver": load_silver_context,
            "gold": load_gold_context,
        }.get(args.stage)
        if loader is not None:
            kwargs = {"pins": pins}
            if args.stage == "ingest":
                kwargs["request_inventory"] = inventory
            context.update(loader(args.environment, args.year, **kwargs))
    if inventory is not None:
        context.setdefault("inputs", {})["request_inventory"] = {
            "sha256": hashlib.sha256(inventory_raw).hexdigest()
        }
    policy_path = args.policy or (
        Path("conf/quality/repair_v1.json") if args.environment else None
    )
    policy_sha = None
    required_checks = set(args.require_check)
    if policy_path is not None:
        from cks_picks_cfb.quality.policy import load_required_policy

        required_checks.update(load_required_policy(policy_path)[args.stage])
        policy_sha = hashlib.sha256(policy_path.read_bytes()).hexdigest()
        context.setdefault("inputs", {})["required_policy"] = {
            "sha256": policy_sha,
            "path": str(policy_path),
        }
    run = run_stage(args.stage, context, required_checks=sorted(required_checks))
    receipt = build_receipt(
        run,
        identity={
            "year": args.year,
            "environment": args.environment,
            "pins": pins,
            "required_policy_sha256": policy_sha,
        },
        code_sha=_code_sha(),
        inputs=context.get("inputs"),
    )
    path = write_receipt_local(receipt, args.output)
    remote_uri = None
    if args.upload_receipt:
        from cks_picks_cfb.data.storage import get_storage
        from cks_picks_cfb.data.storage.base import StorageSettings

        if StorageSettings.from_env(environment=args.environment).backend != "r2":
            raise ValueError(
                "durable quality receipts require explicit R2 configuration"
            )
        remote_uri = write_receipt_storage(
            receipt, get_storage(environment=args.environment)
        )
    print(
        json.dumps(
            {
                "stage": args.stage,
                "checks": receipt["summary"]["checks"],
                "failed": receipt["summary"]["failed"],
                "skipped": receipt["summary"]["skipped"],
                "blocked": receipt["blocked"],
                "receipt": str(path),
                "durable_receipt": remote_uri,
            },
            indent=2,
        )
    )
    return 1 if run.blocked else 0


if __name__ == "__main__":
    sys.exit(main())
