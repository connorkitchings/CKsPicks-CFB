#!/usr/bin/env python3
"""Execute Preview-only Phase 3 measurement certification and core selection."""

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
from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_phase2 import DEVELOPMENT_SEASONS
from cks_picks_cfb.data.data_first_phase2d import sha256, signed_payload
from cks_picks_cfb.data.data_first_phase3 import (
    PHASE3_ADJUSTED_DATASET,
    PHASE3_ADJUSTED_SCHEMA,
    PHASE3_ATTRIBUTION_DATASET,
    PHASE3_ATTRIBUTION_SCHEMA,
    PHASE3_OBSERVATION_DATASET,
    PHASE3_OBSERVATION_SCHEMA,
    PHASE3_PREDICTION_DATASET,
    PHASE3_PREDICTION_SCHEMA,
    REQUIRED_CORE_ELIGIBILITY_SHA256,
    Phase3Error,
    canonical_payload,
    phase3_identity,
    validate_phase3_config,
    verify_core_eligibility,
)
from cks_picks_cfb.data.lake import (
    BuildRequest,
    DatasetRef,
    build_dataset_version,
    read_dataset,
    require_dataset,
)
from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ratings.contracts import (
    OBSERVATION_COLUMNS,
    load_measurement_config,
    validate_observation_frame,
)
from cks_picks_cfb.ratings.observations import build_measurement_observations
from cks_picks_cfb.ratings.phase3 import (
    Phase3Computation,
    build_adjusted_measurements,
    build_component_states,
    build_pass_rush_observations,
    certify_measurements,
    evaluate_tournament,
    independent_definition_audit,
    run_candidate_tournament,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = (
    REPO_ROOT / "conf/research/data_first_football_v1/phase3_measurement_core_v1.yaml"
)
DEFAULT_AS_OF = "2026-03-01T00:00:00Z"
OUTPUT_ROOT = "artifacts/research/data-first-football-v1/phase3"
RELEVANT_PATHS = (
    "conf/research/data_first_football_v1/phase3_measurement_core_v1.yaml",
    "scripts/research/run_data_first_phase3.py",
    "src/cks_picks_cfb/data/data_first_phase3.py",
    "src/cks_picks_cfb/data/schema_contracts.py",
    "src/cks_picks_cfb/ratings/phase3.py",
)


def _git_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _tracked_clean() -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )
    return result.returncode == 0 and not result.stdout.strip()


def _require_committed_paths() -> None:
    for path in RELEVANT_PATHS:
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", path],
            capture_output=True,
            check=False,
            cwd=REPO_ROOT,
        )
        if tracked.returncode:
            raise Phase3Error(f"Phase 3 code path is not committed: {path}")
    matching = subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", *RELEVANT_PATHS],
        capture_output=True,
        check=False,
        cwd=REPO_ROOT,
    )
    if matching.returncode:
        raise Phase3Error("Phase 3 code paths differ from the committed HEAD")


def _write_immutable_json(storage: Any, uri: str, payload: dict[str, Any]) -> None:
    encoded = canonical_payload(payload)
    if storage.exists(uri):
        if storage.read_bytes(uri) != encoded:
            raise Phase3Error(f"immutable Phase 3 artifact collision: {uri}")
        return
    storage.write_bytes(encoded, uri)


def _ref(value: dict[str, Any]) -> DatasetRef:
    return DatasetRef(
        dataset=str(value["dataset"]),
        version_id=str(value["version_id"]),
        schema_version=str(value["schema_version"]),
        content_sha=str(value["content_sha"]),
        uri=str(value["uri"]),
    )


