#!/usr/bin/env python3
"""Independent V5 shadow verifier CLI.

Reconstructs readiness, freeze, scoring, counter, and rehearsal artifacts from
source datasets without importing any producer module, and optionally writes
the signed verifier manifest under the run's verification/ prefix.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import PurePosixPath

from dotenv import load_dotenv

from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.forecast.shadow_verification import (
    ShadowVerificationError,
    verify_shadow_artifact,
    write_verifier_manifest,
)


def _run_prefix(manifest_uri: str) -> str:
    return str(PurePosixPath(manifest_uri).parent)


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-uri", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--environment", required=True, choices=("preview",))
    parser.add_argument(
        "--schedule-uri", default="", help="slate/schedule source (freeze/score)"
    )
    parser.add_argument(
        "--v4-prediction-uri", default="", help="V4 prediction source override"
    )
    parser.add_argument(
        "--outcome-uri", default="", help="outcome source override (score)"
    )
    parser.add_argument(
        "--readiness-cutoff", default="", help="readiness cutoff override"
    )
    parser.add_argument(
        "--write-manifest",
        action="store_true",
        help="persist the signed verifier manifest (idempotent)",
    )
    args = parser.parse_args(argv)
    storage = get_storage(environment="preview")
    try:
        result = verify_shadow_artifact(
            storage,
            manifest_uri=args.manifest_uri,
            expected_code_sha=args.expected_code_sha,
            environment=args.environment,
            schedule_uri=args.schedule_uri,
            v4_prediction_uri=args.v4_prediction_uri,
            outcome_uri=args.outcome_uri,
            readiness_cutoff=args.readiness_cutoff,
        )
        if args.write_manifest:
            prefix = _run_prefix(args.manifest_uri)
            if prefix.endswith("/verification"):
                prefix = str(PurePosixPath(prefix).parent)
            uri = write_verifier_manifest(storage, run_prefix=prefix, payload=result)
            result["verifier_manifest_uri"] = uri
    except ShadowVerificationError as exc:
        print(json.dumps({"verified": False, "error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
