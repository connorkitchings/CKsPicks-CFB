#!/usr/bin/env python3
"""Execute Preview-only Phase 4B target-context selection."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_phase2 import DEVELOPMENT_SEASONS
from cks_picks_cfb.data.data_first_phase3 import (
    REQUIRED_CORE_ELIGIBILITY_SHA256,
    verify_core_eligibility,
)
from cks_picks_cfb.data.data_first_phase4b import (
    PHASE4B_ATTRIBUTION_DATASET,
    PHASE4B_ATTRIBUTION_SCHEMA,
    PHASE4B_COVERAGE_DATASET,
    PHASE4B_COVERAGE_SCHEMA,
    PHASE4B_PREDICTION_DATASET,
    PHASE4B_PREDICTION_SCHEMA,
    REQUIRED_PHASE2E_ELIGIBILITY_SHA256,
    REQUIRED_PHASE3_RETAINED_SHA256,
    REQUIRED_PHASE4A_RETAINED_SHA256,
    Phase4BError,
    canonical_payload,
    phase4b_identity,
    retained_baseline_manifest,
    validate_phase4b_config,
    verify_phase2e_parent,
    verify_phase3_parent,
    verify_phase4a_parent,
)
from cks_picks_cfb.data.lake import (
    BuildRequest,
    DatasetRef,
    build_dataset_version,
    read_dataset,
)
from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ratings.phase4b import (
    Phase4BComputation,
    evaluate_context_tournament,
    run_context_tournament,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = (
    REPO_ROOT / "conf/research/data_first_football_v1/phase4b_target_context_v1.yaml"
)
OUTPUT_ROOT = "artifacts/research/data-first-football-v1/phase4b"
RELEVANT_PATHS = (
    "conf/research/data_first_football_v1/phase4b_target_context_v1.yaml",
    "scripts/research/run_data_first_phase4b.py",
    "scripts/research/verify_data_first_phase4b.py",
    "src/cks_picks_cfb/data/data_first_phase4b.py",
    "src/cks_picks_cfb/data/schema_contracts.py",
    "src/cks_picks_cfb/ratings/phase4b.py",
)


def _git_sha() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()


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
        if subprocess.run(
            ["git", "ls-files", "--error-unmatch", path],
            cwd=REPO_ROOT,
            capture_output=True,
            check=False,
        ).returncode:
            raise Phase4BError(f"Phase 4B code path is not committed: {path}")
    if subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", *RELEVANT_PATHS],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
    ).returncode:
        raise Phase4BError("Phase 4B code paths differ from committed HEAD")


def _ref(value: dict[str, Any]) -> DatasetRef:
    return DatasetRef(
        dataset=str(value["dataset"]),
        version_id=str(value["version_id"]),
        schema_version=str(value["schema_version"]),
        content_sha=str(value["content_sha"]),
        uri=str(value["uri"]),
    )


def _write_immutable_json(storage: Any, uri: str, payload: dict[str, Any]) -> None:
    encoded = canonical_payload(payload)
    if storage.exists(uri):
        if storage.read_bytes(uri) != encoded:
            raise Phase4BError(f"immutable Phase 4B artifact collision: {uri}")
        return
    storage.write_bytes(encoded, uri)


def _load_parent_data(
    storage: Any,
    phase4a_manifest: dict[str, Any],
    phase3_manifest: dict[str, Any],
    phase2e_manifest: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    """Load all parent datasets needed for Phase 4B."""
    phase4a_team_states_ref = _ref(phase4a_manifest["output_refs"]["team_states"])
    team_states = read_dataset(storage, phase4a_team_states_ref)
    phase3_observations_ref = _ref(phase3_manifest["output_refs"]["observations"])
    observations = read_dataset(storage, phase3_observations_ref)
    phase3_identity = phase3_manifest["identity"]
    core_uri = str(phase3_identity["core_eligibility_uri"])
    raw_core = storage.read_bytes(core_uri)
    if hashlib.sha256(raw_core).hexdigest() != REQUIRED_CORE_ELIGIBILITY_SHA256:
        raise Phase4BError("Phase 3 parent does not bind the approved Phase 2d handoff")
    refs = verify_core_eligibility(json.loads(raw_core))
    games, outcomes = [], []
    for ref in refs:
        if ref["dataset"] in {"fbs_involved_games", "game_outcomes"}:
            frame = read_dataset(storage, _ref(ref))
            (games if ref["dataset"] == "fbs_involved_games" else outcomes).append(
                frame
            )
    game_frame = pd.concat(games, ignore_index=True).drop_duplicates(
        ["season", "game_id"]
    )
    outcome_frame = pd.concat(outcomes, ignore_index=True).drop_duplicates(
        ["season", "game_id"]
    )
    accepted_games = set(
        observations[["season", "game_id"]]
        .drop_duplicates()
        .itertuples(index=False, name=None)
    )
    game_frame = game_frame[
        game_frame[["season", "game_id"]].apply(
            lambda row: (int(row.iloc[0]), int(row.iloc[1])) in accepted_games,
            axis=1,
        )
    ].copy()
    context_datasets: dict[str, pd.DataFrame] = {}
    context_only_measurements = {
        "field_position": "average_start_field_position",
        "pace": "plays_per_drive",
        "turnovers": "turnover_rate",
    }
    for family, measurement_id in context_only_measurements.items():
        context_datasets[family] = observations[
            observations["measurement_id"] == measurement_id
        ].copy()
    phase2e_inputs = phase2e_manifest.get("inputs") or {}
    for family in (
        "recruiting",
        "returning_production",
        "coaching",
        "roster_continuity",
        "lagged_rankings",
    ):
        ref_data = phase2e_inputs.get(family)
        if ref_data is None:
            raise Phase4BError(f"Phase 2e parent lacks input for {family}")
        context_datasets[family] = read_dataset(storage, _ref(ref_data))
    return team_states, game_frame, outcome_frame, context_datasets


def compute(
    *,
    storage: Any,
    phase4a_manifest: dict[str, Any],
    phase3_manifest: dict[str, Any],
    phase2e_manifest: dict[str, Any],
    identity: dict[str, Any],
    config: dict[str, Any],
) -> Phase4BComputation:
    team_states, games, outcomes, context_datasets = _load_parent_data(
        storage, phase4a_manifest, phase3_manifest, phase2e_manifest
    )
    predictions, coverage = run_context_tournament(
        team_states,
        games,
        outcomes,
        context_datasets,
        ridge_alpha=float(config["selection"]["ridge_alpha"]),
    )
    attribution = evaluate_context_tournament(predictions)
    margin_attribution = attribution[attribution["target"] == "margin"]
    total_attribution = attribution[attribution["target"] == "total"]
    retained = retained_baseline_manifest(
        identity=identity,
        phase4a_parent=phase4a_manifest,
        phase3_parent=phase3_manifest,
        phase2e_parent=phase2e_manifest,
        margin_attribution=margin_attribution,
        total_attribution=total_attribution,
    )
    return Phase4BComputation(predictions, attribution, coverage, retained)


def _build_dataset(
    storage: Any,
    dataset: str,
    schema: str,
    frame: pd.DataFrame,
    parents: tuple[DatasetRef, ...],
    identity: dict[str, Any],
    as_of: datetime,
) -> DatasetRef:
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
        partitions={"seasons": list(DEVELOPMENT_SEASONS), "environment": "preview"},
        validation=validate_frame(frame, schema_for(dataset, schema)),
    )
    return ref


def apply(
    *,
    storage: Any,
    run_id: str,
    computation: Phase4BComputation,
    phase4a_manifest: dict[str, Any],
    phase3_manifest: dict[str, Any],
    phase2e_manifest: dict[str, Any],
    identity: dict[str, Any],
    as_of: datetime,
) -> dict[str, Any]:
    prefix = f"{OUTPUT_ROOT}/runs/{run_id}"
    uri = f"{prefix}/retained-baseline-manifest.json"
    if storage.exists(uri):
        raise Phase4BError(f"Phase 4B run identity already exists: {run_id}")
    phase4a_team_ref = _ref(phase4a_manifest["output_refs"]["team_states"])
    prediction_ref = _build_dataset(
        storage,
        PHASE4B_PREDICTION_DATASET,
        PHASE4B_PREDICTION_SCHEMA,
        computation.predictions,
        (phase4a_team_ref,),
        identity,
        as_of,
    )
    attribution_ref = _build_dataset(
        storage,
        PHASE4B_ATTRIBUTION_DATASET,
        PHASE4B_ATTRIBUTION_SCHEMA,
        computation.attribution,
        (prediction_ref,),
        identity,
        as_of,
    )
    coverage_ref = _build_dataset(
        storage,
        PHASE4B_COVERAGE_DATASET,
        PHASE4B_COVERAGE_SCHEMA,
        computation.coverage,
        (attribution_ref,),
        identity,
        as_of,
    )
    refs = {
        "context_predictions": asdict(prediction_ref),
        "context_attribution": asdict(attribution_ref),
        "context_coverage": asdict(coverage_ref),
    }
    final = retained_baseline_manifest(
        identity=identity,
        phase4a_parent=phase4a_manifest,
        phase3_parent=phase3_manifest,
        phase2e_parent=phase2e_manifest,
        margin_attribution=computation.attribution[
            computation.attribution["target"] == "margin"
        ],
        total_attribution=computation.attribution[
            computation.attribution["target"] == "total"
        ],
        output_refs=refs,
    )
    _write_immutable_json(storage, f"{prefix}/identity.json", identity)
    for name, value in refs.items():
        _write_immutable_json(storage, f"{prefix}/{name}-ref.json", value)
    _write_immutable_json(storage, uri, final)
    return {"manifest_uri": uri, "manifest": final}


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase4-rating-uri", required=True)
    parser.add_argument("--phase3-retained-uri", required=True)
    parser.add_argument("--auxiliary-eligibility-uri", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument(
        "--environment", choices=["preview", "production"], required=True
    )
    parser.add_argument("--as-of", default="2026-03-01T00:00:00Z")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    if args.environment != "preview":
        raise Phase4BError("Phase 4B is Preview-only")
    if _git_sha() != args.expected_code_sha or not _tracked_clean():
        raise Phase4BError(
            "Phase 4B requires a clean tracked worktree at the expected committed SHA"
        )
    _require_committed_paths()
    config_path = Path(args.config).resolve()
    if config_path != DEFAULT_CONFIG.resolve():
        raise Phase4BError("Phase 4B requires its sealed default configuration")
    config = yaml.safe_load(config_path.read_text())
    validate_phase4b_config(config)
    as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
    if as_of.tzinfo is None:
        raise Phase4BError("--as-of must be timezone-aware")
    storage = get_storage(environment="preview")
    raw_4a = storage.read_bytes(args.phase4_rating_uri)
    raw_4a_sha = hashlib.sha256(raw_4a).hexdigest()
    if raw_4a_sha != REQUIRED_PHASE4A_RETAINED_SHA256:
        raise Phase4BError(
            "--phase4-rating-uri is not the approved signed Phase 4A handoff"
        )
    phase4a_manifest = verify_phase4a_parent(json.loads(raw_4a))
    raw_3 = storage.read_bytes(args.phase3_retained_uri)
    raw_3_sha = hashlib.sha256(raw_3).hexdigest()
    if raw_3_sha != REQUIRED_PHASE3_RETAINED_SHA256:
        raise Phase4BError(
            "--phase3-retained-uri is not the approved signed Phase 3 handoff"
        )
    phase3_manifest = verify_phase3_parent(json.loads(raw_3))
    raw_2e = storage.read_bytes(args.auxiliary_eligibility_uri)
    raw_2e_sha = hashlib.sha256(raw_2e).hexdigest()
    if raw_2e_sha != REQUIRED_PHASE2E_ELIGIBILITY_SHA256:
        raise Phase4BError(
            "--auxiliary-eligibility-uri is not the approved signed Phase 2e handoff"
        )
    phase2e_manifest = verify_phase2e_parent(json.loads(raw_2e))
    identity = phase4b_identity(
        run_id=args.run_id,
        environment="preview",
        as_of=as_of.astimezone(timezone.utc).isoformat(),
        code_sha=_git_sha(),
        config_sha=hashlib.sha256(config_path.read_bytes()).hexdigest(),
        phase4a_retained_uri=args.phase4_rating_uri,
        phase4a_retained_sha256=raw_4a_sha,
        phase3_retained_uri=args.phase3_retained_uri,
        phase3_retained_sha256=raw_3_sha,
        phase2e_eligibility_uri=args.auxiliary_eligibility_uri,
        phase2e_eligibility_sha256=raw_2e_sha,
    )
    result = compute(
        storage=storage,
        phase4a_manifest=phase4a_manifest,
        phase3_manifest=phase3_manifest,
        phase2e_manifest=phase2e_manifest,
        identity=identity,
        config=config,
    )
    summary: dict[str, Any] = {
        "status": "dry_run",
        "identity": identity,
        "margin_context_selected": result.retained_baseline["margin_context_selected"],
        "total_context_selected": result.retained_baseline["total_context_selected"],
        "prediction_rows": len(result.predictions),
        "attribution_rows": len(result.attribution),
        "coverage_rows": len(result.coverage),
    }
    if args.apply:
        written = apply(
            storage=storage,
            run_id=args.run_id,
            computation=result,
            phase4a_manifest=phase4a_manifest,
            phase3_manifest=phase3_manifest,
            phase2e_manifest=phase2e_manifest,
            identity=identity,
            as_of=as_of.astimezone(timezone.utc),
        )
        summary |= {
            "status": "applied",
            "manifest_uri": written["manifest_uri"],
            "retained_baseline_sha256": written["manifest"]["manifest_sha256"],
        }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
