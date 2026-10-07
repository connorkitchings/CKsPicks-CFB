#!/usr/bin/env python3
"""User-run registration of exact packet-bound successor approvals."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import psycopg
from dotenv import load_dotenv

from cks_picks_cfb.artifacts import prediction_run_manifest_path
from cks_picks_cfb.data.data_first_phase2d import (
    Phase2dError,
    signed_payload,
    verify_signed_payload,
)
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ops.prospective_records import write_immutable
from cks_picks_cfb.ops.v5_intended_update_release import (
    AUTH_COLUMNS,
    validate_intended_update_release_record,
)
from cks_picks_cfb.ops.v5_revocations import lock_release_records
from cks_picks_cfb.ratings_lab.artifacts import canonical_json

AUTHORIZER_BY_ENV = {"preview": "cks_preview_migrator", "production": "neondb_owner"}
BUNDLE_COLUMNS = (
    "approval_id",
    "model_id",
    "inference_bundle_sha256",
    "first_live_season",
    "first_live_week",
    "decision_ref",
)


class AuthorizationPacketError(ValueError):
    """An authorization packet is unsigned, incomplete, or internally inconsistent."""


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def validate_packet(packet: dict[str, Any], *, environment: str) -> dict[str, Any]:
    if packet.get("schema_version") != "v5_intended_update_authorization_packet_v1":
        raise AuthorizationPacketError("unknown intended-update authorization packet")
    try:
        verify_signed_payload(packet, label="intended-update authorization packet")
    except Phase2dError as exc:
        raise AuthorizationPacketError(str(exc)) from exc
    if packet.get("environment") != environment or packet.get("season") != 2026:
        raise AuthorizationPacketError("packet environment or season differs")
    cutover = packet.get("cutover_week")
    decision_ref = str(packet.get("decision_ref") or "")
    if not isinstance(cutover, int) or cutover < 5 or not decision_ref.strip():
        raise AuthorizationPacketError(
            "packet cutover week or decision reference is invalid"
        )

    bundle = packet.get("bundle_approval")
    if not isinstance(bundle, dict):
        raise AuthorizationPacketError("packet bundle approval is missing")
    bundle_body = {key: bundle.get(key) for key in BUNDLE_COLUMNS}
    if not all(
        str(bundle_body.get(key) or "").strip()
        for key in (
            "approval_id",
            "model_id",
            "inference_bundle_sha256",
            "decision_ref",
        )
    ):
        raise AuthorizationPacketError("bundle approval fields are incomplete")
    if (
        bundle_body["first_live_season"] != 2026
        or bundle_body["first_live_week"] != cutover
        or bundle_body["decision_ref"] != decision_ref
        or bundle.get("record_sha256") != _sha(canonical_json(bundle_body))
    ):
        raise AuthorizationPacketError(
            "bundle approval hash or cutover binding differs"
        )

    records = packet.get("run_authorizations")
    if not isinstance(records, list) or not records:
        raise AuthorizationPacketError("packet run authorizations are missing")
    by_week: dict[int, dict[str, Any]] = {}
    for item in records:
        if not isinstance(item, dict):
            raise AuthorizationPacketError("run authorization is not an object")
        record = {key: item.get(key) for key in AUTH_COLUMNS}
        week = record.get("week")
        if not isinstance(week, int) or week in by_week:
            raise AuthorizationPacketError(
                "run authorization weeks are duplicate or invalid"
            )
        if (
            record.get("environment") != environment
            or record.get("season") != 2026
            or record.get("model_id") != bundle_body["model_id"]
            or record.get("inference_bundle_sha256")
            != bundle_body["inference_bundle_sha256"]
            or record.get("decision_ref") != decision_ref
            or item.get("record_sha256") != _sha(canonical_json(record))
        ):
            raise AuthorizationPacketError(
                "run authorization identity or canonical hash differs"
            )
        by_week[week] = record
    if sorted(by_week) != list(range(cutover + 1)):
        raise AuthorizationPacketError(
            "run authorizations must cover contiguous Weeks 0 through N"
        )
    for week, record in by_week.items():
        expected_class = "pending" if week == cutover else "replay"
        if record.get("evidence_class") != expected_class:
            raise AuthorizationPacketError(
                "run authorization timing class differs from cutover"
            )
    return {"bundle": bundle_body, "records": by_week, "cutover_week": cutover}


def _verify_packet_artifacts(
    packet: dict[str, Any], *, environment: str, storage: Any
) -> dict[str, Any]:
    validated = validate_packet(packet, environment=environment)
    for week, record in validated["records"].items():
        manifest = json.loads(
            storage.read_bytes(
                prediction_run_manifest_path(2026, week, record["prediction_run_id"])
            )
        )
        validate_intended_update_release_record(
            record,
            manifest=manifest,
            storage=storage,
            season=2026,
            week=week,
            environment=environment,
        )
    return validated


def _assert_identity(cur: Any, environment: str) -> None:
    expected = AUTHORIZER_BY_ENV[environment]
    cur.execute("SELECT session_user, current_user")
    if cur.fetchone() != (expected, expected):
        raise AuthorizationPacketError(
            f"authorization requires exact {environment} identity {expected}"
        )


def apply_packet(
    cur: Any,
    packet: dict[str, Any],
    *,
    environment: str,
) -> None:
    validated = validate_packet(packet, environment=environment)
    lock_release_records(
        cur,
        [("bundle_approval", validated["bundle"]["approval_id"])]
        + [
            ("intended_update_authorization", item["authorization_id"])
            for item in validated["records"].values()
        ],
        exclusive=True,
    )
    bundle = validated["bundle"]
    cur.execute(
        "INSERT INTO v5_model_bundle_approvals (" + ", ".join(BUNDLE_COLUMNS) + ") "
        "VALUES (" + ", ".join(["%s"] * len(BUNDLE_COLUMNS)) + ") "
        "ON CONFLICT (approval_id) DO NOTHING",
        tuple(bundle[key] for key in BUNDLE_COLUMNS),
    )
    cur.execute(
        "SELECT "
        + ", ".join(BUNDLE_COLUMNS)
        + " FROM v5_model_bundle_approvals WHERE approval_id = %s",
        (bundle["approval_id"],),
    )
    if cur.fetchone() != tuple(bundle[key] for key in BUNDLE_COLUMNS):
        raise AuthorizationPacketError(
            "bundle approval ID conflicts with retained record"
        )

    for week in sorted(validated["records"]):
        record = validated["records"][week]
        cur.execute(
            "INSERT INTO v5_intended_update_release_authorizations ("
            + ", ".join(AUTH_COLUMNS)
            + ") "
            "VALUES (" + ", ".join(["%s"] * len(AUTH_COLUMNS)) + ") "
            "ON CONFLICT (authorization_id) DO NOTHING",
            tuple(record[key] for key in AUTH_COLUMNS),
        )
        cur.execute(
            "SELECT "
            + ", ".join(AUTH_COLUMNS)
            + " FROM v5_intended_update_release_authorizations WHERE authorization_id = %s",
            (record["authorization_id"],),
        )
        if cur.fetchone() != tuple(record[key] for key in AUTH_COLUMNS):
            raise AuthorizationPacketError(
                f"run authorization for Week {week} conflicts with retained record"
            )


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--environment", choices=tuple(AUTHORIZER_BY_ENV), required=True
    )
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--expected-packet-sha256", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    forced_environment = os.getenv("CKS_V5_AUTHORIZER_FORCED_ENV")
    if forced_environment and args.environment != forced_environment:
        raise SystemExit(
            "authorization entrypoint is restricted to its named environment"
        )
    if os.getenv("CFB_ARTIFACT_ENV") != args.environment:
        raise SystemExit(
            "authorization environment does not match active operator context"
        )
    if os.getenv("CFB_STORAGE_BACKEND") != "r2":
        raise SystemExit("packet authorization requires the immutable R2 backend")
    packet_raw = args.packet.read_bytes()
    if _sha(packet_raw) != args.expected_packet_sha256:
        raise SystemExit("authorization packet raw-byte checksum differs")
    packet = json.loads(packet_raw)
    storage = get_storage(environment=args.environment)
    validated = _verify_packet_artifacts(
        packet, environment=args.environment, storage=storage
    )
    record_hashes = {
        "bundle_approval": _sha(canonical_json(validated["bundle"])),
        "run_authorizations": {
            str(week): _sha(canonical_json(record))
            for week, record in validated["records"].items()
        },
    }
    if not args.apply:
        print(
            json.dumps(
                {"state": "validated", "record_hashes": record_hashes}, sort_keys=True
            )
        )
        return

    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain=v1"], text=True
    ).strip()
    if dirty or head != args.expected_code_sha:
        raise SystemExit("authorization requires reviewed clean committed code")
    url = os.getenv("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is required for user-run authorization")
    receipt_payload = signed_payload(
        {
            "schema_version": "v5_intended_update_authorization_receipt_v1",
            "state": "registered",
            "environment": args.environment,
            "code_sha": head,
            "packet_sha256": args.expected_packet_sha256,
            "decision_ref": packet["decision_ref"],
            "record_hashes": record_hashes,
        }
    )
    created_receipt = False
    receipt_uri = (
        f"artifacts/authorizations/v5/{args.environment}/"
        f"{args.expected_packet_sha256}.json"
    )
    receipt_raw = canonical_json(receipt_payload)
    try:
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                _assert_identity(cur, args.environment)
                apply_packet(cur, packet, environment=args.environment)
                write_immutable(storage, receipt_uri, receipt_raw)
                args.receipt.parent.mkdir(parents=True, exist_ok=True)
                if args.receipt.exists():
                    if args.receipt.read_bytes() != receipt_raw:
                        raise AuthorizationPacketError(
                            "authorization receipt path contains conflicting bytes"
                        )
                else:
                    with args.receipt.open("xb") as handle:
                        handle.write(receipt_raw)
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
                "state": "registered",
                "record_hashes": record_hashes,
                "receipt_uri": receipt_uri,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
