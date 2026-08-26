#!/usr/bin/env python3
"""Rebuild 2025 shadow states and verify the sealed locked-2025 oracle."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from cks_picks_cfb.data.lake import (
    BuildRequest,
    DatasetRef,
    build_dataset_version,
    read_dataset,
)
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ratings.contracts import load_measurement_config
from cks_picks_cfb.ratings.observations import build_measurement_observations
from cks_picks_cfb.ratings.predictions import prepare_prediction_frame
from cks_picks_cfb.ratings.score_models import (
    SCORE_PREDICTION_DATASET,
    predict_score_model,
)
from cks_picks_cfb.ratings.shadow import (
    SHADOW_EVIDENCE_DATASET,
    SHADOW_EVIDENCE_SCHEMA_VERSION,
    SHADOW_FREEZE_DATASET,
    SHADOW_PREDICTION_SCHEMA_VERSION,
    assemble_season_states,
    compare_oracle,
    immutable_write,
    load_certified_state_inputs,
    load_frozen_model,
    load_shadow_config,
    prediction_config_for_shadow,
    ref_identity,
    score_freeze,
    validate_freeze_predictions,
    week_cutoff,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "conf/ratings/shadow_operations_v1.yaml"
RELEVANT = (
    "src/cks_picks_cfb/data/lake.py",
    "src/cks_picks_cfb/ratings/shadow.py",
    "src/cks_picks_cfb/ratings/score_models.py",
    "src/cks_picks_cfb/ratings/observations.py",
    "src/cks_picks_cfb/ratings/snapshots.py",
    "src/cks_picks_cfb/ratings/states.py",
    "scripts/pipeline/run_rating_shadow_rehearsal.py",
)


def _ref(storage, uri: str) -> DatasetRef:
    return DatasetRef(**json.loads(storage.read_bytes(uri).decode()))


def _require_commit(expected: str | None, config_path: str) -> str:
    current = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    ).stdout.strip()
    code_sha, paths = expected or current, (*RELEVANT, config_path)
    if not code_sha or any(
        subprocess.run(
            ["git", "ls-files", "--error-unmatch", item],
            cwd=REPO_ROOT,
            capture_output=True,
            check=False,
        ).returncode
        for item in paths
    ):
        raise ValueError("Rehearsal requires committed implementation paths")
    if subprocess.run(
        ["git", "diff", "--quiet", code_sha, "--", *paths], cwd=REPO_ROOT, check=False
    ).returncode:
        raise ValueError("Rehearsal paths differ from the recorded commit")
    return code_sha


def _raw_parent_refs(storage, report_uri: str) -> dict[str, list[DatasetRef]]:
    report = json.loads(storage.read_bytes(report_uri).decode())
    result: dict[str, list[DatasetRef]] = {}
    for raw in report["lineage"]["parent_refs"]:
        ref = DatasetRef(**raw)
        result.setdefault(ref.dataset, []).append(ref)
    required = {"byplay", "drives", "games", "game_outcomes", "reconciled_team_game"}
    if not required <= set(result):
        raise ValueError("Phase 1 audit does not pin every rehearsal parent")
    return result


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--environment", choices=("preview", "production"), required=True
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--summary-uri", required=True)
    parser.add_argument("--expected-code-sha")
    args = parser.parse_args(argv)
    if args.environment != "preview":
        raise ValueError("Shadow rehearsal is permitted only in preview")
    shadow = load_shadow_config(args.config)
    prefix = f"{shadow.rehearsal_prefix}/runs/{args.run_id}"
    if not args.summary_uri.startswith(f"{prefix}/"):
        raise ValueError("Rehearsal summary must use its immutable run prefix")
    code_sha = _require_commit(
        args.expected_code_sha, str(Path(args.config).resolve().relative_to(REPO_ROOT))
    )
    storage = get_storage(environment="preview")
    run_as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00")).astimezone(
        timezone.utc
    )
    model, model_ref = load_frozen_model(
        storage, shadow, stage=shadow.rehearsal["model_stage"]
    )
    prediction_ref = _ref(storage, shadow.candidate["predictions_ref_uri"])
    if (
        prediction_ref.version_id != shadow.candidate["expected_predictions_version"]
        or prediction_ref.content_sha != shadow.candidate["expected_predictions_sha"]
        or prediction_ref.dataset != SCORE_PREDICTION_DATASET
    ):
        raise ValueError("Frozen locked oracle ref does not match pins")
    frozen = read_dataset(storage, prediction_ref)
    _, snapshots_ref, terminal_ref, _, certified_snapshots, terminal = (
        load_certified_state_inputs(storage, shadow)
    )
    parents = _raw_parent_refs(
        storage,
        shadow.rehearsal.get(
            "phase1_audit_uri",
            "artifacts/research/rating-successor/measurements-v3/6494832d3dee24bb507a3adddcecdaf9029d9e7ace3396417421dfe53f3f739a/runs/2026-08-26T1236Z-phase1-ppso-v3-final/audit-report.json",
        ),
    )
    all_data = {
        name: pd.concat([read_dataset(storage, ref) for ref in refs], ignore_index=True)
        for name, refs in parents.items()
    }
    season = int(shadow.rehearsal["season"])

    def select(frame: pd.DataFrame) -> pd.DataFrame:
        return frame[pd.to_numeric(frame["season"], errors="coerce").eq(season)].copy()

    observations = build_measurement_observations(
        byplay=select(all_data["byplay"]),
        drives=select(all_data["drives"]),
        games=select(all_data["games"]),
        outcomes=select(all_data["game_outcomes"]),
        reconciled_team_game=select(all_data["reconciled_team_game"]),
        config=load_measurement_config(
            str(REPO_ROOT / shadow.rehearsal["measurement_config_path"])
        ),
        as_of=run_as_of,
        code_sha=code_sha,
        config_sha=shadow.design_id,
        parent_ref_shas=";".join(
            ref.content_sha for refs in parents.values() for ref in refs
        ),
    ).frame
    from cks_picks_cfb.ratings.snapshots import build_pregame_snapshots

    games = select(all_data["games"])
    rebuilt = build_pregame_snapshots(
        observations=observations,
        games=games,
        config=load_measurement_config(
            str(REPO_ROOT / shadow.rehearsal["measurement_config_path"])
        ),
        code_sha=code_sha,
        config_sha=shadow.design_id,
        parent_observation_version_id="phase4-rehearsal",
        parent_ref_shas=";".join(
            ref.content_sha for refs in parents.values() for ref in refs
        ),
    ).frame
    historical_snapshots = certified_snapshots[
        pd.to_numeric(certified_snapshots.season).lt(season)
    ]
    _, states, _ = assemble_season_states(
        pregame_snapshots=pd.concat([historical_snapshots, rebuilt], ignore_index=True),
        terminal_snapshots=terminal,
        state_config_path=str(REPO_ROOT / shadow.rehearsal["state_config_path"]),
        code_sha=code_sha,
        config_sha=shadow.design_id,
        parent_measurement_refs=f"{snapshots_ref.content_sha};{terminal_ref.content_sha}",
    )
    v4 = read_dataset(storage, _ref(storage, shadow.rehearsal["v4_ref_uri"]))
    outcomes = select(all_data["game_outcomes"])
    reports: list[dict[str, object]] = []
    oracle = frozen[frozen.fold_id.str.startswith(shadow.rehearsal["fold_prefix"])]
    for week in sorted(
        pd.to_numeric(games["week"], errors="coerce").dropna().astype(int).unique()
    ):
        oracle_games = set(oracle[oracle.week.astype(int).eq(week)].game_id.astype(int))
        slate = games[games.game_id.astype(int).isin(oracle_games)].copy()
        if slate.empty:
            continue
        cutoff, earliest, latest = week_cutoff(slate)
        state_game_ids = pd.to_numeric(states.as_of_game_id, errors="coerce")
        week_states = states[
            (states.state_kind == "pregame")
            & pd.to_numeric(states.season).eq(season)
            & state_game_ids.isin(oracle_games)
        ]
        frame = prepare_prediction_frame(
            team_states=week_states,
            snapshots=pd.concat([historical_snapshots, rebuilt], ignore_index=True),
            terminal_snapshots=terminal,
            games=slate,
            outcomes=outcomes,
            config=prediction_config_for_shadow(
                shadow, historical_seasons=(2021, 2022, 2023, 2024, 2025)
            ),
        )
        predictions = predict_score_model(
            model, frame, fold_id=f"rehearsal_{season}_w{week:02d}"
        )
        validate_freeze_predictions(predictions, slate=slate, prospective=False)
        comparison = compare_oracle(
            predictions,
            oracle[oracle.game_id.astype(int).isin(oracle_games)],
            fold_prefix=shadow.rehearsal["fold_prefix"],
        )
        evidence, score = score_freeze(
            freeze_predictions=predictions,
            outcomes=outcomes,
            v4=v4,
            lineage={
                "rehearsal_only": True,
                "freeze_manifest_sha256": "rehearsal",
                "scored_at": run_as_of.isoformat(),
            },
        )
        week_prefix = f"{prefix}/weeks/{week:02d}"
        if not score["complete"]:
            immutable_write(
                storage,
                f"{week_prefix}/diagnostic-score.json",
                json.dumps(score, indent=2, sort_keys=True, default=str).encode(),
            )
            raise ValueError(f"Rehearsal score incomplete for 2025 week {week}")
        p_ref, _ = build_dataset_version(
            storage,
            build=BuildRequest(
                dataset=SHADOW_FREEZE_DATASET,
                parent_refs=(model_ref, snapshots_ref, terminal_ref),
                code_sha=code_sha,
                config_sha=shadow.design_id,
                as_of=cutoff,
                schema_version=SHADOW_PREDICTION_SCHEMA_VERSION,
                tier="gold",
            ),
            records=predictions.to_dict("records"),
            partitions={"rehearsal_week": [week]},
            validation={
                "rehearsal_only": True,
                "oracle_passed": comparison["all_checks_passed"],
            },
        )
        e_ref, _ = build_dataset_version(
            storage,
            build=BuildRequest(
                dataset=SHADOW_EVIDENCE_DATASET,
                parent_refs=(p_ref,),
                code_sha=code_sha,
                config_sha=shadow.design_id,
                as_of=run_as_of,
                schema_version=SHADOW_EVIDENCE_SCHEMA_VERSION,
                tier="gold",
            ),
            records=evidence.to_dict("records"),
            partitions={"rehearsal_week": [week]},
            validation={"rehearsal_only": True, "complete": score["complete"]},
        )
        immutable_write(
            storage,
            f"{week_prefix}/predictions-ref.json",
            json.dumps(ref_identity(p_ref), sort_keys=True).encode(),
        )
        immutable_write(
            storage,
            f"{week_prefix}/evidence-ref.json",
            json.dumps(ref_identity(e_ref), sort_keys=True).encode(),
        )
        reports.append(
            {
                "week": week,
                "cutoff": cutoff.isoformat(),
                "earliest_kickoff": earliest.isoformat(),
                "latest_kickoff": latest.isoformat(),
                "games": int(len(slate)),
                "oracle": comparison,
                "scoring": score,
                "prediction_ref": ref_identity(p_ref),
                "evidence_ref": ref_identity(e_ref),
                "all_checks_passed": bool(
                    comparison["all_checks_passed"] and score["complete"]
                ),
            }
        )
    summary = {
        "report_schema_version": "rating_shadow_rehearsal_v1",
        "shadow_design_id": shadow.design_id,
        "code_sha": code_sha,
        "run_id": args.run_id,
        "run_as_of": run_as_of.isoformat(),
        "model_ref": ref_identity(model_ref),
        "rehearsal_only": True,
        "weeks": reports,
        "all_checks_passed": bool(reports)
        and all(item["all_checks_passed"] for item in reports),
    }
    payload = json.dumps(summary, indent=2, sort_keys=True, default=str).encode()
    immutable_write(storage, args.summary_uri, payload)
    print(
        json.dumps(
            {
                "status": "rehearsed",
                "weeks": len(reports),
                "all_checks_passed": summary["all_checks_passed"],
                "summary_sha256": hashlib.sha256(payload).hexdigest(),
            },
            indent=2,
            sort_keys=True,
        )
    )
    if not summary["all_checks_passed"]:
        raise ValueError("Shadow rehearsal failed")


if __name__ == "__main__":
    main()
