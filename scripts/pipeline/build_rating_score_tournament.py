#!/usr/bin/env python3
"""Build the Preview-only sealed Phase 3 team-score tournament."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
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
from cks_picks_cfb.ratings.predictions import prepare_prediction_frame
from cks_picks_cfb.ratings.score_models import (
    SCORE_MODEL_DATASET,
    SCORE_PREDICTION_DATASET,
    expanding_score_predictions,
    fit_score_model,
    load_score_tournament_config,
    locked_score_predictions,
    model_record,
    predict_score_model,
    tournament_selection,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "conf/ratings/score_model_tournament_v3.yaml"
RELEVANT = (
    "src/cks_picks_cfb/ratings/predictions.py",
    "src/cks_picks_cfb/ratings/prediction_evaluation.py",
    "src/cks_picks_cfb/ratings/score_models.py",
    "scripts/pipeline/build_rating_score_tournament.py",
    "conf/ratings/score_model_tournament_v3.yaml",
)


def _ref(storage, uri: str) -> DatasetRef:
    return DatasetRef(**json.loads(storage.read_bytes(uri).decode()))


def _write_immutable(storage, uri: str, payload: bytes) -> None:
    if storage.exists(uri):
        if storage.read_bytes(uri) != payload:
            raise FileExistsError(f"Immutable artifact collision: {uri}")
        return
    storage.write_bytes(payload, uri)


def _prediction_validation() -> dict[str, bool]:
    """Return affirmative lake checks for the explicitly non-prospective dry run."""
    return {
        "positive_predictive_uncertainty": True,
        "non_prospective_dry_run": True,
    }


def _require_commit(expected: str | None, *, config_path: str) -> str:
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
    relevant = (*RELEVANT[:-1], config_path)
    for path in relevant:
        if subprocess.run(
            ["git", "ls-files", "--error-unmatch", path],
            cwd=REPO_ROOT,
            capture_output=True,
            check=False,
        ).returncode:
            raise ValueError(f"Phase 3 artifact path is not committed: {path}")
    if subprocess.run(
        ["git", "diff", "--quiet", code_sha, "--", *relevant],
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
    if (ref.dataset, ref.version_id, ref.content_sha) not in allowed:
        raise ValueError(f"{label} ref is not a certified Phase 1 parent")


def _verify_handoff(
    storage, config, v4_ref_uri: str
) -> tuple[DatasetRef, DatasetRef, DatasetRef, DatasetRef, dict]:
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
        raise ValueError("Team-state ref does not match certified handoff")
    if (
        snapshots_ref.version_id != config.state_inputs["expected_snapshots_version"]
        or snapshots_ref.content_sha != config.state_inputs["expected_snapshots_sha"]
        or terminal_ref.version_id != config.state_inputs["expected_terminal_version"]
        or terminal_ref.content_sha != config.state_inputs["expected_terminal_sha"]
    ):
        raise ValueError("Measurement snapshot refs do not match certified handoff")
    require_dataset(team_ref, "rating_team_states")
    v4_ref = _ref(storage, v4_ref_uri)
    if (
        v4_ref.version_id != config.v4_benchmark["expected_version"]
        or v4_ref.content_sha != config.v4_benchmark["expected_sha"]
    ):
        raise ValueError("V4 benchmark ref does not match certified recovery")
    require_dataset(v4_ref, "rating_v4_historical_predictions")
    phase1 = json.loads(
        storage.read_bytes(config.state_inputs["phase1_audit_uri"]).decode()
    )
    if not phase1.get("all_checks_passed"):
        raise ValueError("Phase 3 requires passing Phase 1 audit")
    return team_ref, snapshots_ref, terminal_ref, v4_ref, phase1


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
    parser.add_argument("--tournament-uri", required=True)
    parser.add_argument("--models-ref-uri", required=True)
    parser.add_argument("--predictions-ref-uri", required=True)
    parser.add_argument("--candidate-manifest-uri", required=True)
    parser.add_argument("--expected-code-sha")
    args = parser.parse_args(argv)
    if args.environment != "preview":
        raise ValueError("Phase 3 research is permitted only in preview")
    config = load_score_tournament_config(args.config)
    prefix = f"{config.research_prefix}/{config.design_id}/runs/{args.run_id}/"
    outputs = (
        args.tournament_uri,
        args.models_ref_uri,
        args.predictions_ref_uri,
        args.candidate_manifest_uri,
    )
    if not args.run_id or any(not uri.startswith(prefix) for uri in outputs):
        raise ValueError("Phase 3 outputs must use their run-stamped research prefix")
    cutoff = datetime.fromisoformat(args.as_of.replace("Z", "+00:00")).astimezone(
        timezone.utc
    )
    config_path = str(Path(args.config).resolve().relative_to(REPO_ROOT))
    code_sha = _require_commit(args.expected_code_sha, config_path=config_path)
    storage = get_storage(environment="preview")
    team_ref, snapshots_ref, terminal_ref, v4_ref, phase1 = _verify_handoff(
        storage, config, args.v4_ref_uri
    )
    allowed = _parents_from_phase1(phase1)
    game_refs = tuple(_ref(storage, uri) for uri in args.games_ref_uri)
    outcome_refs = tuple(_ref(storage, uri) for uri in args.outcomes_ref_uri)
    for ref in game_refs:
        _verify_parent(ref, allowed=allowed, label="games")
    for ref in outcome_refs:
        _verify_parent(ref, allowed=allowed, label="outcomes")
    games = pd.concat(
        [read_dataset(storage, ref) for ref in game_refs], ignore_index=True
    )
    outcomes = pd.concat(
        [read_dataset(storage, ref) for ref in outcome_refs], ignore_index=True
    )
    frame = prepare_prediction_frame(
        team_states=read_dataset(storage, team_ref),
        snapshots=read_dataset(storage, snapshots_ref),
        terminal_snapshots=read_dataset(storage, terminal_ref),
        games=games,
        outcomes=outcomes,
        config=config,
    )
    historical = frame[frame["season"].isin(config.historical_seasons)].copy()
    v4 = read_dataset(storage, v4_ref)
    winner, tournament, selection_models = tournament_selection(
        frame=historical, v4=v4, config=config
    )
    lineage = {
        "foundation_report_sha256": config.state_inputs["foundation_report_sha256"],
        "team_states_ref": asdict(team_ref),
        "snapshots_ref": asdict(snapshots_ref),
        "terminal_ref": asdict(terminal_ref),
        "v4_ref": asdict(v4_ref),
        "games_refs": [asdict(ref) for ref in game_refs],
        "outcomes_refs": [asdict(ref) for ref in outcome_refs],
    }
    tournament.update(
        {
            "prediction_design_id": config.design_id,
            "code_sha": code_sha,
            "config_sha": config.design_id,
            "lineage": lineage,
        }
    )
    if winner is None:
        _write_immutable(
            storage,
            args.tournament_uri,
            json.dumps(tournament, indent=2, sort_keys=True).encode(),
        )
        raise ValueError("No Phase 3 score candidate passed sealed selection gates")
    selection_predictions, _ = expanding_score_predictions(
        winner, historical, config=config
    )
    locked_predictions, locked_model = locked_score_predictions(
        winner, historical, config=config
    )
    locked_evaluation = evaluate_predictions(
        predictions=locked_predictions, v4=v4, gates=config.gates
    )
    tournament["locked_confirmation"] = {
        "family": winner,
        "evaluation": locked_evaluation,
    }
    if not locked_evaluation["all_checks_passed"]:
        _write_immutable(
            storage,
            args.tournament_uri,
            json.dumps(tournament, indent=2, sort_keys=True).encode(),
        )
        raise ValueError("Phase 3 locked 2025 confirmation failed")
    final_model = fit_score_model(
        winner, historical, training_seasons=config.historical_seasons, config=config
    )
    kickoff = pd.to_datetime(frame["kickoff_utc"], utc=True)
    dry_run = frame[(frame["season"] == 2026) & (kickoff > cutoff)].copy()
    if dry_run.empty:
        raise ValueError("No post-cutoff 2026 games available for dry-run predictions")
    # A dry run is reproducibility evidence only.  Do not carry any completed
    # 2026 outcomes into its prediction artifact if an input parent happens to
    # include games played after this cutoff.
    dry_run[
        [
            "actual_home_points",
            "actual_away_points",
            "actual_margin",
            "actual_total",
        ]
    ] = np.nan
    candidate_predictions = predict_score_model(
        final_model, dry_run, fold_id="final_2026_dry_run"
    )
    all_predictions = pd.concat(
        [selection_predictions, locked_predictions, candidate_predictions],
        ignore_index=True,
    )
    all_predictions["prediction_design_id"] = config.design_id
    all_predictions["code_sha"] = code_sha
    all_predictions["config_sha"] = config.design_id
    records = [
        model_record(model)
        | {
            "model_stage": "selection",
            "fold_id": f"expanding_{config.selection_seasons[index]}",
        }
        for index, model in enumerate(selection_models[winner])
    ]
    records.extend(
        [
            model_record(locked_model)
            | {
                "model_stage": "locked_confirmation",
                "fold_id": f"locked_{config.locked_season}",
            },
            model_record(final_model)
            | {"model_stage": "final_refit", "fold_id": "final_2026_dry_run"},
        ]
    )
    model_ref, _ = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset=SCORE_MODEL_DATASET,
            parent_refs=(
                team_ref,
                snapshots_ref,
                terminal_ref,
                v4_ref,
                *game_refs,
                *outcome_refs,
            ),
            code_sha=code_sha,
            config_sha=config.design_id,
            as_of=cutoff,
            schema_version=config.model_schema_version,
            tier="gold",
        ),
        records=records,
        partitions={"training_seasons": list(config.historical_seasons)},
        validation={"selection_passed": True, "locked_confirmation_passed": True},
    )
    all_predictions["model_ref_version_id"] = model_ref.version_id
    prediction_ref, _ = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset=SCORE_PREDICTION_DATASET,
            parent_refs=(model_ref,),
            code_sha=code_sha,
            config_sha=config.design_id,
            as_of=cutoff,
            schema_version=config.prediction_schema_version,
            tier="gold",
        ),
        records=all_predictions.to_dict("records"),
        partitions={"seasons": [*config.selection_seasons, config.locked_season, 2026]},
        validation=_prediction_validation(),
    )
    tournament.update(
        {
            "winner": winner,
            "model_ref": asdict(model_ref),
            "prediction_ref": asdict(prediction_ref),
        }
    )
    tournament_payload = json.dumps(
        tournament, indent=2, sort_keys=True, default=str
    ).encode()
    candidate_manifest = {
        "candidate_schema_version": config.candidate_schema_version,
        "prediction_design_id": config.design_id,
        "code_sha": code_sha,
        "config_sha": config.design_id,
        "winner": winner,
        "cutoff": args.as_of,
        "tournament_uri": args.tournament_uri,
        "tournament_sha256": hashlib.sha256(tournament_payload).hexdigest(),
        "model_ref": asdict(model_ref),
        "prediction_ref": asdict(prediction_ref),
        "earliest_eligible_prospective_window": "2026 Week 1 normal-coverage slate",
        "dry_run_only": True,
    }
    _write_immutable(storage, args.tournament_uri, tournament_payload)
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
                "winner": winner,
                "models_ref": asdict(model_ref),
                "predictions_ref": asdict(prediction_ref),
                "tournament_sha256": hashlib.sha256(tournament_payload).hexdigest(),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