def _compute(
    *,
    storage: Any,
    refs: list[dict[str, Any]],
    identity: dict[str, Any],
    config_path: Path,
    as_of: datetime,
) -> Phase3Computation:
    config = load_measurement_config(config_path)
    validate_phase3_config(config.raw_config)
    config_sha = hashlib.sha256(config_path.read_bytes()).hexdigest()
    code_sha = str(identity["code_sha"])
    parent_ref_shas = ";".join(str(ref["content_sha"]) for ref in refs)
    by_season: dict[int, dict[str, DatasetRef]] = {
        season: {} for season in DEVELOPMENT_SEASONS
    }
    for value in refs:
        season = int(value["season"])
        ref = _ref(value)
        require_dataset(ref, str(value["dataset"]))
        by_season[season][ref.dataset] = ref

    observation_frames: list[pd.DataFrame] = []
    schedule_frames: list[pd.DataFrame] = []
    outcome_frames: list[pd.DataFrame] = []
    observation_audits: dict[int, dict[str, Any]] = {}
    classification_audits: dict[int, dict[str, Any]] = {}
    definition_audits: dict[int, dict[str, Any]] = {}
    for season in DEVELOPMENT_SEASONS:
        season_refs = by_season[season]
        if len(season_refs) != 7:
            raise Phase3Error(f"season {season} does not resolve all seven parents")
        # All 70 physical Parquet checksums are verified here. The plays and
        # team-game-stat frames are certification parents, never model inputs.
        frames = {
            dataset: read_dataset(storage, ref)
            for dataset, ref in sorted(season_refs.items())
        }
        games = frames["fbs_involved_games"]
        outcomes = frames["game_outcomes"]
        base = build_measurement_observations(
            byplay=frames["byplay"],
            drives=frames["drives"],
            games=games,
            outcomes=outcomes,
            reconciled_team_game=frames["reconciled_team_game"],
            config=config,
            as_of=as_of,
            code_sha=code_sha,
            config_sha=config_sha,
            parent_ref_shas=parent_ref_shas,
        )
        validate_observation_frame(base.frame, config)
        pass_rush, pass_rush_audit = build_pass_rush_observations(
            byplay=frames["byplay"], base_observations=base.frame
        )
        observation_frames.extend([base.frame, pass_rush])
        schedule_frames.append(games)
        outcome_frames.append(outcomes)
        observation_audits[season] = base.audit
        classification_audits[season] = pass_rush_audit
        definition_audits[season] = independent_definition_audit(
            byplay=frames["byplay"],
            drives=frames["drives"],
            observations=base.frame,
        )
        observation_audits[season]["verified_parent_rows"] = {
            "plays": int(len(frames["plays"])),
            "team_game_stats": int(len(frames["team_game_stats"])),
        }

    observations = pd.concat(observation_frames, ignore_index=True)[
        list(OBSERVATION_COLUMNS)
    ]
    observations = observations.sort_values(
        ["season", "week", "game_id", "team", "measurement_id", "unit_role"],
        kind="mergesort",
    ).reset_index(drop=True)
    games = pd.concat(schedule_frames, ignore_index=True).drop_duplicates(
        ["season", "game_id"]
    )
    outcomes = pd.concat(outcome_frames, ignore_index=True).drop_duplicates(
        ["season", "game_id"]
    )

    adjusted_frames: list[pd.DataFrame] = []
    terminal_frames: list[pd.DataFrame] = []
    for recency_mode in ("primary", "half_life_4_games"):
        adjusted, terminal = build_adjusted_measurements(
            observations=observations,
            games=games,
            config=config,
            identity_sha=str(identity["identity_sha256"]),
            code_sha=code_sha,
            config_sha=config_sha,
            recency_mode=recency_mode,
        )
        adjusted_frames.append(adjusted)
        terminal_frames.append(terminal)
    adjusted_measurements = pd.concat(adjusted_frames, ignore_index=True)
    adjusted_measurements = adjusted_measurements.sort_values(
        [
            "recency_mode",
            "season",
            "week",
            "as_of_game_id",
            "team",
            "measurement_id",
            "unit_role",
            "adjustment_iteration",
        ],
        kind="mergesort",
    ).reset_index(drop=True)
    terminal_measurements = pd.concat(terminal_frames, ignore_index=True)
    primary_states = build_component_states(
        adjusted=adjusted_measurements,
        terminal=terminal_measurements,
        recency_mode="primary",
    )
    sensitivity_states = build_component_states(
        adjusted=adjusted_measurements,
        terminal=terminal_measurements,
        recency_mode="half_life_4_games",
    )
    selection = config.raw_config["selection"]
    predictions = run_candidate_tournament(
        primary_states=primary_states,
        sensitivity_states=sensitivity_states,
        games=games,
        outcomes=outcomes,
        ridge_alpha=float(selection["ridge_alpha"]),
    )
    attribution, retained = evaluate_tournament(
        predictions,
        minimum_improvement_pct=float(selection["minimum_pooled_improvement_pct"]),
        maximum_seasonal_regression_pct=float(
            selection["maximum_seasonal_regression_pct"]
        ),
        sensitivity_maximum_regression_pct=float(
            selection["sensitivity"]["maximum_regression_vs_epa_only_pct"]
        ),
        bootstrap_replicates=int(selection["bootstrap_replicates"]),
        bootstrap_confidence=float(selection["bootstrap_confidence"]),
        bootstrap_seed=int(selection["bootstrap_seed"]),
    )
    certification = certify_measurements(
        observations=observations,
        adjusted=adjusted_measurements,
        observation_audits=observation_audits,
        pass_rush_audits=classification_audits,
        definition_audits=definition_audits,
    )
    if not certification["all_checks_passed"]:
        failed = [key for key, passed in certification["checks"].items() if not passed]
        raise Phase3Error(f"measurement certification failed: {failed}")
    retained = signed_payload(
        {key: value for key, value in retained.items() if key != "manifest_sha256"}
        | {
            "identity": identity,
            "parent_ref_count": len(refs),
            "parent_ref_set_sha256": sha256(refs),
            "measurement_certification_sha256": certification["report_sha256"],
            "fold_predictions_sha256": sha256(predictions.to_dict("records")),
        }
    )
    return Phase3Computation(
        observations=observations,
        adjusted_measurements=adjusted_measurements,
        fold_predictions=predictions,
        attribution=attribution,
        retained_core=retained,
        certification=certification,
    )


