#!/usr/bin/env python3
"""Freeze the active prediction run after coverage validation."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone

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
) -> dict:
    """Freeze the active run transactionally and return its metadata."""
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            assert_active_pipeline_lease(cur)
            cur.execute(
                """
                SELECT pr.run_id, pr.state, pr.expected_games,
                       pr.predicted_games, pr.lined_games, pr.artifact_uri,
                       pr.artifact_sha256
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
            run_id, state, expected, predicted, lined, artifact_uri, artifact_sha = row
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
                    validation = validation || %s::jsonb
                WHERE run_id = %s
                """,
                (validation_patch, run_id),
            )
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
            conn.commit()
    return {
        "run_id": run_id,
        "state": "frozen",
        "expected_games": expected,
        "predicted_games": predicted,
        "lined_games": lined,
        "artifact_uri": artifact_uri,
        "artifact_sha256": artifact_sha,
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "waiver": waiver,
    }


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--waiver", default=None)
    args = parser.parse_args()

    conn_url = os.getenv("DATABASE_URL")
    if not conn_url:
        raise SystemExit("DATABASE_URL is not set")
    metadata = freeze_run(conn_url, year=args.year, week=args.week, waiver=args.waiver)
    print(f"Frozen {metadata['run_id']} for {args.year} week {args.week}")


if __name__ == "__main__":
    main()
