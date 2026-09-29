#!/usr/bin/env python3
"""Validate and register exact successor authorizations on Preview only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess

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


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--week", type=int, choices=range(6), required=True)
    parser.add_argument("--decision-ref", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-record-sha")
    parser.add_argument("--expected-code-sha")
    parser.add_argument("--release-tag", default="20260929-p1")
    args = parser.parse_args()
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
    record_sha = hashlib.sha256(canonical_json(record)).hexdigest()
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
                bundle_sha = record["inference_bundle_sha256"]
                approval = (
                    f"preview-intended-update-{bundle_sha[:12]}",
                    record["model_id"],
                    bundle_sha,
                    2026,
                    5,
                    args.decision_ref,
                )
                cur.execute(
                    "INSERT INTO v5_model_bundle_approvals "
                    "(approval_id, model_id, inference_bundle_sha256, first_live_season, first_live_week, decision_ref) "
                    "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (approval_id) DO NOTHING",
                    approval,
                )
                cur.execute(
                    "SELECT approval_id, model_id, inference_bundle_sha256, first_live_season, first_live_week, decision_ref "
                    "FROM v5_model_bundle_approvals WHERE approval_id = %s",
                    (approval[0],),
                )
                if cur.fetchone() != approval:
                    raise ValueError(
                        "Preview model approval conflicts with reviewed pair"
                    )
                values = tuple(record[name] for name in AUTH_COLUMNS)
                cur.execute(
                    f"INSERT INTO v5_intended_update_release_authorizations ({', '.join(AUTH_COLUMNS)}) "
                    f"VALUES ({', '.join(['%s'] * len(AUTH_COLUMNS))}) "
                    "ON CONFLICT (authorization_id) DO NOTHING",
                    values,
                )
                cur.execute(
                    f"SELECT {', '.join(AUTH_COLUMNS)} FROM v5_intended_update_release_authorizations "
                    "WHERE authorization_id = %s",
                    (record["authorization_id"],),
                )
                if cur.fetchone() != values:
                    raise ValueError(
                        "Preview run authorization conflicts with reviewed record"
                    )
    print(
        json.dumps(
            {"run_id": run_id, "record_sha256": record_sha, "applied": args.apply},
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
