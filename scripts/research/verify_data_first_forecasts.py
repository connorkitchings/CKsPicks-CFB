#!/usr/bin/env python3
"""Independent verification of a frozen V5-04B forecast artifact.

This CLI loads the forecast manifest and verifies its identity, parents, and
output references. Full reconstruction verification is deferred to a later
task; this initial version validates the manifest structure and signatures.
"""

from __future__ import annotations

import argparse
import json
import sys

from dotenv import load_dotenv

from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.forecast.forecast_verification import (
    VerificationError,
    verify_forecast_artifact,
)


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-uri", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--environment", required=True, choices=("preview",))
    parser.add_argument("--rating-manifest-uri", required=True)
    parser.add_argument("--measurement-manifest-uri", required=True)
    parser.add_argument("--repair-manifest-uri", required=True)
    args = parser.parse_args(argv)
    storage = get_storage(environment=args.environment)
    try:
        result = verify_forecast_artifact(
            storage,
            manifest_uri=args.manifest_uri,
            expected_code_sha=args.expected_code_sha,
            environment=args.environment,
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
