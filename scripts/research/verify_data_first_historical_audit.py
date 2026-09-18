#!/usr/bin/env python3
"""Independent verification of historical-audit evidence.

Re-reads audit evidence (local preflight evidence or the published Preview
prefix), verifies bytes, hashes, identity, internal consistency, source
references, and gate arithmetic. Imports only audit schemas/constants,
generic storage readers, and the verifier-owned verification module — never
the audit runner or check implementations.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

from cks_picks_cfb.audit.verification import (
    AuditVerificationError,
    verify_audit_evidence,
    verify_published_audit,
)
from cks_picks_cfb.data.storage import get_storage

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "conf/research/data_first_football_v1/historical_audit_v1.yaml"


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--evidence-path", default=None)
    group.add_argument("--manifest-uri", default=None)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--environment", required=True, choices=("preview",))
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args(argv)

    config = yaml.safe_load(Path(args.config).read_bytes())
    expected_parents = {
        stage: str(entry["manifest_uri"])
        for stage, entry in (config.get("parents") or {}).items()
    }
    storage = get_storage(environment=args.environment)
    try:
        if args.evidence_path:
            evidence = json.loads(Path(args.evidence_path).read_bytes())
            result = verify_audit_evidence(
                evidence,
                expected_run_id=args.run_id,
                expected_code_sha=args.expected_code_sha,
                expected_parents=expected_parents,
                storage=None,
                require_published=False,
            )
        else:
            prefix = str(args.manifest_uri).rsplit("/audit-manifest.json", 1)[0]
            manifest = json.loads(storage.read_bytes(args.manifest_uri))
            register = json.loads(
                storage.read_bytes(f"{prefix}/evidence-register.json")
            )
            checks = json.loads(storage.read_bytes(f"{prefix}/check-results.json"))
            findings_doc = json.loads(storage.read_bytes(f"{prefix}/findings.json"))
            result = verify_published_audit(
                manifest,
                register,
                checks,
                findings_doc,
                expected_run_id=args.run_id,
                expected_code_sha=args.expected_code_sha,
                expected_parents=expected_parents,
                storage=storage,
            )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (AuditVerificationError, OSError, ValueError) as exc:
        print(f"audit verification failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
