"""Pure Phase 2d recertification and eligibility contracts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd

from cks_picks_cfb.data.data_first_phase2 import DEVELOPMENT_SEASONS, FORBIDDEN_SEASONS
from cks_picks_cfb.data.data_first_phase2c import OUTPUT_DATASETS

RUN_ID_SUFFIX = "phase2d-recertification-v1"
RUN_IDENTITY_SCHEMA = "data_first_phase2d_run_identity_v1"
AUTOMATION_ADMISSION_SCHEMA = "data_first_phase2d_automation_admission_v1"
ELIGIBILITY_SCHEMA = "data_first_phase2_eligibility_v2"
PHASE2C_REF_SET_SCHEMA = "data_first_phase2c_ref_set_v1"

PHASE3_DATASETS = {
    "fbs_involved_games",
    "game_outcomes",
    "plays",
    "team_game_stats",
    "byplay",
    "drives",
    "reconciled_team_game",
}
AUDIT_ONLY_DATASETS = {"source_reconciliation"}
REQUIRED_STAGES = {
    "game_outcomes",
    "plays",
    "team_game_stats",
    "byplay",
    "drives",
    "reconciled_team_game",
    "source_reconciliation",
}


class Phase2dError(ValueError):
    """Raised when Phase 2d immutable evidence is incomplete or inconsistent."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str
    ).encode()


def sha256(value: Any) -> str:
    payload = value if isinstance(value, bytes) else canonical_bytes(value)
    return hashlib.sha256(payload).hexdigest()


def _ref_key(ref: Mapping[str, Any]) -> tuple[str, str, str, str, str]:
    required = ("dataset", "version_id", "schema_version", "content_sha", "uri")
    if missing := [key for key in required if not ref.get(key)]:
        raise Phase2dError(f"dataset ref is missing fields: {missing}")
    return tuple(str(ref[key]) for key in required)


