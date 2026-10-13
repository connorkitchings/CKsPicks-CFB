#!/usr/bin/env python3
"""Validate and register exact successor authorizations on Preview only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from cks_picks_cfb.artifacts import prediction_run_manifest_path
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ops.v5_intended_update_release import (
    AUTH_COLUMNS,
    validate_intended_update_release_record,
)
from cks_picks_cfb.ratings_lab.artifacts import canonical_json
from scripts.pipeline.package_v5_intended_update_runs import CONFIG


def authorization_record(manifest: dict, *, decision_ref: str) -> dict:
    """Bind one Preview authorization to every relevant immutable run hash."""
    if not decision_ref.strip():
        raise ValueError("Preview authorization needs a decision reference")
    return {
        "authorization_id": f"preview-{manifest['run_id']}-{manifest['artifact_sha256'][:12]}",
        "environment": "preview",
        "season": 2026,
        "week": int(manifest["week"]),
        "prediction_run_id": manifest["run_id"],
        "evidence_class": manifest["evidence_class"],
        "model_id": manifest["model_id"],
        "inference_bundle_sha256": manifest["inference_bundle_sha256"],
        "rating_manifest_sha256": manifest["v5_rating_replay_manifest_sha256"],
        "forecast_manifest_uri": manifest["v5_live_forecast_manifest_uri"],
        "forecast_manifest_sha256": manifest["v5_live_forecast_manifest_sha256"],
        "serving_manifest_uri": manifest["v5_intended_update_serving_manifest_uri"],
        "serving_manifest_sha256": manifest[
            "v5_intended_update_serving_manifest_sha256"
        ],
        "verifier_uri": manifest["v5_intended_update_verifier_uri"],
        "verifier_sha256": manifest["v5_intended_update_verifier_sha256"],
        "prediction_artifact_uri": manifest["artifact_uri"],
        "prediction_artifact_sha256": manifest["artifact_sha256"],
        "decision_ref": decision_ref,
    }


APPROVAL_COLUMNS = (
    "approval_id",
    "model_id",
    "inference_bundle_sha256",
    "first_live_season",
    "first_live_week",
    "decision_ref",
)


def register_authorization(
    cur,
    record: dict,
    *,
    approval_id: str,
    approval_bundle_sha256: str,
    approval_decision_ref: str,
) -> bool:
    """Match the reviewed B2 approval, then write the authorization once.

    Expected approval identity comes from the caller, never from the stored
    row. Returns whether a row was written; an identical retry writes nothing.
    """
    if record["environment"] != "preview":
        raise ValueError("Preview authorizer only writes Preview authorizations")
    if record["inference_bundle_sha256"] != approval_bundle_sha256:
        raise ValueError("run bundle differs from the reviewed approval bundle")
    cur.execute(
        f"SELECT {', '.join(APPROVAL_COLUMNS)} FROM v5_model_bundle_approvals "
        "WHERE approval_id = %s OR (model_id = %s AND inference_bundle_sha256 = %s) "
        "FOR SHARE",
        (approval_id, record["model_id"], approval_bundle_sha256),
    )
    rows = cur.fetchall()
    if len(rows) != 1:
        raise ValueError(
            f"expected exactly one reviewed Preview approval, found {len(rows)}"
        )
    stored = dict(zip(APPROVAL_COLUMNS, rows[0]))
    expected = {
        "approval_id": approval_id,
        "model_id": record["model_id"],
        "inference_bundle_sha256": approval_bundle_sha256,
        "first_live_season": record["season"],
        "decision_ref": approval_decision_ref,
    }
    mismatched = sorted(key for key, value in expected.items() if stored[key] != value)
    if mismatched:
        raise ValueError(
            f"Preview approval differs from reviewed identity: {', '.join(mismatched)}"
        )
    if stored["first_live_week"] > record["week"]:
        raise ValueError(
            f"Preview approval is live from week {stored['first_live_week']}, "
            f"after requested week {record['week']}"
        )

    values = tuple(record[name] for name in AUTH_COLUMNS)
    select_auth = (
        f"SELECT {', '.join(AUTH_COLUMNS)} FROM v5_intended_update_release_authorizations "
        "WHERE authorization_id = %s"
    )
    cur.execute(select_auth, (record["authorization_id"],))
    existing = cur.fetchone()
    if existing is not None:
        if existing != values:
            raise ValueError("Preview run authorization conflicts with reviewed record")
        return False
    cur.execute(
        f"INSERT INTO v5_intended_update_release_authorizations ({', '.join(AUTH_COLUMNS)}) "
        f"VALUES ({', '.join(['%s'] * len(AUTH_COLUMNS))}) "
        "ON CONFLICT (authorization_id) DO NOTHING",
        values,
    )
    cur.execute(select_auth, (record["authorization_id"],))
    if cur.fetchone() != values:
        raise ValueError("Preview run authorization conflicts with reviewed record")
    return True


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--week", type=int)
    parser.add_argument(
        "--decision-ref", help="decision reference written on the authorization"
    )
    parser.add_argument("--approval-id", help="reviewed B2 approval ID")
    parser.add_argument(
        "--approval-bundle-sha256", help="full reviewed B2 inference bundle sha256"
    )
    parser.add_argument(
        "--approval-decision-ref",
        help="decision reference stored on the reviewed B2 approval",
    )
    parser.add_argument("--packet", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--expected-packet-sha256")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-record-sha")
    parser.add_argument("--expected-code-sha")
    parser.add_argument("--release-tag", default="20260929-p1")
    args = parser.parse_args()
    if args.packet is not None:
        if not all((args.receipt, args.expected_packet_sha256, args.expected_code_sha)):
            parser.error(
                "packet mode requires --receipt, --expected-packet-sha256, and --expected-code-sha"
            )
        os.environ["CKS_V5_AUTHORIZER_FORCED_ENV"] = "preview"
        from scripts.pipeline.authorize_v5_intended_update_batch import (
            main as batch_main,
        )

        sys.argv = [
            sys.argv[0],
            "--environment",
            "preview",
            "--packet",
            str(args.packet),
            "--receipt",
            str(args.receipt),
            "--expected-packet-sha256",
            args.expected_packet_sha256,
            "--expected-code-sha",
            args.expected_code_sha,
        ]
        if args.apply:
            sys.argv.append("--apply")
        batch_main()
        return
    if not all(
        (
            args.week is not None,
            args.decision_ref,
            args.approval_id,
            args.approval_bundle_sha256,
            args.approval_decision_ref,
        )
    ):
        parser.error(
            "legacy single-run mode requires --week, --decision-ref, --approval-id, "
            "--approval-bundle-sha256 and --approval-decision-ref"
        )
    if not re.fullmatch(r"[0-9a-f]{64}", args.approval_bundle_sha256):
        parser.error("--approval-bundle-sha256 must be a full lowercase sha256")
    if args.week < 0:
        parser.error("--week must be a non-negative week")
    if not re.fullmatch(r"[a-z0-9-]+", args.release_tag):
        raise SystemExit("invalid successor release tag")
    if (
        os.getenv("CFB_STORAGE_BACKEND") != "r2"
        or os.getenv("CFB_ARTIFACT_ENV") != "preview"
    ):
        raise SystemExit("Preview authorization requires Preview R2 context")
    storage = get_storage(environment="preview")
    run_id = f"2026w{args.week}-v5repair-{args.release_tag}"
    manifest = json.loads(
        storage.read_bytes(prediction_run_manifest_path(2026, args.week, run_id))
    )
    if (
        manifest.get("run_id") != run_id
        or manifest.get("model_id") != "v5-intended-update-2026-v1"
        or manifest.get("source_config") != str(CONFIG)
        or manifest.get("config_sha") != hashlib.sha256(CONFIG.read_bytes()).hexdigest()
    ):
        raise ValueError(
            "Preview prediction manifest has another run, model, or config"
        )
    record = authorization_record(manifest, decision_ref=args.decision_ref)
    validate_intended_update_release_record(
        record,
        manifest=manifest,
        storage=storage,
        season=2026,
        week=args.week,
        environment="preview",
    )
    if record["inference_bundle_sha256"] != args.approval_bundle_sha256:
        raise SystemExit("Preview run bundle differs from the reviewed approval bundle")
    record_sha = hashlib.sha256(canonical_json(record)).hexdigest()
    written = False
    if args.apply:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain=v1"], text=True
        ).strip()
        if (
            dirty
            or head != args.expected_code_sha
            or record_sha != args.expected_record_sha
        ):
            raise SystemExit(
                "Preview authorization differs from committed reviewed record"
            )
        url = os.getenv("DATABASE_URL")
        if not url:
            raise SystemExit("Preview migrator DATABASE_URL is required")
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_user, session_user")
                if cur.fetchone() != ("cks_preview_migrator", "cks_preview_migrator"):
                    raise ValueError(
                        "Preview authorization requires exact migrator role"
                    )
                written = register_authorization(
                    cur,
                    record,
                    approval_id=args.approval_id,
                    approval_bundle_sha256=args.approval_bundle_sha256,
                    approval_decision_ref=args.approval_decision_ref,
                )
    print(
        json.dumps(
            {
                "run_id": run_id,
                "record_sha256": record_sha,
                "applied": args.apply,
                "written": written,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
