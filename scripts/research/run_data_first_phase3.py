#!/usr/bin/env python3
"""Validate the signed Phase 3 parent before a committed Preview run."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_phase3 import (
    Phase3Error,
    phase3_identity,
    verify_core_eligibility,
)
from cks_picks_cfb.data.storage import get_storage

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "conf/research/data_first_football_v1/phase3_measurement_core_v1.yaml"


def _git_sha() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _tracked_clean() -> bool:
    result = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], capture_output=True, text=True, check=False)
    return result.returncode == 0 and not result.stdout.strip()


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-eligibility-uri", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--environment", choices=["preview", "production"], required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    if args.environment != "preview":
        raise Phase3Error("Phase 3 is Preview-only")
    code_sha = _git_sha()
    if code_sha != args.expected_code_sha:
        raise Phase3Error("HEAD does not match --expected-code-sha")
    if not _tracked_clean():
        raise Phase3Error("Phase 3 runs require a clean tracked worktree")
    config_bytes = Path(args.config).read_bytes()
    storage = get_storage(environment="preview")
    raw_parent = storage.read_bytes(args.core_eligibility_uri)
    parent = json.loads(raw_parent)
    refs = verify_core_eligibility(parent)
    identity = phase3_identity(
        run_id=args.run_id,
        environment=args.environment,
        code_sha=code_sha,
        config_sha=hashlib.sha256(config_bytes).hexdigest(),
        core_eligibility_uri=args.core_eligibility_uri,
        core_eligibility_sha256=hashlib.sha256(raw_parent).hexdigest(),
    )
    if args.apply:
        raise Phase3Error("Phase 3 apply is blocked until the measurement materializer is committed")
    print(json.dumps({"status": "dry_run", "identity": identity, "parent_ref_count": len(refs)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