def verify_phase2c_ref_set(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Validate the exact closed Phase 2c handoff and return sorted entries."""
    if payload.get("schema_version") != PHASE2C_REF_SET_SCHEMA:
        raise Phase2dError("Phase 2d requires data_first_phase2c_ref_set_v1")
    if payload.get("state") != "complete":
        raise Phase2dError("Phase 2c ref set is not complete")
    expected = payload.get("manifest_sha256")
    unsigned = dict(payload)
    unsigned.pop("manifest_sha256", None)
    if expected != sha256(unsigned):
        raise Phase2dError("Phase 2c ref-set checksum mismatch")
    identity = payload.get("identity") or {}
    if identity.get("schema_version") != "data_first_phase2c_run_identity_v1":
        raise Phase2dError("Phase 2c ref set has an invalid run identity")
    if identity.get("environment") != "preview":
        raise Phase2dError("Phase 2c ref set is not Preview evidence")
    if tuple(identity.get("seasons") or ()) != DEVELOPMENT_SEASONS:
        raise Phase2dError("Phase 2c ref set has the wrong season set")
    if tuple(identity.get("forbidden_seasons") or ()) != FORBIDDEN_SEASONS:
        raise Phase2dError("Phase 2c ref set has the wrong forbidden seasons")
    if tuple(identity.get("output_datasets") or ()) != OUTPUT_DATASETS:
        raise Phase2dError("Phase 2c ref set has the wrong output dataset contract")

    entries = list(payload.get("entries") or [])
    by_season = {int(entry.get("season")): entry for entry in entries}
    if len(entries) != len(DEVELOPMENT_SEASONS) or set(by_season) != set(
        DEVELOPMENT_SEASONS
    ):
        raise Phase2dError(
            "Phase 2c ref set must have one entry for every permitted season"
        )
    refs: set[tuple[str, str, str, str, str]] = set()
    for season in DEVELOPMENT_SEASONS:
        entry = by_season[season]
        outputs = entry.get("outputs") or {}
        if set(outputs) != set(OUTPUT_DATASETS):
            raise Phase2dError(f"Phase 2c season {season} does not have eight outputs")
        for ref in outputs.values():
            key = _ref_key(ref)
            if key in refs:
                raise Phase2dError(f"Phase 2c ref set repeats dataset ref {key[1]}")
            refs.add(key)
        if int((entry.get("reconciliation") or {}).get("blocking", 0)):
            raise Phase2dError(f"Phase 2c season {season} has blocking reconciliation")
    return [by_season[season] for season in DEVELOPMENT_SEASONS]


def phase2d_identity(
    *,
    run_id: str,
    environment: str,
    as_of: str,
    code_sha: str,
    phase2c_ref_set_uri: str,
    phase2c_ref_set_sha256: str,
    prior_audit_prefix: str,
    prior_audit_sha256: str,
    config_sha256: str,
) -> dict[str, Any]:
    if environment != "preview":
        raise Phase2dError("Phase 2d requires Preview")
    if not run_id.endswith(RUN_ID_SUFFIX):
        raise Phase2dError(f"run ID must end in {RUN_ID_SUFFIX}")
    payload = {
        "schema_version": RUN_IDENTITY_SCHEMA,
        "run_id": run_id,
        "environment": environment,
        "as_of": as_of,
        "code_sha": code_sha,
        "phase2c_ref_set_uri": phase2c_ref_set_uri,
        "phase2c_ref_set_sha256": phase2c_ref_set_sha256,
        "prior_audit_prefix": prior_audit_prefix.rstrip("/"),
        "prior_audit_sha256": prior_audit_sha256,
        "config_sha256": config_sha256,
        "development_seasons": list(DEVELOPMENT_SEASONS),
        "forbidden_seasons": list(FORBIDDEN_SEASONS),
    }
    payload["identity_sha256"] = sha256(payload)
    return payload


def _stage_ids(frame: pd.DataFrame) -> set[int]:
    if "game_id" not in frame:
        raise Phase2dError("certification dataset lacks game_id")
    return set(pd.to_numeric(frame["game_id"], errors="raise").astype(int))


def coverage_report(
    games: pd.DataFrame, stage_frames: Mapping[str, pd.DataFrame]
) -> list[dict[str, Any]]:
    """Return complete per-slice coverage, including absent population slices."""
    required = {"season", "season_type", "population", "game_id", "completed"}
    if missing := sorted(required - set(games)):
        raise Phase2dError(f"fbs_involved_games is missing coverage columns: {missing}")
    frame = games.copy()
    frame["season"] = pd.to_numeric(frame["season"], errors="raise").astype(int)
    if frame["season"].isin(FORBIDDEN_SEASONS).any():
        raise Phase2dError("coverage denominator contains 2020")
    frame = frame[frame["completed"].fillna(False).astype(bool)]
    ids_by_stage = {stage: _stage_ids(value) for stage, value in stage_frames.items()}
    rows: list[dict[str, Any]] = []
    observed = {
        (int(season), season_type, population)
        for season, season_type, population in frame[
            ["season", "season_type", "population"]
        ]
        .drop_duplicates()
        .itertuples(index=False, name=None)
    }
    for season in DEVELOPMENT_SEASONS:
        for season_type in ("regular", "postseason"):
            for population in ("fbs_fbs", "fbs_fcs"):
                key = (season, season_type, population)
                subset = frame[
                    (frame["season"] == season)
                    & (frame["season_type"] == season_type)
                    & (frame["population"] == population)
                ]
                denominator = set(
                    pd.to_numeric(subset["game_id"], errors="raise").astype(int)
                )
                for stage, stage_ids in ids_by_stage.items():
                    if key not in observed:
                        rows.append(
                            {
                                "season": season,
                                "season_type": season_type,
                                "population": population,
                                "stage": stage,
                                "state": "not_applicable",
                                "denominator_count": 0,
                                "admitted_count": 0,
                                "coverage_rate": None,
                            }
                        )
                        continue
                    admitted = denominator & stage_ids
                    rows.append(
                        {
                            "season": season,
                            "season_type": season_type,
                            "population": population,
                            "stage": stage,
                            "state": "observed",
                            "denominator_count": len(denominator),
                            "admitted_count": len(admitted),
                            "coverage_rate": len(admitted) / len(denominator),
                        }
                    )
    return rows


def strict_coverage_gate(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    failures = []
    for row in rows:
        if row.get("state") == "not_applicable":
            continue
        population = str(row.get("population"))
        if population not in {"fbs_fbs", "fbs_fcs"}:
            continue
        threshold = 0.95 if population == "fbs_fbs" else 0.90
        rate = float(row["coverage_rate"])
        if rate <= threshold:
            failures.append({**dict(row), "threshold": threshold})
    return {
        "passed": not failures,
        "comparison": "strictly_greater_than",
        "thresholds": {"fbs_fbs": 0.95, "fbs_fcs": 0.90},
        "failed_rows": failures,
    }


def eligibility_role(dataset: str) -> tuple[str, list[str]]:
    if dataset == "fbs_involved_games":
        return "denominator_and_chronology", ["phase3_measurement_validation"]
    if dataset == "game_outcomes":
        return "labels_and_evaluation_only", ["phase3_measurement_validation"]
    if dataset in {
        "plays",
        "team_game_stats",
        "byplay",
        "drives",
        "reconciled_team_game",
    }:
        return "measurement_construction", ["phase3_measurement_validation"]
    if dataset == "source_reconciliation":
        return "audit_evidence_only", ["audit_only"]
    raise Phase2dError(f"unexpected Phase 2c dataset: {dataset}")


def eligibility_manifest(
    *,
    identity: Mapping[str, Any],
    audit: Mapping[str, Any],
    automation_admission: Mapping[str, Any],
    inputs: Sequence[Mapping[str, Any]],
    coverage: Mapping[str, Any],
    omissions: Mapping[str, Any],
) -> dict[str, Any]:
    if audit.get("certification_blocking_issue_count") != 0:
        raise Phase2dError("eligibility requires zero certification blockers")
    if not coverage.get("passed"):
        raise Phase2dError("eligibility requires passing coverage")
    if automation_admission.get("state") != "admitted":
        raise Phase2dError("eligibility requires admitted Preview automation")
    phase3_refs = [
        dict(row)
        for row in inputs
        if row.get("dataset") in PHASE3_DATASETS and row.get("eligible")
    ]
    if len(phase3_refs) != len(DEVELOPMENT_SEASONS) * len(PHASE3_DATASETS):
        raise Phase2dError("eligibility requires seven Phase 3 datasets per season")
    payload = {
        "schema_version": ELIGIBILITY_SCHEMA,
        "state": "eligible",
        "identity": dict(identity),
        "audit_uri": audit["uri"],
        "audit_sha256": audit["sha256"],
        "automation_admission_uri": automation_admission["uri"],
        "automation_admission_sha256": automation_admission["sha256"],
        "development_seasons": list(DEVELOPMENT_SEASONS),
        "forbidden_seasons": list(FORBIDDEN_SEASONS),
        "coverage_gate": dict(coverage),
        "omissions": dict(omissions),
        "inputs": [dict(row) for row in inputs],
        "phase3_input_refs": phase3_refs,
        "production_activation_authorized": False,
        "model_selection_authorized": False,
    }
    payload["manifest_sha256"] = sha256(payload)
    return payload


def automation_admission(
    *,
    run_id: str,
    code_sha: str,
    capture_manifest_uri: str,
    capture_manifest_sha256: str,
    github_run_url: str,
    quota: Mapping[str, Any],
    captures: Sequence[Mapping[str, Any]],
    future_kickoff_count: int,
) -> dict[str, Any]:
    if len(captures) != 7 or any(row.get("state") != "captured" for row in captures):
        raise Phase2dError("automation admission requires seven successful captures")
    if future_kickoff_count < 1:
        raise Phase2dError("automation admission requires a future kickoff")
    payload = {
        "schema_version": AUTOMATION_ADMISSION_SCHEMA,
        "state": "admitted",
        "run_id": run_id,
        "code_sha": code_sha,
        "capture_manifest_uri": capture_manifest_uri,
        "capture_manifest_sha256": capture_manifest_sha256,
        "github_run_url": github_run_url,
        "quota": dict(quota),
        "captures": [dict(row) for row in captures],
        "future_kickoff_count": future_kickoff_count,
    }
    payload["manifest_sha256"] = sha256(payload)
    return payload
