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
    canonical_json,
    classify_schedule,
    extract_dataset_refs,
    frame_audit,
    issue,
    join_cardinality_audit,
    lineage_cycles,
    numeric_semantics_audit,
    pregame_timing_audit,
    recompute_prediction_metrics,
    require_resolved_manifest,
    result_disposition,
    sha256,
    stage_coverage,
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
            refs = extract_dataset_refs(payload)
            root_versions[root_id] = [ref.version_id for ref in refs]
            for ref in refs:
                initial_refs[ref.version_id] = ref
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
                    blockers.append(
                        {
                            "version_id": version_id,
                            "error": "catalog registration missing",
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


def _numeric_claims(value: Any, prefix: str = "") -> list[tuple[str, float]]:
    claims: list[tuple[str, float]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if str(key).casefold().endswith("mae") and isinstance(child, (int, float)):
                claims.append((path, float(child)))
            claims.extend(_numeric_claims(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            claims.extend(_numeric_claims(child, f"{prefix}[{index}]"))
    return claims


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
    frames: dict[str, pd.DataFrame] = {}
    readable_versions: set[str] = set()

    for blocker in resolved.get("blockers", []):
        issues.append(
            issue(
                "unresolved-lineage",
                status="verified",
                severity="high",
                evidence=blocker,
                affected_records=None,
                affected_descendants=[],
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
                frame, dataset=ref.dataset, key_columns=_key_columns(ref.dataset, frame)
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
                stage_ids[stage].update(_game_ids(frame))
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
                        affected_descendants=[],
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
            part = frame.copy()
            part["__captured_at"] = capture.captured_at
            games_parts.append(part)
        elif "teams" in entity:
            teams_parts.append(frame)
        if "plays" in entity:
            stage_ids["plays"].update(_game_ids(frame))
        if "game_stats" in entity:
            stage_ids["game_stats"].update(_game_ids(frame))

    schedule = pd.DataFrame()
    coverage = pd.DataFrame()
    exclusions = pd.DataFrame()
    if games_parts:
        raw_games = pd.concat(games_parts, ignore_index=True)
        raw_games = raw_games.rename(columns={"year": "season", "id": "game_id"})
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
        stage_ids = {
            "captured_schedule": set(schedule["game_id"].astype(int)),
            **stage_ids,
        }
        coverage, exclusions = stage_coverage(schedule, stage_ids)
        for stage, game_ids in sorted(stage_ids.items()):
            if stage == "captured_schedule":
                continue
            stage_frame = pd.DataFrame({"game_id": sorted(game_ids)})
            join = join_cardinality_audit(
                schedule[["game_id"]], stage_frame, keys=("game_id",)
            )
            if join["right_only_keys"]:
                issues.append(
                    issue(
                        "downstream-game-outside-denominator",
                        status="verified",
                        severity="high",
                        evidence={"stage": stage, "join": join},
                        affected_records=int(join["right_only_keys"]),
                        affected_descendants=[stage],
                        root_cause_status="reproduced",
                        certification_impact="Blocks coverage certification for the stage.",
                        phase2_action="Repair the stage join or denominator lineage under new identities.",
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
    for result in config["results"]:
        required_roots = list(result["required_roots"])
        lineage_ok = all(root_states.get(root) == "resolved" for root in required_roots)
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
                    metrics = recompute_prediction_metrics(frames[version])
                    if not metrics.empty:
                        metrics["result_id"] = result["result_id"]
                        tables.append(metrics)
            if tables:
                combined = pd.concat(tables, ignore_index=True)
                metric_tables.append(combined)
                claims = [
                    claim
                    for root in required_roots
                    for claim in _numeric_claims(root_payloads.get(root, {}))
                ]
                recomputed = [float(value) for value in combined["mae"].dropna()]
                metric_ok = (
                    bool(claims)
                    and bool(recomputed)
                    and all(
                        any(
                            abs(float(claimed) - value)
                            <= float(config["metric_tolerance"])
                            for _, claimed in claims
                        )
                        for value in recomputed
                    )
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
        "lineage_edges": pd.DataFrame(resolved["lineage_edges"]),
        "coverage": coverage,
        "exclusions": exclusions,
        "issues": sorted(issues, key=lambda row: row["issue_id"]),
        "dispositions": sorted(dispositions, key=lambda row: row["result_id"]),
        "hypotheses": hypotheses,
        "source_comparison": _source_comparison(config),
        "summary": summary,
    }


def _key_columns(dataset: str, frame: pd.DataFrame) -> list[str]:
    candidates = {
        "games": ["season", "game_id"],
        "game_outcomes": ["season", "game_id"],
        "plays": ["game_id", "play_id"],
        "byplay": ["game_id", "drive_number", "play_number"],
        "drives": ["game_id", "drive_number", "offense", "defense"],
        "reconciled_team_game": ["season", "game_id", "team"],
    }
    for name, keys in candidates.items():
        if dataset == name or dataset.startswith(name):
            return [key for key in keys if key in frame]
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
        "dataset_inventory": writer.write_bytes(
            "dataset-inventory.parquet", _parquet_bytes(result["inventory"])
        ),
        "lineage_edges": writer.write_bytes(
            "lineage-edges.parquet", _parquet_bytes(result["lineage_edges"])
        ),
        "game_stage_coverage": writer.write_bytes(
            "game-stage-coverage.parquet", _parquet_bytes(result["coverage"])
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
