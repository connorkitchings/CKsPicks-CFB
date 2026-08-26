#!/usr/bin/env python3
"""Certify the immutable Phase 1--2 rating handoff before Phase 3 prediction."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from cks_picks_cfb.data.lake import DatasetRef, read_dataset
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ratings.contracts import load_measurement_config
from cks_picks_cfb.ratings.foundation_review import (
    build_foundation_review,
    load_foundation_review_config,
)
from cks_picks_cfb.ratings.state_contracts import load_team_state_config

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "conf/ratings/foundation_review_v2.yaml"
RELEVANT_PATHS = (
    "src/cks_picks_cfb/ratings/foundation_review.py",
    "scripts/pipeline/build_rating_foundation_review.py",
    "conf/ratings/foundation_review_v2.yaml",
)


def _read_ref(storage, uri: str) -> DatasetRef:
    return DatasetRef(**json.loads(storage.read_bytes(uri).decode()))


def _require_committed_code(expected: str | None, *, config_path: str) -> str:
    current = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    code_sha = expected or current
    if not code_sha:
        raise ValueError("Foundation review requires a committed code SHA")
    relevant = (*RELEVANT_PATHS[:-1], config_path)
    for path in relevant:
        if subprocess.run(
            ["git", "ls-files", "--error-unmatch", path],
            cwd=REPO_ROOT,
            capture_output=True,
            check=False,
        ).returncode:
            raise ValueError(f"Foundation review path is not committed: {path}")
    if subprocess.run(
        ["git", "diff", "--quiet", code_sha, "--", *relevant],
        cwd=REPO_ROOT,
        check=False,
    ).returncode:
        raise ValueError("Foundation review paths differ from the recorded commit")
    return code_sha


def _write_immutable(storage, uri: str, payload: bytes) -> None:
    if storage.exists(uri):
        if storage.read_bytes(uri) != payload:
            raise FileExistsError(f"Immutable artifact exists: {uri}")
        return
    storage.write_bytes(payload, uri)


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--environment", choices=("preview", "production"), required=True
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--report-uri", required=True)
    parser.add_argument("--expected-code-sha")
    args = parser.parse_args(argv)
    if args.environment != "preview":
        raise ValueError("Foundation review is permitted only in preview")
    config = load_foundation_review_config(args.config)
    prefix = f"{config.research_prefix}/{config.design_id}/runs/{args.run_id}/"
    if not args.run_id or not args.report_uri.startswith(prefix):
        raise ValueError(
            "Foundation review output must use its run-stamped research prefix"
        )
    datetime.fromisoformat(args.as_of.replace("Z", "+00:00")).astimezone(timezone.utc)
    config_path = str(Path(args.config).resolve().relative_to(REPO_ROOT))
    code_sha = _require_committed_code(args.expected_code_sha, config_path=config_path)
    storage = get_storage(environment="preview")
    phase1_audit = json.loads(storage.read_bytes(config.phase1["audit_uri"]).decode())
    phase2_audit = json.loads(storage.read_bytes(config.phase2["audit_uri"]).decode())
    refs = {
        "observations": _read_ref(storage, config.phase1["observations_ref_uri"]),
        "snapshots": _read_ref(storage, config.phase1["snapshots_ref_uri"]),
        "terminal": _read_ref(storage, config.phase1["terminal_ref_uri"]),
        "measurement_states": _read_ref(
            storage, config.phase2["measurement_states_ref_uri"]
        ),
        "team_states": _read_ref(storage, config.phase2["team_states_ref_uri"]),
    }
    review = build_foundation_review(
        observations=read_dataset(storage, refs["observations"]),
        snapshots=read_dataset(storage, refs["snapshots"]),
        terminal_snapshots=read_dataset(storage, refs["terminal"]),
        measurement_states=read_dataset(storage, refs["measurement_states"]),
        team_states=read_dataset(storage, refs["team_states"]),
        phase1_audit=phase1_audit,
        phase2_audit=phase2_audit,
        refs=refs,
        config=config,
        measurement_config=load_measurement_config(config.measurement_config_path),
        team_state_config=load_team_state_config(config.team_state_config_path),
        code_sha=code_sha,
    )
    review["as_of"] = args.as_of
    review["run_id"] = args.run_id
    payload = json.dumps(review, indent=2, sort_keys=True, default=str).encode()
    _write_immutable(storage, args.report_uri, payload)
    if not review["all_checks_passed"]:
        raise ValueError("Foundation review failed; Phase 3 prediction remains blocked")
    print(
        json.dumps(
            {
                "status": "certified",
                "report_uri": args.report_uri,
                "report_sha256": hashlib.sha256(payload).hexdigest(),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
