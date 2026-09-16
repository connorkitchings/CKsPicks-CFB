#!/usr/bin/env python3
"""Preflight the sealed Preview-only V5-03 possession-rating tournament.

This command intentionally defaults to a no-write preflight.  An immutable
apply is accepted only after the exact committed code SHA is available; the
runner refuses to create a partial ratings prefix while evidence construction is
still incomplete.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import yaml
from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_possession_rating_v1 import (
    POSSESSION_RATING_OUTPUT_ROOT,
    candidate_registry,
    rating_identity,
    validate_config,
    verify_parents,
)
from cks_picks_cfb.data.storage import get_storage

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "conf/research/data_first_football_v1/possession_rating_v1.yaml"


class PossessionRatingRunError(ValueError):
    """Raised before a V5-03 run can produce immutable output."""


def _git_sha() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def _clean_worktree() -> bool:
    return not subprocess.check_output(
        ["git", "status", "--porcelain=v1"], cwd=ROOT, text=True
    ).strip()


def preflight(*, storage: object, args: argparse.Namespace) -> dict[str, object]:
    config_path = Path(args.config)
    config = yaml.safe_load(config_path.read_text())
    validate_config(config)
    measurement_raw = storage.read_bytes(args.measurement_manifest_uri)
    repair_raw = storage.read_bytes(args.repair_manifest_uri)
    measurement, repair = verify_parents(
        json.loads(measurement_raw), json.loads(repair_raw)
    )
    config_sha = hashlib.sha256(config_path.read_bytes()).hexdigest()
    identity = rating_identity(
        run_id=args.run_id,
        as_of=args.as_of,
        code_sha=args.expected_code_sha,
        config_sha=config_sha,
        measurement_manifest_uri=args.measurement_manifest_uri,
        measurement_manifest_raw_sha256=hashlib.sha256(measurement_raw).hexdigest(),
        repair_manifest_uri=args.repair_manifest_uri,
        repair_manifest_raw_sha256=hashlib.sha256(repair_raw).hexdigest(),
    )
    return {
        "state": "dry_run",
        "identity": identity,
        "candidate_count": len(candidate_registry()),
        "candidates": [item["candidate_id"] for item in candidate_registry()],
        "measurement_parent": measurement["identity"]["run_id"],
        "repair_parent": repair["identity"]["run_id"],
        "output_prefix": f"{POSSESSION_RATING_OUTPUT_ROOT}/{args.run_id}",
        "production_activation_authorized": False,
    }


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--environment", required=True, choices=("preview",))
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--measurement-manifest-uri", required=True)
    parser.add_argument("--repair-manifest-uri", required=True)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    if _git_sha() != args.expected_code_sha:
        raise PossessionRatingRunError(
            "expected code SHA does not match committed HEAD"
        )
    storage = get_storage(environment="preview")
    evidence = preflight(storage=storage, args=args)
    if args.apply:
        if not _clean_worktree():
            raise PossessionRatingRunError(
                "apply requires a completely clean committed worktree"
            )
        # Do not create an immutable prefix until all state/bridge partitions are
        # supplied by the sealed materializer.  This prevents a registry-only
        # artifact from being mistaken for a downstream-eligible rating parent.
        raise PossessionRatingRunError(
            "V5-03 apply is blocked pending complete state/bridge materialization"
        )
    print(json.dumps(evidence, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
