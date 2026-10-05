"""Stage 1 (foundation) and Stage 2 (scoring_events_2026) for Stage 6B."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime

import pandas as pd

from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload
from cks_picks_cfb.preseason_features import canonical_team
from cks_picks_cfb.ratings import possession_measurements as pm
from cks_picks_cfb.rebuild.errors import GateError
from cks_picks_cfb.rebuild.orchestrator import StageContext, StageOutput
from cks_picks_cfb.rebuild.published import PublishedRun
from cks_picks_cfb.rebuild.recon_common import (
    EXPECTED_COUNTS,
    TOTAL_2026_GAMES,
    WEEKS,
    checked_read,
    frame_digest,
    json_data,
    original_run_id,
    parquet_data,
    read_parquet_data,
    source_refs,
)

FOUNDATION_SUMMARY = "rebuild/6b/{run_id}/foundation/summary.json"
FOUNDATION_SCHEDULE = "rebuild/6b/{run_id}/foundation/schedule.parquet"

EVENTS_SUMMARY = "rebuild/6b/{run_id}/scoring_events_2026/summary.json"
EVENTS_PARQUET = "rebuild/6b/{run_id}/scoring_events_2026/events.parquet"
OBSERVATIONS_PARQUET = "rebuild/6b/{run_id}/scoring_events_2026/observations.parquet"

EXPECTED_6A_RECEIPT_SHA = (
    "efcedf3e67dd85055782474b5022bf73d7f53d80c630264ca7c491699309d15e"
)


# ---------------------------------------------------------------------------
# Stage 1: Foundation
# ---------------------------------------------------------------------------


def build_foundation(context: StageContext) -> StageOutput:
    run_6a = PublishedRun(context, root_input="root_manifest_6a")
    run_task4 = PublishedRun(context, root_input="root_manifest_task4")

    # 1. Verify Task 4 signed receipt and checksum
    raw_receipt = context.read_input("task4_receipt")
    if (
        hashlib.sha256(raw_receipt).hexdigest()
        != run_task4.objects[run_task4.run_key("receipt/receipt.json")]
    ):
        raise GateError("Task 4 receipt differs from published root")
    receipt = json.loads(raw_receipt)
    verify_signed_payload(receipt, label="Task 4 signed receipt")
    if receipt.get("manifest_sha256") != EXPECTED_6A_RECEIPT_SHA:
        raise GateError(
            f"task4 receipt checksum {receipt.get('manifest_sha256')} != expected {EXPECTED_6A_RECEIPT_SHA}"
        )

    # 2. Verify inputs_for_6b
    inputs_for_6b = receipt["inputs_for_6b"]
    if inputs_for_6b["selected_design"] != context.plan.policies["design"]:
        raise GateError("6A selected design differs from plan")
    if inputs_for_6b["cutoff_2026"] != context.plan.cutoff_2026:
        raise GateError(
            f"receipt cutoff {inputs_for_6b['cutoff_2026']} != plan cutoff {context.plan.cutoff_2026}"
        )
    for uri, expected_sha in inputs_for_6b["artifacts"].items():
        actual_sha = hashlib.sha256(run_6a.read(uri)).hexdigest()
        if actual_sha != expected_sha:
            raise GateError(
                f"6A artifact hash mismatch for {uri}: {actual_sha} != {expected_sha}"
            )

    # 3. Reconstruct locked schedule
    raw_lock = context.read_input("source_lock_2026")
    lock = json.loads(raw_lock)
    cols = lock["games"]["columns"]
    records = [dict(zip(cols, row, strict=True)) for row in lock["games"]["rows"]]
    schedule = pd.DataFrame.from_records(records)
    if len(schedule) != TOTAL_2026_GAMES:
        raise GateError(
            f"locked schedule has {len(schedule)} games, expected {TOTAL_2026_GAMES}"
        )

    schedule["game_id"] = schedule["game_id"].astype(int)
    schedule["week"] = schedule["week"].astype(int)
    schedule["season"] = 2026
    schedule["kickoff_utc"] = pd.to_datetime(schedule["start_date"], utc=True)
    schedule["home_team"] = schedule["home_team"].map(canonical_team)
    schedule["away_team"] = schedule["away_team"].map(canonical_team)
    schedule = schedule.sort_values(["week", "kickoff_utc", "game_id"]).reset_index(
        drop=True
    )

    if (
        schedule.duplicated(["season", "game_id"]).any()
        or schedule[["kickoff_utc", "home_team", "away_team"]].isna().any().any()
    ):
        raise GateError("locked schedule has duplicate or incomplete games")
    from cks_picks_cfb.rebuild import common

    storage = common.preview_storage(context)
    refs = source_refs(context)
    cutoffs = {}
    for w in WEEKS:
        metadata = refs["weeks"][str(w)]
        manifest = json.loads(checked_read(storage, metadata["source_manifest"]))
        if manifest["run_id"] != original_run_id(w):
            raise GateError("source manifest run identity changed")
        cutoffs[w] = manifest["data_as_of"]
        if cutoffs[w] != metadata["as_of"] or (
            w < 5 and cutoffs[w] != lock["market_sources"][str(w)]["as_of"]
        ):
            raise GateError(f"week {w} original forecast cutoff changed")
        if (
            manifest["input_dataset_refs"] != list(metadata["market_sources"].values())
            and {r["dataset"]: r for r in manifest["input_dataset_refs"]}
            != metadata["market_sources"]
        ):
            raise GateError(f"week {w} quote-set identity changed")

    # 4. Check week counts and as_of chronology
    week_counts = schedule["week"].value_counts().to_dict()
    for w in WEEKS:
        if week_counts.get(w, 0) != EXPECTED_COUNTS[w]:
            raise GateError(
                f"week {w} count {week_counts.get(w, 0)} != {EXPECTED_COUNTS[w]}"
            )
        as_of_dt = datetime.fromisoformat(cutoffs[w].replace("Z", "+00:00"))
        first_kickoff = (
            schedule[schedule["week"] == w]["kickoff_utc"].min().to_pydatetime()
        )
        if as_of_dt >= first_kickoff:
            raise GateError(
                f"week {w} as_of {as_of_dt} is not before first kickoff {first_kickoff}"
            )
        if w > 0:
            last_prior_kickoff = (
                schedule[schedule["week"] == w - 1]["kickoff_utc"].max().to_pydatetime()
            )
            if as_of_dt <= last_prior_kickoff:
                raise GateError(
                    f"week {w} as_of {as_of_dt} is not after prior week last kickoff {last_prior_kickoff}"
                )

    summary = {
        "status": "passed",
        "total_games": len(schedule),
        "weekly_counts": {str(w): EXPECTED_COUNTS[w] for w in WEEKS},
        "weekly_as_of": cutoffs,
        "receipt_sha": EXPECTED_6A_RECEIPT_SHA,
        "schedule_digest": frame_digest(schedule),
    }

    prefix_sched = FOUNDATION_SCHEDULE.format(run_id=context.plan.run_id)
    prefix_sum = FOUNDATION_SUMMARY.format(run_id=context.plan.run_id)

    artifacts = [
        (prefix_sched, parquet_data(schedule)),
        (prefix_sum, json_data(summary)),
    ]
    return StageOutput(artifacts=artifacts, metrics={"games": len(schedule)})


def verify_foundation(context: StageContext) -> list[str]:
    problems: list[str] = []
    prefix_sum = FOUNDATION_SUMMARY.format(run_id=context.plan.run_id)
    prefix_sched = FOUNDATION_SCHEDULE.format(run_id=context.plan.run_id)
    try:
        summary = json.loads(context.read_artifact("foundation", prefix_sum))
        schedule = read_parquet_data(context.read_artifact("foundation", prefix_sched))
    except Exception as exc:
        return [f"failed to read foundation artifacts: {exc}"]

    if summary["total_games"] != TOTAL_2026_GAMES or len(schedule) != TOTAL_2026_GAMES:
        problems.append(f"total games != {TOTAL_2026_GAMES}")
    if frame_digest(schedule) != summary["schedule_digest"]:
        problems.append("schedule digest mismatch")
    return problems


# ---------------------------------------------------------------------------
# Stage 2: Scoring events 2026
# ---------------------------------------------------------------------------


def build_scoring_events_2026(context: StageContext) -> StageOutput:
    from cks_picks_cfb.data.data_first_possession_v1 import build_population
    from cks_picks_cfb.data.data_first_repair_v2 import reconcile_population
    from cks_picks_cfb.data.lake import read_dataset
    from cks_picks_cfb.rebuild import common, silver_2026

    run_6a = PublishedRun(context, root_input="root_manifest_6a")
    storage = common.preview_storage(context)
    pin_file = json.loads(context.read_input("silver_2026_parents"))
    lock = json.loads(context.read_input("source_lock_2026"))

    # Load 2026 Silver byplay from published 6A root
    byplay_frames = run_6a.dataset_frames("byplay", season_scope="2026")
    if 2026 not in byplay_frames:
        raise GateError("published 2026 byplay not found in 6A root")
    byplay = byplay_frames[2026]

    # Load schedule from foundation
    sched_key = FOUNDATION_SCHEDULE.format(run_id=context.plan.run_id)
    schedule = read_parquet_data(context.read_artifact("foundation", sched_key))

    # Read outcomes
    outcomes_ref = silver_2026.silver._ref(pin_file["game_outcomes"])
    outcomes = read_dataset(storage, outcomes_ref)

    # Reconcile population
    rec_frames = run_6a.dataset_frames("source_reconciliation", season_scope="2026")
    reconciliation = rec_frames[2026]

    completed = schedule[
        schedule["home_points"].notna() & schedule["away_points"].notna()
    ].copy()
    completed["completed"] = True
    expected_completed = int(lock["research_2026_prediction_keys"]["completed_games"])

    population_raw, _ = reconcile_population(
        schedule=completed[
            [
                "season",
                "week",
                "game_id",
                "kickoff_utc",
                "home_team",
                "away_team",
                "completed",
            ]
        ],
        outcomes=outcomes[
            ["season", "game_id", "completed", "home_points", "away_points"]
        ],
        observed_games=completed[["season", "game_id"]],
        reconciliation=reconciliation,
        omissions={},
        scope="season_2026",
    )
    population = build_population(
        population_raw,
        scope="season_2026",
        expected_rows=expected_completed,
        expected_eligible=expected_completed,
    )

    result = pm.build_measurements(
        byplay=byplay, population=population, outcomes=outcomes, scope="season_2026"
    )

    # Hard gate: observations digest must equal published 6A states_2026/observations.parquet
    expected_obs = run_6a.frame("states_2026/observations.parquet")
    actual_obs = result.observations.sort_values(
        ["season", "week", "game_id", "team", "measurement_id", "unit_role"]
    ).reset_index(drop=True)
    expected_obs_sorted = expected_obs.sort_values(
        ["season", "week", "game_id", "team", "measurement_id", "unit_role"]
    ).reset_index(drop=True)

    actual_digest = frame_digest(actual_obs)
    expected_digest = frame_digest(expected_obs_sorted)
    if actual_digest != expected_digest:
        raise GateError(
            f"2026 observations digest mismatch with 6A: {actual_digest} != {expected_digest}"
        )

    # Persist scoring events as baseline_unchanged
    events = result.scoring_events.copy()
    if "admission" not in events.columns:
        events["admission"] = "baseline_unchanged"
    else:
        events["admission"] = events["admission"].fillna("baseline_unchanged")

    prefix_events = EVENTS_PARQUET.format(run_id=context.plan.run_id)
    prefix_obs = OBSERVATIONS_PARQUET.format(run_id=context.plan.run_id)
    prefix_sum = EVENTS_SUMMARY.format(run_id=context.plan.run_id)

    summary = {
        "status": "passed",
        "completed_games": len(completed),
        "events_count": len(events),
        "observations_count": len(actual_obs),
        "observations_digest": actual_digest,
    }

    artifacts = [
        (prefix_events, parquet_data(events)),
        (prefix_obs, parquet_data(actual_obs)),
        (prefix_sum, json_data(summary)),
    ]
    return StageOutput(artifacts=artifacts, metrics={"events": len(events)})


def verify_scoring_events_2026(context: StageContext) -> list[str]:
    problems: list[str] = []
    prefix_sum = EVENTS_SUMMARY.format(run_id=context.plan.run_id)
    prefix_obs = OBSERVATIONS_PARQUET.format(run_id=context.plan.run_id)
    try:
        summary = json.loads(context.read_artifact("scoring_events_2026", prefix_sum))
        obs = read_parquet_data(
            context.read_artifact("scoring_events_2026", prefix_obs)
        )
    except Exception as exc:
        return [f"failed to read scoring events artifacts: {exc}"]

    run_6a = PublishedRun(context, root_input="root_manifest_6a")
    expected_obs = (
        run_6a.frame("states_2026/observations.parquet")
        .sort_values(
            ["season", "week", "game_id", "team", "measurement_id", "unit_role"]
        )
        .reset_index(drop=True)
    )

    if summary.get("status") != "passed":
        problems.append("scoring events summary status is not passed")
    if frame_digest(obs) != frame_digest(expected_obs):
        problems.append(
            "2026 observations digest does not match 6A published observations"
        )
    return problems
