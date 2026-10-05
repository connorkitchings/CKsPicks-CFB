"""Stage 3: 2026 offsets with the offset-freeze gate and Gold lake persistence."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from cks_picks_cfb.forecast.live import DEVELOPMENT_SEASONS
from cks_picks_cfb.forecast.offsets import build_offsets, unresolved_team_games
from cks_picks_cfb.rebuild.errors import GateError
from cks_picks_cfb.rebuild.orchestrator import StageContext, StageOutput
from cks_picks_cfb.rebuild.published import PublishedRun
from cks_picks_cfb.rebuild.recon_common import (
    TOTAL_2026_GAMES,
    WEEK_AS_OF,
    WEEKS,
    frame_digest,
    json_data,
    load_partitioned_gold,
    parquet_data,
    read_parquet_data,
    write_partitioned_gold,
)
from cks_picks_cfb.rebuild.recon_foundation import FOUNDATION_SCHEDULE

OFFSETS_SUMMARY = "rebuild/6b/{run_id}/offsets_2026/summary.json"
OFFSETS_PARQUET = "rebuild/6b/{run_id}/offsets_2026/offsets.parquet"

OFFSET_DATASET = "reconstruction_offsets_2026"
OFFSET_SCHEMA_VERSION = "reconstruction_offsets_2026_v1"


def build_offsets_2026(context: StageContext) -> StageOutput:
    run_6a = PublishedRun(context, root_input="root_manifest_6a")

    # Load historical foundation from 6A
    historical_offsets = run_6a.frame("forecast/offsets.parquet")
    admitted_events = run_6a.frame("comparison/admitted_events.parquet")
    pop_raw = run_6a.frame("eligibility/population.parquet")

    from cks_picks_cfb.data.data_first_possession_v1 import build_population
    historical_population = build_population(pop_raw, scope="historical")

    # Load 2026 schedule and events
    sched_key = FOUNDATION_SCHEDULE.format(run_id=context.plan.run_id)
    schedule = read_parquet_data(context.read_artifact("foundation", sched_key))

    events_2026 = read_parquet_data(
        context.read_artifact(
            "scoring_events_2026",
            f"rebuild/6b/{context.plan.run_id}/scoring_events_2026/events.parquet",
        )
    )

    combined_events = pd.concat([admitted_events, events_2026], ignore_index=True)

    # Global kickoff-order computation for all 2026 games
    full_2026_pop = schedule.assign(
        forecast_eligible=True,
        schedule_completed=schedule["home_points"].notna() & schedule["away_points"].notna(),
        outcome_valid=schedule["home_points"].notna() & schedule["away_points"].notna(),
        measurement_usable=schedule["home_points"].notna() & schedule["away_points"].notna(),
    )
    all_seasons_population = pd.concat(
        [historical_population, full_2026_pop], ignore_index=True, sort=False
    )
    global_computation = build_offsets(
        all_seasons_population,
        combined_events,
        development_seasons=DEVELOPMENT_SEASONS + (2026,),
        equivalent_games=4,
    )
    global_2026_offsets = global_computation.offsets[
        global_computation.offsets["season"].eq(2026)
    ].set_index(["week", "game_id"])

    # Weekly frozen-at-cutoff offset computation
    weekly_offsets: dict[int, pd.DataFrame] = {}
    freeze_mismatches: list[dict[str, Any]] = []
    duplicate_appearances: list[dict[str, Any]] = []

    for w in WEEKS:
        as_of_dt = pd.Timestamp(WEEK_AS_OF[w])
        # Games in earlier weeks are completed evidence if kicked off before as_of
        earlier_games = schedule[
            schedule["week"].lt(w) & schedule["kickoff_utc"].lt(as_of_dt)
        ].copy()
        earlier_games = earlier_games.assign(
            forecast_eligible=True,
            schedule_completed=True,
            outcome_valid=True,
            measurement_usable=True,
        )

        # Target week games are forecast-eligible but not usable as earlier evidence
        target_games = schedule[schedule["week"].eq(w)].copy()
        target_games = target_games.assign(
            forecast_eligible=True,
            schedule_completed=False,
            outcome_valid=False,
            measurement_usable=False,
        )

        # Check for teams playing multiple games in target week
        team_counts = pd.concat([target_games["home_team"], target_games["away_team"]]).value_counts()
        for team, count in team_counts.items():
            if count > 1:
                duplicate_appearances.append({"week": w, "team": str(team), "games": int(count)})

        week_pop = pd.concat(
            [historical_population, earlier_games, target_games],
            ignore_index=True,
            sort=False,
        )
        week_comp = build_offsets(
            week_pop,
            combined_events,
            development_seasons=DEVELOPMENT_SEASONS + (2026,),
            equivalent_games=4,
        )
        week_offsets = week_comp.offsets[
            week_comp.offsets["season"].eq(2026) & week_comp.offsets["week"].eq(w)
        ].copy()

        # Hard Gate: compare frozen-at-cutoff offsets to global kickoff-order offsets
        for row in week_offsets.itertuples(index=False):
            key = (int(row.week), int(row.game_id))
            global_row = global_2026_offsets.loc[key]
            delta_margin = abs(float(row.offset_margin) - float(global_row["offset_margin"]))
            delta_total = abs(float(row.offset_total) - float(global_row["offset_total"]))
            if delta_margin > 1e-9 or delta_total > 1e-9:
                freeze_mismatches.append(
                    {
                        "week": w,
                        "game_id": int(row.game_id),
                        "frozen_margin": float(row.offset_margin),
                        "kickoff_order_margin": float(global_row["offset_margin"]),
                        "delta_margin": delta_margin,
                        "frozen_total": float(row.offset_total),
                        "kickoff_order_total": float(global_row["offset_total"]),
                        "delta_total": delta_total,
                    }
                )

        weekly_offsets[w] = week_offsets.reset_index(drop=True)

    if freeze_mismatches:
        raise GateError(
            f"offset-freeze gate failed: {len(freeze_mismatches)} games differ from kickoff order"
        )

    # Verify historical offsets equal 6A forecast/offsets.parquet
    hist_subset = week_comp.offsets[week_comp.offsets["season"].lt(2026)].reset_index(drop=True)
    if len(hist_subset) != len(historical_offsets):
        raise GateError("historical offset row count differs from 6A")
    if frame_digest(hist_subset[["season", "game_id", "offset_margin", "offset_total"]]) != frame_digest(
        historical_offsets[["season", "game_id", "offset_margin", "offset_total"]]
    ):
        raise GateError("historical offsets differ from 6A forecast/offsets.parquet")

    # Combine 2026 offsets
    all_2026_offsets = pd.concat([weekly_offsets[w] for w in WEEKS], ignore_index=True)
    if len(all_2026_offsets) != TOTAL_2026_GAMES:
        raise GateError(
            f"2026 offsets has {len(all_2026_offsets)} rows, expected {TOTAL_2026_GAMES}"
        )

    # Lake Gold dataset persistence
    lake_summary, lake_files = write_partitioned_gold(
        context,
        dataset=OFFSET_DATASET,
        schema_version=OFFSET_SCHEMA_VERSION,
        frames_by_week=weekly_offsets,
        parent_refs=[
            {"dataset": "scoring_events_2026", "version_id": context.plan.run_id},
            {"dataset": "foundation", "version_id": context.plan.run_id},
        ],
    )

    unresolved = unresolved_team_games(events_2026)
    summary = {
        "status": "passed",
        "total_offsets": len(all_2026_offsets),
        "weekly_counts": {str(w): len(weekly_offsets[w]) for w in WEEKS},
        "freeze_mismatches_count": len(freeze_mismatches),
        "duplicate_weekly_appearances": duplicate_appearances,
        "unresolved_team_games_count": len(unresolved),
        "lake_gold": lake_summary,
        "offsets_digest": frame_digest(all_2026_offsets),
    }

    prefix_off = OFFSETS_PARQUET.format(run_id=context.plan.run_id)
    prefix_sum = OFFSETS_SUMMARY.format(run_id=context.plan.run_id)

    artifacts = [
        (prefix_off, parquet_data(all_2026_offsets)),
        (prefix_sum, json_data(summary)),
        *lake_files,
    ]
    return StageOutput(artifacts=artifacts, metrics={"offsets": len(all_2026_offsets)})


def verify_offsets_2026(context: StageContext) -> list[str]:
    problems: list[str] = []
    prefix_sum = OFFSETS_SUMMARY.format(run_id=context.plan.run_id)
    prefix_off = OFFSETS_PARQUET.format(run_id=context.plan.run_id)
    try:
        summary = json.loads(context.read_artifact("offsets_2026", prefix_sum))
        offsets = read_parquet_data(context.read_artifact("offsets_2026", prefix_off))
    except Exception as exc:
        return [f"failed to read offsets artifacts: {exc}"]

    if summary.get("freeze_mismatches_count", 0) > 0:
        problems.append("offset freeze gate reported mismatches")
    if len(offsets) != TOTAL_2026_GAMES:
        problems.append(f"total offsets {len(offsets)} != {TOTAL_2026_GAMES}")
    if frame_digest(offsets) != summary["offsets_digest"]:
        problems.append("offsets frame digest mismatch")

    # Verify lake dataset
    try:
        lake_offsets = load_partitioned_gold(context, "offsets_2026", summary["lake_gold"])
        if len(lake_offsets) != TOTAL_2026_GAMES:
            problems.append(f"lake offsets count {len(lake_offsets)} != {TOTAL_2026_GAMES}")
    except Exception as exc:
        problems.append(f"failed to load partitioned lake offsets: {exc}")

    return problems
