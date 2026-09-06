#!/usr/bin/env python3
"""Resolve and audit immutable evidence for data-first football Phase 1."""

from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg
import pyarrow as pa
import pyarrow.parquet as pq
import yaml
from dotenv import load_dotenv

from cks_picks_cfb.data.evidence_audit import (
    AUDIT_SCHEMA_VERSION,
    DEVELOPMENT_SEASONS,
    ImmutableAuditWriter,
    add_team_experience,
    attach_prediction_labels,
    canonical_json,
    classify_schedule,
    extract_dataset_refs,
    extract_json_links,
    frame_audit,
    issue,
    join_cardinality_audit,
    lineage_cycles,
    match_reported_metrics,
    numeric_semantics_audit,
    pregame_timing_audit,
    propagate_timing_classes,
    recompute_prediction_metrics,
    reported_metric_claims,
    require_resolved_manifest,
    result_disposition,
    sha256,
    stage_coverage,
    transitive_descendants,
)
from cks_picks_cfb.data.lake import (
    DatasetRef,
    SourceCapture,
    read_dataset,
    read_source_capture,
)
from cks_picks_cfb.data.runtime import resolve_runtime_target
from cks_picks_cfb.data.storage import ReadOnlyStorage, get_storage

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = "conf/research/data_first_football_v1/phase1_audit_v1.yaml"


