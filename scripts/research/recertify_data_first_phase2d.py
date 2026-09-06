#!/usr/bin/env python3
"""Recertify the sealed Phase 2c corpus for Phase 3 eligibility."""

from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg
import pyarrow.parquet as pq
import yaml
from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_phase2 import DEVELOPMENT_SEASONS
from cks_picks_cfb.data.data_first_phase2d import (
    REQUIRED_STAGES,
    Phase2dError,
    canonical_bytes,
    coverage_report,
    phase2d_identity,
    sha256,
    strict_coverage_gate,
    validate_certification_inputs,
    validate_omissions,
    verify_phase2c_ref_set,
)
from cks_picks_cfb.data.evidence_audit import frame_audit
from cks_picks_cfb.data.lake import DatasetRef, SourceCapture, read_dataset
from cks_picks_cfb.data.runtime import resolve_runtime_target
from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame
from cks_picks_cfb.data.storage import get_storage

PHASE1_ROOT = "artifacts/research/data-first-football-v1/phase1"
PHASE2C_REF_SET_URI = (
    "artifacts/research/data-first-football-v1/phase2/silver/runs/"
    "2026-09-06T1437Z-phase2c-expanded-silver-v1/ref-set.json"
)
PHASE2C_REF_SET_SHA256 = (
    "b3023ab5b7a304ddbc81ae2feca56238959520a54b3a75ed9be136f5d8f51df3"
)
DEFAULT_CONFIG = "conf/research/data_first_football_v1/phase2d_audit_v2.yaml"


def _git_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _tracked_worktree_clean() -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and not result.stdout.strip()


