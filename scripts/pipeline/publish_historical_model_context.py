#!/usr/bin/env python3
"""Publish verified diagnostic-only historical aggregates to Neon."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone

import psycopg
from dotenv import load_dotenv

from cks_picks_cfb.data.runtime import resolve_runtime_target
from cks_picks_cfb.data.storage import get_storage


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _context_id(row: dict[str, object]) -> str:
    identity = {
        key: row[key]
        for key in (
            "model_id",
            "comparison_season",
            "period_scope",
            "comparison_week",
            "calculation_version",
        )
    }
    return (
        "hmc_"
        + _sha(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode())[
            :24
        ]
    )


def validate(rows: list[dict[str, object]], audit: dict[str, object]) -> None:
    if not audit.get("all_checks_passed"):
        raise ValueError("Historical context audit did not pass")
    if len(rows) != 16:
        raise ValueError(
            "Historical context requires one season and fifteen weekly rows"
        )
    if sum(row.get("period_scope") == "season" for row in rows) != 1:
        raise ValueError("Historical context requires exactly one season row")
    weeks = {
        row.get("comparison_week") for row in rows if row.get("period_scope") == "week"
    }
    if weeks != set(range(1, 16)):
        raise ValueError("Historical context requires exactly Weeks 1-15")
    for row in rows:
        for target in ("spread", "total"):
            if int(row[f"{target}_wins"]) + int(row[f"{target}_losses"]) + int(
                row[f"{target}_pushes"]
            ) != int(row[f"{target}_compared_games"]):
                raise ValueError(f"Invalid {target} aggregate")


UPSERT = """
INSERT INTO historical_model_context (
  context_id, model_id, model_name, comparison_season, period_scope, comparison_week,
  calculation_version, timing_class, usage,
  spread_wins, spread_losses, spread_pushes, spread_compared_games,
  total_wins, total_losses, total_pushes, total_compared_games,
  source_artifact_uri, source_artifact_sha256, created_at, updated_at
) VALUES (
  %(context_id)s, %(model_id)s, %(model_name)s, %(comparison_season)s, %(period_scope)s, %(comparison_week)s,
  %(calculation_version)s, 'historically_reconstructed', 'post_phase5_diagnostic_only',
  %(spread_wins)s, %(spread_losses)s, %(spread_pushes)s, %(spread_compared_games)s,
  %(total_wins)s, %(total_losses)s, %(total_pushes)s, %(total_compared_games)s,
  %(source_artifact_uri)s, %(source_artifact_sha256)s, NOW(), NOW()
)
ON CONFLICT (context_id) DO UPDATE SET
  source_artifact_uri = EXCLUDED.source_artifact_uri,
  source_artifact_sha256 = EXCLUDED.source_artifact_sha256,
  updated_at = NOW()
"""


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--environment", choices=("preview", "production"), required=True
    )
    parser.add_argument("--aggregates-uri", required=True)
    parser.add_argument("--audit-uri", required=True)
    parser.add_argument("--source-artifact-uri", required=True)
    parser.add_argument("--source-artifact-sha256", required=True)
    args = parser.parse_args()
    if len(args.source_artifact_sha256) != 64:
        raise ValueError("Source artifact SHA must be SHA-256")
    storage = get_storage(environment=args.environment)
    aggregate_payload = storage.read_bytes(args.aggregates_uri)
    rows = json.loads(aggregate_payload)
    audit = json.loads(storage.read_bytes(args.audit_uri))
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("Aggregate payload must be a list of rows")
    validate(rows, audit)
    records = []
    for raw in rows:
        row = dict(raw)
        row.update(
            {
                "context_id": _context_id(row),
                "model_name": "V4 2026 Production Design",
                "source_artifact_uri": args.source_artifact_uri,
                "source_artifact_sha256": args.source_artifact_sha256,
            }
        )
        records.append(row)
    with psycopg.connect(resolve_runtime_target(args.environment).database_url) as conn:
        with conn.cursor() as cur:
            for record in records:
                cur.execute(UPSERT, record)
        conn.commit()
    print(
        json.dumps(
            {
                "status": "published",
                "row_count": len(records),
                "published_at": datetime.now(timezone.utc).isoformat(),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
