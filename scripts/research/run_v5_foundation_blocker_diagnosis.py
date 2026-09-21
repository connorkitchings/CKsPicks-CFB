#!/usr/bin/env python3
"""Run Contract 02 V5 Foundation-Blocker Diagnosis."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from cks_picks_cfb.audit.corpus import concat_all, read_any
from cks_picks_cfb.audit.foundation_blocker_diagnosis import (
    DiagnosisError,
    diagnose_excess_keys,
    render_diagnosis_report,
    validate_parents,
    verify_repair_independence_contract,
)
from cks_picks_cfb.data.storage import get_storage

ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = (
    ROOT / "docs" / "research" / "2026-09-21-v5-foundation-blocker-diagnosis-report.md"
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    # diagnose: run read-only diagnosis
    subparsers.add_parser(
        "diagnose",
        help="Reconstruct and classify all 81 excess keys (read-only).",
    )

    # report: render and write formal diagnosis report
    subparsers.add_parser(
        "report",
        help="Write diagnosis report to docs/research/.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = _parser().parse_args(argv)
    storage = get_storage(environment="preview")

    print("Step 1: Validating exact 10B/Repair/R6 parent bindings...")
    parents = validate_parents(storage)
    print("  Parents verified: 10B manifest, Repair v2, Measurement R6.")

    print("Step 2: Loading scoring events and repair population...")
    repair_pop = concat_all(
        read_any(storage, parents["repair_v2"]["output_refs"]["population"])
    )
    events = concat_all(
        read_any(storage, parents["measurement_r6"]["output_refs"]["scoring_events"])
    )
    print(f"  Loaded {len(repair_pop)} repair rows, {len(events)} scoring events.")

    print("Step 3: Diagnosing and classifying 81 excess keys...")
    diagnosis = diagnose_excess_keys(events, repair_pop)
    print(f"  Exact count: {diagnosis['total_keys']} keys.")
    print(f"  Keys SHA-256: {diagnosis['sha256']}")
    print("  Cause breakdown:")
    for cause, count in sorted(diagnosis["cause_counts"].items(), key=lambda x: -x[1]):
        print(f"    - {cause}: {count}")

    print("Step 4: Specifying independent Repair verification...")
    independence = verify_repair_independence_contract()
    print("  Independent Repair verifier architecture validated.")

    if args.command == "report":
        content = render_diagnosis_report(diagnosis, independence)
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(content)
        print(f"Diagnosis report written to {REPORT_PATH}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DiagnosisError as exc:
        print(f"Diagnosis failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
