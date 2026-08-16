"""Neon catalog registration for immutable R2 objects."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from typing import Any, Mapping

import psycopg

from cks_picks_cfb.data.lake import DatasetManifest, DatasetRef, SourceCapture
from cks_picks_cfb.data.runtime import resolve_runtime_target
from cks_picks_cfb.data.schema_contracts import schema_for
from cks_picks_cfb.data.storage import StorageBackend


def catalog_connection_url(environment: str) -> str:
    """Resolve the catalog connection without allowing Preview to fall into production."""
    return resolve_runtime_target(environment).database_url


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _catalog_timestamp(value: str | None) -> datetime | str | None:
    """Match Postgres TIMESTAMPTZ values when verifying legacy manifests."""
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def register_existing_dataset_ref(
    conn_url: str,
    storage: StorageBackend,
    ref_uri: str,
) -> DatasetRef:
    """Verify and register an immutable dataset that was built in an earlier run."""
    raw_ref = json.loads(storage.read_bytes(ref_uri).decode("utf-8"))
    ref = DatasetRef(
        dataset=str(raw_ref["dataset"]),
        version_id=str(raw_ref["version_id"]),
        schema_version=str(raw_ref["schema_version"]),
        content_sha=str(raw_ref["content_sha"]),
        uri=str(raw_ref["uri"]),
    )
    manifest_uri = ref.uri.rsplit("/", 1)[0] + "/manifest.json"
    raw_manifest = json.loads(storage.read_bytes(manifest_uri).decode("utf-8"))
    manifest = _dataset_manifest(raw_manifest)
    _verify_ref_manifest(ref, manifest, ref_uri)

    manifest_paths = {
        path.rsplit("/version=", 1)[-1].split("/", 1)[0]: path
        for path in storage.list_files("lake/")
        if path.endswith("/manifest.json") and "/version=" in path
    }
    _register_manifest_ancestry(
        conn_url,
        storage,
        ref,
        manifest,
        manifest_paths=manifest_paths,
        registered=set(),
    )
    return ref


def _dataset_manifest(raw_manifest: Mapping[str, Any]) -> DatasetManifest:
    raw_manifest = dict(raw_manifest)
    raw_manifest["parent_versions"] = tuple(raw_manifest.get("parent_versions", ()))
    raw_manifest["source_capture_ids"] = tuple(
        raw_manifest.get("source_capture_ids", ())
    )
    return DatasetManifest(**raw_manifest)


def _verify_ref_manifest(
    ref: DatasetRef, manifest: DatasetManifest, ref_uri: str
) -> None:
    identity = {
        "dataset": (ref.dataset, manifest.dataset),
        "version_id": (ref.version_id, manifest.version_id),
        "schema_version": (ref.schema_version, manifest.schema_version),
        "content_sha": (ref.content_sha, manifest.content_sha),
        "uri": (ref.uri, manifest.uri),
    }
    mismatches = [name for name, values in identity.items() if values[0] != values[1]]
    if mismatches:
        raise ValueError(
            f"Dataset ref and manifest disagree for {ref_uri}: {', '.join(mismatches)}"
        )


def _register_manifest_ancestry(
    conn_url: str,
    storage: StorageBackend,
    ref: DatasetRef,
    manifest: DatasetManifest,
    *,
    manifest_paths: Mapping[str, str],
    registered: set[str],
) -> None:
    if ref.version_id in registered:
        return
    for parent_version in manifest.parent_versions:
        if parent_version in registered:
            continue
        parent_manifest_uri = manifest_paths.get(parent_version)
        if not parent_manifest_uri:
            raise LookupError(
                f"No immutable manifest found for parent version {parent_version}"
            )
        parent_manifest = _dataset_manifest(
            json.loads(storage.read_bytes(parent_manifest_uri).decode("utf-8"))
        )
        parent_ref = DatasetRef(
            dataset=parent_manifest.dataset,
            version_id=parent_manifest.version_id,
            schema_version=parent_manifest.schema_version,
            content_sha=parent_manifest.content_sha,
            uri=parent_manifest.uri,
        )
        if parent_ref.version_id != parent_version:
            raise ValueError(
                f"Parent manifest {parent_manifest_uri} does not match {parent_version}"
            )
        _register_manifest_ancestry(
            conn_url,
            storage,
            parent_ref,
            parent_manifest,
            manifest_paths=manifest_paths,
            registered=registered,
        )
    register_dataset_version(conn_url, ref, manifest)
    registered.add(ref.version_id)


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
                "SELECT provider, entity, request FROM catalog.ingestion_runs "
                "WHERE ingestion_run_id = %s",
                (ingestion_run_id,),
            )
            existing = cur.fetchone()
            expected = (provider, entity, dict(request))
            if (
                existing
                and (str(existing[0]), str(existing[1]), dict(existing[2])) != expected
            ):
                raise ValueError(
                    f"Immutable ingestion run conflict: {ingestion_run_id}"
                )
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
            _register_source_capture_cursor(cur, capture, ingestion_run_id)
        conn.commit()


def _register_source_capture_cursor(
    cur: psycopg.Cursor,
    capture: SourceCapture,
    ingestion_run_id: str | None,
) -> None:
    cur.execute(
        "SELECT provider, entity, captured_at, effective_at, request, content_sha, "
        "object_sha, uri, row_count, provider_api_version, response_metadata "
        "FROM catalog.source_captures WHERE capture_id = %s",
        (capture.capture_id,),
    )
    existing = cur.fetchone()
    expected = (
        capture.provider,
        capture.entity,
        capture.captured_at,
        capture.effective_at,
        dict(capture.request),
        capture.content_sha,
        capture.object_sha,
        capture.uri,
        capture.row_count,
        capture.provider_api_version,
        dict(capture.response_metadata),
    )
    if existing and _canonical(tuple(existing)) != _canonical(expected):
        raise ValueError(f"Immutable source capture conflict: {capture.capture_id}")
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


def register_source_captures(
    conn_url: str,
    captures: list[SourceCapture],
    *,
    ingestion_run_id: str | None = None,
) -> int:
    """Register immutable observations in one transaction for catalog recovery."""
    if not captures:
        return 0
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            for capture in captures:
                _register_source_capture_cursor(cur, capture, ingestion_run_id)
        conn.commit()
    return len(captures)


def register_schema_version(conn_url: str, dataset: str, schema_version: str) -> str:
    """Register an executable schema once and reject same-name drift."""
    schema = schema_for(dataset, schema_version)
    schema_json = schema.json()
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT schema_json, schema_sha FROM catalog.schema_versions "
                "WHERE dataset = %s AND schema_version = %s",
                (dataset, schema_version),
            )
            existing = cur.fetchone()
            if existing:
                existing_json, existing_sha = dict(existing[0]), existing[1]
                if _canonical(existing_json) != _canonical(schema_json) or (
                    existing_sha is not None and str(existing_sha) != schema.sha256
                ):
                    raise ValueError(
                        f"Immutable schema conflict: {dataset}/{schema_version}"
                    )
            else:
                cur.execute(
                    "INSERT INTO catalog.schema_versions "
                    "(dataset, schema_version, schema_json, schema_sha) "
                    "VALUES (%s, %s, %s::jsonb, %s)",
                    (dataset, schema_version, _canonical(schema_json), schema.sha256),
                )
        conn.commit()
    return schema.sha256


def register_dataset_version(
    conn_url: str,
    ref: DatasetRef,
    manifest: DatasetManifest,
) -> None:
    """Register a validated dataset and its complete dependency edges atomically."""
    manifest_uri = ref.uri.rsplit("/", 1)[0] + "/manifest.json"
    if manifest.identity_version == "dataset_identity_v2":
        registered_schema_sha = register_schema_version(
            conn_url, ref.dataset, ref.schema_version
        )
        if manifest.schema_sha != registered_schema_sha:
            raise ValueError(
                f"Dataset schema SHA mismatch for {ref.dataset}/{ref.version_id}"
            )
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT dataset, tier, schema_version, content_sha, uri, manifest_uri, "
                "row_count, partitions, as_of, code_sha, config_sha, state, identity_version, "
                "schema_sha FROM catalog.dataset_versions WHERE version_id = %s",
                (ref.version_id,),
            )
            existing = cur.fetchone()
            expected = (
                ref.dataset,
                manifest.tier,
                ref.schema_version,
                ref.content_sha,
                ref.uri,
                manifest_uri,
                manifest.row_count,
                dict(manifest.partitions),
                _catalog_timestamp(manifest.as_of),
                manifest.code_sha,
                manifest.config_sha,
                manifest.state,
                manifest.identity_version,
                manifest.schema_sha,
            )
            if existing and _canonical(tuple(existing)) != _canonical(expected):
                raise ValueError(
                    f"Immutable dataset version conflict: {ref.version_id}"
                )
            cur.execute(
                "INSERT INTO catalog.dataset_versions "
                "(version_id, dataset, tier, schema_version, content_sha, uri, "
                "manifest_uri, row_count, partitions, as_of, code_sha, config_sha, state, "
                "identity_version, schema_sha) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s) "
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
                    manifest.identity_version,
                    manifest.schema_sha,
                ),
            )
            cur.execute(
                "SELECT parent_version_id, ordinal FROM catalog.dataset_dependencies "
                "WHERE child_version_id = %s ORDER BY ordinal",
                (ref.version_id,),
            )
            existing_parents = tuple(
                (str(row[0]), int(row[1])) for row in cur.fetchall()
            )
            expected_parents = tuple(enumerate(manifest.parent_versions))
            normalized_expected_parents = tuple(
                (parent, ordinal) for ordinal, parent in expected_parents
            )
            if existing_parents and existing_parents != normalized_expected_parents:
                raise ValueError(
                    f"Immutable dataset dependency conflict: {ref.version_id}"
                )
            for ordinal, parent_version in enumerate(manifest.parent_versions):
                cur.execute(
                    "INSERT INTO catalog.dataset_dependencies "
                    "(child_version_id, parent_version_id, ordinal) VALUES (%s, %s, %s) "
                    "ON CONFLICT (child_version_id, parent_version_id) DO NOTHING",
                    (ref.version_id, parent_version, ordinal),
                )
            cur.execute(
                "SELECT capture_id, ordinal FROM catalog.dataset_capture_dependencies "
                "WHERE child_version_id = %s ORDER BY ordinal",
                (ref.version_id,),
            )
            existing_captures = tuple(
                (str(row[0]), int(row[1])) for row in cur.fetchall()
            )
            expected_captures = tuple(
                (capture_id, ordinal)
                for ordinal, capture_id in enumerate(manifest.source_capture_ids)
            )
            if existing_captures and existing_captures != expected_captures:
                raise ValueError(
                    f"Immutable capture dependency conflict: {ref.version_id}"
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
                details = {"value": value}
                cur.execute(
                    "SELECT passed, details FROM catalog.quality_results "
                    "WHERE version_id = %s AND check_name = %s",
                    (ref.version_id, str(check_name)),
                )
                existing_quality = cur.fetchone()
                if existing_quality and (
                    bool(existing_quality[0]) != passed
                    or _canonical(dict(existing_quality[1])) != _canonical(details)
                ):
                    raise ValueError(
                        f"Immutable quality result conflict: {ref.version_id}/{check_name}"
                    )
                cur.execute(
                    "INSERT INTO catalog.quality_results "
                    "(version_id, check_name, passed, details) VALUES (%s, %s, %s, %s::jsonb) "
                    "ON CONFLICT (version_id, check_name) DO NOTHING",
                    (
                        ref.version_id,
                        str(check_name),
                        passed,
                        json.dumps(details, default=str),
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
