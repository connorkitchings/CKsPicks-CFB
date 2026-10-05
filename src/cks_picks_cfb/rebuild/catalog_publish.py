"""Atomic Preview catalog registration of the published Silver and Gold datasets.

Everything the root manifest published is registered in ONE transaction: schema versions,
dataset versions, dependency and capture edges and quality results. Any failure rolls the
whole registration back, so the catalog never points at a half-published set. Existing rows
must match exactly (immutability); an identical retry changes nothing. Gold datasets are
registered as their partitioned roots only; the per-season children stay unregistered, like
the legacy partitioned runs.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from cks_picks_cfb.rebuild.errors import GateError
from cks_picks_cfb.rebuild.targets import assert_catalog_only

PLAIN_MANIFEST = re.compile(
    r"^lake/(?P<tier>silver|gold)/dataset=(?P<dataset>[^/]+)/version=(?P<version>[^/]+)/manifest\.json$"
)
ROOT_MANIFEST = re.compile(
    r"^lake/gold/dataset=(?P<dataset>[^/]+)/version=(?P<version>[^/]+)/partitioned-manifest\.json$"
)


@dataclass(frozen=True)
class Entry:
    """One catalog dataset version, from a published manifest."""

    kind: str  # "plain" or "partitioned"
    dataset: str
    version_id: str
    tier: str
    schema_version: str
    content_sha: str
    uri: str
    manifest_uri: str
    row_count: int
    partitions: Mapping[str, Any]
    as_of: str
    code_sha: str | None
    config_sha: str | None
    state: str
    identity_version: str
    schema_sha: str | None
    parents: tuple[str, ...]
    captures: tuple[str, ...]
    validation: Mapping[str, Any]


def collect_entries(
    published: Mapping[str, str], read: Callable[[str], bytes]
) -> list[Entry]:
    """Entries for every published dataset manifest, parents before children.

    ``published`` is the root manifest's ``objects`` map (key -> sha256). Silver datasets
    are plain; Gold datasets are registered through their partitioned roots, and the
    per-season child datasets those roots reference are skipped.
    """
    import hashlib

    children: set[str] = set()
    roots: list[tuple[str, dict[str, Any], str]] = []
    for key in sorted(published):
        match = ROOT_MANIFEST.match(key)
        if match:
            raw = read(key)
            manifest = json.loads(raw)
            roots.append((key, manifest, hashlib.sha256(raw).hexdigest()))
            children.update(
                part["ref"]["version_id"] for part in manifest["parts"] if part["ref"]
            )
    entries: list[Entry] = []
    plain = []
    for key in sorted(published):
        match = PLAIN_MANIFEST.match(key)
        if not match or match["version"] in children:
            continue
        manifest = json.loads(read(key))
        if manifest["tier"] != "silver":
            raise GateError(f"unexpected unregistered plain dataset: {key}")
        plain.append((key, manifest))
    plain.sort(
        key=lambda item: (
            item[1]["partitions"].get("seasons", [0])[0],
            item[1]["dataset"],
        )
    )
    for key, manifest in plain:
        entries.append(
            Entry(
                kind="plain",
                dataset=manifest["dataset"],
                version_id=manifest["version_id"],
                tier=manifest["tier"],
                schema_version=manifest["schema_version"],
                content_sha=manifest["content_sha"],
                uri=manifest["uri"],
                manifest_uri=key,
                row_count=int(manifest["row_count"]),
                partitions=manifest["partitions"],
                as_of=manifest["as_of"],
                code_sha=manifest.get("code_sha"),
                config_sha=manifest.get("config_sha"),
                state=manifest.get("state", "validated"),
                identity_version=manifest.get(
                    "identity_version", "dataset_identity_v2"
                ),
                schema_sha=manifest.get("schema_sha"),
                parents=tuple(manifest.get("parent_versions", ())),
                captures=tuple(manifest.get("source_capture_ids", ())),
                validation=manifest.get("validation", {}),
            )
        )
    for key, manifest, content_sha in roots:
        entries.append(
            Entry(
                kind="partitioned",
                dataset=manifest["dataset"],
                version_id=manifest["version_id"],
                tier=manifest["tier"],
                schema_version=manifest["schema_version"],
                content_sha=content_sha,
                uri=key,
                manifest_uri=key,
                row_count=int(manifest["row_count"]),
                partitions={
                    "artifact_kind": manifest["artifact_kind"],
                    "partition_keys": list(manifest["partition_keys"]),
                },
                as_of=manifest["as_of"],
                code_sha=manifest.get("code_sha"),
                config_sha=manifest.get("config_sha"),
                state="validated",
                identity_version="dataset_identity_v2",
                schema_sha=None,
                parents=tuple(
                    str(p["version_id"]) for p in manifest.get("parents", ())
                ),
                captures=tuple(manifest.get("source_captures", ())),
                validation={},
            )
        )
    return entries


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def register_entries(
    conn_url: str,
    entries: Sequence[Entry],
    *,
    schema_lookup: Callable[[str, str], Any],
    before_write: Callable[[Any], None] | None = None,
    connect: Callable[[str], Any] | None = None,
) -> dict[str, int]:
    """Register every entry in one transaction; return counts of rows newly written."""
    from cks_picks_cfb.data.catalog import _catalog_timestamp

    if connect is None:
        import psycopg

        connect = psycopg.connect
    written = {"schemas": 0, "versions": 0, "dependencies": 0, "quality": 0}
    with connect(conn_url) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                if before_write is not None:
                    before_write(cur)
                for entry in entries:
                    schema = schema_lookup(entry.dataset, entry.schema_version)
                    cur.execute(
                        "SELECT schema_json, schema_sha FROM catalog.schema_versions "
                        "WHERE dataset = %s AND schema_version = %s",
                        (entry.dataset, entry.schema_version),
                    )
                    existing_schema = cur.fetchone()
                    if existing_schema:
                        if _canonical(dict(existing_schema[0])) != _canonical(
                            schema.json()
                        ) or (
                            existing_schema[1] is not None
                            and str(existing_schema[1]) != schema.sha256
                        ):
                            raise GateError(
                                f"immutable schema conflict: {entry.dataset}/{entry.schema_version}"
                            )
                    else:
                        cur.execute(
                            "INSERT INTO catalog.schema_versions "
                            "(dataset, schema_version, schema_json, schema_sha) "
                            "VALUES (%s, %s, %s::jsonb, %s)",
                            (
                                entry.dataset,
                                entry.schema_version,
                                _canonical(schema.json()),
                                schema.sha256,
                            ),
                        )
                        written["schemas"] += 1
                    row = (
                        entry.dataset,
                        entry.tier,
                        entry.schema_version,
                        entry.content_sha,
                        entry.uri,
                        entry.manifest_uri,
                        entry.row_count,
                        dict(entry.partitions),
                        _catalog_timestamp(entry.as_of),
                        entry.code_sha,
                        entry.config_sha,
                        entry.state,
                        entry.identity_version,
                        entry.schema_sha,
                    )
                    cur.execute(
                        "SELECT dataset, tier, schema_version, content_sha, uri, "
                        "manifest_uri, row_count, partitions, as_of, code_sha, config_sha, "
                        "state, identity_version, schema_sha "
                        "FROM catalog.dataset_versions WHERE version_id = %s",
                        (entry.version_id,),
                    )
                    existing = cur.fetchone()
                    if existing:
                        if _canonical(tuple(existing)) != _canonical(row):
                            raise GateError(
                                f"immutable dataset version conflict: {entry.version_id}"
                            )
                    else:
                        cur.execute(
                            "INSERT INTO catalog.dataset_versions "
                            "(version_id, dataset, tier, schema_version, content_sha, uri, "
                            "manifest_uri, row_count, partitions, as_of, code_sha, "
                            "config_sha, state, identity_version, schema_sha) VALUES "
                            "(%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, "
                            "%s, %s)",
                            (
                                entry.version_id,
                                *row[:7],
                                json.dumps(row[7]),
                                *row[8:],
                            ),
                        )
                        written["versions"] += 1
                    for ordinal, parent in enumerate(entry.parents):
                        cur.execute(
                            "INSERT INTO catalog.dataset_dependencies "
                            "(child_version_id, parent_version_id, ordinal) "
                            "VALUES (%s, %s, %s) ON CONFLICT "
                            "(child_version_id, parent_version_id) DO NOTHING",
                            (entry.version_id, parent, ordinal),
                        )
                        written["dependencies"] += max(cur.rowcount or 0, 0)
                    for ordinal, capture in enumerate(entry.captures):
                        cur.execute(
                            "INSERT INTO catalog.dataset_capture_dependencies "
                            "(child_version_id, capture_id, ordinal) VALUES (%s, %s, %s) "
                            "ON CONFLICT (child_version_id, capture_id) DO NOTHING",
                            (entry.version_id, capture, ordinal),
                        )
                    for check, value in entry.validation.items():
                        passed = bool(value) if isinstance(value, bool) else True
                        cur.execute(
                            "INSERT INTO catalog.quality_results "
                            "(version_id, check_name, passed, details) "
                            "VALUES (%s, %s, %s, %s::jsonb) "
                            "ON CONFLICT (version_id, check_name) DO NOTHING",
                            (
                                entry.version_id,
                                str(check),
                                passed,
                                json.dumps({"value": value}, default=str),
                            ),
                        )
                        written["quality"] += max(cur.rowcount or 0, 0)
    return written


SQL_WRITE_STATEMENTS = (
    "INSERT INTO catalog.schema_versions",
    "INSERT INTO catalog.dataset_versions",
    "INSERT INTO catalog.dataset_dependencies",
    "INSERT INTO catalog.dataset_capture_dependencies",
    "INSERT INTO catalog.quality_results",
)


def write_scope_ok() -> bool:
    """Every statement this module can issue targets the catalog schema only."""
    try:
        assert_catalog_only(SQL_WRITE_STATEMENTS)
    except Exception:  # noqa: BLE001 - reported as False
        return False
    return True
