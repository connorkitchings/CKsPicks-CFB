#!/usr/bin/env python3
"""Run and publish Contract 12A conditional historical scorecard evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.forecast.historical_scorecard import ScorecardError
from cks_picks_cfb.forecast.scorecard_publication import (
    ScorecardPublicationError,
    _Progress,
    publish_scorecard,
    run_scorecard_preflight,
    verify_scorecard_publication,
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


def _load_evidence(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        raise ScorecardError("Reviewed evidence is unreadable") from exc
    if not isinstance(payload, dict):
        raise ScorecardError("Reviewed evidence must be a JSON object")
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    # preflight: dry-run, no writes
    pf = subparsers.add_parser(
        "preflight",
        help="Validate 11A entry gate and compute scorecard metrics (no writes).",
    )
    pf.add_argument("--run-id", required=True)
    pf.add_argument("--out", type=Path, help="Write evidence JSON to this path")

    # apply: evidence-bound publish to Preview R2
    ap = subparsers.add_parser(
        "apply",
        help="Publish scorecard to Preview R2 from reviewed evidence.",
    )
    ap.add_argument("--run-id", required=True)
    ap.add_argument(
        "--preflight-evidence",
        type=Path,
        required=True,
        help="Path to JSON output from the preflight step.",
    )

    # verify: independently re-read a published manifest
    vf = subparsers.add_parser(
        "verify",
        help="Independently re-read a published scorecard manifest.",
    )
    vf.add_argument("--manifest-uri", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = _parser().parse_args(argv)
    storage = get_storage(environment="preview")

    if args.command == "verify":
        result = verify_scorecard_publication(storage, manifest_uri=args.manifest_uri)
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
        return 0

    if args.command == "preflight":
        progress = _Progress(args.run_id)
        progress.start()
        try:
            result = run_scorecard_preflight(
                storage, run_id=args.run_id, progress=progress
            )
        finally:
            progress.close()
        out_str = json.dumps(result, indent=2, sort_keys=True, default=str)
        print(out_str)
        if getattr(args, "out", None):
            args.out.write_text(out_str)
        return 0

    if args.command == "apply":
        if not _clean_worktree():
            print("ERROR: apply requires a clean committed worktree", file=sys.stderr)
            return 1
        evidence = _load_evidence(args.preflight_evidence)
        progress = _Progress(args.run_id)
        progress.start()
        try:
            result = publish_scorecard(
                storage,
                run_id=args.run_id,
                reviewed_evidence=evidence,
                progress=progress,
            )
        finally:
            progress.close()
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
        return 0 if result.get("state") in ("applied", "already_applied") else 1

    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ScorecardError, ScorecardPublicationError) as exc:
        print(f"scorecard failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
