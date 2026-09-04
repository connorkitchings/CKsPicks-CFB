#!/usr/bin/env python3
"""Idempotently persist frozen Silver market quotes into Neon Postgres.

Catalog mode discovers every validated ``market_quotes`` dataset version
(optionally filtered by season); explicit ref mode replays exact pipeline-run
refs. Rows are written with ``INSERT ... ON CONFLICT DO NOTHING`` so reruns are
no-ops and no frozen artifact is ever modified. Snapshot-quote links are
reconciled from each stored snapshot's ``source_quote_ids``.

Requires DATABASE_URL (and R2 credentials for catalog/ref reads).

Usage:
    PYTHONPATH=.:src uv run python scripts/pipeline/backfill_market_quotes_db.py \\
        --season 2026 --dry-run
    PYTHONPATH=.:src uv run python scripts/pipeline/backfill_market_quotes_db.py \\
        --from-quotes-ref artifacts/production/pipeline-runs/<run>/market_quotes_ref.json \\
        --from-snapshots-ref artifacts/production/pipeline-runs/<run>/market_snapshots_ref.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd
import psycopg
from dotenv import load_dotenv

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from publish_to_db import (  # noqa: E402
    INSERT_MARKET_QUOTE_SQL,
    INSERT_MARKET_SNAPSHOT_QUOTE_SQL,
    _quote_frame_to_records,
    _quote_link_targets,
)

from cks_picks_cfb.data.lake import DatasetRef, read_dataset  # noqa: E402
from cks_picks_cfb.data.storage import get_storage  # noqa: E402

# Retro-specific: repairs the lineage columns of already-inserted snapshot
# rows (older publishes dropped source_quote_ids/captured_at/rules before the
# inference merge was fixed). Identity columns are never rewritten.
UPSERT_MARKET_SNAPSHOT_LINEAGE_SQL = """
INSERT INTO market_snapshots (
    snapshot_id, game_id, captured_at, spread, total,
    spread_rule, total_rule, spread_provider_count, total_provider_count,
    source_quote_ids, policy_version
) VALUES (
    %(market_snapshot_id)s, %(game_id)s, %(market_captured_at)s,
    %(home_team_spread_line)s, %(total_line)s, %(spread_selection_rule)s,
    %(total_selection_rule)s, %(spread_provider_count)s,
    %(total_provider_count)s, %(source_quote_ids)s::jsonb,
    %(market_policy_version)s
)
ON CONFLICT (snapshot_id) DO UPDATE SET
    captured_at = EXCLUDED.captured_at,
    spread_rule = EXCLUDED.spread_rule,
    total_rule = EXCLUDED.total_rule,
    spread_provider_count = EXCLUDED.spread_provider_count,
    total_provider_count = EXCLUDED.total_provider_count,
    source_quote_ids = EXCLUDED.source_quote_ids
