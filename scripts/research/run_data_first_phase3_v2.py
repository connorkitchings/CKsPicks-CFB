#!/usr/bin/env python3
"""Materialize immutable Preview-only Phase 3 v2 evidence from Repair v2."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import pandas as pd
import yaml
from dotenv import load_dotenv

try:  # Supports both `python script.py` and repository-module invocation.
    from scripts.research.run_data_first_phase3 import _compute as v1_compute
except ModuleNotFoundError:  # pragma: no cover - direct script path only
    from run_data_first_phase3 import _compute as v1_compute

from cks_picks_cfb.data.data_first_phase3 import verify_core_eligibility
from cks_picks_cfb.data.data_first_phase3_v2 import (
    PHASE3_V2_DATASETS,
    PHASE3_V2_OUTPUT_ROOT,
    REQUIRED_REPAIR_CANONICAL_SHA256,
    REQUIRED_REPAIR_RAW_SHA256,
    Phase3V2Error,
    build_population,
    certification,
    complete_observation_grid,
    phase3_v2_identity,
    select_retained_core,
    sha256,
    validate_phase3_v2_config,
    verify_repair_manifest,
)
from cks_picks_cfb.data.lake import (
    BuildRequest,
    DatasetRef,
    build_dataset_version,
    read_dataset,
)
from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ratings.phase3_v2 import (
    build_replayable_measurements,
    run_repaired_tournament,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = (
    REPO_ROOT / "conf/research/data_first_football_v1/phase3_measurement_core_v2.yaml"
)
V1_CONFIG = (
    REPO_ROOT / "conf/research/data_first_football_v1/phase3_measurement_core_v1.yaml"
)
RELEVANT_PATHS = (
    "conf/research/data_first_football_v1/phase3_measurement_core_v2.yaml",
    "scripts/research/run_data_first_phase3_v2.py",
    "scripts/research/verify_data_first_phase3_v2.py",
    "src/cks_picks_cfb/data/data_first_phase3_v2.py",
    "src/cks_picks_cfb/ratings/phase3_v2.py",
    "src/cks_picks_cfb/data/schema_contracts.py",
    "tests/test_data_first_phase3_v2.py",
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
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", path],
            cwd=REPO_ROOT,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            raise Phase3V2Error(f"Phase 3 v2 path is not committed: {path}")
    result = subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", *RELEVANT_PATHS],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise Phase3V2Error("Phase 3 v2 code paths differ from committed HEAD")


def _utc(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise Phase3V2Error("--as-of must be timezone-aware")
    return result.astimezone(timezone.utc)


def _ref(value: Mapping[str, Any]) -> DatasetRef:
    return DatasetRef(
        dataset=str(value["dataset"]),
        version_id=str(value["version_id"]),
        schema_version=str(value["schema_version"]),
        content_sha=str(value["content_sha"]),
        uri=str(value["uri"]),
    )


def _immutable_json(storage: Any, uri: str, payload: Mapping[str, Any]) -> None:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=str
    ).encode()
    if storage.exists(uri):
        if storage.read_bytes(uri) != encoded:
            raise Phase3V2Error(f"immutable artifact collision: {uri}")
        return
    storage.write_bytes(encoded, uri)


def _load_config(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text())
    if not isinstance(payload, dict):
        raise Phase3V2Error("Phase 3 v2 configuration must be a mapping")
    validate_phase3_v2_config(payload)
    return payload


def _read_repair_parent(storage: Any, uri: str) -> tuple[dict[str, Any], str]:
    raw = storage.read_bytes(uri)
    raw_sha = hashlib.sha256(raw).hexdigest()
    if raw_sha != REQUIRED_REPAIR_RAW_SHA256:
        raise Phase3V2Error("--repair-manifest-uri is not the sealed Repair v2 parent")
    payload = verify_repair_manifest(json.loads(raw))
    if payload.get("manifest_sha256") != REQUIRED_REPAIR_CANONICAL_SHA256:
        raise Phase3V2Error("Repair parent canonical checksum changed")
    return payload, raw_sha


def _v1_observations(
    *,
    storage: Any,
    repair: Mapping[str, Any],
    identity: Mapping[str, Any],
    as_of: datetime,
) -> pd.DataFrame:
    """Reuse only v1's fixed raw measurement construction."""
    core_uri = ((repair.get("parents") or {}).get("core_eligibility") or {}).get("uri")
    if not core_uri:
        raise Phase3V2Error("Repair manifest does not bind a core eligibility parent")
    core_payload = json.loads(storage.read_bytes(str(core_uri)))
    refs = verify_core_eligibility(core_payload)
    legacy_identity = {
        "code_sha": identity["code_sha"],
        "config_sha": identity["config_sha"],
        "identity_sha256": identity["identity_sha256"],
    }
    computation = v1_compute(
        storage=storage,
        refs=refs,
        identity=legacy_identity,
        config_path=V1_CONFIG,
        as_of=as_of,
    )
    return computation.observations


