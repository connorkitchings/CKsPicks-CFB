"""Stage 5 (application_frames) and Stage 6 (predictions) for Stage 6B."""

from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd

from cks_picks_cfb.forecast.live import (
    DEVELOPMENT_SEASONS,
    apply_exported_bridge,
    build_live_application_frame,
)
from cks_picks_cfb.rebuild.errors import GateError
from cks_picks_cfb.rebuild.orchestrator import StageContext, StageOutput
from cks_picks_cfb.rebuild.published import PublishedRun
from cks_picks_cfb.rebuild.recon_common import (
    EXPECTED_COUNTS,
    TOTAL_2026_GAMES,
    WEEKS,
    frame_digest,
    json_data,
    load_partitioned_gold,
    parquet_data,
    read_parquet_data,
    recon_run_id,
    weekly_as_of,
    write_partitioned_gold,
)
from cks_picks_cfb.rebuild.recon_foundation import FOUNDATION_SCHEDULE

FRAMES_SUMMARY = "rebuild/6b/{run_id}/application_frames/summary.json"
FRAMES_PARQUET = "rebuild/6b/{run_id}/application_frames/frames.parquet"
FRAMES_DATASET = "reconstruction_application_frames"
FRAMES_SCHEMA_VERSION = "reconstruction_application_frames_v1"

PREDICTIONS_SUMMARY = "rebuild/6b/{run_id}/predictions/summary.json"
PREDICTIONS_PARQUET = "rebuild/6b/{run_id}/predictions/predictions.parquet"
PREDICTIONS_DATASET = "reconstruction_predictions"
PREDICTIONS_SCHEMA_VERSION = "reconstruction_predictions_v1"


# ---------------------------------------------------------------------------
# Stage 5: Application Frames
# ---------------------------------------------------------------------------


def build_application_frames(context: StageContext) -> StageOutput:
    sched_key = FOUNDATION_SCHEDULE.format(run_id=context.plan.run_id)
    schedule = read_parquet_data(context.read_artifact("foundation", sched_key))

    off_key = f"rebuild/6b/{context.plan.run_id}/offsets_2026/offsets.parquet"
    offsets = read_parquet_data(context.read_artifact("offsets_2026", off_key))

    st_key = f"rebuild/6b/{context.plan.run_id}/states_at_cutoff/team_states.parquet"
    team_states = read_parquet_data(context.read_artifact("states_at_cutoff", st_key))

    weekly_frames: dict[int, pd.DataFrame] = {}
    weekly_state_refs: dict[int, dict[int, str]] = {}

    for w in WEEKS:
        as_of_str = weekly_as_of(context)[w]
        as_of_dt = pd.Timestamp(as_of_str)

        completed_prior = schedule[
            schedule["week"].lt(w)
            & schedule["kickoff_utc"].lt(as_of_dt)
            & schedule["home_points"].notna()
            & schedule["away_points"].notna()
        ].copy()
        completed_prior = completed_prior.assign(
            schedule_completed=True,
            outcome_valid=True,
        )

        w_states = team_states[team_states["target_week"].eq(w)].copy()
        w_states["game_id"] = 0  # ensure integer game_id for sorting

        frame, refs = build_live_application_frame(
            schedule,
            completed_prior,
            w_states,
            offsets,
            as_of=as_of_str,
            target_week=w,
        )

        if len(frame) != EXPECTED_COUNTS[w]:
            raise GateError(
                f"week {w} application frame has {len(frame)} rows, expected {EXPECTED_COUNTS[w]}"
            )
        if not (frame["home_host"] == 1.0).all():
            raise GateError(f"week {w} application frame home_host is not 1.0")
        if not frame["venue_unknown"].all():
            raise GateError(f"week {w} application frame venue_unknown is not True")

        weekly_frames[w] = frame.reset_index(drop=True)
        games = schedule[schedule.week.eq(w)]
        state_key = f"{context.plan.run_prefix()}states_at_cutoff/team_states.parquet"
        parent_sha = context.parents["states_at_cutoff"]
        weekly_state_refs[w] = {
            int(game.game_id): "|".join(
                f"{state_key}#target_week={w};team={team};stage_sha={parent_sha}"
                for team in (game.home_team, game.away_team)
            )
            for game in games.itertuples(index=False)
        }

    all_frames = pd.concat([weekly_frames[w] for w in WEEKS], ignore_index=True)
    if len(all_frames) != TOTAL_2026_GAMES:
        raise GateError(
            f"total application frames {len(all_frames)} != {TOTAL_2026_GAMES}"
        )

    lake_summary, lake_files = write_partitioned_gold(
        context,
        dataset=FRAMES_DATASET,
        schema_version=FRAMES_SCHEMA_VERSION,
        frames_by_week=weekly_frames,
        parent_refs=[
            {"dataset": "offsets_2026", "version_id": context.plan.run_id},
            {"dataset": "states_at_cutoff", "version_id": context.plan.run_id},
        ],
    )

    summary = {
        "status": "passed",
        "total_games": len(all_frames),
        "weekly_counts": {str(w): len(weekly_frames[w]) for w in WEEKS},
        "frames_digest": frame_digest(all_frames),
        "state_refs_by_week": {
            str(w): {str(g): r for g, r in weekly_state_refs[w].items()} for w in WEEKS
        },
        "lake_gold": lake_summary,
    }

    prefix_fr = FRAMES_PARQUET.format(run_id=context.plan.run_id)
    prefix_sum = FRAMES_SUMMARY.format(run_id=context.plan.run_id)

    artifacts = [
        (prefix_fr, parquet_data(all_frames)),
        (prefix_sum, json_data(summary)),
        *lake_files,
    ]
    return StageOutput(
        artifacts=artifacts, metrics={"application_frames": len(all_frames)}
    )


