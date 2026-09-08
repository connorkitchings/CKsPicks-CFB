#!/usr/bin/env python3
"""Execute Preview-only Phase 4A context-free rating selection."""

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
from cks_picks_cfb.data.data_first_phase4a import (
    PHASE4A_ATTRIBUTION_DATASET,
    PHASE4A_ATTRIBUTION_SCHEMA,
    PHASE4A_PREDICTION_DATASET,
    PHASE4A_PREDICTION_SCHEMA,
    PHASE4A_RATING_STATE_DATASET,
    PHASE4A_RATING_STATE_SCHEMA,
    PHASE4A_TEAM_STATE_DATASET,
    PHASE4A_TEAM_STATE_SCHEMA,
    REQUIRED_PHASE3_RETAINED_SHA256,
    Phase4AError,
    canonical_payload,
    phase4a_identity,
    retained_rating_manifest,
    validate_phase4a_config,
    verify_phase3_parent,
)
from cks_picks_cfb.data.lake import (
    BuildRequest,
    DatasetRef,
    build_dataset_version,
    read_dataset,
)
from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ratings.contracts import load_measurement_config
from cks_picks_cfb.ratings.phase3 import build_adjusted_measurements
from cks_picks_cfb.ratings.phase4a import (
    Phase4AComputation,
    build_rating_states,
    build_team_states,
    evaluate_rating_tournament,
    run_rating_tournament,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = (
    REPO_ROOT / "conf/research/data_first_football_v1/phase4a_rating_v1.yaml"
)
PHASE3_CONFIG = (
    REPO_ROOT / "conf/research/data_first_football_v1/phase3_measurement_core_v1.yaml"
)
OUTPUT_ROOT = "artifacts/research/data-first-football-v1/phase4a"
RELEVANT_PATHS = (
    "conf/research/data_first_football_v1/phase4a_rating_v1.yaml",
    "scripts/research/run_data_first_phase4a.py",
    "scripts/research/verify_data_first_phase4a.py",
    "src/cks_picks_cfb/data/data_first_phase4a.py",
    "src/cks_picks_cfb/data/schema_contracts.py",
    "src/cks_picks_cfb/ratings/phase3.py",
    "src/cks_picks_cfb/ratings/phase4a.py",
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
            raise Phase4AError(f"Phase 4A code path is not committed: {path}")
    if subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", *RELEVANT_PATHS],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
    ).returncode:
        raise Phase4AError("Phase 4A code paths differ from committed HEAD")


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
            raise Phase4AError(f"immutable Phase 4A artifact collision: {uri}")
        return
    storage.write_bytes(encoded, uri)


def _parent_frames(
    storage: Any, manifest: dict[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[dict[str, Any]]]:
    observations_ref = _ref(manifest["output_refs"]["observations"])
    observations = read_dataset(storage, observations_ref)
    identity = manifest["identity"]
    core_uri = str(identity["core_eligibility_uri"])
    raw_core = storage.read_bytes(core_uri)
    if hashlib.sha256(raw_core).hexdigest() != REQUIRED_CORE_ELIGIBILITY_SHA256:
        raise Phase4AError("Phase 3 parent does not bind the approved Phase 2d handoff")
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
    return observations, game_frame, outcome_frame, refs


def compute(
    *,
    storage: Any,
    manifest: dict[str, Any],
    identity: dict[str, Any],
    config: dict[str, Any],
) -> Phase4AComputation:
    observations, games, outcomes, _ = _parent_frames(storage, manifest)
    measurement_config = load_measurement_config(PHASE3_CONFIG)
    adjusted_by_mode: dict[str, tuple[pd.DataFrame, pd.DataFrame]] = {}
    for mode in (
        "primary",
        "half_life_2_games",
        "half_life_4_games",
        "half_life_8_games",
    ):
        adjusted_by_mode[mode] = build_adjusted_measurements(
            observations=observations,
            games=games,
            config=measurement_config,
            identity_sha=str(identity["identity_sha256"]),
            code_sha=str(identity["code_sha"]),
            config_sha=str(identity["config_sha"]),
            recency_mode=mode,
        )
    state_frames = []
    for candidate in config["candidates"]:
        mode = (
            "primary"
            if candidate.endswith("__exposure")
            else f"half_life_{candidate.rsplit('_', 1)[1]}_games"
        )
        adjusted, terminal = adjusted_by_mode[mode]
        state_frames.append(
            build_rating_states(
                adjusted=adjusted,
                terminal=terminal,
                candidate=candidate,
                identity_sha=str(identity["identity_sha256"]),
                code_sha=str(identity["code_sha"]),
                config_sha=str(identity["config_sha"]),
            )
        )
    states = pd.concat(state_frames, ignore_index=True)
    teams = build_team_states(states)
    predictions = run_rating_tournament(
        teams, games, outcomes, ridge_alpha=float(config["selection"]["ridge_alpha"])
    )
    attribution = evaluate_rating_tournament(predictions)
    retained = retained_rating_manifest(
        identity=identity, phase3_parent=manifest, attribution=attribution
    )
    return Phase4AComputation(states, teams, predictions, attribution, retained)


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
    computation: Phase4AComputation,
    manifest: dict[str, Any],
    identity: dict[str, Any],
    as_of: datetime,
) -> dict[str, Any]:
    prefix = f"{OUTPUT_ROOT}/runs/{run_id}"
    uri = f"{prefix}/retained-rating-manifest.json"
    if storage.exists(uri):
        raise Phase4AError(f"Phase 4A run identity already exists: {run_id}")
    parent = _ref(manifest["output_refs"]["adjusted_measurements"])
    state_ref = _build_dataset(
        storage,
        PHASE4A_RATING_STATE_DATASET,
        PHASE4A_RATING_STATE_SCHEMA,
        computation.rating_states,
        (parent,),
        identity,
        as_of,
    )
    team_ref = _build_dataset(
        storage,
        PHASE4A_TEAM_STATE_DATASET,
        PHASE4A_TEAM_STATE_SCHEMA,
        computation.team_states,
        (state_ref,),
        identity,
        as_of,
    )
    prediction_ref = _build_dataset(
        storage,
        PHASE4A_PREDICTION_DATASET,
        PHASE4A_PREDICTION_SCHEMA,
        computation.predictions,
        (team_ref,),
        identity,
        as_of,
    )
    attribution_ref = _build_dataset(
        storage,
        PHASE4A_ATTRIBUTION_DATASET,
        PHASE4A_ATTRIBUTION_SCHEMA,
        computation.attribution,
        (prediction_ref,),
        identity,
        as_of,
    )
    refs = {
        "rating_states": asdict(state_ref),
        "team_states": asdict(team_ref),
        "fold_predictions": asdict(prediction_ref),
        "attribution_coverage": asdict(attribution_ref),
    }
    final = retained_rating_manifest(
        identity=identity,
        phase3_parent=manifest,
        attribution=computation.attribution,
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
    parser.add_argument("--phase3-retained-uri", required=True)
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
        raise Phase4AError("Phase 4A is Preview-only")
    if _git_sha() != args.expected_code_sha or not _tracked_clean():
        raise Phase4AError(
            "Phase 4A requires a clean tracked worktree at the expected committed SHA"
        )
    _require_committed_paths()
    config_path = Path(args.config).resolve()
    if config_path != DEFAULT_CONFIG.resolve():
        raise Phase4AError("Phase 4A requires its sealed default configuration")
    config = yaml.safe_load(config_path.read_text())
    validate_phase4a_config(config)
    as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
    if as_of.tzinfo is None:
        raise Phase4AError("--as-of must be timezone-aware")
    storage = get_storage(environment="preview")
    raw = storage.read_bytes(args.phase3_retained_uri)
    raw_sha = hashlib.sha256(raw).hexdigest()
    if raw_sha != REQUIRED_PHASE3_RETAINED_SHA256:
        raise Phase4AError(
            "--phase3-retained-uri is not the approved signed Phase 3 handoff"
        )
    manifest = verify_phase3_parent(json.loads(raw))
    identity = phase4a_identity(
        run_id=args.run_id,
        environment="preview",
        as_of=as_of.astimezone(timezone.utc).isoformat(),
        code_sha=_git_sha(),
        config_sha=hashlib.sha256(config_path.read_bytes()).hexdigest(),
        phase3_retained_uri=args.phase3_retained_uri,
        phase3_retained_sha256=raw_sha,
    )
    result = compute(
        storage=storage, manifest=manifest, identity=identity, config=config
    )
    summary: dict[str, Any] = {
        "status": "dry_run",
        "identity": identity,
        "selected_candidate": result.retained_rating["selected_candidate"],
        "rating_state_rows": len(result.rating_states),
        "team_state_rows": len(result.team_states),
        "prediction_rows": len(result.predictions),
        "attribution_rows": len(result.attribution),
    }
    if args.apply:
        written = apply(
            storage=storage,
            run_id=args.run_id,
            computation=result,
            manifest=manifest,
            identity=identity,
            as_of=as_of.astimezone(timezone.utc),
        )
        summary |= {
            "status": "applied",
            "manifest_uri": written["manifest_uri"],
            "retained_rating_sha256": written["manifest"]["manifest_sha256"],
        }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
