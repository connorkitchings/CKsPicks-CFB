#!/usr/bin/env python3
"""Freeze one prospective rating-shadow slate before kickoff (Phase 4)."""

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
from cks_picks_cfb.data.runtime import resolve_runtime_target
from cks_picks_cfb.data.storage import ReadOnlyStorage, get_storage
from cks_picks_cfb.ratings.contracts import load_measurement_config
from cks_picks_cfb.ratings.observations import build_measurement_observations
from cks_picks_cfb.ratings.predictions import prepare_prediction_frame
from cks_picks_cfb.ratings.score_models import predict_score_model
from cks_picks_cfb.ratings.shadow import (
    SHADOW_FREEZE_DATASET,
    SHADOW_FREEZE_SCHEMA_VERSION,
    SHADOW_PREDICTION_SCHEMA_VERSION,
    ShadowConfig,
    assemble_season_states,
    canonical_manifest_uri,
    existing_or_collision,
    immutable_write,
    load_certified_state_inputs,
    load_frozen_model,
    load_shadow_config,
    normal_coverage,
    normalize_v4_prediction_run,
    prediction_config_for_shadow,
    ref_identity,
    validate_freeze_predictions,
    validate_freeze_timing,
    week_cutoff,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "conf/ratings/shadow_operations_v1.yaml"
RELEVANT = (
    "src/cks_picks_cfb/ratings/shadow.py",
    "src/cks_picks_cfb/ratings/score_models.py",
    "src/cks_picks_cfb/ratings/observations.py",
    "src/cks_picks_cfb/ratings/snapshots.py",
    "src/cks_picks_cfb/ratings/states.py",
    "src/cks_picks_cfb/ratings/predictions.py",
    "scripts/pipeline/build_rating_shadow_freeze.py",
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
    code_sha = expected or current
    if not code_sha:
        raise ValueError("Shadow freeze artifacts require a committed code SHA")
    paths = (*RELEVANT, config_path)
    for path in paths:
        if subprocess.run(
            ["git", "ls-files", "--error-unmatch", path],
            cwd=REPO_ROOT,
            capture_output=True,
            check=False,
        ).returncode:
            raise ValueError(f"Shadow freeze path is not committed: {path}")
    if subprocess.run(
        ["git", "diff", "--quiet", code_sha, "--", *paths], cwd=REPO_ROOT, check=False
    ).returncode:
        raise ValueError("Shadow freeze paths differ from the recorded commit")
    return code_sha


def _validate_parent_as_of(storage, ref: DatasetRef, as_of: datetime) -> None:
    manifest_uri = ref.uri.rsplit("/", 1)[0] + "/manifest.json"
    if not storage.exists(manifest_uri):
        raise ValueError(f"Parent manifest is missing: {manifest_uri}")
    manifest = json.loads(storage.read_bytes(manifest_uri).decode())
    if (
        manifest.get("version_id") != ref.version_id
        or manifest.get("content_sha") != ref.content_sha
    ):
        raise ValueError("Parent ref and manifest disagree")
    parent_as_of = datetime.fromisoformat(str(manifest["as_of"]).replace("Z", "+00:00"))
    if parent_as_of.astimezone(timezone.utc) > as_of:
        raise ValueError("Parent dataset is newer than the requested shadow freeze")


def _slate(games: pd.DataFrame, season: int, week: int) -> pd.DataFrame:
    frame = games.copy()
    frame["season"] = pd.to_numeric(frame["season"], errors="coerce")
    frame["week"] = pd.to_numeric(frame["week"], errors="coerce")
    kickoff = pd.to_datetime(frame["kickoff_utc"], utc=True, errors="coerce")
    status = (
        frame.get("status", pd.Series("", index=frame.index))
        .astype(str)
        .str.lower()
        .str.strip()
    )
    result = frame[
        (frame.season == season)
        & (frame.week == week)
        & kickoff.notna()
        & ~status.isin(("cancelled", "canceled", "postponed"))
    ].copy()
    if result.empty:
        raise ValueError(f"No eligible games for {season} week {week}")
    return result.sort_values(["kickoff_utc", "game_id"], kind="mergesort")


def _frozen_v4_metadata(run_id: str, season: int, week: int) -> dict[str, object]:
    """Read production metadata only; this function never mutates Neon."""
    import psycopg

    with psycopg.connect(resolve_runtime_target("production").database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT state, artifact_uri, artifact_sha256, frozen_at FROM prediction_runs "
                "WHERE run_id = %s AND season = %s AND week = %s",
                (run_id, season, week),
            )
            row = cur.fetchone()
    if not row:
        raise ValueError("Production V4 run is missing or belongs to another slate")
    state, artifact_uri, artifact_sha, frozen_at = row
    if state not in {"frozen", "scored"} or frozen_at is None:
        raise ValueError("Production V4 run must be frozen before shadow freeze")
    return {
        "run_id": run_id,
        "state": state,
        "artifact_uri": artifact_uri,
        "artifact_sha256": artifact_sha,
        "frozen_at": frozen_at.astimezone(timezone.utc).isoformat(),
    }


def _load_v4_proof(
    storage, metadata: dict[str, object], season: int, week: int, earliest: datetime
) -> tuple[pd.DataFrame, dict[str, object]]:
    manifest_uri = str(metadata["artifact_uri"]).rsplit("/", 1)[0] + "/manifest.json"
    manifest_bytes = storage.read_bytes(manifest_uri)
    manifest = json.loads(manifest_bytes.decode())
    csv_bytes = storage.read_bytes(str(metadata["artifact_uri"]))
    if hashlib.sha256(csv_bytes).hexdigest() != str(metadata["artifact_sha256"]):
        raise ValueError("Production Neon and R2 V4 artifact checksum mismatch")
    frozen_at = datetime.fromisoformat(
        str(metadata["frozen_at"]).replace("Z", "+00:00")
    )
    data_as_of = datetime.fromisoformat(
        str(manifest["data_as_of"]).replace("Z", "+00:00")
    )
    if frozen_at >= earliest or data_as_of >= earliest:
        raise ValueError(
            "Production V4 artifact was not frozen before earliest kickoff"
        )
    rows = normalize_v4_prediction_run(
        manifest=manifest, csv_bytes=csv_bytes, season=season, week=week
    )
    proof = {
        **metadata,
        "manifest_uri": manifest_uri,
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "prediction_sha256": hashlib.sha256(csv_bytes).hexdigest(),
        "model_bundle_sha256": manifest["model_bundle_sha256"],
        "data_as_of": str(manifest["data_as_of"]),
    }
    return rows, proof


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--environment", choices=("preview", "production"), required=True
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--byplay-ref-uri", action="append", required=True)
    parser.add_argument("--drives-ref-uri", action="append", required=True)
    parser.add_argument("--games-ref-uri", required=True)
    parser.add_argument("--outcomes-ref-uri", action="append", required=True)
    parser.add_argument("--reconciled-ref-uri", required=True)
    parser.add_argument("--v4-run-id", required=True)
    parser.add_argument("--expected-code-sha")
    parser.add_argument("--register-catalog", action="store_true")
    args = parser.parse_args(argv)
    if args.environment != "preview":
        raise ValueError("Shadow freezes are permitted only in preview")
    shadow: ShadowConfig = load_shadow_config(args.config)
    config_path = str(Path(args.config).resolve().relative_to(REPO_ROOT))
    code_sha = _require_commit(args.expected_code_sha, config_path)
    preview = get_storage(environment="preview")
    production = ReadOnlyStorage(get_storage(environment="production"))
    as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00")).astimezone(
        timezone.utc
    )
    season, week = args.season, args.week
    game_ref = _ref(preview, args.games_ref_uri)
    refs = tuple(
        _ref(preview, uri)
        for uri in (
            *args.byplay_ref_uri,
            *args.drives_ref_uri,
            args.games_ref_uri,
            *args.outcomes_ref_uri,
            args.reconciled_ref_uri,
        )
    )
    for ref in refs:
        _validate_parent_as_of(preview, ref, as_of)
    games = read_dataset(preview, game_ref)
    slate = _slate(games, season, week)
    validate_freeze_timing(as_of=as_of, slate=slate)
    _, earliest, latest = week_cutoff(slate)
    v4_rows, v4_proof = _load_v4_proof(
        production,
        _frozen_v4_metadata(args.v4_run_id, season, week),
        season,
        week,
        earliest,
    )
    model, model_ref = load_frozen_model(
        preview, shadow, stage=shadow.candidate["model_stage"]
    )
    input_identity = {
        "parents": [ref_identity(ref) for ref in refs],
        "model": ref_identity(model_ref),
        "v4": v4_proof,
    }
    expected = {
        "shadow_design_id": shadow.design_id,
        "season": season,
        "week": week,
        "as_of": as_of.isoformat(),
        "input_identity": input_identity,
    }
    manifest_uri = canonical_manifest_uri(
        shadow, season=season, week=week, kind="freeze"
    )
    if existing := existing_or_collision(preview, manifest_uri, expected):
        print(
            json.dumps(
                {"status": "existing", "manifest": existing}, indent=2, sort_keys=True
            )
        )
        return

    byplay_refs = tuple(_ref(preview, uri) for uri in args.byplay_ref_uri)
    drives_refs = tuple(_ref(preview, uri) for uri in args.drives_ref_uri)
    outcome_refs = tuple(_ref(preview, uri) for uri in args.outcomes_ref_uri)
    reconciled_ref = _ref(preview, args.reconciled_ref_uri)
    byplay = pd.concat(
        [read_dataset(preview, ref) for ref in byplay_refs], ignore_index=True
    )
    drives = pd.concat(
        [read_dataset(preview, ref) for ref in drives_refs], ignore_index=True
    )
    outcomes = pd.concat(
        [read_dataset(preview, ref) for ref in outcome_refs], ignore_index=True
    )
    reconciled = read_dataset(preview, reconciled_ref)

    def target(frame: pd.DataFrame) -> pd.DataFrame:
        return frame[pd.to_numeric(frame["season"], errors="coerce").eq(season)].copy()

    measurement = load_measurement_config(
        str(REPO_ROOT / shadow.rehearsal["measurement_config_path"])
    )
    observations = build_measurement_observations(
        byplay=target(byplay),
        drives=target(drives),
        games=target(games),
        outcomes=target(outcomes),
        reconciled_team_game=target(reconciled),
        config=measurement,
        as_of=as_of,
        code_sha=code_sha,
        config_sha=shadow.design_id,
        parent_ref_shas=";".join(ref.content_sha for ref in refs),
    ).frame
    from cks_picks_cfb.ratings.snapshots import build_pregame_snapshots

    new_snapshots = build_pregame_snapshots(
        observations=observations,
        games=slate,
        config=measurement,
        code_sha=code_sha,
        config_sha=shadow.design_id,
        parent_observation_version_id="shadow-current-season",
        parent_ref_shas=";".join(ref.content_sha for ref in refs),
    ).frame
    _, snapshots_ref, terminal_ref, _, certified_snapshots, certified_terminal = (
        load_certified_state_inputs(preview, shadow)
    )
    combined_snapshots = pd.concat(
        [certified_snapshots, new_snapshots], ignore_index=True
    )
    _, states, _ = assemble_season_states(
        pregame_snapshots=combined_snapshots,
        terminal_snapshots=certified_terminal,
        state_config_path=str(REPO_ROOT / shadow.rehearsal["state_config_path"]),
        code_sha=code_sha,
        config_sha=shadow.design_id,
        parent_measurement_refs=f"{snapshots_ref.content_sha};{terminal_ref.content_sha}",
    )
    frame = prepare_prediction_frame(
        team_states=states[
            (states.state_kind == "pregame") & pd.to_numeric(states.season).eq(season)
        ],
        snapshots=combined_snapshots,
        terminal_snapshots=certified_terminal,
        games=slate,
        outcomes=outcomes,
        config=prediction_config_for_shadow(
            shadow, historical_seasons=(2021, 2022, 2023, 2024, 2025)
        ),
    )
    predictions = predict_score_model(
        model, frame, fold_id=f"shadow_{season}_w{week:02d}"
    )
    validate_freeze_predictions(predictions, slate=slate, prospective=True)
    prediction_ref, prediction_manifest = build_dataset_version(
        preview,
        build=BuildRequest(
            dataset=SHADOW_FREEZE_DATASET,
            parent_refs=(model_ref, snapshots_ref, terminal_ref, game_ref),
            code_sha=code_sha,
            config_sha=shadow.design_id,
            as_of=as_of,
            schema_version=SHADOW_PREDICTION_SCHEMA_VERSION,
            tier="gold",
        ),
        records=predictions.to_dict("records"),
        partitions={"slate": [f"{season}_w{week:02d}"]},
        validation={
            "prospective_outcomes_excluded": True,
            "positive_predictive_uncertainty": True,
        },
    )
    manifest = {
        **expected,
        "manifest_schema_version": SHADOW_FREEZE_SCHEMA_VERSION,
        "code_sha": code_sha,
        "earliest_kickoff": earliest.isoformat(),
        "latest_kickoff": latest.isoformat(),
        "lead_seconds": (earliest - as_of).total_seconds(),
        "scheduled_games": int(len(slate)),
        "predicted_games": int(predictions.game_id.nunique()),
        "normal_coverage_slate": normal_coverage(
            int(len(slate)), shadow.gates, week=week
        ),
        "predictions_ref": ref_identity(prediction_ref),
        "v4_source": v4_proof,
        "prospective": True,
    }
    prefix = shadow.canonical_week_prefix(season=season, week=week)
    immutable_write(
        preview,
        manifest_uri,
        json.dumps(manifest, indent=2, sort_keys=True, default=str).encode(),
    )
    immutable_write(
        preview,
        f"{prefix}/predictions-ref.json",
        json.dumps(ref_identity(prediction_ref), sort_keys=True).encode(),
    )
    if args.register_catalog:
        from cks_picks_cfb.data.catalog import register_dataset_version

        register_dataset_version(
            resolve_runtime_target("preview").database_url,
            prediction_ref,
            prediction_manifest,
        )
    print(
        json.dumps(
            {
                "status": "frozen",
                "manifest_uri": manifest_uri,
                "predictions_ref": ref_identity(prediction_ref),
                "v4_rows_verified": len(v4_rows),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