def _utc(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise Phase2dError("--as-of must be an explicit UTC timestamp")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _immutable_json(storage, uri: str, value: dict[str, Any]) -> None:
    payload = canonical_bytes(value)
    if storage.exists(uri):
        if storage.read_bytes(uri) != payload:
            raise FileExistsError(f"immutable Phase 2d artifact collision: {uri}")
        return
    storage.write_bytes(payload, uri)


def _catalog_ref(conn, ref: DatasetRef) -> tuple[list[str], list[str]]:
    row = conn.execute(
        "SELECT dataset, schema_version, content_sha, uri FROM catalog.dataset_versions "
        "WHERE version_id = %s",
        (ref.version_id,),
    ).fetchone()
    if not row or tuple(map(str, row)) != (
        ref.dataset,
        ref.schema_version,
        ref.content_sha,
        ref.uri,
    ):
        raise Phase2dError(f"Preview catalog mismatch: {ref.version_id}")
    parents = [
        str(value[0])
        for value in conn.execute(
            "SELECT parent_version_id FROM catalog.dataset_dependencies "
            "WHERE child_version_id = %s ORDER BY ordinal",
            (ref.version_id,),
        ).fetchall()
    ]
    captures = [
        str(value[0])
        for value in conn.execute(
            "SELECT capture_id FROM catalog.dataset_capture_dependencies "
            "WHERE child_version_id = %s ORDER BY ordinal",
            (ref.version_id,),
        ).fetchall()
    ]
    return parents, captures


def _manifest(storage, ref: DatasetRef) -> tuple[dict[str, Any], str, str]:
    if not ref.uri.endswith("/data.parquet"):
        raise Phase2dError(f"noncanonical dataset URI: {ref.uri}")
    uri = f"{ref.uri[: -len('/data.parquet')]}/manifest.json"
    raw = storage.read_bytes(uri)
    value = json.loads(raw)
    for key, expected in asdict(ref).items():
        if str(value.get(key)) != str(expected):
            raise Phase2dError(f"dataset manifest mismatch for {ref.version_id}: {key}")
    return value, uri, sha256(raw)


def _capture_timing(capture) -> tuple[str, str]:
    timing = str(capture.response_metadata.get("timing_class") or "")
    timing_evidence = "response_metadata"
    if not timing:
        request_year = (capture.request.get("parameters") or {}).get("year")
        profile = capture.response_metadata.get("capture_profile")
        legacy_historical = (
            profile in {"history_source_capture_v2", "history_play_capture_v2"}
            and request_year in DEVELOPMENT_SEASONS
            and capture.captured_at.year > int(request_year)
            and capture.effective_at is None
        )
        if legacy_historical:
            timing = "historically_reconstructed"
            timing_evidence = str(profile)
    if timing not in {"historically_reconstructed", "authentic_pregame"}:
        raise Phase2dError(f"source capture timing is undeclared: {capture.capture_id}")
    if timing == "historically_reconstructed" and capture.effective_at is not None:
        raise Phase2dError(
            f"reconstructed capture has an effective time: {capture.capture_id}"
        )
    if timing == "authentic_pregame" and capture.effective_at != capture.captured_at:
        raise Phase2dError(f"pregame capture timing mismatch: {capture.capture_id}")
    return timing, timing_evidence


def _capture_from_catalog(conn, capture_id: str) -> SourceCapture:
    row = conn.execute(
        "SELECT provider,entity,captured_at,effective_at,request,content_sha,"
        "object_sha,uri,row_count,provider_api_version,response_metadata,state "
        "FROM catalog.source_captures WHERE capture_id=%s",
        (capture_id,),
    ).fetchone()
    if not row:
        raise Phase2dError(f"source capture is absent from catalog: {capture_id}")
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


def _capture_evidence(storage, conn, capture_id: str) -> dict[str, Any]:
    capture = _capture_from_catalog(conn, capture_id)
    if capture.state != "registered":
        raise Phase2dError(f"source capture is not registered: {capture_id}")
    payload = storage.read_bytes(capture.uri)
    if sha256(payload) != capture.object_sha:
        raise Phase2dError(f"source capture object checksum mismatch: {capture_id}")
    if pq.ParquetFile(io.BytesIO(payload)).metadata.num_rows != capture.row_count:
        raise Phase2dError(f"source capture row-count mismatch: {capture_id}")
    timing, timing_evidence = _capture_timing(capture)
    return {
        "capture_id": capture.capture_id,
        "provider": capture.provider,
        "entity": capture.entity,
        "captured_at": capture.captured_at.isoformat(),
        "effective_at": capture.effective_at.isoformat()
        if capture.effective_at
        else None,
        "request": dict(capture.request),
        "content_sha": capture.content_sha,
        "object_sha": capture.object_sha,
        "uri": capture.uri,
        "row_count": capture.row_count,
        "timing_class": timing,
        "timing_evidence": timing_evidence,
    }


def _audit_ref(
    storage,
    conn,
    ref_value: dict[str, Any],
    capture_cache: dict[str, dict[str, Any]],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    ref = DatasetRef(**ref_value)
    frame = read_dataset(storage, ref)
    schema = schema_for(ref.dataset, ref.schema_version)
    validate_frame(frame, schema)
    audit = frame_audit(frame, dataset=ref.dataset, key_columns=schema.keys)
    if (
        audit["duplicate_key_rows"]
        or audit["infinite_numeric_values"]
        or audit["forbidden_2020"]
    ):
        raise Phase2dError(f"dataset correctness failed: {ref.version_id}")
    parents, captures = _catalog_ref(conn, ref)
    manifest, manifest_uri, manifest_raw_sha256 = _manifest(storage, ref)
    if list(manifest.get("parent_versions") or []) != parents:
        raise Phase2dError(f"catalog parent mismatch: {ref.version_id}")
    if list(manifest.get("source_capture_ids") or []) != captures:
        raise Phase2dError(f"catalog capture mismatch: {ref.version_id}")
    capture_evidence = []
    for capture_id in captures:
        if capture_id not in capture_cache:
            capture_cache[capture_id] = _capture_evidence(storage, conn, capture_id)
        capture_evidence.append(capture_cache[capture_id])
    return frame, {
        **ref_value,
        "row_count": len(frame),
        "parent_versions": parents,
        "source_capture_ids": captures,
        "source_captures": capture_evidence,
        "manifest_uri": manifest_uri,
        "manifest_raw_sha256": manifest_raw_sha256,
        "lineage_timing_class": (
            "authentic_pregame"
            if capture_evidence
            and all(
                row["timing_class"] == "authentic_pregame" for row in capture_evidence
            )
            else "historically_reconstructed"
        ),
        "semantic_availability": "postgame",
    }


def _omission_summary(
    entries: list[dict[str, Any]], games: pd.DataFrame
) -> dict[str, Any]:
    game_type = {
        int(row.game_id): str(row.season_type)
        for row in games[["game_id", "season_type"]].itertuples(index=False)
    }
    play_rows: list[dict[str, Any]] = []
    stat_rows: list[dict[str, Any]] = []
    for entry in entries:
        season = int(entry["season"])
        omissions = entry.get("omissions") or {}
        declared_reasons = omissions.get("reasons") or {}
        expected_play_reasons = [
            {
                "game_id": int(game_id),
                "reason": "provider_response_omission",
            }
            for game_id in omissions.get("missing_play_game_ids") or []
        ]
        expected_stat_reasons = [
            {
                "game_id": int(game_id),
                "reason": "provider_response_omission",
            }
            for game_id in omissions.get("missing_stat_game_ids") or []
        ]
        if list(declared_reasons.get("plays") or []) != expected_play_reasons:
            raise Phase2dError(f"Phase 2c play omission reasons drifted for {season}")
        if list(declared_reasons.get("team_game_stats") or []) != expected_stat_reasons:
            raise Phase2dError(f"Phase 2c stat omission reasons drifted for {season}")
        for game_id in omissions.get("missing_play_game_ids") or []:
            if game_type.get(int(game_id)) != "regular":
                raise Phase2dError("postseason play omission is not eligible")
            play_rows.append(
                {
                    "season": season,
                    "game_id": int(game_id),
                    "season_type": "regular",
                    "reason": "provider_response_omission",
                }
            )
        for game_id in omissions.get("missing_stat_game_ids") or []:
            if game_type.get(int(game_id)) != "regular":
                raise Phase2dError("postseason stat omission is not eligible")
            stat_rows.append(
                {
                    "season": season,
                    "game_id": int(game_id),
                    "season_type": "regular",
                    "reason": "provider_response_omission",
                }
            )
    if (len(play_rows), len(stat_rows)) != (32, 1):
        raise Phase2dError(
            f"unexpected omission totals: plays={len(play_rows)}, stats={len(stat_rows)}"
        )
    return {
        "plays": sorted(play_rows, key=lambda row: (row["season"], row["game_id"])),
        "team_game_stats": sorted(
            stat_rows, key=lambda row: (row["season"], row["game_id"])
        ),
        "postseason_omissions": 0,
    }


def _historical_crosswalk(
    storage, prior_audit_prefix: str
) -> tuple[list[dict[str, Any]], str]:
    raw = storage.read_bytes(f"{prior_audit_prefix.rstrip('/')}/issue-register.json")
    payload = json.loads(raw)
    issues = []
    resolutions = {
        "catalog-registration-missing": (
            "resolved_for_certification",
            "Phase 2a registered and schema-validated the exact immutable object",
        ),
        "dataset-correctness": (
            "resolved_for_certification",
            "Phase 2c rebuilt the affected dataset and Phase 2d validates its schema and keys",
        ),
        "downstream-game-outside-denominator": (
            "resolved_for_certification",
            "Phase 2c uses the independent full FBS-involved schedule denominator",
        ),
        "postseason-capture-gap": (
            "resolved_for_certification",
            "Phase 2b captured all ten postseason schedules plus play and stat detail",
        ),
        "silver-fbs-fcs-exclusion": (
            "resolved_for_certification",
            "Phase 2c retains FBS-FCS games in its explicit population",
        ),
        "unresolved-lineage": (
            "historical_exclusion",
            "noncanonical historical parquet remains visible and is not a Phase 2c input",
        ),
    }
    for issue in payload.get("issues") or []:
        category = str(issue.get("category"))
        if category not in resolutions:
            raise Phase2dError(f"uncrosswalked historical issue category: {category}")
        disposition, reason = resolutions[category]
        issues.append(
            {
                "prior_issue_id": issue.get("issue_id"),
                "category": category,
                "disposition": disposition,
                "reason": reason,
                "prior_evidence": issue.get("evidence"),
                "affected_descendants": issue.get("affected_descendants") or [],
            }
        )
    return issues, sha256(raw)


def _load_config(path: str) -> tuple[dict[str, Any], str]:
    raw = Path(path).read_bytes()
    config = yaml.safe_load(raw)
    if not isinstance(config, dict):
        raise Phase2dError("Phase 2d config must be a mapping")
    if config.get("schema_version") != "data_first_phase2d_audit_v2":
        raise Phase2dError("Phase 2d config has the wrong schema version")
    if config.get("environment") != "preview":
        raise Phase2dError("Phase 2d config must require Preview")
    if tuple(config.get("development_seasons") or ()) != tuple(DEVELOPMENT_SEASONS):
        raise Phase2dError("Phase 2d config has the wrong development seasons")
    if tuple(config.get("forbidden_seasons") or ()) != (2020,):
        raise Phase2dError("Phase 2d config must forbid 2020")
    if set(config.get("required_stages") or ()) != REQUIRED_STAGES:
        raise Phase2dError("Phase 2d config has the wrong required stages")
    if tuple(config.get("season_types") or ()) != ("regular", "postseason"):
        raise Phase2dError("Phase 2d config has the wrong season types")
    if config.get("population") != "fbs_involved":
        raise Phase2dError("Phase 2d config has the wrong population")
    thresholds = config.get("coverage_thresholds") or {}
    expected = {
        "comparison": "strictly_greater_than",
        "fbs_fbs": 0.95,
        "fbs_fcs": 0.90,
        "outcomes": 1.0,
        "source_reconciliation": 1.0,
        "postseason_detail": 1.0,
    }
    if thresholds != expected:
        raise Phase2dError("Phase 2d config coverage thresholds have drifted")
    if (config.get("historical_issue_dispositions") or {}) != {
        "catalog-registration-missing": "resolved_by_phase2a_registration",
        "dataset-correctness": "resolved_by_phase2c_rebuild",
        "downstream-game-outside-denominator": "resolved_by_phase2c_denominator",
        "postseason-capture-gap": "resolved_by_phase2b_capture",
        "silver-fbs-fcs-exclusion": "resolved_by_phase2c_population",
        "unresolved-lineage": "historical_exclusion",
    }:
        raise Phase2dError("Phase 2d historical issue dispositions have drifted")
    omission = config.get("omission_policy") or {}
    if (
        omission.get("permitted_reason") != "provider_response_omission"
        or omission.get("expected_counts") != {"plays": 32, "team_game_stats": 1}
        or omission.get("postseason_omissions") != "blocking"
    ):
        raise Phase2dError("Phase 2d omission policy has drifted")
    return config, sha256(raw)


def build_recertification(
    *, storage, conn_url: str, args, config: dict[str, Any], config_sha256: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    raw_refset = storage.read_bytes(args.phase2c_ref_set_uri)
    refset = json.loads(raw_refset)
    if refset.get("manifest_sha256") != PHASE2C_REF_SET_SHA256:
        raise Phase2dError("Phase 2c ref set does not match the pinned checksum")
    entries = verify_phase2c_ref_set(refset)
    certification_root = config.get("certification_root") or {}
    if (
        args.phase2c_ref_set_uri != certification_root.get("phase2c_ref_set_uri")
        or refset.get("manifest_sha256")
        != certification_root.get("phase2c_ref_set_sha256")
        or certification_root.get("follow_policy") != "no_follow"
    ):
        raise Phase2dError("Phase 2d certification root does not match config")
    prior_audit_prefix = str(config.get("prior_audit_prefix") or "")
    crosswalk, prior_audit_sha = _historical_crosswalk(storage, prior_audit_prefix)
    identity = phase2d_identity(
        run_id=args.run_id,
        environment=args.environment,
        as_of=args.as_of,
        code_sha=args.expected_code_sha,
        phase2c_ref_set_uri=args.phase2c_ref_set_uri,
        phase2c_ref_set_sha256=refset["manifest_sha256"],
        phase2c_ref_set_raw_sha256=sha256(raw_refset),
        prior_audit_prefix=prior_audit_prefix,
        prior_audit_sha256=prior_audit_sha,
        config_sha256=config_sha256,
    )
    rows: list[dict[str, Any]] = []
    frames: dict[tuple[int, str], pd.DataFrame] = {}
    inputs = []
    capture_cache: dict[str, dict[str, Any]] = {}
    with psycopg.connect(conn_url) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        for entry in entries:
            season = int(entry["season"])
            for dataset, ref in sorted((entry.get("outputs") or {}).items()):
                frame, evidence = _audit_ref(storage, conn, ref, capture_cache)
                frames[(season, dataset)] = frame
                rows.append({"season": season, "dataset": dataset, **evidence})
                inputs.append({"season": season, "dataset": dataset, **evidence})
    games = pd.concat(
        [
            frames[(season, "fbs_involved_games")]
            for season in sorted({row["season"] for row in rows})
        ],
        ignore_index=True,
    )
    stage_frames = {
        dataset: pd.concat(
            [
                frames[(season, dataset)]
                for season in sorted({row["season"] for row in rows})
            ],
            ignore_index=True,
        )
        for dataset in REQUIRED_STAGES
    }
    coverage_rows = coverage_report(games, stage_frames)
    gate = strict_coverage_gate(coverage_rows)
    omissions = _omission_summary(entries, games)
    validate_certification_inputs(inputs)
    validate_omissions(omissions)
    blocking = []
    if not gate["passed"]:
        blocking.append("coverage_gate")
    if int(
        sum((entry.get("reconciliation") or {}).get("blocking", 0) for entry in entries)
    ):
        blocking.append("reconciliation")
    audit = {
        "schema_version": "data_first_phase1_audit_v2",
        "state": "complete" if not blocking else "complete_with_blockers",
        "certification_blocking_issue_count": len(blocking),
        "certification_blockers": blocking,
        "historical_exclusion_count": sum(
            row["disposition"] == "historical_exclusion" for row in crosswalk
        ),
        "identity": identity,
        "phase2c_ref_set_uri": args.phase2c_ref_set_uri,
        "phase2c_ref_set_sha256": refset["manifest_sha256"],
        "coverage_gate": gate,
        "coverage": coverage_rows,
        "omissions": omissions,
        "inputs": inputs,
        "issue_crosswalk": crosswalk,
    }
    audit["manifest_sha256"] = sha256(audit)
    return audit, identity


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("dry-run", "apply"), required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--environment", choices=("preview",), required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--phase2c-ref-set-uri", default=PHASE2C_REF_SET_URI)
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    args = parser.parse_args()
    args.as_of = _utc(args.as_of)
    if os.getenv("CFB_STORAGE_BACKEND", "").casefold() != "r2":
        raise Phase2dError("Phase 2d requires R2")
    if args.expected_code_sha != _git_sha():
        raise Phase2dError("--expected-code-sha must match HEAD")
    if args.mode == "apply" and not _tracked_worktree_clean():
        raise Phase2dError("apply requires a clean tracked worktree")
    target = resolve_runtime_target(args.environment)
    storage = get_storage(environment=args.environment)
    config, config_sha256 = _load_config(args.config)
    audit, identity = build_recertification(
        storage=storage,
        conn_url=target.database_url,
        args=args,
        config=config,
        config_sha256=config_sha256,
    )
    prefix = f"{PHASE1_ROOT}/{args.run_id}"
    if args.mode == "apply":
        _immutable_json(storage, f"{prefix}/identity.json", identity)
        _immutable_json(storage, f"{prefix}/audit-v5.json", audit)
        _immutable_json(
            storage,
            f"{prefix}/issue-crosswalk.json",
            {
                "schema_version": audit["schema_version"],
                "issues": audit["issue_crosswalk"],
            },
        )
    print(
        json.dumps(
            {
                "state": audit["state"],
                "prefix": prefix,
                "identity": identity,
                "input_count": len(audit["inputs"]),
                "coverage_gate": audit["coverage_gate"],
                "omission_counts": {
                    "plays": len(audit["omissions"]["plays"]),
                    "team_game_stats": len(audit["omissions"]["team_game_stats"]),
                    "postseason": audit["omissions"]["postseason_omissions"],
                },
                "historical_exclusion_count": audit["historical_exclusion_count"],
            },
            sort_keys=True,
            default=str,
        )
    )
    if audit["certification_blocking_issue_count"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
