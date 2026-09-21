#!/usr/bin/env python3
"""Run, publish, and verify Contract 12 V5 historical scorecard evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.forecast.final_historical_scorecard import (
    ScorecardError,
    render_report,
)
from cks_picks_cfb.forecast.final_scorecard_publication import (
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
        help="Validate 11D entry gate and compute full scorecard metrics (no writes).",
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

    # render-report: generate Markdown report
    rp = subparsers.add_parser(
        "render-report",
        help="Render Markdown readiness review report from evidence JSON.",
    )
    rp.add_argument(
        "--evidence-file",
        type=Path,
        required=True,
        help="Path to evidence or scorecard JSON.",
    )
    rp.add_argument("--run-id", required=True)
    rp.add_argument("--manifest-uri", required=True)
    rp.add_argument("--manifest-raw-sha256", required=True)
    rp.add_argument("--out", type=Path, help="Output markdown path")

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
        except ScorecardError as exc:
            progress.emit("preflight.error", error=str(exc))
            print(f"Preflight failed: {exc}", file=sys.stderr)
            return 1
        finally:
            progress.close()

        if args.out:
            args.out.write_text(json.dumps(result, indent=2, sort_keys=True))
            print(f"Evidence written to {args.out}")
        else:
            print(json.dumps(result, indent=2, sort_keys=True, default=str))
        return 0

    if args.command == "apply":
        if not _clean_worktree():
            print(
                "Apply requires a clean committed working tree. Commit changes first.",
                file=sys.stderr,
            )
            return 2

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
        except ScorecardPublicationError as exc:
            progress.emit("apply.error", error=str(exc))
            print(f"Apply failed: {exc}", file=sys.stderr)
            return 1
        finally:
            progress.close()

        print(json.dumps(result, indent=2, sort_keys=True, default=str))
        return 0

    if args.command == "render-report":
        data = _load_evidence(args.evidence_file)
        scorecard_data = data.get("scorecard", data)
        md = render_report(
            scorecard_data,
            run_id=args.run_id,
            manifest_uri=args.manifest_uri,
            manifest_raw_sha256=args.manifest_raw_sha256,
        )
        if args.out:
            args.out.write_text(md)
            print(f"Report written to {args.out}")
        else:
            print(md)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
