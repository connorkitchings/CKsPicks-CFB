#!/usr/bin/env python3
"""Independent verification of a frozen V5-11C forecast artifact.

This CLI recursively verifies the frozen parents, reconstructs every stored
forecast computation independently (including the through-2025 final-fit
rows), and compares all six outputs by canonical digest and partition. With
``--publish`` it additionally writes the signed Preview verification record
under the run's ``verification/`` prefix (idempotent, collision-fail).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.forecast.forecast_verification import (
    VerificationError,
    publish_verification_manifest,
    verify_forecast_artifact,
)

ROOT = Path(__file__).resolve().parents[2]


def _git_sha() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def _clean_worktree() -> bool:
    return not subprocess.check_output(
        ["git", "status", "--porcelain=v1"], cwd=ROOT, text=True
    ).strip()


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-uri", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--environment", required=True, choices=("preview",))
    parser.add_argument("--rating-manifest-uri", required=True)
    parser.add_argument("--measurement-manifest-uri", required=True)
    parser.add_argument("--repair-manifest-uri", required=True)
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Write the signed verification record (requires a clean worktree).",
    )
    args = parser.parse_args(argv)
    storage = get_storage(environment=args.environment)
    try:
        if args.publish and not _clean_worktree():
            raise VerificationError(
                "--publish requires a completely clean committed worktree"
            )
        result = verify_forecast_artifact(
            storage,
            manifest_uri=args.manifest_uri,
            expected_code_sha=args.expected_code_sha,
            environment=args.environment,
            rating_manifest_uri=args.rating_manifest_uri,
            measurement_manifest_uri=args.measurement_manifest_uri,
            repair_manifest_uri=args.repair_manifest_uri,
        )
        if args.publish:
            result |= publish_verification_manifest(
                storage,
                result=result,
                verifier_code_sha=_git_sha(),
                rating_manifest_uri=args.rating_manifest_uri,
                measurement_manifest_uri=args.measurement_manifest_uri,
                repair_manifest_uri=args.repair_manifest_uri,
            )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except VerificationError as exc:
        print(f"verification failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
