"""Promote immutable Silver dataset versions from one catalog to another.

The Preview lake holds the weekly 2026 play-by-play lineage; production's catalog
has no 2026 ``byplay``/``drives``. Preview and production share one R2 bucket
(``CFB_R2_PREVIEW_*`` and ``CFB_R2_*`` resolve to the same bucket), so promotion
is *catalog registration only*: no object is copied or rewritten. Each version
(and its parents and source captures) is verified against its sealed manifest
and content hash, then registered through the same immutable-catalog code the
pipeline uses. Different buckets are refused: a copy step is a separate decision.

Source captures are registered without their ingestion run (the column is
nullable); the capture row itself, its object hash and URI are preserved.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

import psycopg

from cks_picks_cfb.data.catalog import (
    _dataset_manifest,
    _verify_ref_manifest,
    register_dataset_version,
    register_source_capture,
)
from cks_picks_cfb.data.lake import DatasetManifest, DatasetRef, SourceCapture
from cks_picks_cfb.data.storage.base import StorageBackend, StorageSettings


class PromotionError(RuntimeError):
    """Raised when a version cannot be promoted safely."""


@dataclass
class PromotionReport:
    versions: list[dict[str, Any]] = field(default_factory=list)
    captures_to_register: list[str] = field(default_factory=list)
    captures_present: list[str] = field(default_factory=list)

    @property
    def new_versions(self) -> list[dict[str, Any]]:
        return [v for v in self.versions if not v["already_in_target"]]


def assert_same_bucket(source: StorageSettings, target: StorageSettings) -> None:
    """Promotion registers existing objects; both catalogs must read one bucket."""
    for label, a, b in (
        ("bucket", source.bucket, target.bucket),
        ("account", source.account_id, target.account_id),
        ("endpoint", source.endpoint, target.endpoint),
    ):
        if not a or a != b:
            raise PromotionError(
                f"Source and target storage differ ({label}); refusing to promote "
                "by catalog registration. Copy the objects first."
            )


def resolve_version(
    conn_url: str, dataset: str, season: int, version_id: str | None = None
) -> str:
    """Pinned (prefix ok) or latest validated Silver version for the season."""
    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        if version_id:
            cur.execute(
                "SELECT version_id FROM catalog.dataset_versions WHERE dataset = %s "
                "AND tier = 'silver' AND state = 'validated' AND version_id LIKE %s "
                "LIMIT 2",
                (dataset, f"{version_id}%"),
            )
        else:
            cur.execute(
                "SELECT version_id FROM catalog.dataset_versions WHERE dataset = %s "
                "AND tier = 'silver' AND state = 'validated' "
                "AND partitions @> %s::jsonb ORDER BY as_of DESC, created_at DESC "
                "LIMIT 1",
                (dataset, json.dumps({"seasons": [season]})),
            )
        rows = cur.fetchall()
    if len(rows) != 1:
        raise PromotionError(
            f"Silver {dataset} {version_id or f'latest for {season}'}: "
            f"matched {len(rows)} validated versions"
        )
    return str(rows[0][0])


def _closure(source_url: str, roots: list[str]) -> list[str]:
    """Roots and all ancestors, parents before children."""
    order: list[str] = []
    seen: set[str] = set()
    with psycopg.connect(source_url) as conn, conn.cursor() as cur:

        def visit(version_id: str) -> None:
            if version_id in seen:
                return
            seen.add(version_id)
            cur.execute(
                "SELECT parent_version_id FROM catalog.dataset_dependencies "
                "WHERE child_version_id = %s ORDER BY ordinal",
                (version_id,),
            )
            for (parent,) in cur.fetchall():
                visit(str(parent))
            order.append(version_id)

        for root in roots:
            visit(root)
    return order


def _source_capture(source_url: str, capture_id: str) -> SourceCapture:
    with psycopg.connect(source_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT capture_id, provider, entity, captured_at, effective_at, request, "
            "content_sha, object_sha, uri, row_count, provider_api_version, "
            "response_metadata FROM catalog.source_captures WHERE capture_id = %s",
            (capture_id,),
        )
        row = cur.fetchone()
    if row is None:
        raise PromotionError(f"Source catalog has no capture {capture_id}")
    return SourceCapture(
        capture_id=str(row[0]),
        provider=str(row[1]),
        entity=str(row[2]),
        captured_at=row[3],
        effective_at=row[4],
        request=dict(row[5]),
        content_sha=str(row[6]),
        object_sha=str(row[7]),
        uri=str(row[8]),
        row_count=int(row[9]),
        provider_api_version=row[10],
        response_metadata=dict(row[11] or {}),
    )


def _present(conn_url: str, table: str, column: str, value: str) -> bool:
    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        cur.execute(f"SELECT 1 FROM {table} WHERE {column} = %s", (value,))  # noqa: S608
        return cur.fetchone() is not None


def _verified_manifest(
    source_url: str, storage: StorageBackend, version_id: str
) -> tuple[DatasetRef, DatasetManifest, dict[str, Any]]:
    with psycopg.connect(source_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT dataset, version_id, schema_version, content_sha, uri, "
            "manifest_uri, state FROM catalog.dataset_versions WHERE version_id = %s",
            (version_id,),
        )
        row = cur.fetchone()
    if row is None:
        raise PromotionError(f"Source catalog has no version {version_id}")
    ref = DatasetRef(str(row[0]), str(row[1]), str(row[2]), str(row[3]), str(row[4]))
    if row[6] != "validated":
        raise PromotionError(f"{ref.dataset}/{version_id} is {row[6]}, not validated")
    manifest = _dataset_manifest(json.loads(storage.read_bytes(str(row[5]))))
    _verify_ref_manifest(ref, manifest, str(row[5]))
    payload = storage.read_bytes(ref.uri)
    actual = hashlib.sha256(payload).hexdigest()
    if actual != ref.content_sha:
        raise PromotionError(
            f"Content hash mismatch for {ref.dataset}/{version_id}: "
            f"{actual} != {ref.content_sha}"
        )
    info = {
        "dataset": ref.dataset,
        "version_id": version_id,
        "row_count": manifest.row_count,
        "bytes": len(payload),
        "parents": len(manifest.parent_versions),
        "captures": len(manifest.source_capture_ids),
    }
    return ref, manifest, info


def promote(
    *,
    source_url: str,
    target_url: str,
    storage: StorageBackend,
    root_versions: list[str],
    dry_run: bool,
) -> PromotionReport:
    """Verify and (unless ``dry_run``) register roots, ancestors and captures."""
    report = PromotionReport()
    seen_captures: set[str] = set()
    for version_id in _closure(source_url, root_versions):
        ref, manifest, info = _verified_manifest(source_url, storage, version_id)
        info["already_in_target"] = _present(
            target_url, "catalog.dataset_versions", "version_id", version_id
        )
        report.versions.append(info)
        for capture_id in manifest.source_capture_ids:
            if capture_id in seen_captures:
                continue
            seen_captures.add(capture_id)
            if _present(
                target_url, "catalog.source_captures", "capture_id", capture_id
            ):
                report.captures_present.append(capture_id)
                continue
            report.captures_to_register.append(capture_id)
            if not dry_run:
                register_source_capture(
                    target_url, _source_capture(source_url, capture_id)
                )
        if not dry_run and not info["already_in_target"]:
            register_dataset_version(target_url, ref, manifest)
    return report
