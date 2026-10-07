#!/usr/bin/env python3
"""Freeze the active prediction run after coverage validation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import timedelta

from dotenv import load_dotenv

from cks_picks_cfb.ops.lease import assert_active_pipeline_lease

try:
    import psycopg
except ImportError as exc:  # pragma: no cover
    raise SystemExit("psycopg not installed; run uv sync") from exc


def freeze_run(
    conn_url: str,
    *,
    year: int,
    week: int,
    waiver: str | None = None,
    decision_ref: str | None = None,
) -> dict:
    """Freeze the active run transactionally and return its metadata."""
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            assert_active_pipeline_lease(cur)
            cur.execute("SELECT pg_advisory_xact_lock(%s, %s)", (year, week))
            cur.execute(
                """SELECT pr.run_id, pr.state, pr.expected_games,
                       pr.predicted_games, pr.lined_games, pr.artifact_uri,
                       pr.artifact_sha256, pr.evidence_class, pr.model_id,
                       pr.model_bundle_sha256,
                       (SELECT MIN(g.start_date) FROM predictions p
                        JOIN games g ON g.game_id = p.game_id
                        WHERE p.run_id = pr.run_id), NOW()
                FROM current_week cw
                JOIN prediction_runs pr ON pr.run_id = cw.active_run_id
                WHERE cw.id = 1 AND cw.season = %s AND cw.week = %s
                FOR UPDATE
                """,
                (year, week),
            )
            row = cur.fetchone()
            if not row:
                raise RuntimeError(f"No active prediction run for {year} week {week}")
            (
                run_id,
                state,
                expected,
                predicted,
                lined,
                artifact_uri,
                artifact_sha,
                evidence_class,
                model_id,
                bundle_sha256,
                first_kickoff,
                db_now,
            ) = row
            freeze_manifest = None
            needs_decision_ref = False
            if str(model_id or "").startswith("v5-"):
                from cks_picks_cfb.ops.v5_freeze_guard import (
                    require_v5_freeze_authorization,
                )

                freeze_manifest = require_v5_freeze_authorization(
                    cur,
                    run_id=str(run_id),
                    season=year,
                    week=week,
                    model_id=str(model_id),
                    bundle_sha256=bundle_sha256,
                    artifact_uri=artifact_uri,
                    artifact_sha256=artifact_sha,
                    evidence_class=str(evidence_class),
                    environment=os.getenv("CFB_ARTIFACT_ENV", "production"),
                )
                needs_decision_ref = (
                    year == 2026 and week >= 5 and state not in {"frozen", "scored"}
                )
            if state in {"frozen", "scored"}:
                return {
                    "run_id": run_id,
                    "state": state,
                    "expected_games": expected,
                    "predicted_games": predicted,
                    "lined_games": lined,
                    "artifact_uri": artifact_uri,
                    "artifact_sha256": artifact_sha,
                }
            if evidence_class == "replay":
                raise RuntimeError("Reconstructed replay cannot receive a live freeze")
            if evidence_class == "missed":
                return {
                    "run_id": run_id,
                    "state": "missed",
                    "reason": "freeze deadline passed",
                }
            if evidence_class == "pending":
                if first_kickoff is None:
                    raise RuntimeError("V5 run has no scheduled kickoff")
                if db_now >= first_kickoff - timedelta(hours=1):
                    cur.execute(
                        "UPDATE prediction_runs SET evidence_class = 'missed', "
                        "validation = validation || %s::jsonb WHERE run_id = %s",
                        (
                            json.dumps(
                                {"freeze_missed": "one-hour hard boundary passed"}
                            ),
                            run_id,
                        ),
                    )
                    conn.commit()
                    return {
                        "run_id": run_id,
                        "state": "missed",
                        "reason": "freeze deadline passed",
                    }
            # Checked after the deadline branches so a run past its one-hour
            # boundary is recorded as missed rather than failing on the ref.
            if needs_decision_ref and (not decision_ref or not decision_ref.strip()):
                raise RuntimeError(
                    "a decision reference is required to retain a prospective V5 freeze"
                )
            if predicted != expected:
                raise RuntimeError(
                    f"Cannot freeze {run_id}: predicted {predicted}/{expected} games"
                )
            if lined != expected and not waiver:
                raise RuntimeError(
                    f"Cannot freeze {run_id}: lines cover {lined}/{expected} games; "
                    "pass --waiver with a recorded reason to override"
                )
            validation_patch = json.dumps(
                {"freeze_waiver": waiver}
                if waiver
                else {"freeze_coverage_complete": True}
            )
            cur.execute(
                """
                UPDATE prediction_runs
                SET state = 'frozen', frozen_at = NOW(),
                    evidence_class = CASE WHEN evidence_class = 'pending' THEN 'live' ELSE evidence_class END,
                    validation = validation || %s::jsonb
                WHERE run_id = %s
                RETURNING frozen_at
                """,
                (validation_patch, run_id),
            )
            frozen_at = cur.fetchone()[0]
            if waiver:
                cur.execute(
                    "INSERT INTO ops.waivers (run_id, waiver_type, reason) "
                    "VALUES (%s, 'line_coverage', %s)",
                    (run_id, waiver),
                )
            cur.execute(
                "INSERT INTO ops.activation_history "
                "(environment, season, week, run_id, action, metadata) "
                "VALUES (%s, %s, %s, %s, 'freeze', %s::jsonb) "
                "ON CONFLICT (run_id, action) DO NOTHING",
                (
                    os.getenv("CFB_ARTIFACT_ENV", "production"),
                    year,
                    week,
                    run_id,
                    validation_patch,
                ),
            )
            prospective_record = None
            if (
                freeze_manifest is not None
                and year == 2026
                and week >= 5
                and str(evidence_class) == "pending"
            ):
                from cks_picks_cfb.artifacts import (
                    prediction_run_manifest_path,
                )
                from cks_picks_cfb.data.storage import get_storage
                from cks_picks_cfb.ops.prospective_records import (
                    register_prospective_freeze,
                )

                storage = get_storage(
                    environment=os.getenv("CFB_ARTIFACT_ENV", "production")
                )
                manifest_uri = prediction_run_manifest_path(year, week, str(run_id))
                manifest_raw = storage.read_bytes(manifest_uri)
                prospective_record = register_prospective_freeze(
                    cur,
                    storage=storage,
                    environment=os.getenv("CFB_ARTIFACT_ENV", "production"),
                    season=year,
                    week=week,
                    run_id=str(run_id),
                    model_id=str(model_id),
                    bundle_sha256=str(bundle_sha256),
                    prediction_artifact_uri=str(artifact_uri),
                    prediction_artifact_sha256=str(artifact_sha),
                    manifest_uri=manifest_uri,
                    manifest_sha256=hashlib.sha256(manifest_raw).hexdigest(),
                    frozen_at=frozen_at,
                    first_kickoff_utc=first_kickoff,
                    decision_ref=str(decision_ref),
                    code_sha=subprocess.check_output(
                        ["git", "rev-parse", "HEAD"], text=True
                    ).strip(),
                )
            conn.commit()
    return {
        "run_id": run_id,
        "state": "frozen",
        "expected_games": expected,
        "predicted_games": predicted,
        "lined_games": lined,
        "artifact_uri": artifact_uri,
        "artifact_sha256": artifact_sha,
        "frozen_at": frozen_at.isoformat(),
        "waiver": waiver,
        "prospective_receipt": prospective_record,
    }


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--waiver", default=None)
    parser.add_argument("--decision-ref", default=None)
    args = parser.parse_args()

    conn_url = os.getenv("DATABASE_URL")
    if not conn_url:
        raise SystemExit("DATABASE_URL is not set")
    metadata = freeze_run(
        conn_url,
        year=args.year,
        week=args.week,
        waiver=args.waiver,
        decision_ref=args.decision_ref,
    )
    if metadata["state"] == "missed":
        raise SystemExit(
            f"Missed freeze boundary for {metadata['run_id']} in {args.year} week {args.week}"
        )
    print(f"Frozen {metadata['run_id']} for {args.year} week {args.week}")


if __name__ == "__main__":
    main()
