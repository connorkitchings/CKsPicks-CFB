#!/usr/bin/env python3
"""User-run append-only revocation of one exact V5 release record."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ops.prospective_records import write_immutable
from cks_picks_cfb.ops.v5_revocations import append_release_revocation
from cks_picks_cfb.ratings_lab.artifacts import canonical_json

AUTHORIZER_BY_ENV = {
    "preview": "cks_preview_migrator",
    "production": "neondb_owner",
}


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--environment", choices=tuple(AUTHORIZER_BY_ENV), required=True
    )
    parser.add_argument(
        "--record-type",
        choices=("bundle_approval", "intended_update_authorization"),
        required=True,
    )
    parser.add_argument("--record-id", required=True)
    parser.add_argument("--decision-ref", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if os.getenv("CFB_ARTIFACT_ENV") != args.environment:
        raise SystemExit(
            "revocation environment does not match the active operator context"
        )
    if os.getenv("CFB_STORAGE_BACKEND") != "r2":
        raise SystemExit("V5 revocation receipts require immutable R2 storage")
    if not args.record_id.strip() or not args.decision_ref.strip():
        raise SystemExit("exact record ID and decision reference are required")
    if not args.apply:
        print(json.dumps({"state": "validated", "environment": args.environment}))
        return

    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain=v1"], text=True
    ).strip()
    if dirty or head != args.expected_code_sha:
        raise SystemExit("revocation requires the reviewed clean committed code SHA")
    url = os.getenv("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is required for the user-run revocation")
    storage = get_storage(environment=args.environment)

    created_receipt = False
    try:
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT session_user, current_user")
                identity = cur.fetchone()
                expected = AUTHORIZER_BY_ENV[args.environment]
                if identity != (expected, expected):
                    raise SystemExit(
                        f"revocation requires exact {args.environment} authorizer identity"
                    )
                record = append_release_revocation(
                    cur,
                    record_type=args.record_type,
                    record_id=args.record_id,
                    decision_ref=args.decision_ref,
                )
                record_hash = hashlib.sha256(canonical_json(record)).hexdigest()
                receipt = signed_payload(
                    {
                        "schema_version": "v5_release_revocation_receipt_v1",
                        "state": "recorded",
                        "environment": args.environment,
                        "code_sha": head,
                        "decision_ref": args.decision_ref,
                        "record_sha256": record_hash,
                        "record": record,
                    }
                )
                raw = canonical_json(receipt)
                receipt_uri = (
                    f"artifacts/authorizations/v5/{args.environment}/revocations/"
                    f"{args.record_type}-{args.record_id}-{record_hash}.json"
                )
                write_immutable(storage, receipt_uri, raw)
                args.receipt.parent.mkdir(parents=True, exist_ok=True)
                if args.receipt.exists():
                    if args.receipt.read_bytes() != raw:
                        raise SystemExit("receipt path contains conflicting bytes")
                else:
                    with args.receipt.open("xb") as handle:
                        handle.write(raw)
                        handle.flush()
                        os.fsync(handle.fileno())
                    created_receipt = True
            conn.commit()
    except Exception:
        if created_receipt:
            args.receipt.unlink(missing_ok=True)
        raise
    print(
        json.dumps(
            {
                "state": "recorded",
                "environment": args.environment,
                "record_id": args.record_id,
                "record_sha256": record_hash,
                "receipt": str(args.receipt),
                "receipt_uri": receipt_uri,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