"""


def _ref_from_payload(payload: dict) -> DatasetRef:
    return DatasetRef(
        dataset=str(payload["dataset"]),
        version_id=str(payload["version_id"]),
        schema_version=str(payload["schema_version"]),
        content_sha=str(payload["content_sha"]),
        uri=str(payload["uri"]),
    )


def _load_ref_uri(storage, uri: str) -> DatasetRef:
    payload = json.loads(storage.read_bytes(uri).decode("utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"Malformed dataset ref: {uri}")
    return _ref_from_payload(payload)


def _catalog_quote_refs(conn_url: str, season: int | None) -> list[DatasetRef]:
    query = (
        "SELECT version_id, schema_version, content_sha, uri "
        "FROM catalog.dataset_versions "
        "WHERE dataset = 'market_quotes' AND state = 'validated'"
    )
    params: list[str] = []
    if season is not None:
        query += " AND partitions @> %s::jsonb"
        params.append(json.dumps({"seasons": [season]}))
    query += " ORDER BY as_of, created_at"
    with psycopg.connect(conn_url) as conn:
        rows = conn.execute(query, params).fetchall()
    return [
        DatasetRef("market_quotes", str(row[0]), str(row[1]), str(row[2]), str(row[3]))
        for row in rows
    ]


def _load_quote_records(refs: list[DatasetRef]) -> list[dict]:
    storage = get_storage()
    frames = [read_dataset(storage, ref) for ref in refs]
    if not frames:
        return []
    quotes = pd.concat(frames, ignore_index=True)
    quotes = quotes.drop_duplicates(subset=["quote_id"], keep="first")
    return _quote_frame_to_records(quotes)


def _snapshot_records_from_frame(frame: pd.DataFrame) -> list[dict]:
    records = []
    for _, row in frame.iterrows():
        captured_at = pd.to_datetime(
            row.get("market_captured_at"), utc=True, errors="coerce"
        )
        if pd.isna(captured_at):
            raise ValueError(
                "Snapshot "
                f"{row.get('market_snapshot_id')} has no authentic captured_at; "
                "refusing to backfill with a fabricated timestamp"
            )
        source_quote_ids = row.get("source_quote_ids", "[]")
        if isinstance(source_quote_ids, str):
            source_quote_ids = json.loads(source_quote_ids)
        records.append(
            {
                "market_snapshot_id": str(row["market_snapshot_id"]),
                "game_id": int(row["game_id"]),
                "market_captured_at": captured_at.to_pydatetime(),
                "home_team_spread_line": _optional_float(row.get("spread_line")),
                "total_line": _optional_float(row.get("total_line")),
                "spread_selection_rule": row.get("spread_selection_rule"),
                "total_selection_rule": row.get("total_selection_rule"),
                "spread_provider_count": int(row.get("spread_provider_count") or 0),
                "total_provider_count": int(row.get("total_provider_count") or 0),
                "source_quote_ids": json.dumps(source_quote_ids),
                "market_policy_version": str(
                    row.get("market_policy_version") or "consensus_then_median_v1"
                ),
            }
        )
    return records


def _optional_float(value) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(result) else result


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--from-quotes-ref",
        action="append",
        default=None,
        help="Explicit durable market_quotes ref JSON URI (repeatable).",
    )
    parser.add_argument(
        "--from-snapshots-ref",
        action="append",
        default=None,
        help="Explicit durable market_snapshots ref JSON URI (repeatable).",
    )
    parser.add_argument(
        "--season",
        type=int,
        default=None,
        help="Catalog-mode season filter (used when --from-quotes-ref is absent).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be written without touching the database.",
    )
    args = parser.parse_args()

    conn_url = os.getenv("DATABASE_URL")
    if not conn_url:
        raise SystemExit("DATABASE_URL is not set")

    storage = get_storage()
    if args.from_quotes_ref:
        quote_refs = [_load_ref_uri(storage, uri) for uri in args.from_quotes_ref]
    else:
        quote_refs = _catalog_quote_refs(conn_url, args.season)
    if not quote_refs:
        raise SystemExit("No market_quotes dataset versions resolved")

    quote_records = _load_quote_records(quote_refs)
    print(f"Resolved {len(quote_refs)} market_quotes versions")
    print(f"Loaded {len(quote_records)} unique quote rows")

    snapshot_records: list[dict] = []
    if args.from_snapshots_ref:
        snapshot_frames = [
            read_dataset(storage, _load_ref_uri(storage, uri))
            for uri in args.from_snapshots_ref
        ]
        if snapshot_frames:
            snapshots = pd.concat(snapshot_frames, ignore_index=True)
            snapshots = snapshots.drop_duplicates(
                subset=["market_snapshot_id"], keep="first"
            )
            snapshot_records = _snapshot_records_from_frame(snapshots)
        print(f"Loaded {len(snapshot_records)} snapshot rows")

    if args.dry_run:
        print("Dry run: no database writes performed")
        return

    quote_by_id = {record["quote_id"]: record for record in quote_records}
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT game_id FROM games")
            known_game_ids = {int(row[0]) for row in cur.fetchall()}
            cur.execute("SELECT snapshot_id FROM market_snapshots")
            existing_snapshot_ids = {str(row[0]) for row in cur.fetchall()}
            insertable = [q for q in quote_records if q["game_id"] in known_game_ids]
            skipped = len(quote_records) - len(insertable)
            if skipped:
                print(
                    f"Skipping {skipped} quotes whose game_id is not yet in "
                    "the games table (they remain durable in R2)"
                )
            for record in insertable:
                cur.execute(INSERT_MARKET_QUOTE_SQL, record)
            repairable_snapshots = [
                s
                for s in snapshot_records
                if s["game_id"] in known_game_ids
                or s["market_snapshot_id"] in existing_snapshot_ids
            ]
            skipped_snapshots = len(snapshot_records) - len(repairable_snapshots)
            if skipped_snapshots:
                print(
                    f"Skipping {skipped_snapshots} snapshots whose game_id is "
                    "not in the games table and which have no existing row to "
                    "repair (they remain durable in R2)"
                )
            for record in repairable_snapshots:
                cur.execute(UPSERT_MARKET_SNAPSHOT_LINEAGE_SQL, record)

            cur.execute("SELECT snapshot_id, source_quote_ids FROM market_snapshots")
            link_count = 0
            for snapshot_id, source_ids in cur.fetchall():
                ids = source_ids if isinstance(source_ids, list) else []
                for quote_id in ids:
                    quote = quote_by_id.get(str(quote_id))
                    if quote is None:
                        continue
                    for target in _quote_link_targets(quote):
                        cur.execute(
                            INSERT_MARKET_SNAPSHOT_QUOTE_SQL,
                            {
                                "snapshot_id": snapshot_id,
                                "quote_id": quote["quote_id"],
                                "target": target,
                            },
                        )
                        link_count += 1
        conn.commit()
    print(
        f"Persisted {len(insertable)} quote rows, "
        f"{len(repairable_snapshots)} snapshots, reconciled {link_count} quote links"
    )


if __name__ == "__main__":
    main()