def compute_phase3_v2(
    *,
    storage: Any,
    repair: Mapping[str, Any],
    identity: Mapping[str, Any],
    as_of: datetime,
) -> dict[str, Any]:
    """Compute all v2 frames without writes; shared by dry run and apply."""
    population_ref = _ref(repair["output_refs"]["population"])
    repair_population = read_dataset(storage, population_ref)
    validate_frame(
        repair_population,
        schema_for(population_ref.dataset, population_ref.schema_version),
    )
    population = build_population(repair_population)
    observed = _v1_observations(
        storage=storage, repair=repair, identity=identity, as_of=as_of
    )
    observations = complete_observation_grid(population=population, observed=observed)
    snapshots, history, terminal = build_replayable_measurements(
        population=population, observations=observations
    )
    predictions = run_repaired_tournament(
        population=population, snapshots=snapshots, terminal=terminal
    )
    attribution, retained = select_retained_core(predictions)
    certified = certification(
        population=population,
        observations=observations,
        snapshots=snapshots,
        history=history,
    )
    if not certified["all_checks_passed"]:
        failed = [name for name, passed in certified["checks"].items() if not passed]
        raise Phase3V2Error(f"Phase 3 v2 certification failed: {failed}")
    frames = {
        "population": population,
        "observations": observations,
        "pregame_snapshots": snapshots,
        "adjusted_history": history,
        "terminal": terminal,
        "predictions": predictions,
        "attribution": attribution,
    }
    for name, frame in frames.items():
        dataset, schema = PHASE3_V2_DATASETS[name]
        validate_frame(frame, schema_for(dataset, schema))
    return {"frames": frames, "certification": certified, "retained": retained}


def _build_dataset(
    *,
    storage: Any,
    dataset: str,
    schema: str,
    frame: pd.DataFrame,
    parents: tuple[DatasetRef, ...],
    identity: Mapping[str, Any],
    as_of: datetime,
) -> DatasetRef:
    validation = validate_frame(frame, schema_for(dataset, schema))
    ref, _ = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset=dataset,
            parent_refs=parents,
            code_sha=str(identity["code_sha"]),
            config_sha=str(identity["config_sha"]),
            as_of=as_of,
            schema_version=schema,
            tier="gold",
        ),
        records=frame.to_dict("records"),
        partitions={"environment": "preview", "stage": "phase3_v2"},
        validation=validation,
    )
    return ref


