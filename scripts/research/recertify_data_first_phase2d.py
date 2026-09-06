#!/usr/bin/env python3
"""Recertify the sealed Phase 2c corpus for Phase 3 eligibility."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import psycopg
from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_phase2d import (
    REQUIRED_STAGES,
    Phase2dError,
    canonical_bytes,
    coverage_report,
    phase2d_identity,
    sha256,
    strict_coverage_gate,
    verify_phase2c_ref_set,
)
from cks_picks_cfb.data.evidence_audit import frame_audit
from cks_picks_cfb.data.lake import DatasetRef, read_dataset
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
PRIOR_AUDIT_PREFIX = (
    "artifacts/research/data-first-football-v1/phase1/"
    "2026-09-06T0055Z-phase1-evidence-audit-v3"
)


def _git_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


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


def _catalog_ref(conn_url: str, ref: DatasetRef) -> tuple[list[str], list[str]]:
    with psycopg.connect(conn_url) as conn:
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


def _manifest(storage, ref: DatasetRef) -> dict[str, Any]:
    if not ref.uri.endswith("/data.parquet"):
        raise Phase2dError(f"noncanonical dataset URI: {ref.uri}")
    uri = f"{ref.uri[: -len('/data.parquet')]}/manifest.json"
    value = json.loads(storage.read_bytes(uri))
    for key, expected in asdict(ref).items():
        if str(value.get(key)) != str(expected):
            raise Phase2dError(f"dataset manifest mismatch for {ref.version_id}: {key}")
    return value


def _audit_ref(
    storage, conn_url: str, ref_value: dict[str, Any]
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
    parents, captures = _catalog_ref(conn_url, ref)
    manifest = _manifest(storage, ref)
    if list(manifest.get("parent_versions") or []) != parents:
        raise Phase2dError(f"catalog parent mismatch: {ref.version_id}")
    if list(manifest.get("source_capture_ids") or []) != captures:
        raise Phase2dError(f"catalog capture mismatch: {ref.version_id}")
    return frame, {
        **ref_value,
        "row_count": len(frame),
        "parent_versions": parents,
        "source_capture_ids": captures,
        "lineage_timing_class": "historically_reconstructed",
        "semantic_availability": "postgame",
    }


def _omission_summary(
    entries: list[dict[str, Any]], games: pd.DataFrame
) -> dict[str, Any]:
    game_type = {
        int(row.game_id): str(row.season_type)
        for row in games[["game_id", "season_type"]].itertuples(index=False)
    }
    play = stat = 0
    for entry in entries:
        omissions = entry.get("omissions") or {}
        for game_id in omissions.get("missing_play_game_ids") or []:
            if game_type.get(int(game_id)) != "regular":
                raise Phase2dError("postseason play omission is not eligible")
            play += 1
        for game_id in omissions.get("missing_stat_game_ids") or []:
            if game_type.get(int(game_id)) != "regular":
                raise Phase2dError("postseason stat omission is not eligible")
            stat += 1
    if (play, stat) != (32, 1):
        raise Phase2dError(f"unexpected omission totals: plays={play}, stats={stat}")
    return {
        "play_count": play,
        "team_stat_count": stat,
        "reason": "provider_response_omission",
        "postseason_omissions": 0,
    }


def _historical_crosswalk(storage) -> tuple[list[dict[str, Any]], str]:
    payload = json.loads(
        storage.read_bytes(f"{PRIOR_AUDIT_PREFIX}/issue-register.json")
    )
    raw = canonical_bytes(payload)
    issues = []
    for issue in payload.get("issues") or []:
        category = str(issue.get("category"))
        disposition = (
            "historical_exclusion"
            if category == "unresolved-lineage"
            else "resolved_for_certification"
        )
        issues.append(
            {
                "prior_issue_id": issue.get("issue_id"),
                "category": category,
                "disposition": disposition,
                "reason": (
                    "noncanonical historical parquet remains visible and ineligible"
                    if disposition == "historical_exclusion"
                    else "does not affect the sealed Phase 2c certification root"
                ),
            }
        )
    return issues, sha256(raw)


def build_recertification(
    *, storage, conn_url: str, args
) -> tuple[dict[str, Any], dict[str, Any]]:
    raw_refset = storage.read_bytes(args.phase2c_ref_set_uri)
    refset = json.loads(raw_refset)
    if refset.get("manifest_sha256") != PHASE2C_REF_SET_SHA256:
        raise Phase2dError("Phase 2c ref set does not match the pinned checksum")
    entries = verify_phase2c_ref_set(refset)
    crosswalk, prior_audit_sha = _historical_crosswalk(storage)
    identity = phase2d_identity(
        run_id=args.run_id,
        environment=args.environment,
        as_of=args.as_of,
        code_sha=args.expected_code_sha,
        phase2c_ref_set_uri=args.phase2c_ref_set_uri,
        phase2c_ref_set_sha256=refset["manifest_sha256"],
        prior_audit_prefix=PRIOR_AUDIT_PREFIX,
        prior_audit_sha256=prior_audit_sha,
        config_sha256=sha256(canonical_bytes(vars(args))),
    )
    rows: list[dict[str, Any]] = []
    frames: dict[tuple[int, str], pd.DataFrame] = {}
    inputs = []
    for entry in entries:
        season = int(entry["season"])
        for dataset, ref in sorted((entry.get("outputs") or {}).items()):
            frame, evidence = _audit_ref(storage, conn_url, ref)
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
    blocking = []
    if not gate["passed"]:
        blocking.append("coverage_gate")
    if int(
        sum((entry.get("reconciliation") or {}).get("blocking", 0) for entry in entries)
    ):
        blocking.append("reconciliation")
    audit = {
        "schema_version": "data_first_phase1_audit_v1",
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
    args = parser.parse_args()
    args.as_of = _utc(args.as_of)
    if os.getenv("CFB_STORAGE_BACKEND", "").casefold() != "r2":
        raise Phase2dError("Phase 2d requires R2")
    if args.expected_code_sha != _git_sha():
        raise Phase2dError("--expected-code-sha must match HEAD")
    target = resolve_runtime_target(args.environment)
    storage = get_storage(environment=args.environment)
    audit, identity = build_recertification(
        storage=storage, conn_url=target.database_url, args=args
    )
    prefix = f"{PHASE1_ROOT}/{args.run_id}"
    if args.mode == "apply":
        _immutable_json(storage, f"{prefix}/identity.json", identity)
        _immutable_json(storage, f"{prefix}/audit-v4.json", audit)
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
            {"state": audit["state"], "audit": audit}, sort_keys=True, default=str
        )
    )
    if audit["certification_blocking_issue_count"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