def verify_application_frames(context: StageContext) -> list[str]:
    problems: list[str] = []
    prefix_sum = FRAMES_SUMMARY.format(run_id=context.plan.run_id)
    prefix_fr = FRAMES_PARQUET.format(run_id=context.plan.run_id)
    try:
        summary = json.loads(context.read_artifact("application_frames", prefix_sum))
        frames = read_parquet_data(
            context.read_artifact("application_frames", prefix_fr)
        )
    except Exception as exc:
        return [f"failed to read application frames artifacts: {exc}"]

    if len(frames) != TOTAL_2026_GAMES:
        problems.append(f"application frames count {len(frames)} != {TOTAL_2026_GAMES}")
    if frame_digest(frames) != summary["frames_digest"]:
        problems.append("application frames digest mismatch")

    try:
        lake_frames = load_partitioned_gold(
            context, "application_frames", summary["lake_gold"]
        )
        if len(lake_frames) != TOTAL_2026_GAMES:
            problems.append(
                f"lake application frames count {len(lake_frames)} != {TOTAL_2026_GAMES}"
            )
    except Exception as exc:
        problems.append(f"failed to load partitioned lake application frames: {exc}")

    return problems


# ---------------------------------------------------------------------------
# Stage 6: Predictions
# ---------------------------------------------------------------------------


INFERENCE_BUNDLE_INPUT = "inference_bundle"


def prediction_bundle(context: StageContext, run_6a: PublishedRun) -> tuple[bytes, str]:
    """The bundle the replay applies, and the reference recorded on each prediction.

    A plan that names an ``inference_bundle`` input uses exactly those pinned bytes (the
    successor bridge refit on the corrected frames, the recipe the site serves). A plan
    without it keeps the 6A refit, which the first 6B run used and which is the accepted
    forecast-v1 recipe, not the served one.
    """
    if any(pin.name == INFERENCE_BUNDLE_INPUT for pin in context.plan.inputs):
        raw = context.read_input(INFERENCE_BUNDLE_INPUT)
        return raw, f"{INFERENCE_BUNDLE_INPUT}#sha256={hashlib.sha256(raw).hexdigest()}"
    key = run_6a.run_key("forecast/bundle.json")
    raw = run_6a.read(key)
    return raw, f"{key}#sha256={hashlib.sha256(raw).hexdigest()}"