def _apply(
    *,
    storage: Any,
    run_id: str,
    computation: Mapping[str, Any],
    repair: Mapping[str, Any],
    identity: Mapping[str, Any],
    as_of: datetime,
) -> dict[str, Any]:
    prefix = f"{PHASE3_V2_OUTPUT_ROOT}/{run_id}"
    manifest_uri = f"{prefix}/retained-core-manifest.json"
    if storage.exists(manifest_uri):
        raise Phase3V2Error(f"Phase 3 v2 run already exists: {run_id}")
    repair_population_ref = _ref(repair["output_refs"]["population"])
    parents: tuple[DatasetRef, ...] = (repair_population_ref,)
    output_refs: dict[str, dict[str, Any]] = {}
    for name, frame in computation["frames"].items():
        dataset, schema = PHASE3_V2_DATASETS[name]
        ref = _build_dataset(
            storage=storage,
            dataset=dataset,
            schema=schema,
            frame=frame,
            parents=parents,
            identity=identity,
            as_of=as_of,
        )
        output_refs[name] = asdict(ref)
        parents = (ref,)
    retained = {
        key: value
        for key, value in computation["retained"].items()
        if key != "manifest_sha256"
    } | {
        "identity": dict(identity),
        "repair_manifest_uri": identity["repair_manifest_uri"],
        "repair_manifest_raw_sha256": identity["repair_manifest_raw_sha256"],
        "repair_manifest_canonical_sha256": identity[
            "repair_manifest_canonical_sha256"
        ],
        "output_refs": output_refs,
        "output_rows": {
            name: int(len(frame)) for name, frame in computation["frames"].items()
        },
        "certification_sha256": computation["certification"]["manifest_sha256"],
        "production_activation_authorized": False,
    }
    from cks_picks_cfb.data.data_first_phase2d import signed_payload

    retained = signed_payload(retained)
    _immutable_json(storage, f"{prefix}/identity.json", identity)
    _immutable_json(
        storage, f"{prefix}/certification.json", computation["certification"]
    )
    for name, ref in output_refs.items():
        _immutable_json(storage, f"{prefix}/{name}-ref.json", ref)
    _immutable_json(storage, manifest_uri, retained)
    return {"manifest_uri": manifest_uri, "manifest": retained, "run_prefix": prefix}


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repair-manifest-uri", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--environment", choices=["preview"], required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    config_path = Path(args.config).resolve()
    if config_path != DEFAULT_CONFIG.resolve():
        raise Phase3V2Error("Phase 3 v2 requires the sealed default configuration")
    _load_config(config_path)
    as_of = _utc(args.as_of)
    if args.apply:
        if _git_sha() != args.expected_code_sha:
            raise Phase3V2Error("apply requires --expected-code-sha equal to HEAD")
        if not _tracked_clean():
            raise Phase3V2Error("apply requires a clean tracked worktree")
        _require_committed_paths()
    storage = get_storage(environment="preview")
    repair, raw_sha = _read_repair_parent(storage, args.repair_manifest_uri)
    identity = phase3_v2_identity(
        run_id=args.run_id,
        environment="preview",
        as_of=as_of.isoformat().replace("+00:00", "Z"),
        code_sha=args.expected_code_sha,
        config_sha=sha256(config_path.read_bytes()),
        repair_manifest_uri=args.repair_manifest_uri,
        repair_manifest_raw_sha256=raw_sha,
        repair_manifest_canonical_sha256=repair["manifest_sha256"],
    )
    computation = compute_phase3_v2(
        storage=storage, repair=repair, identity=identity, as_of=as_of
    )
    summary: dict[str, Any] = {
        "state": "dry_run",
        "identity": identity,
        "row_counts": {
            name: len(frame) for name, frame in computation["frames"].items()
        },
        "selected_candidate": computation["retained"]["selected_candidate"],
        "certification_sha256": computation["certification"]["manifest_sha256"],
        "retained_core_sha256": computation["retained"]["manifest_sha256"],
    }
    if args.apply:
        applied = _apply(
            storage=storage,
            run_id=args.run_id,
            computation=computation,
            repair=repair,
            identity=identity,
            as_of=as_of,
        )
        summary |= {
            "state": "applied",
            "manifest_uri": applied["manifest_uri"],
            "run_prefix": applied["run_prefix"],
            "retained_core_sha256": applied["manifest"]["manifest_sha256"],
        }
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
