#!/usr/bin/env python3
"""Freeze one prospective rating-shadow slate before kickoff (Phase 4)."""

from __future__ import annotations

import argparse
import hashlib
import json
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
from cks_picks_cfb.ratings.prospective import (
    FREEZE_CODE_PATHS,
    committed_code_manifest,
    load_prospective_policy,
    validate_exact_game_keys,
    validate_freeze_clock,
    validate_parent_manifest,
    validate_source_times,
)
from cks_picks_cfb.ratings.score_models import predict_score_model
from cks_picks_cfb.ratings.shadow import (
    SHADOW_FREEZE_DATASET,
    SHADOW_FREEZE_SCHEMA_VERSION,
    SHADOW_MEASUREMENT_STATES_DATASET,
    SHADOW_MEASUREMENT_STATES_SCHEMA_VERSION,
    SHADOW_PREDICTION_SCHEMA_VERSION,
    SHADOW_TEAM_STATES_DATASET,
    SHADOW_TEAM_STATES_SCHEMA_VERSION,
    ShadowConfig,
    assemble_season_states,
    assert_canonical_artifact_set,
    canonical_manifest_uri,
    eligibility_declaration,
    existing_or_collision,
    immutable_write,
    load_certified_state_inputs,
    load_frozen_model,
    load_shadow_config,
    normalize_v4_prediction_run,
    prediction_config_for_shadow,
    ref_identity,
    validate_freeze_predictions,
    validate_freeze_timing,
    week_cutoff,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "conf/ratings/shadow_operations_v1.yaml"
DEFAULT_POLICY = REPO_ROOT / "conf/ratings/prospective_evidence_v1.yaml"


def _ref(storage, uri: str) -> DatasetRef:
    return DatasetRef(**json.loads(storage.read_bytes(uri).decode()))


def _validate_parent_as_of(
    storage, ref: DatasetRef, as_of: datetime, freeze_started_at: datetime
) -> None:
    manifest_uri = ref.uri.rsplit("/", 1)[0] + "/manifest.json"
    if not storage.exists(manifest_uri):
        raise ValueError(f"Parent manifest is missing: {manifest_uri}")
    manifest = json.loads(storage.read_bytes(manifest_uri).decode())
    validate_parent_manifest(
        manifest,
        ref=ref_identity(ref),
        as_of=as_of,
        freeze_started_at=freeze_started_at,
    )


def _ref_set(
    storage, uri: str, *, environment: str, as_of: datetime
) -> dict[str, DatasetRef]:
    payload = json.loads(storage.read_bytes(uri).decode())
    if payload.get("schema_version") != "rating_input_ref_set_v1":
        raise ValueError("Unsupported prospective input ref set")
    if payload.get("environment") != environment:
        raise ValueError("Prospective input ref set targets another environment")
    if (
        datetime.fromisoformat(str(payload["as_of"]).replace("Z", "+00:00")).astimezone(
            timezone.utc
        )
        != as_of
    ):
        raise ValueError("Prospective input ref set has another cutoff")
    outputs = payload.get("outputs")
    if not isinstance(outputs, dict) or set(outputs) != {
        "byplay",
        "drives",
        "reconciled_team_game",
        "source_reconciliation",
    }:
        raise ValueError("Prospective input ref set is partial")
    refs = {name: DatasetRef(**value) for name, value in outputs.items()}
    for name, ref in refs.items():
        if ref.dataset != name:
            raise ValueError("Prospective input ref set contains crossed outputs")
    return refs


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
    storage,
    metadata: dict[str, object],
    season: int,
    week: int,
    earliest: datetime,
    expected_v4: dict[str, str],
    hard_lead_seconds: int,
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
    if (earliest - frozen_at).total_seconds() < hard_lead_seconds or (
        earliest - data_as_of
    ).total_seconds() < hard_lead_seconds:
        raise ValueError("Production V4 artifact missed the prospective hard lead")
    rows = normalize_v4_prediction_run(
        manifest=manifest,
        csv_bytes=csv_bytes,
        season=season,
        week=week,
        expected_v4=expected_v4,
    )
    proof = {
        **metadata,
        "manifest_uri": manifest_uri,
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "prediction_sha256": hashlib.sha256(csv_bytes).hexdigest(),
        "model_bundle_sha256": manifest["model_bundle_sha256"],
        "data_as_of": str(manifest["data_as_of"]),
        "expected_games": int(manifest.get("expected_games", rows.game_id.nunique())),
        "predicted_games": int(manifest.get("predicted_games", rows.game_id.nunique())),
    }
    if (
        proof["expected_games"] != proof["predicted_games"]
        or proof["predicted_games"] != rows.game_id.nunique()
    ):
        raise ValueError("Production V4 expected/predicted game metadata is incomplete")
    return rows, proof


def _preflight_catalog() -> None:
    """Verify optional Preview catalog connectivity before R2 canonical writes."""
    import psycopg

    with psycopg.connect(resolve_runtime_target("preview").database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--environment", choices=("preview", "production"), required=True
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--prospective-policy", default=str(DEFAULT_POLICY))
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--input-ref-set-uri")
    parser.add_argument("--byplay-ref-uri", action="append")
    parser.add_argument("--drives-ref-uri", action="append")
    parser.add_argument("--games-ref-uri", required=True)
    parser.add_argument("--outcomes-ref-uri", action="append")
    parser.add_argument("--reconciled-ref-uri")
    parser.add_argument("--v4-run-id", required=True)
    parser.add_argument("--expected-code-sha")
    parser.add_argument("--register-catalog", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args(argv)
    if args.environment != "preview":
        raise ValueError("Shadow freezes are permitted only in preview")
    shadow: ShadowConfig = load_shadow_config(args.config)
    policy = load_prospective_policy(args.prospective_policy)
    if policy.shadow_design_id != shadow.design_id:
        raise ValueError("Prospective policy and shadow config do not match")
    code_manifest = committed_code_manifest(
        repo_root=REPO_ROOT,
        code_sha=args.expected_code_sha,
        paths=FREEZE_CODE_PATHS,
        policy_sha256=policy.policy_sha256,
    )
    code_sha = str(code_manifest["code_sha"])
    preview = get_storage(environment="preview")
    production = ReadOnlyStorage(get_storage(environment="production"))
    if args.register_catalog:
        _preflight_catalog()
    as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00")).astimezone(
        timezone.utc
    )
    freeze_started_at = datetime.now(timezone.utc)
    if as_of > freeze_started_at:
        raise ValueError("Prospective as-of cannot be in the future")
    season, week = args.season, args.week
    if season != policy.season or week < policy.first_eligible_week:
        raise ValueError("Prospective policy does not permit this slate")
    if args.input_ref_set_uri:
        input_refs = _ref_set(
            preview, args.input_ref_set_uri, environment="preview", as_of=as_of
        )
        byplay_refs = (input_refs["byplay"],)
        drives_refs = (input_refs["drives"],)
        reconciled_ref = input_refs["reconciled_team_game"]
        source_reconciliation_ref = input_refs["source_reconciliation"]
    else:
        if not (
            args.byplay_ref_uri and args.drives_ref_uri and args.reconciled_ref_uri
        ):
            raise ValueError(
                "A complete input ref set or explicit raw refs is required"
            )
        byplay_refs = tuple(_ref(preview, uri) for uri in args.byplay_ref_uri)
        drives_refs = tuple(_ref(preview, uri) for uri in args.drives_ref_uri)
        reconciled_ref = _ref(preview, args.reconciled_ref_uri)
        source_reconciliation_ref = None
    if not args.outcomes_ref_uri:
        raise ValueError("Prospective freeze requires explicit outcomes refs")
    outcome_refs = tuple(_ref(preview, uri) for uri in args.outcomes_ref_uri)
    game_ref = _ref(preview, args.games_ref_uri)
    refs = (
        *byplay_refs,
        *drives_refs,
        game_ref,
        *outcome_refs,
        reconciled_ref,
        *((source_reconciliation_ref,) if source_reconciliation_ref else ()),
    )
    for ref in refs:
        _validate_parent_as_of(preview, ref, as_of, freeze_started_at)
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
        dict(shadow.production_v4),
        policy.hard_lead_seconds,
    )
    validate_exact_game_keys(schedule=slate, v4=v4_rows)
    model, model_ref = load_frozen_model(
        preview, shadow, stage=shadow.candidate["model_stage"]
    )
    input_identity = {
        "parents": [ref_identity(ref) for ref in refs],
        "model": ref_identity(model_ref),
        "v4": v4_proof,
        "prospective_policy_sha256": policy.policy_sha256,
        "freeze_code_manifest": code_manifest,
        "input_ref_set_uri": args.input_ref_set_uri,
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
    prefix = shadow.canonical_week_prefix(season=season, week=week)
    assert_canonical_artifact_set(preview, prefix=prefix, kind="freeze")
    if existing := existing_or_collision(preview, manifest_uri, expected):
        print(
            json.dumps(
                {"status": "existing", "manifest": existing}, indent=2, sort_keys=True
            )
        )
        return

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
    for source_frame in (byplay, drives, games, outcomes, reconciled):
        validate_source_times(source_frame, as_of=as_of)

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
    component_states, states, _ = assemble_season_states(
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
    validate_exact_game_keys(schedule=slate, v4=v4_rows, predictions=predictions)
    target_state_ids = {f"game:{season}:{int(game_id)}" for game_id in slate.game_id}
    measurement_states = component_states[
        (component_states.state_kind == "pregame")
        & component_states.state_id.isin(target_state_ids)
    ].copy()
    team_states = states[
        (states.state_kind == "pregame") & states.state_id.isin(target_state_ids)
    ].copy()
    if measurement_states.empty or team_states.empty:
        raise ValueError("Prospective freeze produced incomplete target states")
    if args.preflight_only:
        print(
            json.dumps(
                {
                    "status": "go",
                    "season": season,
                    "week": week,
                    "policy_sha256": policy.policy_sha256,
                    "freeze_code_manifest": code_manifest,
                    "earliest_kickoff": earliest.isoformat(),
                    "requested_as_of": as_of.isoformat(),
                    "v4_source": v4_proof,
                    "input_identity": input_identity,
                },
                indent=2,
                sort_keys=True,
                default=str,
            )
        )
        return
    state_parent_refs = (model_ref, snapshots_ref, terminal_ref, game_ref, *refs)
    measurement_states_ref, measurement_states_manifest = build_dataset_version(
        preview,
        build=BuildRequest(
            dataset=SHADOW_MEASUREMENT_STATES_DATASET,
            parent_refs=state_parent_refs,
            code_sha=code_sha,
            config_sha=policy.policy_sha256,
            as_of=as_of,
            schema_version=SHADOW_MEASUREMENT_STATES_SCHEMA_VERSION,
            tier="gold",
        ),
        records=measurement_states.to_dict("records"),
        partitions={"slate": [f"{season}_w{week:02d}"]},
        validation={"prospective": True, "target_only": True},
    )
    team_states_ref, team_states_manifest = build_dataset_version(
        preview,
        build=BuildRequest(
            dataset=SHADOW_TEAM_STATES_DATASET,
            parent_refs=state_parent_refs,
            code_sha=code_sha,
            config_sha=policy.policy_sha256,
            as_of=as_of,
            schema_version=SHADOW_TEAM_STATES_SCHEMA_VERSION,
            tier="gold",
        ),
        records=team_states.to_dict("records"),
        partitions={"slate": [f"{season}_w{week:02d}"]},
        validation={"prospective": True, "target_only": True},
    )
    prediction_ref, prediction_manifest = build_dataset_version(
        preview,
        build=BuildRequest(
            dataset=SHADOW_FREEZE_DATASET,
            parent_refs=(
                model_ref,
                snapshots_ref,
                terminal_ref,
                game_ref,
                measurement_states_ref,
                team_states_ref,
            ),
            code_sha=code_sha,
            config_sha=policy.policy_sha256,
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
    freeze_completed_at = datetime.now(timezone.utc)
    timing = validate_freeze_clock(
        requested_as_of=as_of,
        freeze_started_at=freeze_started_at,
        freeze_completed_at=freeze_completed_at,
        earliest_kickoff=earliest,
        policy=policy,
    )
    normal_coverage_slate = int(len(slate)) >= policy.normal_coverage_min_games
    manifest = {
        **expected,
        "manifest_schema_version": SHADOW_FREEZE_SCHEMA_VERSION,
        "code_sha": code_sha,
        "freeze_started_at": freeze_started_at.isoformat(),
        "freeze_completed_at": freeze_completed_at.isoformat(),
        "prospective_policy_sha256": policy.policy_sha256,
        "freeze_code_manifest": code_manifest,
        "earliest_kickoff": earliest.isoformat(),
        "latest_kickoff": latest.isoformat(),
        **timing,
        "scheduled_games": int(len(slate)),
        "scheduled_game_keys": [
            {
                "game_id": int(row.game_id),
                "home_team": str(row.home_team),
                "away_team": str(row.away_team),
                "kickoff_utc": pd.Timestamp(row.kickoff_utc).isoformat(),
            }
            for row in slate[["game_id", "home_team", "away_team", "kickoff_utc"]]
            .sort_values("game_id", kind="mergesort")
            .itertuples(index=False)
        ],
        "predicted_games": int(predictions.game_id.nunique()),
        "normal_coverage_slate": normal_coverage_slate,
        "eligibility": {
            **eligibility_declaration(
                shadow, week=week, normal_coverage_slate=normal_coverage_slate
            ),
            "policy_eligible": bool(
                week >= policy.first_eligible_week and normal_coverage_slate
            ),
        },
        "predictions_ref": ref_identity(prediction_ref),
        "measurement_states_ref": ref_identity(measurement_states_ref),
        "team_states_ref": ref_identity(team_states_ref),
        "v4_source": v4_proof,
        "prospective": True,
    }
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
    immutable_write(
        preview,
        f"{prefix}/measurement-states-ref.json",
        json.dumps(ref_identity(measurement_states_ref), sort_keys=True).encode(),
    )
    immutable_write(
        preview,
        f"{prefix}/team-states-ref.json",
        json.dumps(ref_identity(team_states_ref), sort_keys=True).encode(),
    )
    if args.register_catalog:
        from cks_picks_cfb.data.catalog import register_dataset_version

        register_dataset_version(
            resolve_runtime_target("preview").database_url,
            prediction_ref,
            prediction_manifest,
        )
        register_dataset_version(
            resolve_runtime_target("preview").database_url,
            measurement_states_ref,
            measurement_states_manifest,
        )
        register_dataset_version(
            resolve_runtime_target("preview").database_url,
            team_states_ref,
            team_states_manifest,
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