def _build_dataset(
    *,
    storage: Any,
    dataset: str,
    schema_version: str,
    frame: pd.DataFrame,
    parents: tuple[DatasetRef, ...],
    identity: dict[str, Any],
    as_of: datetime,
) -> DatasetRef:
    validation = validate_frame(frame, schema_for(dataset, schema_version))
    ref, _ = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset=dataset,
            parent_refs=parents,
            code_sha=str(identity["code_sha"]),
            config_sha=str(identity["config_sha"]),
            as_of=as_of,
            schema_version=schema_version,
            tier="gold",
        ),
        records=frame.to_dict("records"),
        partitions={"seasons": list(DEVELOPMENT_SEASONS), "environment": "preview"},
        validation=validation,
    )
    return ref


def _apply(
    *,
    storage: Any,
    run_id: str,
    computation: Phase3Computation,
    refs: list[dict[str, Any]],
    identity: dict[str, Any],
    as_of: datetime,
) -> dict[str, Any]:
    run_prefix = f"{OUTPUT_ROOT}/runs/{run_id}"
    manifest_uri = f"{run_prefix}/retained-core-manifest.json"
    if storage.exists(manifest_uri):
        raise Phase3Error(f"Phase 3 run identity already exists: {run_id}")
    parents = tuple(_ref(value) for value in refs)
    observations_ref = _build_dataset(
        storage=storage,
        dataset=PHASE3_OBSERVATION_DATASET,
        schema_version=PHASE3_OBSERVATION_SCHEMA,
        frame=computation.observations,
        parents=parents,
        identity=identity,
        as_of=as_of,
    )
    adjusted_ref = _build_dataset(
        storage=storage,
        dataset=PHASE3_ADJUSTED_DATASET,
        schema_version=PHASE3_ADJUSTED_SCHEMA,
        frame=computation.adjusted_measurements,
        parents=(observations_ref,),
        identity=identity,
        as_of=as_of,
    )
    predictions_ref = _build_dataset(
        storage=storage,
        dataset=PHASE3_PREDICTION_DATASET,
        schema_version=PHASE3_PREDICTION_SCHEMA,
        frame=computation.fold_predictions,
        parents=(adjusted_ref,),
        identity=identity,
        as_of=as_of,
    )
    attribution_ref = _build_dataset(
        storage=storage,
        dataset=PHASE3_ATTRIBUTION_DATASET,
        schema_version=PHASE3_ATTRIBUTION_SCHEMA,
        frame=computation.attribution,
        parents=(predictions_ref,),
        identity=identity,
        as_of=as_of,
    )
    output_refs = {
        "observations": asdict(observations_ref),
        "adjusted_measurements": asdict(adjusted_ref),
        "fold_predictions": asdict(predictions_ref),
        "attribution_coverage": asdict(attribution_ref),
    }
    final_manifest = signed_payload(
        {
            key: value
            for key, value in computation.retained_core.items()
            if key != "manifest_sha256"
        }
        | {"output_refs": output_refs}
    )
    _write_immutable_json(storage, f"{run_prefix}/identity.json", identity)
    _write_immutable_json(
        storage,
        f"{run_prefix}/measurement-certification.json",
        computation.certification,
    )
    for name, value in output_refs.items():
        _write_immutable_json(storage, f"{run_prefix}/{name}-ref.json", value)
    _write_immutable_json(storage, manifest_uri, final_manifest)
    return {
        "run_prefix": run_prefix,
        "manifest_uri": manifest_uri,
        "manifest": final_manifest,
    }


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-eligibility-uri", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--environment", choices=["preview", "production"], required=True
    )
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--as-of", default=DEFAULT_AS_OF)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    if args.environment != "preview":
        raise Phase3Error("Phase 3 is Preview-only")
    code_sha = _git_sha()
    if code_sha != args.expected_code_sha:
        raise Phase3Error("HEAD does not match --expected-code-sha")
    if not _tracked_clean():
        raise Phase3Error("Phase 3 runs require a clean tracked worktree")
    _require_committed_paths()
    config_path = Path(args.config).resolve()
    if config_path != DEFAULT_CONFIG.resolve():
        raise Phase3Error("Phase 3 requires the sealed default configuration")
    config_bytes = config_path.read_bytes()
    as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
    if as_of.tzinfo is None:
        raise Phase3Error("--as-of must be timezone-aware")
    as_of = as_of.astimezone(timezone.utc)
    storage = get_storage(environment="preview")
    raw_parent = storage.read_bytes(args.core_eligibility_uri)
    raw_parent_sha = hashlib.sha256(raw_parent).hexdigest()
    if raw_parent_sha != REQUIRED_CORE_ELIGIBILITY_SHA256:
        raise Phase3Error("--core-eligibility-uri is not the approved Phase 2d handoff")
    refs = verify_core_eligibility(json.loads(raw_parent))
    identity = phase3_identity(
        run_id=args.run_id,
        environment=args.environment,
        as_of=as_of.isoformat(),
        code_sha=code_sha,
        config_sha=hashlib.sha256(config_bytes).hexdigest(),
        core_eligibility_uri=args.core_eligibility_uri,
        core_eligibility_sha256=raw_parent_sha,
    )
    computation = _compute(
        storage=storage,
        refs=refs,
        identity=identity,
        config_path=config_path,
        as_of=as_of,
    )
    summary: dict[str, Any] = {
        "status": "dry_run",
        "identity": identity,
        "parent_ref_count": len(refs),
        "selected_candidate": computation.retained_core["selected_candidate"],
        "observation_rows": len(computation.observations),
        "adjusted_rows": len(computation.adjusted_measurements),
        "prediction_rows": len(computation.fold_predictions),
        "certification_sha256": computation.certification["report_sha256"],
        "retained_core_sha256": computation.retained_core["manifest_sha256"],
    }
    if args.apply:
        applied = _apply(
            storage=storage,
            run_id=args.run_id,
            computation=computation,
            refs=refs,
            identity=identity,
            as_of=as_of,
        )
        summary.update(
            {
                "status": "applied",
                "run_prefix": applied["run_prefix"],
                "manifest_uri": applied["manifest_uri"],
                "retained_core_sha256": applied["manifest"]["manifest_sha256"],
            }
        )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