def build_predictions(context: StageContext) -> StageOutput:
    run_6a = PublishedRun(context, root_input="root_manifest_6a")

    # Load the bundle (the plan's pinned inference bundle, else the 6A refit)
    bundle_raw, model_ref = prediction_bundle(context, run_6a)
    bundle = json.loads(bundle_raw)

    # Pre-check gate: verify bundle compatibility with apply_exported_bridge
    if bundle.get("schema_version") != "v5_inference_bundle_v1":
        raise GateError(
            f"bundle schema version {bundle.get('schema_version')} is not v5_inference_bundle_v1"
        )
    if set(bundle.get("development_seasons", [])) != set(DEVELOPMENT_SEASONS):
        raise GateError("bundle development seasons mismatch")

    # Leakage gates
    seasons = bundle.get("development_seasons", [])
    if any(s > 2025 or s == 2020 for s in seasons):
        raise GateError("bundle contains post-2025 or 2020 development seasons")

    # Load application frames and state refs
    fr_key = FRAMES_PARQUET.format(run_id=context.plan.run_id)
    all_frames = read_parquet_data(context.read_artifact("application_frames", fr_key))

    sum_key = FRAMES_SUMMARY.format(run_id=context.plan.run_id)
    frames_summary = json.loads(context.read_artifact("application_frames", sum_key))
    state_refs_by_week = frames_summary["state_refs_by_week"]

    schedule = read_parquet_data(
        context.read_artifact(
            "foundation", FOUNDATION_SCHEDULE.format(run_id=context.plan.run_id)
        )
    )
    states = read_parquet_data(
        context.read_artifact(
            "states_at_cutoff",
            f"{context.plan.run_prefix()}states_at_cutoff/team_states.parquet",
        )
    )
    if states.duplicated(["target_week", "team"]).any():
        raise GateError("state keys duplicate")
    for w, cutoff in weekly_as_of(context).items():
        if (
            pd.to_datetime(states[states.target_week.eq(w)].cutoff_utc, utc=True)
            .gt(pd.Timestamp(cutoff))
            .any()
        ):
            raise GateError("state cutoff exceeds forecast as_of")
        if schedule[schedule.week.lt(w)].kickoff_utc.ge(pd.Timestamp(cutoff)).any():
            raise GateError("offset evidence kicked off at or after as_of")
    if not np.isfinite(all_frames.select_dtypes(include="number").to_numpy()).all():
        raise GateError("application frame contains nonfinite inputs")

    evidence = read_parquet_data(
        context.read_artifact(
            "offsets_2026", f"{context.plan.run_prefix()}offsets_2026/evidence.parquet"
        )
    )
    for w, cutoff in weekly_as_of(context).items():
        rows = evidence[evidence.target_week.eq(w)]
        if pd.to_datetime(rows.kickoff_utc, utc=True).ge(pd.Timestamp(cutoff)).any():
            raise GateError("usable offset evidence kicked off at or after as_of")

    # Pre-check test with a single-game slice before full production
    sample_frame = all_frames.iloc[:1].copy()
    sample_game_id = int(sample_frame["game_id"].iloc[0])
    sample_refs = {sample_game_id: "team_states/0#sample|team_states/0#sample"}
    try:
        apply_exported_bridge(
            bundle,
            sample_frame,
            run_id="test-run",
            model_ref="v5-test",
            state_refs=sample_refs,
            source_ref="test",
            timing_class="replay",
        )
    except Exception as exc:
        raise GateError(f"bundle compatibility check failed: {exc}") from exc

    weekly_preds: dict[int, pd.DataFrame] = {}
    for w in WEEKS:
        w_frame = all_frames[all_frames["week"].eq(w)].copy()
        w_refs = {int(g): r for g, r in state_refs_by_week[str(w)].items()}
        run_id_w = recon_run_id(w)

        computation = apply_exported_bridge(
            bundle,
            w_frame,
            run_id=run_id_w,
            model_ref=model_ref,
            state_refs=w_refs,
            source_ref=context.plan.run_id,
            timing_class="replay",
        )
        preds = computation.predictions.copy()
        preds["timing_class"] = "retrospective_reconstruction"
        if len(preds) != len(w_frame) * 2:
            raise GateError(
                f"week {w} predictions count {len(preds)} != {len(w_frame) * 2}"
            )

        weekly_preds[w] = preds.reset_index(drop=True)

    all_preds = pd.concat([weekly_preds[w] for w in WEEKS], ignore_index=True)
    if len(all_preds) != TOTAL_2026_GAMES * 2:
        raise GateError(
            f"total predictions count {len(all_preds)} != {TOTAL_2026_GAMES * 2}"
        )

    lake_summary, lake_files = write_partitioned_gold(
        context,
        dataset=PREDICTIONS_DATASET,
        schema_version=PREDICTIONS_SCHEMA_VERSION,
        frames_by_week=weekly_preds,
        parent_refs=[
            {"dataset": "application_frames", "version_id": context.plan.run_id},
        ],
    )

    summary = {
        "status": "passed",
        "total_predictions": len(all_preds),
        "bundle_compatibility": "passed",
        "state_cutoff_gate": "passed",
        "offset_evidence_cutoff_gate": "passed",
        "weekly_counts": {str(w): len(weekly_preds[w]) for w in WEEKS},
        "predictions_digest": frame_digest(all_preds),
        "lake_gold": lake_summary,
    }

    prefix_pr = PREDICTIONS_PARQUET.format(run_id=context.plan.run_id)
    prefix_sum = PREDICTIONS_SUMMARY.format(run_id=context.plan.run_id)

    artifacts = [
        (prefix_pr, parquet_data(all_preds)),
        (prefix_sum, json_data(summary)),
        *lake_files,
    ]
    return StageOutput(artifacts=artifacts, metrics={"predictions": len(all_preds)})


def verify_predictions(context: StageContext) -> list[str]:
    problems: list[str] = []
    prefix_sum = PREDICTIONS_SUMMARY.format(run_id=context.plan.run_id)
    prefix_pr = PREDICTIONS_PARQUET.format(run_id=context.plan.run_id)
    try:
        summary = json.loads(context.read_artifact("predictions", prefix_sum))
        preds = read_parquet_data(context.read_artifact("predictions", prefix_pr))
    except Exception as exc:
        return [f"failed to read predictions artifacts: {exc}"]

    if len(preds) != TOTAL_2026_GAMES * 2:
        problems.append(f"predictions count {len(preds)} != {TOTAL_2026_GAMES * 2}")
    if frame_digest(preds) != summary["predictions_digest"]:
        problems.append("predictions frame digest mismatch")

    try:
        lake_preds = load_partitioned_gold(context, "predictions", summary["lake_gold"])
        if len(lake_preds) != TOTAL_2026_GAMES * 2:
            problems.append(
                f"lake predictions count {len(lake_preds)} != {TOTAL_2026_GAMES * 2}"
            )
    except Exception as exc:
        problems.append(f"failed to load partitioned lake predictions: {exc}")

    return problems
