#!/usr/bin/env python3
"""Independently verify a published Contract 06 Preview evidence report."""

from __future__ import annotations

import argparse
import json
import sys

from dotenv import load_dotenv

from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ratings.prospective_v5_evidence_sources import EvidenceSourceError
from cks_picks_cfb.ratings.prospective_v5_evidence_verification import (
    EvidenceVerificationError,
    verify_evidence_artifact,
)


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-uri", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--environment", required=True, choices=("preview",))
    args = parser.parse_args(argv)
    storage = get_storage(environment="preview")
    try:
        result = verify_evidence_artifact(
            storage,
            manifest_uri=args.manifest_uri,
            expected_code_sha=args.expected_code_sha,
        )
    except (EvidenceVerificationError, EvidenceSourceError, ValueError, OSError) as exc:
        print(json.dumps({"verified": False, "error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