def _git_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _utc(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError("--as-of must be an explicit UTC timestamp")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _config(path: str) -> tuple[dict[str, Any], bytes]:
    config_path = REPO_ROOT / path
    payload = config_path.read_bytes()
    value = yaml.safe_load(payload)
    if value.get("schema_version") != AUDIT_SCHEMA_VERSION:
        raise ValueError("Phase 1 configuration has the wrong schema version")
    if tuple(value.get("development_seasons", ())) != DEVELOPMENT_SEASONS:
        raise ValueError("Phase 1 configuration changed the approved seasons")
    if value.get("environment") != "preview":
        raise ValueError("Phase 1 is Preview-only")
    return value, payload


def _verify_runtime(expected_code_sha: str) -> tuple[Any, str]:
    if expected_code_sha != _git_sha():
        raise ValueError("--expected-code-sha must match the current committed HEAD")
    if os.getenv("CFB_STORAGE_BACKEND", "").lower() != "r2":
        raise RuntimeError("Phase 1 requires CFB_STORAGE_BACKEND=r2")
    target = resolve_runtime_target("preview")
    storage = get_storage(environment="preview")
    return storage, target.database_url


def _read_json(storage: ReadOnlyStorage, uri: str) -> tuple[dict[str, Any], bytes]:
    payload = storage.read_bytes(uri)
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise ValueError(f"evidence root is not a JSON object: {uri}")
    return value, payload


def _dataset_manifest_uri(ref: DatasetRef) -> str:
    suffix = "/data.parquet"
    if not ref.uri.endswith(suffix):
        raise ValueError(f"dataset URI has no canonical manifest location: {ref.uri}")
    return f"{ref.uri[: -len(suffix)]}/manifest.json"


def _catalog_dataset(cur, version_id: str) -> dict[str, Any] | None:
    cur.execute(
        "SELECT version_id,dataset,tier,schema_version,content_sha,uri,manifest_uri,"
        "row_count,partitions,as_of,code_sha,config_sha,state,identity_version,schema_sha "
        "FROM catalog.dataset_versions WHERE version_id=%s",
        (version_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    keys = (
        "version_id",
        "dataset",
        "tier",
        "schema_version",
        "content_sha",
        "uri",
        "manifest_uri",
        "row_count",
        "partitions",
        "as_of",
        "code_sha",
        "config_sha",
        "state",
        "identity_version",
        "schema_sha",
    )
    value = dict(zip(keys, row, strict=True))
    value["partitions"] = dict(value["partitions"] or {})
    value["as_of"] = (
        value["as_of"].isoformat()
        if hasattr(value["as_of"], "isoformat")
        else str(value["as_of"])
    )
    return value


def _catalog_dependencies(
    cur, version_id: str
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    cur.execute(
        "SELECT parent_version_id FROM catalog.dataset_dependencies "
        "WHERE child_version_id=%s ORDER BY ordinal",
        (version_id,),
    )
    parents = [str(row[0]) for row in cur.fetchall()]
    cur.execute(
        "SELECT capture_id FROM catalog.dataset_capture_dependencies "
        "WHERE child_version_id=%s ORDER BY ordinal",
        (version_id,),
    )
    captures = [str(row[0]) for row in cur.fetchall()]
    cur.execute(
        "SELECT check_name,passed,details FROM catalog.quality_results "
        "WHERE version_id=%s ORDER BY check_name",
        (version_id,),
    )
    quality = [
        {
            "check_name": str(name),
            "passed": bool(passed),
            "details": dict(details or {}),
        }
        for name, passed, details in cur.fetchall()
    ]
    return parents, captures, quality


def _catalog_capture(cur, capture_id: str) -> dict[str, Any] | None:
    cur.execute(
        "SELECT capture_id,provider,entity,captured_at,effective_at,request,content_sha,"
        "object_sha,uri,row_count,provider_api_version,response_metadata,state "
        "FROM catalog.source_captures WHERE capture_id=%s",
        (capture_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    keys = (
        "capture_id",
        "provider",
        "entity",
        "captured_at",
        "effective_at",
        "request",
        "content_sha",
        "object_sha",
        "uri",
        "row_count",
        "provider_api_version",
        "response_metadata",
        "state",
    )
    value = dict(zip(keys, row, strict=True))
    for key in ("captured_at", "effective_at"):
        if value[key] is not None and hasattr(value[key], "isoformat"):
            value[key] = value[key].isoformat()
    value["request"] = dict(value["request"] or {})
    value["response_metadata"] = dict(value["response_metadata"] or {})
    return value


def resolve_evidence(
    *,
    config: dict[str, Any],
    config_bytes: bytes,
    storage,
    conn_url: str,
    run_id: str,
    as_of: str,
    code_sha: str,
) -> dict[str, Any]:
    reader = ReadOnlyStorage(storage)
    roots: list[dict[str, Any]] = []
    initial_refs: dict[str, DatasetRef] = {}
    root_versions: dict[str, list[str]] = {}
    blockers: list[dict[str, Any]] = []
    registration_gaps: list[dict[str, Any]] = []
    linked_documents: dict[str, dict[str, Any]] = {}
    document_cache: dict[str, tuple[dict[str, Any], bytes]] = {}

    def add_ref(ref: DatasetRef, *, root_id: str, document_uri: str) -> None:
        existing = initial_refs.get(ref.version_id)
        if existing is not None and existing != ref:
            blockers.append(
                {
                    "version_id": ref.version_id,
                    "error": "conflicting immutable dataset references",
                    "root_id": root_id,
                    "document_uri": document_uri,
                }
            )
            return
        initial_refs[ref.version_id] = ref
        linked_documents.setdefault(document_uri, {}).setdefault("root_ids", set()).add(
            root_id
        )
        linked_documents[document_uri].setdefault("dataset_versions", set()).add(
            ref.version_id
        )

    def walk_document(
        payload: dict[str, Any], *, root_id: str, document_uri: str
    ) -> set[str]:
        versions: set[str] = set()
        pending = [(document_uri, payload)]
        visited: set[str] = set()
        while pending:
            uri, document = pending.pop()
            if uri in visited:
                continue
            visited.add(uri)
            entry = linked_documents.setdefault(uri, {})
            entry.setdefault("root_ids", set()).add(root_id)
            entry.setdefault("dataset_versions", set())
            for ref in extract_dataset_refs(document):
                add_ref(ref, root_id=root_id, document_uri=uri)
                versions.add(ref.version_id)
            for link in extract_json_links(document):
                try:
                    linked, raw = document_cache.get(link) or _read_json(reader, link)
                    document_cache[link] = (linked, raw)
                    linked_documents.setdefault(link, {}).update(
                        {"sha256": sha256(raw), "state": "resolved"}
                    )
                    pending.append((link, linked))
                except Exception as exc:
                    blockers.append(
                        {
                            "root_id": root_id,
                            "document_uri": uri,
                            "linked_uri": link,
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                        }
                    )
        return versions

    for spec in config["roots"]:
        root_id = str(spec["root_id"])
        try:
            if spec["kind"] == "local_yaml":
                raw = (REPO_ROOT / spec["path"]).read_bytes()
                payload = yaml.safe_load(raw)
                location = str(spec["path"])
            else:
                payload, raw = _read_json(reader, str(spec["uri"]))
                location = str(spec["uri"])
            actual_sha = sha256(raw)
            expected_sha = spec.get("expected_sha256")
            if expected_sha and actual_sha != expected_sha:
                raise ValueError(
                    f"root checksum mismatch: {actual_sha} != {expected_sha}"
                )
            root_versions[root_id] = sorted(
                walk_document(payload, root_id=root_id, document_uri=location)
            )
            roots.append(
                {
                    "root_id": root_id,
                    "location": location,
                    "required": bool(spec.get("required", True)),
                    "state": "resolved",
                    "sha256": actual_sha,
                    "dataset_versions": root_versions[root_id],
                }
            )
        except Exception as exc:
            detail = {
                "root_id": root_id,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            blockers.append(detail)
            roots.append(
                {
                    "root_id": root_id,
                    "location": str(spec.get("uri") or spec.get("path")),
                    "required": bool(spec.get("required", True)),
                    "state": "unresolved",
                    "error": str(exc),
                    "dataset_versions": [],
                }
            )
            root_versions[root_id] = []

    datasets: dict[str, dict[str, Any]] = {}
    captures: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, str]] = []
    queue = deque(sorted(initial_refs))
    with psycopg.connect(conn_url) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        with conn.cursor() as cur:
            while queue:
                version_id = queue.popleft()
                if version_id in datasets:
                    continue
                catalog_row = _catalog_dataset(cur, version_id)
                if not catalog_row:
                    ref = initial_refs.get(version_id)
                    if ref is None:
                        blockers.append(
                            {
                                "version_id": version_id,
                                "error": "catalog registration and exact reference missing",
                            }
                        )
                        continue
                    try:
                        frame = read_dataset(reader, ref)
                        manifest_uri = _dataset_manifest_uri(ref)
                        manifest = None
                        if reader.exists(manifest_uri):
                            manifest, _ = _read_json(reader, manifest_uri)
                            for key in (
                                "dataset",
                                "version_id",
                                "schema_version",
                                "content_sha",
                                "uri",
                            ):
                                if str(manifest.get(key)) != str(getattr(ref, key)):
                                    raise ValueError(f"manifest/ref mismatch: {key}")
                        registration_gaps.append(
                            {
                                "version_id": version_id,
                                "dataset": ref.dataset,
                                "uri": ref.uri,
                                "manifest_uri": manifest_uri if manifest else None,
                                "object_state": "checksum_verified",
                            }
                        )
                        catalog_row = {
                            "version_id": version_id,
                            "dataset": ref.dataset,
                            "tier": ref.uri.split("/", 2)[1]
                            if ref.uri.startswith("lake/")
                            else "research",
                            "schema_version": ref.schema_version,
                            "content_sha": ref.content_sha,
                            "uri": ref.uri,
                            "manifest_uri": manifest_uri if manifest else None,
                            "row_count": int(len(frame)),
                            "partitions": dict(
                                (manifest or {}).get("partitions") or {}
                            ),
                            "as_of": (manifest or {}).get("as_of"),
                            "code_sha": (manifest or {}).get("code_sha"),
                            "config_sha": (manifest or {}).get("config_sha"),
                            "state": "unregistered_object_verified",
                            "identity_version": (manifest or {}).get(
                                "identity_version", "unknown"
                            ),
                            "schema_sha": (manifest or {}).get("schema_sha"),
                            "parent_versions": list(
                                (manifest or {}).get("parent_versions") or []
                            ),
                            "source_capture_ids": list(
                                (manifest or {}).get("source_capture_ids") or []
                            ),
                            "quality_results": [],
                        }
                        datasets[version_id] = catalog_row
                        for parent in catalog_row["parent_versions"]:
                            edges.append(
                                {
                                    "child_version_id": version_id,
                                    "parent_version_id": str(parent),
                                }
                            )
                            if parent not in datasets:
                                queue.append(str(parent))
                        for capture_id in catalog_row["source_capture_ids"]:
                            if capture_id in captures:
                                continue
                            capture = _catalog_capture(cur, str(capture_id))
                            if capture is None:
                                blockers.append(
                                    {
                                        "capture_id": str(capture_id),
                                        "version_id": version_id,
                                        "error": "catalog capture missing",
                                    }
                                )
                            else:
                                captures[str(capture_id)] = capture
                        continue
                    except Exception as exc:
                        blockers.append(
                            {
                                "version_id": version_id,
                                "uri": ref.uri,
                                "error_type": type(exc).__name__,
                                "error": f"unregistered dataset object invalid: {exc}",
                            }
                        )
                        continue
                ref = initial_refs.get(version_id)
                if ref:
                    comparisons = {
                        "dataset": ref.dataset,
                        "schema_version": ref.schema_version,
                        "content_sha": ref.content_sha,
                        "uri": ref.uri,
                    }
                    mismatches = [
                        key
                        for key, value in comparisons.items()
                        if str(catalog_row[key]) != str(value)
                    ]
                    if mismatches:
                        blockers.append(
                            {
                                "version_id": version_id,
                                "error": f"ref/catalog mismatch: {mismatches}",
                            }
                        )
                        continue
                try:
                    manifest, _ = _read_json(reader, str(catalog_row["manifest_uri"]))
                    for key in (
                        "dataset",
                        "version_id",
                        "schema_version",
                        "content_sha",
                        "uri",
                    ):
                        if str(manifest.get(key)) != str(catalog_row[key]):
                            raise ValueError(f"manifest/catalog mismatch: {key}")
                except Exception as exc:
                    blockers.append(
                        {
                            "version_id": version_id,
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                        }
                    )
                    continue
                parents, capture_ids, quality = _catalog_dependencies(cur, version_id)
                catalog_row["parent_versions"] = parents
                catalog_row["source_capture_ids"] = capture_ids
                catalog_row["quality_results"] = quality
                datasets[version_id] = catalog_row
                for parent in parents:
                    edges.append(
                        {"child_version_id": version_id, "parent_version_id": parent}
                    )
                    if parent not in datasets:
                        queue.append(parent)
                for capture_id in capture_ids:
                    if capture_id in captures:
                        continue
                    capture = _catalog_capture(cur, capture_id)
                    if capture is None:
                        blockers.append(
                            {
                                "capture_id": capture_id,
                                "error": "catalog capture missing",
                            }
                        )
                    else:
                        captures[capture_id] = capture

    payload: dict[str, Any] = {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "state": "resolved_with_blockers" if blockers else "resolved",
        "run_id": run_id,
        "as_of": as_of,
        "code_sha": code_sha,
        "config_sha256": sha256(config_bytes),
        "roots": sorted(roots, key=lambda row: row["root_id"]),
        "root_dataset_versions": root_versions,
        "datasets": [datasets[key] for key in sorted(datasets)],
        "lineage_edges": sorted(
            edges, key=lambda row: (row["child_version_id"], row["parent_version_id"])
        ),
        "source_captures": [captures[key] for key in sorted(captures)],
        "linked_documents": [
            {
                "uri": uri,
                **{
                    key: sorted(value) if isinstance(value, set) else value
                    for key, value in linked_documents[uri].items()
                },
            }
            for uri in sorted(linked_documents)
        ],
        "registration_gaps": sorted(
            registration_gaps, key=lambda row: row["version_id"]
        ),
        "blockers": sorted(blockers, key=lambda row: canonical_json(row)),
    }
    for cycle in lineage_cycles(payload["lineage_edges"]):
        payload["blockers"].append({"error": "lineage cycle", "cycle": cycle})
    if payload["blockers"]:
        payload["state"] = "resolved_with_blockers"
        payload["blockers"] = sorted(
            payload["blockers"], key=lambda row: canonical_json(row)
        )
    payload["manifest_sha256"] = sha256(canonical_json(payload))
    return payload


def _source_capture(value: dict[str, Any]) -> SourceCapture:
    return SourceCapture(
        capture_id=str(value["capture_id"]),
        provider=str(value["provider"]),
        entity=str(value["entity"]),
        captured_at=datetime.fromisoformat(
            str(value["captured_at"]).replace("Z", "+00:00")
        ),
        effective_at=(
            datetime.fromisoformat(str(value["effective_at"]).replace("Z", "+00:00"))
            if value.get("effective_at")
            else None
        ),
        request=dict(value.get("request") or {}),
        content_sha=str(value["content_sha"]),
        object_sha=str(value["object_sha"]),
        uri=str(value["uri"]),
        row_count=int(value["row_count"]),
        provider_api_version=value.get("provider_api_version"),
        response_metadata=dict(value.get("response_metadata") or {}),
        state=str(value.get("state") or "registered"),
    )


def _parquet_bytes(frame: pd.DataFrame) -> bytes:
    ordered = frame.copy()
    if not ordered.empty:
        columns = sorted(ordered.columns)
        ordered = ordered[columns]
        sortable = [
            column
            for column in columns
            if not ordered[column]
            .map(lambda value: isinstance(value, (dict, list)))
            .any()
        ]
        if sortable:
            ordered = ordered.sort_values(
                sortable, kind="mergesort", na_position="last"
            )
    table = pa.Table.from_pandas(ordered, preserve_index=False)
    sink = io.BytesIO()
    pq.write_table(table, sink, compression="snappy")
    return sink.getvalue()


def _game_ids(frame: pd.DataFrame) -> set[int]:
    if "game_id" not in frame:
        if "gameId" in frame:
            values = frame["gameId"]
        elif "id" in frame:
            values = frame["id"]
        else:
            return set()
    else:
        values = frame["game_id"]
    return set(pd.to_numeric(values, errors="coerce").dropna().astype(int))


def _canonical_columns(part: pd.DataFrame, aliases: dict[str, str]) -> pd.DataFrame:
    rename: dict[str, str] = {}
    drop: list[str] = []
    for alias, canonical in aliases.items():
        has_alias = alias in part.columns
        has_canonical = canonical in part.columns
        if has_alias and not has_canonical:
            rename[alias] = canonical
        elif has_alias and has_canonical:
            drop.append(alias)
    return part.rename(columns=rename).drop(columns=drop)


def _stage(dataset: str) -> str | None:
    name = dataset.casefold()
    if "outcome" in name:
        return "outcomes"
    if name == "games" or name.endswith("_games"):
        return "silver_games"
    if "reconciled_team_game" in name:
        return "reconciled_team_game"
    if "team_game" in name or "game_stats" in name:
        return "game_stats"
    if "byplay" in name:
        return "byplay"
    if "drive" in name:
        return "drives"
    if "snapshot" in name:
        return "snapshots"
    if "measurement" in name and "state" not in name:
        return "measurements"
    if "state" in name:
        return "team_states"
    if "prediction" in name:
        return "predictions"
    if "play" in name:
        return "plays"
    return None


def _source_comparison(config: dict[str, Any]) -> dict[str, Any]:
    assessments = {
        "cfbd": {
            "monthly_cost_usd": 4.0,
            "published_comparable_tier_usd": 5.0,
            "automation": "documented REST API and installed typed Python client",
            "timing": "endpoint-dependent; capture timestamps must be stored",
            "terms": "commercial use permitted; raw-data redistribution prohibited",
            "maintenance": "low",
            "recommendation": "retain existing subscription and audit endpoint coverage before adding a source",
        },
        "ncaa_stats_and_team_sites": {
            "monthly_cost_usd": 0.0,
            "automation": "no single stable documented aggregate API",
            "timing": "school and NCAA publication timing varies",
            "terms": "site-specific review required before automated collection",
            "maintenance": "high",
            "recommendation": "verification source only; do not make a recurring dependency",
        },
        "noaa_ncei": {
            "monthly_cost_usd": 0.0,
            "automation": "documented HTTPS Access Data Service",
            "timing": "historical station observations; not a pregame forecast feed",
            "terms": "US government data service",
            "maintenance": "medium due to venue-to-station mapping",
            "recommendation": "candidate historical-weather verification source",
        },
        "open_meteo": {
            "monthly_cost_usd": 0.0,
            "automation": "documented forecast and historical APIs",
            "timing": "forecast archives require explicit retrieval timestamps",
            "terms": "free/open-access limits and attribution terms require confirmation for product use",
            "maintenance": "medium due to venue coordinates and forecast-cutoff capture",
            "recommendation": "candidate weather source after a Phase 2 timing proof",
        },
        "sportsdataio": {
            "monthly_cost_usd": None,
            "automation": "documented commercial NCAA football API",
            "timing": "commercial feed",
            "terms": "license and quote required",
            "maintenance": "medium",
            "recommendation": "reject unless a written quote fits the remaining $11/month budget",
        },
        "sportradar": {
            "monthly_cost_usd": None,
            "automation": "documented commercial NCAA football API",
            "timing": "commercial feed",
            "terms": "license and quote required",
            "maintenance": "medium",
            "recommendation": "reject unless a written quote fits the remaining $11/month budget",
        },
    }
    rows = []
    for source in config["source_candidates"]:
        rows.append({**source, **assessments[str(source["source_id"])]})
    return {
        "schema_version": "data_first_source_comparison_v1",
        "retrieved_on": "2026-09-05",
        "existing_monthly_cost_usd": float(config["existing_monthly_cost_usd"]),
        "maximum_monthly_cost_usd": float(config["maximum_monthly_cost_usd"]),
        "remaining_budget_usd": float(
            config["maximum_monthly_cost_usd"] - config["existing_monthly_cost_usd"]
        ),
        "sources": rows,
        "purchase_authorized": False,
    }


def _issue_subject(value: dict[str, Any]) -> tuple[str, str, str]:
    evidence = dict(value.get("evidence") or {})
    audit = dict(evidence.get("audit") or {})
    return (
        str(value.get("category") or ""),
        str(evidence.get("version_id") or audit.get("version_id") or ""),
        str(evidence.get("stage") or ""),
    )


def _issue_crosswalk(
    prior: list[dict[str, Any]], current: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    current_by_subject: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(
        list
    )
    for item in current:
        current_by_subject[_issue_subject(item)].append(item)
    rows = []
    for item in prior:
        matches = current_by_subject.get(_issue_subject(item), [])
        rows.append(
            {
                "prior_issue_id": item.get("issue_id"),
                "prior_category": item.get("category"),
                "disposition": "retained" if matches else "resolved_or_reclassified",
                "current_issue_ids": sorted(
                    str(match["issue_id"]) for match in matches
                ),
            }
        )
    return rows


def audit_evidence(
    *,
    config: dict[str, Any],
    resolved: dict[str, Any],
    storage,
) -> dict[str, Any]:
    require_resolved_manifest(resolved)
    reader = ReadOnlyStorage(storage)
    inventory: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    stage_ids: dict[str, set[int]] = defaultdict(set)
    stage_version_ids: dict[tuple[str, str], set[int]] = {}
    stage_game_seasons: dict[str, dict[int, set[int]]] = defaultdict(
        lambda: defaultdict(set)
    )
    frames: dict[str, pd.DataFrame] = {}
    readable_versions: set[str] = set()
    descendants = {
        version: transitive_descendants(version, resolved["lineage_edges"])
        for version in {str(row["version_id"]) for row in resolved.get("datasets", [])}
        | {str(row["parent_version_id"]) for row in resolved.get("lineage_edges", [])}
    }

    for gap in resolved.get("registration_gaps", []):
        version_id = str(gap["version_id"])
        issues.append(
            issue(
                "catalog-registration-missing",
                status="verified",
                severity="high",
                evidence=gap,
                affected_records=None,
                affected_descendants=[version_id, *descendants.get(version_id, [])],
                root_cause_status="reproduced",
                certification_impact=(
                    "The exact object is checksum-verified but cannot be admitted until "
                    "its immutable metadata is registered or explicitly quarantined."
                ),
                phase2_action="Register only from a complete verified manifest.",
            )
        )

    for blocker in resolved.get("blockers", []):
        version_id = str(blocker.get("version_id") or "")
        issues.append(
            issue(
                "unresolved-lineage",
                status="verified",
                severity="high",
                evidence=blocker,
                affected_records=None,
                affected_descendants=(
                    [version_id, *descendants.get(version_id, [])] if version_id else []
                ),
                root_cause_status="unresolved",
                certification_impact="Blocks the affected root and descendants.",
                phase2_action="Resolve or recapture the exact missing immutable evidence.",
            )
        )

    for row in resolved["datasets"]:
        version_id = str(row["version_id"])
        ref = DatasetRef(
            dataset=str(row["dataset"]),
            version_id=version_id,
            schema_version=str(row["schema_version"]),
            content_sha=str(row["content_sha"]),
            uri=str(row["uri"]),
        )
        try:
            frame = read_dataset(reader, ref)
            frames[version_id] = frame
            readable_versions.add(version_id)
            audit = frame_audit(
                frame,
                dataset=ref.dataset,
                key_columns=_key_columns(
                    ref.dataset, ref.schema_version, frame, require_declared=True
                ),
            )
            exposure_columns = [
                column
                for column in frame
                if column in {"primary_exposure", "games_exposure"}
                or column.endswith("_exposure")
            ]
            semantics = numeric_semantics_audit(frame, exposures=exposure_columns)
            row_count_match = int(row["row_count"]) == len(frame)
            inventory.append(
                {
                    **{
                        key: row.get(key)
                        for key in (
                            "version_id",
                            "dataset",
                            "tier",
                            "schema_version",
                            "content_sha",
                            "uri",
                            "row_count",
                            "as_of",
                            "state",
                        )
                    },
                    **audit,
                    "numeric_semantics": canonical_json(semantics).decode(),
                    "manifest_row_count": int(row["row_count"]),
                    "row_count_matches": row_count_match,
                    "parent_count": len(row.get("parent_versions", [])),
                    "source_capture_count": len(row.get("source_capture_ids", [])),
                }
            )
            stage = _stage(ref.dataset)
            if stage:
                ids = _game_ids(frame)
                stage_ids[stage].update(ids)
                stage_version_ids[(stage, version_id)] = ids
                if {"season", "game_id"}.issubset(frame):
                    key_rows = frame[["game_id", "season"]].dropna().drop_duplicates()
                    for game_id, season in key_rows.itertuples(index=False, name=None):
                        stage_game_seasons[stage][int(game_id)].add(int(season))
            if (
                not row_count_match
                or audit["duplicate_key_rows"]
                or audit["infinite_numeric_values"]
                or audit["forbidden_2020"]
            ):
                issues.append(
                    issue(
                        "dataset-correctness",
                        status="verified",
                        severity="critical" if audit["forbidden_2020"] else "high",
                        evidence={
                            "version_id": version_id,
                            "audit": audit,
                            "row_count_matches": row_count_match,
                        },
                        affected_records=int(len(frame)),
                        affected_descendants=[
                            version_id,
                            *descendants.get(version_id, []),
                        ],
                        root_cause_status="reproduced",
                        certification_impact="Blocks this dataset from certification.",
                        phase2_action="Repair under a new dataset identity and rebuild descendants.",
                    )
                )
            negative_exposure = sum(
                int((pd.to_numeric(frame[column], errors="coerce") < 0).sum())
                for column in exposure_columns
            )
            if negative_exposure:
                issues.append(
                    issue(
                        "invalid-exposure",
                        status="verified",
                        severity="high",
                        evidence={
                            "version_id": version_id,
                            "negative_rows": negative_exposure,
                        },
                        affected_records=negative_exposure,
                        affected_descendants=[version_id],
                        root_cause_status="reproduced",
                        certification_impact="Blocks measurement use until the exposure unit is corrected.",
                        phase2_action="Repair negative exposures under a new measurement identity.",
                    )
                )
        except Exception as exc:
            inventory.append(
                {
                    "version_id": version_id,
                    "dataset": ref.dataset,
                    "uri": ref.uri,
                    "state": "unreadable",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            issues.append(
                issue(
                    "unreadable-dataset",
                    status="verified",
                    severity="critical",
                    evidence={"version_id": version_id, "error": str(exc)},
                    affected_records=int(row.get("row_count") or 0),
                    affected_descendants=[],
                    root_cause_status="reproduced",
                    certification_impact="Blocks this dataset and descendants.",
                    phase2_action="Recapture or rebuild under a new identity after root-cause analysis.",
                )
            )

    games_parts: list[pd.DataFrame] = []
    teams_parts: list[pd.DataFrame] = []
    capture_inventory: list[dict[str, Any]] = []
    games_aliases = {"year": "season", "id": "game_id"}
    teams_aliases = {"year": "season", "school": "team"}
    for raw_capture in resolved["source_captures"]:
        capture = _source_capture(raw_capture)
        entity = capture.entity.casefold()
        should_read = any(
            token in entity for token in ("games", "teams", "plays", "game_stats")
        )
        capture_inventory.append(
            {
                "capture_id": capture.capture_id,
                "provider": capture.provider,
                "entity": capture.entity,
                "captured_at": capture.captured_at.isoformat(),
                "effective_at": capture.effective_at.isoformat()
                if capture.effective_at
                else None,
                "row_count": capture.row_count,
                "uri": capture.uri,
                "state": capture.state,
                "season_type": capture.request.get("parameters", capture.request).get(
                    "season_type"
                ),
            }
        )
        if not should_read:
            continue
        try:
            frame = read_source_capture(reader, capture)
        except Exception as exc:
            issues.append(
                issue(
                    "unreadable-source-capture",
                    status="verified",
                    severity="critical",
                    evidence={"capture_id": capture.capture_id, "error": str(exc)},
                    affected_records=capture.row_count,
                    affected_descendants=[],
                    root_cause_status="reproduced",
                    certification_impact="Blocks dependent datasets.",
                    phase2_action="Recapture the source request under an authentic timestamp.",
                )
            )
            continue
        if "games" in entity and "game_stats" not in entity:
            if not frame.empty:
                part = _canonical_columns(frame.copy(), games_aliases)
                part["__captured_at"] = capture.captured_at
                games_parts.append(part)
        elif "teams" in entity:
            if not frame.empty:
                teams_parts.append(_canonical_columns(frame, teams_aliases))
        if "plays" in entity:
            stage_ids["plays"].update(_game_ids(frame))
        if "game_stats" in entity:
            stage_ids["game_stats"].update(_game_ids(frame))

    schedule = pd.DataFrame()
    coverage = pd.DataFrame()
    version_coverage = pd.DataFrame()
    exclusions = pd.DataFrame()
    if games_parts:
        raw_games = pd.concat(games_parts, ignore_index=True)
        raw_games["season"] = pd.to_numeric(raw_games["season"], errors="coerce")
        raw_games = raw_games[raw_games["season"].isin(DEVELOPMENT_SEASONS)]
        raw_games = raw_games.sort_values("__captured_at").drop_duplicates(
            ["season", "game_id"], keep="last"
        )
        raw_teams = pd.concat(teams_parts, ignore_index=True) if teams_parts else None
        schedule, classification_conflicts = classify_schedule(raw_games, raw_teams)
        schedule = add_team_experience(schedule)
        kickoff_by_game = dict(
            zip(schedule["game_id"].astype(int), schedule["kickoff_utc"], strict=True)
        )
        for version_id, frame in frames.items():
            timing = pregame_timing_audit(frame, kickoff_by_game=kickoff_by_game)
            for row in inventory:
                if row.get("version_id") == version_id:
                    row["pregame_timing_rows"] = timing["pregame_rows"]
                    row["reconstructed_timing_rows"] = timing[
                        "postgame_or_reconstructed_rows"
                    ]
                    row["unresolved_timing_rows"] = timing["unresolved_rows"]
                    break
        own_timing = {}
        for row in inventory:
            version_id = row.get("version_id")
            if not version_id:
                continue
            total = int(row.get("rows") or 0)
            pregame = int(row.get("pregame_timing_rows") or 0)
            reconstructed = int(row.get("reconstructed_timing_rows") or 0)
            unresolved = int(row.get("unresolved_timing_rows") or 0)
            if total and pregame == total:
                own_timing[str(version_id)] = "authentic_pregame"
            elif reconstructed:
                own_timing[str(version_id)] = "reconstructed"
            elif unresolved or total:
                own_timing[str(version_id)] = "unresolved"
        inherited_timing = propagate_timing_classes(
            own_timing, resolved["lineage_edges"]
        )
        for row in inventory:
            if row.get("version_id"):
                row["timing_class"] = inherited_timing.get(
                    str(row["version_id"]), "unresolved"
                )
        stage_ids = {
            "captured_schedule": set(schedule["game_id"].astype(int)),
            **stage_ids,
        }
        coverage, exclusions = stage_coverage(schedule, stage_ids)
        version_parts = []
        for (stage, version_id), game_ids in sorted(stage_version_ids.items()):
            part, _ = stage_coverage(schedule, {stage: game_ids})
            part["dataset_version_id"] = version_id
            version_parts.append(part)
        version_coverage = (
            pd.concat(version_parts, ignore_index=True)
            if version_parts
            else pd.DataFrame()
        )
        for stage, game_ids in sorted(stage_ids.items()):
            if stage == "captured_schedule":
                continue
            stage_frame = pd.DataFrame({"game_id": sorted(game_ids)})
            join = join_cardinality_audit(
                schedule[["game_id"]], stage_frame, keys=("game_id",)
            )
            if join["right_only_keys"]:
                outside_ids = sorted(game_ids - set(schedule["game_id"].astype(int)))
                outside_seasons = sorted(
                    {
                        season
                        for game_id in outside_ids
                        for season in stage_game_seasons.get(stage, {}).get(
                            game_id, set()
                        )
                    }
                )
                by_design = (
                    bool(outside_seasons)
                    and set(outside_seasons).isdisjoint(DEVELOPMENT_SEASONS)
                    and 2020 not in outside_seasons
                )
                issues.append(
                    issue(
                        "downstream-game-outside-denominator",
                        status="accepted-limitation" if by_design else "verified",
                        severity="low" if by_design else "high",
                        evidence={
                            "stage": stage,
                            "join": join,
                            "outside_seasons": outside_seasons,
                            "outside_game_id_examples": outside_ids[:100],
                            "classification": (
                                "outside_development_scope"
                                if by_design
                                else "unresolved"
                            ),
                        },
                        affected_records=int(join["right_only_keys"]),
                        affected_descendants=[stage],
                        root_cause_status="reproduced",
                        certification_impact=(
                            "No impact on development coverage."
                            if by_design
                            else "Blocks coverage certification for the stage."
                        ),
                        phase2_action=(
                            "Preserve as an explicit out-of-scope disposition."
                            if by_design
                            else "Repair the stage join or denominator lineage under new identities."
                        ),
                    )
                )
        if classification_conflicts:
            issues.append(
                issue(
                    "classification-disagreement",
                    status="verified",
                    severity="high",
                    evidence={
                        "examples": classification_conflicts[:25],
                        "count": len(classification_conflicts),
                    },
                    affected_records=len(classification_conflicts),
                    affected_descendants=["population denominator"],
                    root_cause_status="reproduced",
                    certification_impact="Affected games remain visible but classification is unresolved.",
                    phase2_action="Publish a versioned season/team classification correction.",
                )
            )
        fcs_count = int(schedule["population"].eq("fbs_fcs").sum())
        if fcs_count and not stage_ids.get("silver_games", set()).issuperset(
            set(
                schedule.loc[schedule["population"].eq("fbs_fcs"), "game_id"].astype(
                    int
                )
            )
        ):
            issues.append(
                issue(
                    "silver-fbs-fcs-exclusion",
                    status="verified",
                    severity="critical",
                    evidence={"fbs_fcs_schedule_games": fcs_count},
                    affected_records=fcs_count,
                    affected_descendants=["measurements", "team_states", "predictions"],
                    root_cause_status="reproduced",
                    certification_impact="Blocks full-population certification.",
                    phase2_action="Create a new FBS-involved Silver schedule version without changing production games_v1.",
                )
            )
    else:
        issues.append(
            issue(
                "schedule-denominator-missing",
                status="verified",
                severity="critical",
                evidence={"games_capture_count": 0},
                affected_records=None,
                affected_descendants=["all coverage reports"],
                root_cause_status="unresolved",
                certification_impact="Blocks full-population certification.",
                phase2_action="Resolve or recapture an all-season FBS-involved schedule.",
            )
        )

    postseason_requests = [
        row
        for row in capture_inventory
        if str(row.get("season_type") or "").casefold() in {"postseason", "both"}
    ]
    if not postseason_requests:
        issues.append(
            issue(
                "postseason-capture-gap",
                status="verified",
                severity="critical",
                evidence={"postseason_requests": 0},
                affected_records=None,
                affected_descendants=[
                    "schedule denominator",
                    "plays",
                    "game_stats",
                    "measurements",
                ],
                root_cause_status="reproduced",
                certification_impact="The complete approved population cannot be counted.",
                phase2_action="Boundedly capture postseason schedules, plays, and stats under new identities.",
            )
        )

    root_states = {row["root_id"]: row["state"] for row in resolved["roots"]}
    roots_to_versions = resolved["root_dataset_versions"]
    root_blockers: set[str] = {
        str(blocker["root_id"])
        for blocker in resolved.get("blockers", [])
        if blocker.get("root_id")
    }
    for blocker in resolved.get("blockers", []):
        blocked_version = blocker.get("version_id")
        if blocked_version:
            root_blockers.update(
                root
                for root, versions in roots_to_versions.items()
                if str(blocked_version) in set(map(str, versions))
            )
    root_payloads: dict[str, dict[str, Any]] = {}
    for spec in config["roots"]:
        if spec["kind"] != "json" or root_states.get(spec["root_id"]) != "resolved":
            continue
        try:
            root_payloads[spec["root_id"]], _ = _read_json(reader, spec["uri"])
        except Exception:
            pass

    dispositions = []
    metric_tables: list[pd.DataFrame] = []
    metric_comparisons: list[dict[str, Any]] = []
    dataset_names = {
        str(row["version_id"]): str(row["dataset"])
        for row in resolved.get("datasets", [])
    }
    outcome_frames = [
        frame
        for version, frame in frames.items()
        if _stage(dataset_names.get(version, "")) == "outcomes"
    ]
    immutable_labels = (
        pd.concat(outcome_frames, ignore_index=True)
        if outcome_frames
        else pd.DataFrame()
    )
    for result in config["results"]:
        required_roots = list(result["required_roots"])
        lineage_ok = all(
            root_states.get(root) == "resolved" and root not in root_blockers
            for root in required_roots
        )
        versions = {
            version
            for root in required_roots
            for version in roots_to_versions.get(root, [])
        }
        readable = (
            lineage_ok
            and bool(versions)
            and all(version in readable_versions for version in versions)
        )
        row_counts_match = (
            all(
                row.get("row_count_matches", False)
                for row in inventory
                if row.get("version_id") in versions
            )
            if versions
            else lineage_ok
        )
        metric_ok = result["evidence_mode"] == "integrity_counts"
        reasons: list[str] = []
        if result["evidence_mode"] == "prediction_metrics":
            tables = []
            for version in versions:
                if version in frames:
                    labeled = attach_prediction_labels(
                        frames[version], immutable_labels
                    )
                    metrics = recompute_prediction_metrics(labeled)
                    if not metrics.empty:
                        metrics["result_id"] = result["result_id"]
                        tables.append(metrics)
            if tables:
                combined = pd.concat(tables, ignore_index=True)
                metric_tables.append(combined)
                duplicate_rows = int(combined["duplicate_game_rows"].sum())
                nonfinite_rows = int(combined["nonfinite_rows"].sum())
                if duplicate_rows:
                    issues.append(
                        issue(
                            "evaluator-stacked-row-semantics",
                            status="verified",
                            severity="high",
                            evidence={
                                "result_id": result["result_id"],
                                "duplicate_game_rows": duplicate_rows,
                                "actual_evaluator_semantics": "counts_input_rows",
                                "audit_semantics": "unique_game_only",
                            },
                            affected_records=duplicate_rows,
                            affected_descendants=sorted(versions),
                            root_cause_status="reproduced",
                            certification_impact="Blocks the reported metric until its sampling unit is corrected.",
                            phase2_action="Recompute one row per game with a game-level paired bootstrap.",
                        )
                    )
                if nonfinite_rows:
                    issues.append(
                        issue(
                            "prediction-nonfinite",
                            status="verified",
                            severity="high",
                            evidence={
                                "result_id": result["result_id"],
                                "nonfinite_rows": nonfinite_rows,
                            },
                            affected_records=nonfinite_rows,
                            affected_descendants=sorted(versions),
                            root_cause_status="reproduced",
                            certification_impact="Blocks reported metrics containing non-finite predictions or labels.",
                            phase2_action="Quarantine non-finite rows and recompute the declared population.",
                        )
                    )
                claims = [
                    claim
                    for root in required_roots
                    for claim in reported_metric_claims(root_payloads.get(root, {}))
                ]
                metric_ok, comparisons = match_reported_metrics(
                    combined,
                    claims,
                    tolerance=float(config["metric_tolerance"]),
                )
                metric_comparisons.append(
                    {
                        "result_id": result["result_id"],
                        "claim_count": len(claims),
                        "comparisons": comparisons,
                    }
                )
                if not metric_ok:
                    reasons.append(
                        "reported MAE claims did not match recomputed immutable rows"
                    )
            else:
                readable = False
                metric_ok = False
                reasons.append(
                    "no immutable prediction-and-label rows were available for recomputation"
                )
        defect = any(
            item["severity"] in {"critical", "high"}
            and bool(versions & set(item.get("affected_descendants", [])))
            for item in issues
        )
        dispositions.append(
            result_disposition(
                result_id=str(result["result_id"]),
                lineage_resolved=lineage_ok,
                evidence_readable=readable,
                counts_match=row_counts_match,
                metrics_match_report=metric_ok,
                correctness_defect=defect,
                modeling_status=str(result["modeling_status"]),
                reasons=reasons,
            )
        )

    metrics_frame = (
        pd.concat(metric_tables, ignore_index=True) if metric_tables else pd.DataFrame()
    )
    hypotheses = _hypothesis_map(schedule, metrics_frame)
    blockers = [item for item in issues if item["severity"] in {"critical", "high"}]
    prior_issues: list[dict[str, Any]] = []
    prior_prefix = str(config.get("prior_audit_prefix") or "").rstrip("/")
    if prior_prefix:
        try:
            prior_payload, _ = _read_json(reader, f"{prior_prefix}/issue-register.json")
            prior_issues = list(prior_payload.get("issues") or [])
        except Exception as exc:
            issues.append(
                issue(
                    "prior-audit-unreadable",
                    status="verified",
                    severity="high",
                    evidence={"uri": prior_prefix, "error": str(exc)},
                    affected_records=None,
                    affected_descendants=[],
                    root_cause_status="reproduced",
                    certification_impact="Blocks correction crosswalk completion.",
                    phase2_action="Restore the exact prior audit artifact.",
                )
            )
            blockers = [
                item for item in issues if item["severity"] in {"critical", "high"}
            ]
    crosswalk = _issue_crosswalk(prior_issues, issues)
    summary = {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "state": "complete_with_blockers" if blockers else "complete",
        "run_id": resolved["run_id"],
        "as_of": resolved["as_of"],
        "code_sha": resolved["code_sha"],
        "resolved_manifest_sha256": resolved["manifest_sha256"],
        "dataset_count": len(inventory),
        "source_capture_count": len(capture_inventory),
        "schedule_game_count": int(len(schedule)),
        "issue_count": len(issues),
        "blocking_issue_count": len(blockers),
        "result_status_counts": pd.Series(
            [row["evidence_status"] for row in dispositions]
        )
        .value_counts()
        .to_dict(),
        "phase2_issue_ids": sorted(item["issue_id"] for item in blockers),
    }
    return {
        "inventory": pd.DataFrame(inventory + capture_inventory),
        "schedule": schedule,
        "lineage_edges": pd.DataFrame(resolved["lineage_edges"]),
        "coverage": coverage,
        "version_coverage": version_coverage,
        "exclusions": exclusions,
        "issues": sorted(issues, key=lambda row: row["issue_id"]),
        "dispositions": sorted(dispositions, key=lambda row: row["result_id"]),
        "hypotheses": hypotheses,
        "metric_comparisons": metric_comparisons,
        "issue_crosswalk": crosswalk,
        "source_comparison": _source_comparison(config),
        "summary": summary,
    }


def _key_columns(
    dataset: str,
    schema_version: str,
    frame: pd.DataFrame,
    *,
    require_declared: bool = False,
) -> list[str]:
    candidates = {
        "games": ["season", "game_id"],
        "game_outcomes": ["season", "game_id"],
        "plays": ["game_id", "play_id"],
        "byplay": ["game_id", "drive_number", "play_number"],
        "drives": ["game_id", "drive_number", "offense", "defense"],
        "reconciled_team_game": ["season", "game_id", "team"],
        "preseason_team_inputs": ["season", "team", "as_of"],
    }
    for name, keys in candidates.items():
        if dataset == name or dataset.startswith(name):
            missing = sorted(set(keys) - set(frame))
            if missing and require_declared:
                raise ValueError(
                    f"{dataset}/{schema_version} is missing declared key columns: {missing}"
                )
            return keys if not missing else [key for key in keys if key in frame]
    return [
        key
        for key in ("season", "game_id", "team", "candidate_id", "target")
        if key in frame
    ]


def _hypothesis_map(schedule: pd.DataFrame, metrics: pd.DataFrame) -> pd.DataFrame:
    hypotheses = (
        "preseason_strength",
        "opponent_quality",
        "possession_volume",
        "scoring_efficiency",
        "roster_change",
        "sparse_opponents",
        "fbs_fcs_status",
        "first_game_status",
        "asymmetric_experience",
        "overtime",
    )
    observable = {
        "fbs_fcs_status": not schedule.empty and "population" in schedule,
        "first_game_status": not schedule.empty and "first_game_involved" in schedule,
        "asymmetric_experience": not schedule.empty
        and "asymmetric_experience" in schedule,
        "overtime": not schedule.empty and "overtime" in schedule,
    }
    rows = []
    for name in hypotheses:
        rows.append(
            {
                "hypothesis": name,
                "status": "descriptive_population_available"
                if observable.get(name, False)
                else "unavailable_in_audited_evidence",
                "prediction_metric_rows": int(len(metrics)),
                "model_selection_permitted": False,
            }
        )
    return pd.DataFrame(rows)


def _write_audit(
    writer: ImmutableAuditWriter, result: dict[str, Any]
) -> dict[str, str]:
    outputs = {
        "schedule_denominator": writer.write_bytes(
            "schedule-denominator.parquet", _parquet_bytes(result["schedule"])
        ),
        "dataset_inventory": writer.write_bytes(
            "dataset-inventory.parquet", _parquet_bytes(result["inventory"])
        ),
        "lineage_edges": writer.write_bytes(
            "lineage-edges.parquet", _parquet_bytes(result["lineage_edges"])
        ),
        "game_stage_coverage": writer.write_bytes(
            "game-stage-coverage.parquet", _parquet_bytes(result["coverage"])
        ),
        "game_stage_version_coverage": writer.write_bytes(
            "game-stage-version-coverage.parquet",
            _parquet_bytes(result["version_coverage"]),
        ),
        "exclusions": writer.write_bytes(
            "exclusions.parquet", _parquet_bytes(result["exclusions"])
        ),
        "issue_register": writer.write_json(
            "issue-register.json",
            {"schema_version": AUDIT_SCHEMA_VERSION, "issues": result["issues"]},
        ),
        "result_dispositions": writer.write_json(
            "result-dispositions.json",
            {"schema_version": AUDIT_SCHEMA_VERSION, "results": result["dispositions"]},
        ),
        "hypothesis_error_map": writer.write_bytes(
            "hypothesis-error-map.parquet", _parquet_bytes(result["hypotheses"])
        ),
        "source_comparison": writer.write_json(
            "source-comparison.json", result["source_comparison"]
        ),
        "issue_crosswalk": writer.write_json(
            "issue-crosswalk.json",
            {
                "schema_version": AUDIT_SCHEMA_VERSION,
                "issues": result["issue_crosswalk"],
            },
        ),
        "metric_comparisons": writer.write_json(
            "metric-comparisons.json",
            {
                "schema_version": AUDIT_SCHEMA_VERSION,
                "results": result["metric_comparisons"],
            },
        ),
    }
    summary = {**result["summary"], "outputs": outputs}
    summary["summary_sha256"] = sha256(canonical_json(summary))
    outputs["summary"] = writer.write_json("summary.json", summary)
    return outputs


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="stage", required=True)
    for name in ("resolve", "audit"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--environment", choices=("preview",), required=True)
        sub.add_argument("--config", default=DEFAULT_CONFIG)
        sub.add_argument("--run-id", required=True)
        sub.add_argument("--as-of", required=True)
        sub.add_argument("--expected-code-sha", required=True)
        if name == "audit":
            sub.add_argument("--resolved-manifest-uri", required=True)
    args = parser.parse_args()
    as_of = _utc(args.as_of)
    config, config_bytes = _config(args.config)
    storage, conn_url = _verify_runtime(args.expected_code_sha)
    writer = ImmutableAuditWriter(storage, run_id=args.run_id)
    if args.stage == "resolve":
        resolved = resolve_evidence(
            config=config,
            config_bytes=config_bytes,
            storage=storage,
            conn_url=conn_url,
            run_id=args.run_id,
            as_of=as_of,
            code_sha=args.expected_code_sha,
        )
        uri = writer.write_json("resolved-evidence-manifest.json", resolved)
        print(
            json.dumps(
                {
                    "state": resolved["state"],
                    "uri": uri,
                    "blockers": len(resolved["blockers"]),
                },
                sort_keys=True,
            )
        )
        return
    expected_uri = f"{writer.prefix}resolved-evidence-manifest.json"
    if args.resolved_manifest_uri != expected_uri:
        raise ValueError(f"--resolved-manifest-uri must be {expected_uri}")
    resolved, _ = _read_json(ReadOnlyStorage(storage), args.resolved_manifest_uri)
    if (
        resolved.get("run_id") != args.run_id
        or resolved.get("as_of") != as_of
        or resolved.get("code_sha") != args.expected_code_sha
    ):
        raise ValueError("audit arguments do not match the sealed resolved manifest")
    result = audit_evidence(config=config, resolved=resolved, storage=storage)
    outputs = _write_audit(writer, result)
    print(
        json.dumps(
            {"state": result["summary"]["state"], "outputs": outputs}, sort_keys=True
        )
    )


if __name__ == "__main__":
    main()
