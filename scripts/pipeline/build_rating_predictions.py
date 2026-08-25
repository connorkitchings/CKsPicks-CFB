#!/usr/bin/env python3
"""Build the Preview-only Phase 3 structured rating predictions."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from cks_picks_cfb.data.lake import (
    BuildRequest,
    DatasetRef,
    build_dataset_version,
    read_dataset,
    require_dataset,
)
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ratings.prediction_evaluation import evaluate_predictions
from cks_picks_cfb.ratings.predictions import (
    PREDICTION_DATASET,
    PREDICTION_MODEL_DATASET,
    PREDICTION_MODEL_SCHEMA_VERSION,
    PREDICTION_SCHEMA_VERSION,
    expanding_predictions,
    fit_ols,
    load_prediction_config,
    model_records,
    predict,
    prepare_prediction_frame,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "conf/ratings/prediction_baseline_v1.yaml"
RELEVANT = (
    "src/cks_picks_cfb/ratings/predictions.py",
    "src/cks_picks_cfb/ratings/prediction_evaluation.py",
    "scripts/pipeline/build_rating_predictions.py",
    "conf/ratings/prediction_baseline_v1.yaml",
)


def _ref(storage, uri: str) -> DatasetRef:
    return DatasetRef(**json.loads(storage.read_bytes(uri).decode()))


def _write_immutable(storage, uri: str, payload: bytes) -> None:
    if storage.exists(uri):
        if storage.read_bytes(uri) != payload:
            raise FileExistsError(f"Immutable artifact collision: {uri}")
        return
    storage.write_bytes(payload, uri)


def _require_commit(expected: str | None) -> str:
    current = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    ).stdout.strip()
    code_sha = expected or current
    if not code_sha:
        raise ValueError("Phase 3 artifacts require a committed code SHA")
    for path in RELEVANT:
        if subprocess.run(
            ["git", "ls-files", "--error-unmatch", path],
            cwd=REPO_ROOT,
            capture_output=True,
            check=False,
        ).returncode:
            raise ValueError(f"Phase 3 artifact path is not committed: {path}")
    if subprocess.run(
        ["git", "diff", "--quiet", code_sha, "--", *RELEVANT],
        cwd=REPO_ROOT,
        check=False,
    ).returncode:
        raise ValueError("Phase 3 paths differ from the recorded commit")
    return code_sha


def _parents_from_phase1(report: dict) -> set[tuple[str, str, str]]:
    return {
        (
            str(item.get("dataset")),
            str(item.get("version_id")),
            str(item.get("content_sha")),
        )
        for item in report.get("lineage", {}).get("parent_refs", [])
    }


def _verify_parent(
    ref: DatasetRef, *, allowed: set[tuple[str, str, str]], label: str
) -> None:
    identity = (ref.dataset, ref.version_id, ref.content_sha)
    if identity not in allowed:
        raise ValueError(f"{label} ref is not a certified Phase 1 parent")


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--environment", choices=("preview", "production"), required=True
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--games-ref-uri", action="append", required=True)
    parser.add_argument("--outcomes-ref-uri", action="append", required=True)
    parser.add_argument("--v4-ref-uri", required=True)
    parser.add_argument("--models-ref-uri", required=True)
    parser.add_argument("--predictions-ref-uri", required=True)
    parser.add_argument("--evaluation-uri", required=True)
    parser.add_argument("--candidate-manifest-uri", required=True)
    parser.add_argument("--expected-code-sha")
    args = parser.parse_args(argv)
    if args.environment != "preview":
        raise ValueError("Phase 3 prediction research is permitted only in preview")
    config = load_prediction_config(args.config)
    prefix = f"{config.research_prefix}/{config.design_id}/runs/{args.run_id}/"
    if not args.run_id or any(
        not uri.startswith(prefix)
        for uri in (
            args.models_ref_uri,
            args.predictions_ref_uri,
            args.evaluation_uri,
            args.candidate_manifest_uri,
        )
    ):
        raise ValueError("Phase 3 outputs must use their run-stamped research prefix")
    cutoff = datetime.fromisoformat(args.as_of.replace("Z", "+00:00")).astimezone(
        timezone.utc
    )
    code_sha = _require_commit(args.expected_code_sha)
    storage = get_storage(environment="preview")
    foundation_payload = storage.read_bytes(
        config.state_inputs["foundation_report_uri"]
    )
    if (
        hashlib.sha256(foundation_payload).hexdigest()
        != config.state_inputs["foundation_report_sha256"]
    ):
        raise ValueError("Foundation certification report checksum mismatch")
    foundation = json.loads(foundation_payload.decode())
    if not foundation.get("all_checks_passed"):
        raise ValueError("Phase 3 requires a passing foundation certification")
    team_ref = _ref(storage, config.state_inputs["team_states_ref_uri"])
    snapshots_ref = _ref(storage, config.state_inputs["snapshots_ref_uri"])
    terminal_ref = _ref(storage, config.state_inputs["terminal_ref_uri"])
    if (
        team_ref.version_id != config.state_inputs["expected_team_states_version"]
        or team_ref.content_sha != config.state_inputs["expected_team_states_sha"]
    ):
        raise ValueError("Team-state ref does not match the certified handoff")
    require_dataset(team_ref, "rating_team_states")
    if (
        snapshots_ref.version_id != config.state_inputs["expected_snapshots_version"]
        or snapshots_ref.content_sha != config.state_inputs["expected_snapshots_sha"]
        or terminal_ref.version_id != config.state_inputs["expected_terminal_version"]
        or terminal_ref.content_sha != config.state_inputs["expected_terminal_sha"]
    ):
        raise ValueError("Measurement snapshot refs do not match the certified handoff")
    v4_ref = _ref(storage, args.v4_ref_uri)
    if (
        v4_ref.version_id != config.v4_benchmark["expected_version"]
        or v4_ref.content_sha != config.v4_benchmark["expected_sha"]
    ):
        raise ValueError("V4 benchmark ref does not match the certified recovery")
    require_dataset(v4_ref, "rating_v4_historical_predictions")
    phase1 = json.loads(
        storage.read_bytes(config.state_inputs["phase1_audit_uri"]).decode()
    )
    if not phase1.get("all_checks_passed"):
        raise ValueError("Phase 3 requires the passing Phase 1 audit")
    allowed = _parents_from_phase1(phase1)
    game_refs = tuple(_ref(storage, uri) for uri in args.games_ref_uri)
    outcome_refs = tuple(_ref(storage, uri) for uri in args.outcomes_ref_uri)
    for ref in game_refs:
        _verify_parent(ref, allowed=allowed, label="games")
    for ref in outcome_refs:
        _verify_parent(ref, allowed=allowed, label="outcomes")
    import pandas as pd

    games = pd.concat(
        [read_dataset(storage, ref) for ref in game_refs], ignore_index=True
    )
    outcomes = pd.concat(
        [read_dataset(storage, ref) for ref in outcome_refs], ignore_index=True
    )
    feature_frame = prepare_prediction_frame(
        team_states=read_dataset(storage, team_ref),
        snapshots=read_dataset(storage, snapshots_ref),
        terminal_snapshots=read_dataset(storage, terminal_ref),
        games=games,
        outcomes=outcomes,
        config=config,
    )
    historical = feature_frame[
        feature_frame["season"].isin(config.historical_seasons)
    ].copy()
    predictions, models = expanding_predictions(historical, config)
    lineage = {
        "foundation_report_sha256": config.state_inputs["foundation_report_sha256"],
        "team_states_ref": asdict(team_ref),
        "snapshots_ref": asdict(snapshots_ref),
        "terminal_ref": asdict(terminal_ref),
        "v4_ref": asdict(v4_ref),
        "games_refs": [asdict(ref) for ref in game_refs],
        "outcomes_refs": [asdict(ref) for ref in outcome_refs],
    }
    evaluation = evaluate_predictions(
        predictions=predictions, v4=read_dataset(storage, v4_ref), gates=config.gates
    )
    if not evaluation["all_checks_passed"]:
        evaluation.update(
            {
                "prediction_design_id": config.design_id,
                "code_sha": code_sha,
                "config_sha": config.design_id,
                "lineage": lineage,
            }
        )
        _write_immutable(
            storage,
            args.evaluation_uri,
            json.dumps(evaluation, indent=2, sort_keys=True, default=str).encode(),
        )
        raise ValueError(
            "Phase 3 historical gates failed; successful refs and candidate manifest were not published"
        )
    final_models = [
        fit_ols(historical, target=target, training_seasons=config.historical_seasons)
        for target in ("margin", "total")
    ]
    final_frame = feature_frame[feature_frame["season"].eq(2026)].copy()
    if final_frame.empty:
        raise ValueError("No 2026 state-backed games available for candidate freeze")
    candidate_predictions = pd.concat(
        [predict(model, final_frame, fold_id="final_2026") for model in final_models],
        ignore_index=True,
    )
    model_ref, _ = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset=PREDICTION_MODEL_DATASET,
            parent_refs=(
                team_ref,
                snapshots_ref,
                terminal_ref,
                *game_refs,
                *outcome_refs,
            ),
            code_sha=code_sha,
            config_sha=config.design_id,
            as_of=cutoff,
            schema_version=PREDICTION_MODEL_SCHEMA_VERSION,
            tier="gold",
        ),
        records=model_records(
            models + final_models,
            design_id=config.design_id,
            code_sha=code_sha,
            config_sha=config.design_id,
            lineage=lineage,
        ),
        partitions={"seasons": list(config.historical_seasons)},
        validation={"ols_contract_valid": True},
    )
    all_predictions = pd.concat([predictions, candidate_predictions], ignore_index=True)
    all_predictions["prediction_design_id"] = config.design_id
    all_predictions["code_sha"] = code_sha
    all_predictions["config_sha"] = config.design_id
    all_predictions["model_ref_version_id"] = model_ref.version_id
    prediction_ref, _ = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset=PREDICTION_DATASET,
            parent_refs=(model_ref,),
            code_sha=code_sha,
            config_sha=config.design_id,
            as_of=cutoff,
            schema_version=PREDICTION_SCHEMA_VERSION,
            tier="gold",
        ),
        records=all_predictions.to_dict("records"),
        partitions={"seasons": [*config.evaluation_seasons, 2026]},
        validation={"positive_predictive_uncertainty": True, "candidate_frozen": True},
    )
    evaluation.update(
        {
            "prediction_design_id": config.design_id,
            "code_sha": code_sha,
            "config_sha": config.design_id,
            "lineage": lineage,
            "model_ref": asdict(model_ref),
            "prediction_ref": asdict(prediction_ref),
        }
    )
    evaluation_payload = json.dumps(
        evaluation, indent=2, sort_keys=True, default=str
    ).encode()
    _write_immutable(storage, args.evaluation_uri, evaluation_payload)
    candidate_manifest = {
        "candidate_schema_version": "rating_prediction_candidate_v1",
        "prediction_design_id": config.design_id,
        "code_sha": code_sha,
        "config_sha": config.design_id,
        "cutoff": args.as_of,
        "historical_evaluation_uri": args.evaluation_uri,
        "historical_evaluation_sha256": hashlib.sha256(evaluation_payload).hexdigest(),
        "model_ref": asdict(model_ref),
        "prediction_ref": asdict(prediction_ref),
        "final_models": model_records(
            final_models,
            design_id=config.design_id,
            code_sha=code_sha,
            config_sha=config.design_id,
            lineage=lineage,
        ),
        "earliest_eligible_prospective_window": "2026 Week 1 normal-coverage slate",
        "candidate_prediction_count": int(len(candidate_predictions)),
    }
    _write_immutable(
        storage,
        args.models_ref_uri,
        json.dumps(asdict(model_ref), sort_keys=True).encode(),
    )
    _write_immutable(
        storage,
        args.predictions_ref_uri,
        json.dumps(asdict(prediction_ref), sort_keys=True).encode(),
    )
    _write_immutable(
        storage,
        args.candidate_manifest_uri,
        json.dumps(candidate_manifest, indent=2, sort_keys=True).encode(),
    )
    print(
        json.dumps(
            {
                "status": "built",
                "models_ref": asdict(model_ref),
                "predictions_ref": asdict(prediction_ref),
                "evaluation_sha256": hashlib.sha256(evaluation_payload).hexdigest(),
                "candidate_manifest_uri": args.candidate_manifest_uri,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
