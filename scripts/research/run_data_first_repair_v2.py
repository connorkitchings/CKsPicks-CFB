#!/usr/bin/env python3
"""Reconcile and publish Preview-only data-first Repair v2 evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import cfbd
import pandas as pd
import psycopg
import yaml
from dotenv import load_dotenv

from cks_picks_cfb.data.catalog import (
    begin_or_resume_request_set,
    catalog_connection_url,
    completed_request_capture_ids,
    next_source_request_attempt,
    record_source_request_attempt,
    register_dataset_version,
    register_source_capture,
    source_capture_by_id,
    source_request_sha,
)
from cks_picks_cfb.data.data_first_phase2 import DEVELOPMENT_SEASONS
from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload
from cks_picks_cfb.data.data_first_phase2e import validate_capture_set_manifest
from cks_picks_cfb.data.data_first_repair_v2 import (
    REPAIR_AUXILIARY_DATASET,
    REPAIR_AUXILIARY_SCHEMA,
    REPAIR_CAPTURE_PLAN_DATASET,
    REPAIR_CAPTURE_PLAN_SCHEMA,
    REPAIR_COVERAGE_DATASET,
    REPAIR_COVERAGE_SCHEMA,
    REPAIR_ISSUE_DATASET,
    REPAIR_ISSUE_SCHEMA,
    REPAIR_POPULATION_DATASET,
    REPAIR_POPULATION_SCHEMA,
    RepairV2Error,
    assemble_auxiliary,
    build_team_universe,
    coverage_and_admission,
    normalize_coaching_v2,
    normalize_recruiting_v2,
    normalize_returning_production_v2,
    normalize_roster_continuity_v2,
    reconcile_population,
    repair_identity,
    repair_manifest,
    sha256,
    verify_parent,
)
from cks_picks_cfb.data.lake import (
    BuildRequest,
    DatasetRef,
    SourceCapture,
    build_dataset_version,
    capture_provider_records,
    read_dataset,
    read_source_capture,
)
from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.preseason_features import canonical_team

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "conf/research/data_first_football_v1/repair_v2.yaml"
OUTPUT_ROOT = "artifacts/research/data-first-football-v1/repair/v2/runs"
CORE_RAW_SHA = "cdeeea01035c9108491a42b2e29a9e6033cdd7781d1ab837df8e411b29afe760"
CORE_CANONICAL_SHA = "3092101af7f5021e1cd0788d43706260804289e71ef43d3d6d566c9a85efe5cb"
AUXILIARY_RAW_SHA = "d06ed3968a7bb6ec7ba97212aa2063068c253f26202e810c921b044006ab13ad"
AUXILIARY_CANONICAL_SHA = (
    "0f537ced993535eff3f554a35f23d75b24106100dc787d72f0b83beb13f13a3d"
)
PHASE3_RAW_SHA = "c8bc1ebd8a369c59cf298844dfdb2167baaa17dc72a3b29ceebd119eeacaf234"
PHASE3_CANONICAL_SHA = (
    "25219c6f5cce932531a1f4f3eed7f17c1842c1966444f4e7956d342ae03cbf44"
)
RELEVANT_PATHS = (
    "conf/research/data_first_football_v1/repair_v2.yaml",
    "scripts/research/run_data_first_repair_v2.py",
    "scripts/research/verify_data_first_repair_v2.py",
    "src/cks_picks_cfb/data/data_first_repair_v2.py",
    "src/cks_picks_cfb/data/lake.py",
    "src/cks_picks_cfb/data/schema_contracts.py",
    "tests/test_data_lake.py",
)


def _git_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _tracked_clean() -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and not result.stdout.strip()


def _require_committed_paths() -> None:
    for path in RELEVANT_PATHS:
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", path],
            cwd=REPO_ROOT,
            capture_output=True,
            check=False,
        )
        if tracked.returncode:
            raise RepairV2Error(f"Repair v2 path is not committed: {path}")
    changed = subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", *RELEVANT_PATHS],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
    )
    if changed.returncode:
        raise RepairV2Error("Repair v2 code paths differ from committed HEAD")


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise RepairV2Error("--as-of must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _immutable_json(storage: Any, uri: str, value: Mapping[str, Any]) -> None:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str
    ).encode()
    if storage.exists(uri):
        if storage.read_bytes(uri) != payload:
            raise RepairV2Error(f"immutable artifact collision: {uri}")
        return
    storage.write_bytes(payload, uri)


def _read_json(storage: Any, uri: str) -> tuple[dict[str, Any], str]:
    raw = storage.read_bytes(uri)
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def _ref(value: Mapping[str, Any]) -> DatasetRef:
    return DatasetRef(
        dataset=str(value["dataset"]),
        version_id=str(value["version_id"]),
        schema_version=str(value["schema_version"]),
        content_sha=str(value["content_sha"]),
        uri=str(value["uri"]),
    )


def _capture(value: Mapping[str, Any]) -> SourceCapture:
    captured_at = datetime.fromisoformat(
        str(value["captured_at"]).replace("Z", "+00:00")
    )
    effective_at = value.get("effective_at")
    return SourceCapture(
        capture_id=str(value["capture_id"]),
        provider=str(value["provider"]),
        entity=str(value["entity"]),
        captured_at=captured_at,
        effective_at=datetime.fromisoformat(str(effective_at).replace("Z", "+00:00"))
        if effective_at
        else None,
        request=dict(value["request"]),
        content_sha=str(value["content_sha"]),
        object_sha=str(value["object_sha"]),
        uri=str(value["uri"]),
        row_count=int(value["row_count"]),
        state=str(value.get("state", "registered")),
        provider_api_version=value.get("provider_api_version"),
        response_metadata=dict(value.get("response_metadata") or {}),
    )


def _config(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text())
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != "data_first_repair_v2_config_v1"
    ):
        raise RepairV2Error("Repair v2 requires data_first_repair_v2_config_v1")
    if tuple(value.get("development_seasons") or ()) != DEVELOPMENT_SEASONS or tuple(
        value.get("forbidden_seasons") or ()
    ) != (2020,):
        raise RepairV2Error("Repair v2 config changes the sealed seasons")
    requests = list(value.get("gap_capture_requests") or [])
    expected = {
        (
            "rosters",
            "TeamsApi.get_roster",
            _stable_parameters({"year": 2014, "classification": "fbs"}),
        ),
        (
            "coaches",
            "CoachesApi.get_coaches",
            _stable_parameters({"min_year": 1869, "max_year": 2014}),
        ),
    }
    actual = {
        (
            str(row.get("entity")),
            str(row.get("endpoint")),
            _stable_parameters(dict(row.get("parameters") or {})),
        )
        for row in requests
    }
    if actual != expected or len(requests) != 2:
        raise RepairV2Error("Repair v2 capture inventory changed")
    policy = value.get("capture_policy") or {}
    if (
        int(policy.get("max_total_requests", 0)) != 200
        or int(policy.get("max_attempts_per_request", 0)) != 3
    ):
        raise RepairV2Error("Repair v2 capture policy changed")
    return value


def _stable_parameters(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _validate_parents(
    storage: Any, args: argparse.Namespace
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, str]]:
    core, core_raw = _read_json(storage, args.core_eligibility_uri)
    verify_parent(
        core,
        raw_sha256=core_raw,
        expected_raw_sha256=CORE_RAW_SHA,
        expected_manifest_sha256=CORE_CANONICAL_SHA,
        schema_version="data_first_phase2_eligibility_v3",
        state="eligible",
        label="Phase 2d eligibility",
    )
    auxiliary, auxiliary_raw = _read_json(storage, args.auxiliary_eligibility_uri)
    verify_parent(
        auxiliary,
        raw_sha256=auxiliary_raw,
        expected_raw_sha256=AUXILIARY_RAW_SHA,
        expected_manifest_sha256=AUXILIARY_CANONICAL_SHA,
        schema_version="data_first_phase2e_eligibility_v1",
        state="eligible_reconstructed_only",
        label="Phase 2e eligibility",
    )
    phase3, phase3_raw = _read_json(storage, args.phase3_retained_uri)
    try:
        verify_signed_payload(phase3, label="Phase 3 retained core")
    except ValueError as exc:
        raise RepairV2Error(str(exc)) from exc
    if (
        phase3_raw != PHASE3_RAW_SHA
        or phase3.get("manifest_sha256") != PHASE3_CANONICAL_SHA
        or phase3.get("schema_version") != "data_first_phase3_retained_core_v1"
        or phase3.get("state") != "frozen"
    ):
        raise RepairV2Error(
            "Phase 3 retained core is not the reviewed diagnostic parent"
        )
    if phase3.get("production_activation_authorized") is not False:
        raise RepairV2Error("Phase 3 parent improperly permits production")
    return (
        core,
        auxiliary,
        phase3,
        {"core": core_raw, "auxiliary": auxiliary_raw, "phase3": phase3_raw},
    )


def _load_core_frames(
    storage: Any, core: Mapping[str, Any], phase3: Mapping[str, Any]
) -> tuple[
    pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, tuple[DatasetRef, ...]
]:
    inputs = list(core.get("inputs") or [])
    expected = len(DEVELOPMENT_SEASONS) * 8
    if len(inputs) != expected:
        raise RepairV2Error(
            "Phase 2d parent does not contain the complete 80-ref audit set"
        )
    by_key: dict[tuple[int, str], DatasetRef] = {}
    for value in inputs:
        key = (int(value["season"]), str(value["dataset"]))
        if key in by_key:
            raise RepairV2Error(f"duplicate core parent {key}")
        by_key[key] = _ref(value)
    expected_keys = {
        (season, dataset)
        for season in DEVELOPMENT_SEASONS
        for dataset in ("fbs_involved_games", "game_outcomes", "source_reconciliation")
    }
    if not expected_keys.issubset(by_key):
        raise RepairV2Error("core parent is missing a required reconciliation dataset")
    schedule = pd.concat(
        [
            read_dataset(storage, by_key[(season, "fbs_involved_games")])
            for season in DEVELOPMENT_SEASONS
        ],
        ignore_index=True,
    )
    outcomes = pd.concat(
        [
            read_dataset(storage, by_key[(season, "game_outcomes")])
            for season in DEVELOPMENT_SEASONS
        ],
        ignore_index=True,
    )
    reconciliation = pd.concat(
        [
            read_dataset(storage, by_key[(season, "source_reconciliation")])
            for season in DEVELOPMENT_SEASONS
        ],
        ignore_index=True,
    )
    observations = read_dataset(
        storage, _ref(dict(phase3["output_refs"])["observations"])
    )
    return schedule, outcomes, observations, reconciliation, tuple(by_key.values())


def _capture_set(
    storage: Any, auxiliary_uri: str, auxiliary: Mapping[str, Any]
) -> tuple[list[SourceCapture], str]:
    uri = f"{auxiliary_uri.rsplit('/', 1)[0]}/capture-set.json"
    payload, raw_sha = _read_json(storage, uri)
    captures = validate_capture_set_manifest(payload)
    if payload.get("manifest_sha256") != auxiliary.get("capture_set_sha256"):
        raise RepairV2Error(
            "Phase 2e capture-set checksum does not match its eligibility manifest"
        )
    return [_capture(row) for row in captures], raw_sha


def _raw_captures(
    storage: Any, captures: list[SourceCapture]
) -> tuple[dict[str, pd.DataFrame], dict[str, list[str]]]:
    frames: dict[str, list[pd.DataFrame]] = {}
    identities: dict[str, list[str]] = {}
    for capture in captures:
        entity = str(capture.entity)
        entity = (
            "coaches"
            if entity.endswith("coaches")
            else "rosters"
            if entity.endswith("rosters")
            else entity
        )
        if entity not in {"recruiting", "returning_production", "coaches", "rosters"}:
            continue
        frame = read_source_capture(storage, capture).copy()
        parameters = dict(capture.request.get("parameters") or {})
        if "year" in parameters:
            frame["__capture_season"] = int(parameters["year"])
            if "season" not in frame:
                frame["season"] = int(parameters["year"])
        frame["source_capture_id"] = capture.capture_id
        frames.setdefault(entity, []).append(frame)
        identities.setdefault(entity, []).append(capture.capture_id)
    required = {"recruiting", "returning_production", "coaches", "rosters"}
    missing = required - set(frames)
    if missing:
        raise RepairV2Error(
            f"auxiliary capture set is missing entities: {sorted(missing)}"
        )
    return {
        entity: pd.concat(values, ignore_index=True)
        for entity, values in frames.items()
    }, identities


def _first_kickoffs(schedule: pd.DataFrame) -> pd.DataFrame:
    sides = pd.concat(
        [
            schedule[
                ["season", "kickoff_utc", "home_team", "home_classification"]
            ].rename(
                columns={"home_team": "team", "home_classification": "classification"}
            ),
            schedule[
                ["season", "kickoff_utc", "away_team", "away_classification"]
            ].rename(
                columns={"away_team": "team", "away_classification": "classification"}
            ),
        ],
        ignore_index=True,
    )
    sides = sides[sides["classification"].astype(str).str.casefold().eq("fbs")].copy()
    sides["kickoff_utc"] = pd.to_datetime(
        sides["kickoff_utc"], utc=True, errors="raise"
    )
    sides["team"] = sides["team"].map(canonical_team)
    return (
        sides.groupby(["season", "team"], as_index=False)["kickoff_utc"]
        .min()
        .rename(columns={"kickoff_utc": "first_kickoff_utc"})
    )


def _capture_rows(
    config: Mapping[str, Any],
    existing: Mapping[str, SourceCapture] | None = None,
    captures: Mapping[str, SourceCapture] | None = None,
    attempts: Mapping[str, int] | None = None,
) -> pd.DataFrame:
    existing, captures, attempts = existing or {}, captures or {}, attempts or {}
    policy = dict(config["capture_policy"])
    rows = []
    for request in config["gap_capture_requests"]:
        semantic = {
            "provider": policy["provider"],
            "entity": request["entity"],
            "endpoint": request["endpoint"],
            "parameters": dict(request["parameters"]),
        }
        request_id = source_request_sha(semantic)
        existing_capture = existing.get(request_id)
        capture = captures.get(request_id) or existing_capture
        rows.append(
            {
                "request_id": request_id,
                **semantic,
                "parameters": _stable_parameters(semantic["parameters"]),
                "reason": request["reason"],
                "existing_captures_checked": _stable_parameters(sorted(existing)),
                "max_attempts": int(policy["max_attempts_per_request"]),
                "max_total_requests": int(policy["max_total_requests"]),
                "state": "existing_capture"
                if existing_capture
                else "captured"
                if capture
                else "planned",
                "capture_id": capture.capture_id if capture else None,
                "attempt_count": int(attempts.get(request_id, 0)),
                "captured_at": capture.captured_at.isoformat() if capture else None,
                "content_sha": capture.content_sha if capture else None,
                "row_count": capture.row_count if capture else 0,
                "timing_class": "historically_reconstructed",
            }
        )
    return pd.DataFrame(rows)


def _registered_gap_captures(
    conn_url: str, config: Mapping[str, Any]
) -> dict[str, SourceCapture]:
    """Return exact, timing-safe previously registered Repair v2 captures."""
    policy = dict(config["capture_policy"])
    expected = {
        source_request_sha(
            {
                "provider": policy["provider"],
                "entity": request["entity"],
                "endpoint": request["endpoint"],
                "parameters": dict(request["parameters"]),
            }
        )
        for request in config["gap_capture_requests"]
    }
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT capture_id FROM catalog.source_captures "
                "WHERE provider = %s AND state = 'registered' "
                "AND entity IN ('data_first_repair_rosters', "
                "'data_first_repair_coaches')",
                (policy["provider"],),
            )
            capture_ids = [str(row[0]) for row in cur.fetchall()]
    matches: dict[str, list[SourceCapture]] = {}
    for capture_id in capture_ids:
        capture = source_capture_by_id(conn_url, capture_id)
        request_id = source_request_sha(dict(capture.request))
        timing = dict(capture.response_metadata).get("timing_class")
        if (
            request_id in expected
            and capture.effective_at is None
            and timing == "historically_reconstructed"
        ):
            matches.setdefault(request_id, []).append(capture)
    duplicates = [
        request_id for request_id, values in matches.items() if len(values) > 1
    ]
    if duplicates:
        raise RepairV2Error(
            "ambiguous registered Repair v2 captures: " + ", ".join(sorted(duplicates))
        )
    return {request_id: values[0] for request_id, values in matches.items()}


def _plain(row: Any) -> dict[str, Any]:
    return dict(row) if isinstance(row, dict) else dict(row.to_dict())


def _fetch(client: cfbd.ApiClient, request: Mapping[str, Any]) -> list[dict[str, Any]]:
    api_class, method_name = {
        "TeamsApi.get_roster": (cfbd.TeamsApi, "get_roster"),
        "CoachesApi.get_coaches": (cfbd.CoachesApi, "get_coaches"),
    }[str(request["endpoint"])]
    return [
        _plain(row)
        for row in getattr(api_class(client), method_name)(
            **dict(request["parameters"]), _request_timeout=60
        )
    ]


def _capture_gaps(
    storage: Any,
    conn_url: str,
    config: Mapping[str, Any],
    identity: Mapping[str, Any],
    run_prefix: str,
    existing_captures: Mapping[str, SourceCapture],
) -> list[SourceCapture]:
    policy = dict(config["capture_policy"])
    requests = [
        {
            "provider": policy["provider"],
            "entity": row["entity"],
            "endpoint": row["endpoint"],
            "parameters": dict(row["parameters"]),
        }
        for row in config["gap_capture_requests"]
    ]
    plan = begin_or_resume_request_set(
        conn_url,
        ingestion_run_id=f"data-first-repair-v2-{identity['run_id']}",
        provider="cfbd",
        entity="data_first_repair_v2",
        requests=requests,
        policy=policy,
        contract_version="data_first_repair_v2_capture_set_v1",
        identity=identity,
    )
    # The caller persisted the immutable, user-readable capture inventory
    # before entering this function.  The catalog header above independently
    # enforces the same semantic request set for a resume; do not overwrite
    # the R2 inventory with an internal representation.
    completed = completed_request_capture_ids(
        conn_url, f"data-first-repair-v2-{identity['run_id']}"
    )
    output: list[SourceCapture] = list(existing_captures.values()) + [
        source_capture_by_id(conn_url, capture_id) for capture_id in completed.values()
    ]
    for request in plan:
        request_id = source_request_sha(
            {
                key: request[key]
                for key in ("provider", "entity", "endpoint", "parameters")
            }
        )
        if request_id in completed or request_id in existing_captures:
            continue
        client = cfbd.ApiClient(
            cfbd.Configuration(access_token=os.environ["CFBD_API_KEY"])
        )
        for _ in range(int(policy["max_attempts_per_request"])):
            attempt = next_source_request_attempt(
                conn_url,
                ingestion_run_id=f"data-first-repair-v2-{identity['run_id']}",
                request_sha=request_id,
            )
            if attempt > int(policy["max_attempts_per_request"]):
                break
            record_source_request_attempt(
                conn_url,
                ingestion_run_id=f"data-first-repair-v2-{identity['run_id']}",
                request_sha=request_id,
                attempt=attempt,
                state="running",
            )
            try:
                rows = _fetch(client, request)
                if not rows:
                    raise RepairV2Error(
                        "provider returned an empty gap-capture response"
                    )
                capture = capture_provider_records(
                    storage,
                    provider="cfbd",
                    entity=f"data_first_repair_{request['entity']}",
                    records=rows,
                    captured_at=datetime.now(timezone.utc),
                    effective_at=None,
                    request={
                        key: request[key]
                        for key in ("provider", "entity", "endpoint", "parameters")
                    },
                    response_metadata={
                        "timing_class": "historically_reconstructed",
                        "phase": "data_first_repair_v2",
                    },
                )
                register_source_capture(conn_url, capture)
                record_source_request_attempt(
                    conn_url,
                    ingestion_run_id=f"data-first-repair-v2-{identity['run_id']}",
                    request_sha=request_id,
                    attempt=attempt,
                    state="succeeded",
                    capture_id=capture.capture_id,
                )
                output.append(capture)
                break
            except Exception as exc:
                record_source_request_attempt(
                    conn_url,
                    ingestion_run_id=f"data-first-repair-v2-{identity['run_id']}",
                    request_sha=request_id,
                    attempt=attempt,
                    state="failed",
                    error=exc,
                )
        else:
            continue
    _immutable_json(
        storage,
        f"{run_prefix}/capture-results.json",
        {
            "schema_version": "data_first_repair_capture_results_v2",
            "identity": dict(identity),
            "capture_ids": [capture.capture_id for capture in output],
        },
    )
    return output


def compute_repair(
    storage: Any,
    *,
    core: Mapping[str, Any],
    auxiliary_uri: str,
    auxiliary: Mapping[str, Any],
    phase3: Mapping[str, Any],
    extra_captures: list[SourceCapture] | None = None,
) -> tuple[dict[str, pd.DataFrame], dict[str, Any], dict[str, Any]]:
    schedule, outcomes, observations, reconciliation, core_refs = _load_core_frames(
        storage, core, phase3
    )
    population, population_issues = reconcile_population(
        schedule=schedule,
        outcomes=outcomes,
        observed_games=observations[["season", "game_id"]],
        reconciliation=reconciliation,
        omissions=dict(core["omissions"]),
    )
    universe = build_team_universe(schedule)
    capture_set, capture_set_raw = _capture_set(storage, auxiliary_uri, auxiliary)
    raw, capture_ids = _raw_captures(storage, [*capture_set, *(extra_captures or [])])
    if extra_captures:
        for capture in extra_captures:
            entity = "coaches" if capture.entity.endswith("coaches") else "rosters"
            capture_ids.setdefault(entity, []).append(capture.capture_id)
    recruiting, recruiting_issues = normalize_recruiting_v2(raw["recruiting"], universe)
    returning, returning_issues = normalize_returning_production_v2(
        raw["returning_production"], universe
    )
    coaching, coaching_issues = normalize_coaching_v2(
        raw["coaches"], universe, _first_kickoffs(schedule)
    )
    roster, roster_issues = normalize_roster_continuity_v2(raw["rosters"], universe)
    source_ids = {
        "recruiting": capture_ids["recruiting"],
        "returning_production": capture_ids["returning_production"],
        "coaching": capture_ids["coaches"],
        "roster_continuity": capture_ids["rosters"],
    }
    auxiliary_frame = assemble_auxiliary(
        universe=universe,
        recruiting=recruiting,
        returning_production=returning,
        coaching=coaching,
        roster_continuity=roster,
        source_capture_ids=source_ids,
    )
    coverage, family_admission = coverage_and_admission(auxiliary_frame)
    issues = pd.concat(
        [
            population_issues,
            recruiting_issues,
            returning_issues,
            coaching_issues,
            roster_issues,
        ],
        ignore_index=True,
    )
    issues = (
        issues.drop_duplicates(["issue_id", "affected_key"], keep="first")
        .sort_values(["issue_id", "affected_key"], kind="mergesort")
        .reset_index(drop=True)
    )
    details = {
        "core_refs": core_refs,
        "capture_set_raw_sha256": capture_set_raw,
        "capture_ids": source_ids,
        "population": population,
    }
    return (
        {
            "population": population,
            "auxiliary": auxiliary_frame,
            "coverage": coverage,
            "issues": issues,
        },
        family_admission,
        details,
    )


def _build_dataset(
    storage: Any,
    conn_url: str,
    *,
    dataset: str,
    schema: str,
    frame: pd.DataFrame,
    parents: tuple[DatasetRef, ...],
    source_capture_ids: tuple[str, ...],
    identity: Mapping[str, Any],
    as_of: datetime,
) -> DatasetRef:
    validation = validate_frame(frame, schema_for(dataset, schema))
    ref, manifest = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset=dataset,
            parent_refs=parents,
            code_sha=str(identity["code_sha"]),
            config_sha=str(identity["config_sha"]),
            as_of=as_of,
            source_capture_ids=source_capture_ids,
            schema_version=schema,
            tier="gold",
        ),
        records=frame.to_dict("records"),
        partitions={
            "seasons": list(DEVELOPMENT_SEASONS),
            "environment": "preview",
            "stage": "repair_v2",
        },
        validation=validation,
    )
    register_dataset_version(conn_url, ref, manifest)
    return ref


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-eligibility-uri", required=True)
    parser.add_argument("--auxiliary-eligibility-uri", required=True)
    parser.add_argument("--phase3-retained-uri", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--environment", choices=["preview"], required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    config_path = Path(args.config).resolve()
    if config_path != DEFAULT_CONFIG.resolve():
        raise RepairV2Error("Repair v2 requires the sealed default configuration")
    config = _config(config_path)
    as_of = _utc(args.as_of)
    if args.apply:
        if _git_sha() != args.expected_code_sha:
            raise RepairV2Error("apply requires --expected-code-sha equal to HEAD")
        if not _tracked_clean():
            raise RepairV2Error("apply requires a clean tracked worktree")
        _require_committed_paths()
    storage = get_storage(environment="preview")
    core, auxiliary, phase3, raw_shas = _validate_parents(storage, args)
    identity = repair_identity(
        run_id=args.run_id,
        environment="preview",
        as_of=as_of.isoformat().replace("+00:00", "Z"),
        code_sha=args.expected_code_sha,
        config_sha=sha256(config_path.read_bytes()),
        core_eligibility_uri=args.core_eligibility_uri,
        core_eligibility_raw_sha256=raw_shas["core"],
        auxiliary_eligibility_uri=args.auxiliary_eligibility_uri,
        auxiliary_eligibility_raw_sha256=raw_shas["auxiliary"],
        phase3_retained_uri=args.phase3_retained_uri,
        phase3_retained_raw_sha256=raw_shas["phase3"],
    )
    run_prefix = f"{OUTPUT_ROOT}/{args.run_id}"
    if args.apply and storage.exists(f"{run_prefix}/repair-manifest.json"):
        raise RepairV2Error(f"Repair v2 run identity already exists: {args.run_id}")
    extra_captures: list[SourceCapture] = []
    capture_plan = _capture_rows(config)
    if args.apply:
        conn_url = catalog_connection_url("preview")
        registered_captures = _registered_gap_captures(conn_url, config)
        capture_plan = _capture_rows(config, existing=registered_captures)
        _immutable_json(storage, f"{run_prefix}/identity.json", identity)
        _immutable_json(
            storage,
            f"{run_prefix}/capture-plan.json",
            {
                "schema_version": "data_first_repair_capture_plan_v2",
                "identity": identity,
                "plan": capture_plan.to_dict("records"),
            },
        )
        extra_captures = _capture_gaps(
            storage,
            conn_url,
            config,
            identity,
            run_prefix,
            existing_captures=registered_captures,
        )
        captures_by_request = {
            source_request_sha(dict(capture.request)): capture
            for capture in extra_captures
        }
        capture_plan = _capture_rows(
            config,
            existing=registered_captures,
            captures=captures_by_request,
        )
    frames, family_admission, details = compute_repair(
        storage,
        core=core,
        auxiliary_uri=args.auxiliary_eligibility_uri,
        auxiliary=auxiliary,
        phase3=phase3,
        extra_captures=extra_captures,
    )
    for name, dataset, schema in (
        ("population", REPAIR_POPULATION_DATASET, REPAIR_POPULATION_SCHEMA),
        ("auxiliary", REPAIR_AUXILIARY_DATASET, REPAIR_AUXILIARY_SCHEMA),
        ("coverage", REPAIR_COVERAGE_DATASET, REPAIR_COVERAGE_SCHEMA),
        ("issues", REPAIR_ISSUE_DATASET, REPAIR_ISSUE_SCHEMA),
    ):
        validate_frame(frames[name], schema_for(dataset, schema))
    validate_frame(
        capture_plan,
        schema_for(REPAIR_CAPTURE_PLAN_DATASET, REPAIR_CAPTURE_PLAN_SCHEMA),
    )
    summary: dict[str, Any] = {
        "state": "dry_run",
        "identity": identity,
        "population": {
            "scheduled_games": len(frames["population"]),
            "forecast_eligible_games": int(
                frames["population"]["forecast_eligible"].sum()
            ),
            "measurement_usable_games": int(
                frames["population"]["measurement_usable"].sum()
            ),
            "omission_issues": int(
                len(
                    frames["issues"][
                        frames["issues"]["category"].eq("population_reconciliation")
                    ]
                )
            ),
        },
        "auxiliary_rows": len(frames["auxiliary"]),
        "family_admission": family_admission,
        "capture_plan": capture_plan.to_dict("records"),
    }
    if args.apply:
        conn_url = catalog_connection_url("preview")
        parents = details["core_refs"]
        source_ids = tuple(
            sorted(
                {
                    capture_id
                    for values in details["capture_ids"].values()
                    for capture_id in values
                }
            )
        )
        refs = {
            "population": _build_dataset(
                storage,
                conn_url,
                dataset=REPAIR_POPULATION_DATASET,
                schema=REPAIR_POPULATION_SCHEMA,
                frame=frames["population"],
                parents=parents,
                source_capture_ids=source_ids,
                identity=identity,
                as_of=as_of,
            ),
            "auxiliary": _build_dataset(
                storage,
                conn_url,
                dataset=REPAIR_AUXILIARY_DATASET,
                schema=REPAIR_AUXILIARY_SCHEMA,
                frame=frames["auxiliary"],
                parents=parents,
                source_capture_ids=source_ids,
                identity=identity,
                as_of=as_of,
            ),
            "coverage": _build_dataset(
                storage,
                conn_url,
                dataset=REPAIR_COVERAGE_DATASET,
                schema=REPAIR_COVERAGE_SCHEMA,
                frame=frames["coverage"],
                parents=parents,
                source_capture_ids=source_ids,
                identity=identity,
                as_of=as_of,
            ),
            "issues": _build_dataset(
                storage,
                conn_url,
                dataset=REPAIR_ISSUE_DATASET,
                schema=REPAIR_ISSUE_SCHEMA,
                frame=frames["issues"],
                parents=parents,
                source_capture_ids=source_ids,
                identity=identity,
                as_of=as_of,
            ),
            "capture_plan": _build_dataset(
                storage,
                conn_url,
                dataset=REPAIR_CAPTURE_PLAN_DATASET,
                schema=REPAIR_CAPTURE_PLAN_SCHEMA,
                frame=capture_plan,
                parents=parents,
                source_capture_ids=source_ids,
                identity=identity,
                as_of=as_of,
            ),
        }
        output_refs = {name: asdict(ref) for name, ref in refs.items()}
        manifest = repair_manifest(
            identity=identity,
            parents={
                "core_eligibility": {
                    "uri": args.core_eligibility_uri,
                    "raw_sha256": raw_shas["core"],
                    "canonical_sha256": CORE_CANONICAL_SHA,
                },
                "auxiliary_eligibility": {
                    "uri": args.auxiliary_eligibility_uri,
                    "raw_sha256": raw_shas["auxiliary"],
                    "canonical_sha256": AUXILIARY_CANONICAL_SHA,
                    "capture_set_raw_sha256": details["capture_set_raw_sha256"],
                },
                "phase3_retained_diagnostic_only": {
                    "uri": args.phase3_retained_uri,
                    "raw_sha256": raw_shas["phase3"],
                    "canonical_sha256": PHASE3_CANONICAL_SHA,
                },
            },
            output_refs=output_refs,
            output_rows={name: len(frame) for name, frame in frames.items()}
            | {"capture_plan": len(capture_plan)},
            population=frames["population"],
            family_admission=family_admission,
            capture_plan_ref=output_refs["capture_plan"],
        )
        _immutable_json(storage, f"{run_prefix}/repair-manifest.json", manifest)
        summary |= {
            "state": "applied",
            "run_prefix": run_prefix,
            "manifest_uri": f"{run_prefix}/repair-manifest.json",
            "manifest_sha256": manifest["manifest_sha256"],
        }
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
