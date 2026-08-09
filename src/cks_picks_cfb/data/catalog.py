"""Neon catalog registration for immutable R2 objects."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Mapping

import psycopg

from cks_picks_cfb.data.lake import DatasetManifest, DatasetRef, SourceCapture


def begin_ingestion_run(
    conn_url: str,
    *,
    ingestion_run_id: str,
    provider: str,
    entity: str,
    request: Mapping[str, Any],
) -> None:
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO catalog.ingestion_runs "
                "(ingestion_run_id, provider, entity, state, request) "
                "VALUES (%s, %s, %s, 'running', %s::jsonb) "
                "ON CONFLICT (ingestion_run_id) DO NOTHING",
                (ingestion_run_id, provider, entity, json.dumps(dict(request))),
            )
        conn.commit()


def finish_ingestion_run(
    conn_url: str,
    ingestion_run_id: str,
    *,
    succeeded: bool,
    error_category: str | None = None,
    error_detail: str | None = None,
) -> None:
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE catalog.ingestion_runs SET state = %s, finished_at = NOW(), "
                "error_category = %s, error_detail = %s WHERE ingestion_run_id = %s",
                (
                    "succeeded" if succeeded else "failed",
                    error_category,
                    error_detail[-4000:] if error_detail else None,
                    ingestion_run_id,
                ),
            )
        conn.commit()


def register_source_capture(
    conn_url: str,
    capture: SourceCapture,
    *,
    ingestion_run_id: str | None = None,
) -> None:
    """Register a provider observation; content SHA may repeat by design."""
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO catalog.source_captures "
                "(capture_id, ingestion_run_id, provider, entity, captured_at, "
                "effective_at, request, content_sha, object_sha, uri, row_count, provider_api_version, "
                "response_metadata, state) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, "
                "%s, %s::jsonb, 'registered') "
                "ON CONFLICT (capture_id) DO NOTHING",
                (
                    capture.capture_id,
                    ingestion_run_id,
                    capture.provider,
                    capture.entity,
                    capture.captured_at,
                    capture.effective_at,
                    json.dumps(dict(capture.request)),
                    capture.content_sha,
                    capture.object_sha,
                    capture.uri,
                    capture.row_count,
                    capture.provider_api_version,
                    json.dumps(dict(capture.response_metadata)),
                ),
            )
        conn.commit()


def register_dataset_version(
    conn_url: str,
    ref: DatasetRef,
    manifest: DatasetManifest,
) -> None:
    """Register a validated dataset and its complete dependency edges atomically."""
    manifest_uri = ref.uri.rsplit("/", 1)[0] + "/manifest.json"
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO catalog.dataset_versions "
                "(version_id, dataset, tier, schema_version, content_sha, uri, "
                "manifest_uri, row_count, partitions, as_of, code_sha, config_sha, state) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s) "
                "ON CONFLICT (version_id) DO NOTHING",
                (
                    ref.version_id,
                    ref.dataset,
                    manifest.tier,
                    ref.schema_version,
                    ref.content_sha,
                    ref.uri,
                    manifest_uri,
                    manifest.row_count,
                    json.dumps(dict(manifest.partitions)),
                    manifest.as_of,
                    manifest.code_sha,
                    manifest.config_sha,
                    manifest.state,
                ),
            )
            for ordinal, parent_version in enumerate(manifest.parent_versions):
                cur.execute(
                    "INSERT INTO catalog.dataset_dependencies "
                    "(child_version_id, parent_version_id, ordinal) VALUES (%s, %s, %s) "
                    "ON CONFLICT (child_version_id, parent_version_id) DO NOTHING",
                    (ref.version_id, parent_version, ordinal),
                )
            for ordinal, capture_id in enumerate(manifest.source_capture_ids):
                cur.execute(
                    "INSERT INTO catalog.dataset_capture_dependencies "
                    "(child_version_id, capture_id, ordinal) VALUES (%s, %s, %s) "
                    "ON CONFLICT (child_version_id, capture_id) DO NOTHING",
                    (ref.version_id, capture_id, ordinal),
                )
            for check_name, value in manifest.validation.items():
                passed = bool(value) if isinstance(value, bool) else True
                cur.execute(
                    "INSERT INTO catalog.quality_results "
                    "(version_id, check_name, passed, details) VALUES (%s, %s, %s, %s::jsonb) "
                    "ON CONFLICT (version_id, check_name) DO UPDATE SET "
                    "passed = EXCLUDED.passed, details = EXCLUDED.details, checked_at = NOW()",
                    (
                        ref.version_id,
                        str(check_name),
                        passed,
                        json.dumps({"value": value}, default=str),
                    ),
                )
        conn.commit()


def register_reconciliation_results(
    conn_url: str,
    results,
    *,
    source_dataset_versions: list[str],
) -> None:
    """Persist deterministic per-game reconciliation classifications."""
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            for row in results.to_dict("records"):
                details = row.get("details", {})
                if isinstance(details, str):
                    details = json.loads(details)
                cur.execute(
                    "INSERT INTO catalog.source_reconciliations "
                    "(reconciliation_id, season, game_id, classification, blocking, "
                    "source_dataset_versions, details) "
                    "VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb) "
                    "ON CONFLICT (reconciliation_id) DO UPDATE SET "
                    "classification = EXCLUDED.classification, "
                    "blocking = EXCLUDED.blocking, details = EXCLUDED.details",
                    (
                        row["reconciliation_id"],
                        int(row["season"]),
                        int(row["game_id"]),
                        row["classification"],
                        bool(row["blocking"]),
                        json.dumps(source_dataset_versions),
                        json.dumps(details),
                    ),
                )
        conn.commit()


def dataset_ref_as_of(conn_url: str, dataset: str, as_of: str) -> DatasetRef:
    """Resolve an explicit catalog version at or before the point-in-time cutoff."""
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT version_id, schema_version, content_sha, uri "
                "FROM catalog.dataset_versions WHERE dataset = %s "
                "AND as_of <= %s AND state = 'validated' "
                "ORDER BY as_of DESC, created_at DESC LIMIT 1",
                (dataset, as_of),
            )
            row = cur.fetchone()
    if not row:
        raise LookupError(f"No validated {dataset} dataset exists as of {as_of}")
    return DatasetRef(dataset, str(row[0]), str(row[1]), str(row[2]), str(row[3]))


def dataset_ref_for_partition_as_of(
    conn_url: str,
    dataset: str,
    as_of: str,
    *,
    partitions: Mapping[str, Any],
) -> DatasetRef:
    """Resolve an explicit validated version matching a partition selector."""
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT version_id, schema_version, content_sha, uri "
                "FROM catalog.dataset_versions WHERE dataset = %s "
                "AND as_of <= %s AND state = 'validated' "
                "AND partitions @> %s::jsonb "
                "ORDER BY as_of DESC, created_at DESC LIMIT 1",
                (dataset, as_of, json.dumps(dict(partitions))),
            )
            row = cur.fetchone()
    if not row:
        raise LookupError(
            f"No validated {dataset} dataset for {dict(partitions)} as of {as_of}"
        )
    return DatasetRef(dataset, str(row[0]), str(row[1]), str(row[2]), str(row[3]))


def source_capture_by_id(conn_url: str, capture_id: str) -> SourceCapture:
    """Resolve one explicit registered Bronze observation."""
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT provider, entity, captured_at, effective_at, request, "
                "content_sha, object_sha, uri, row_count, provider_api_version, "
                "response_metadata, state FROM catalog.source_captures "
                "WHERE capture_id = %s",
                (capture_id,),
            )
            row = cur.fetchone()
    if not row:
        raise LookupError(f"Unknown source capture: {capture_id}")
    return SourceCapture(
        capture_id=capture_id,
        provider=str(row[0]),
        entity=str(row[1]),
        captured_at=row[2],
        effective_at=row[3],
        request=dict(row[4]),
        content_sha=str(row[5]),
        object_sha=str(row[6]),
        uri=str(row[7]),
        row_count=int(row[8]),
        provider_api_version=str(row[9]) if row[9] else None,
        response_metadata=dict(row[10]),
        state=str(row[11]),
    )


def ref_json(ref: DatasetRef) -> dict:
    return asdict(ref)
