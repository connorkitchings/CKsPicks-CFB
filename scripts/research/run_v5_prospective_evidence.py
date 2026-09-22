#!/usr/bin/env python3
"""Preview-only Contract 06 evidence preflight/apply/verify runner."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ratings.prospective_v5_evidence import (
    ProspectiveEvidenceError,
    apply_evidence,
    preflight_evidence,
)
from cks_picks_cfb.ratings.prospective_v5_evidence_sources import EVIDENCE_INPUT_SCHEMA
from cks_picks_cfb.ratings.prospective_v5_evidence_verification import (
    verify_evidence_artifact,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = (
    ROOT / "conf/research/data_first_football_v1/prospective_evidence_v1.yaml"
)


def _git_sha() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def _clean_worktree() -> bool:
    return not subprocess.check_output(
        ["git", "status", "--porcelain=v1"], cwd=ROOT, text=True
    ).strip()


def _load_descriptor(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProspectiveEvidenceError(
            "evidence input descriptor is invalid JSON"
        ) from exc
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != EVIDENCE_INPUT_SCHEMA
    ):
        raise ProspectiveEvidenceError("unexpected evidence input descriptor schema")
    return value, raw


def _validate_config(path: Path) -> bytes:
    raw = path.read_bytes()
    value = yaml.safe_load(raw)
    expected = {
        "schema_version": "data_first_v5_prospective_evidence_config_v1",
        "environment": "preview",
        "candidate_schema": "data_first_live_forecast_manifest_v1",
        "minimum_paired_games": 40,
        "freeze_hard_lead_seconds": 3600,
        "score_stabilization_seconds": 86400,
        "required_qualifying_slates": 6,
        "allowed_recommendations": [
            "retain_v4",
            "continue_shadowing",
            "prepare_phase7",
        ],
        "production_activation_authorized": False,
    }
    if value != expected:
        raise ProspectiveEvidenceError(
            "Contract 06 evidence config differs from its approved policy"
        )
    return raw


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "apply", "verify"))
    parser.add_argument("--run-id", default="")
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--environment", required=True, choices=("preview",))
    parser.add_argument("--as-of", default="")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--input-descriptor", default="")
    parser.add_argument("--preflight-evidence", default="")
    parser.add_argument("--manifest-uri", default="")
    parser.add_argument("--write-preflight", default="")
    args = parser.parse_args(argv)
    try:
        if _git_sha() != args.expected_code_sha:
            raise ProspectiveEvidenceError(
                "expected code SHA does not match committed HEAD"
            )
        config_bytes = _validate_config(Path(args.config))
        storage = get_storage(environment="preview")
        if args.action == "verify":
            if not args.manifest_uri:
                raise ProspectiveEvidenceError("--manifest-uri is required for verify")
            result = verify_evidence_artifact(
                storage,
                manifest_uri=args.manifest_uri,
                expected_code_sha=args.expected_code_sha,
            )
        else:
            if not args.input_descriptor or not args.run_id or not args.as_of:
                raise ProspectiveEvidenceError(
                    "preflight/apply require --input-descriptor, --run-id, and --as-of"
                )
            descriptor, descriptor_bytes = _load_descriptor(Path(args.input_descriptor))
            if args.action == "preflight":
                result = preflight_evidence(
                    storage,
                    descriptor=descriptor,
                    expected_code_sha=args.expected_code_sha,
                    run_id=args.run_id,
                    as_of=args.as_of,
                    config_bytes=config_bytes,
                    descriptor_bytes=descriptor_bytes,
                )
                if args.write_preflight:
                    Path(args.write_preflight).write_bytes(
                        json.dumps(
                            result, sort_keys=True, indent=2, default=str
                        ).encode()
                    )
            else:
                if not args.preflight_evidence:
                    raise ProspectiveEvidenceError(
                        "--preflight-evidence is required for apply"
                    )
                if not _clean_worktree():
                    raise ProspectiveEvidenceError(
                        "apply requires a completely clean committed worktree"
                    )
                preflight = json.loads(Path(args.preflight_evidence).read_bytes())
                result = apply_evidence(
                    storage,
                    descriptor=descriptor,
                    expected_code_sha=args.expected_code_sha,
                    run_id=args.run_id,
                    as_of=args.as_of,
                    config_bytes=config_bytes,
                    descriptor_bytes=descriptor_bytes,
                    expected_preflight=preflight,
                )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"verified": False, "error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
