"""Stage 4: 2026 rating states evaluated at each original week's as_of cutoff."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd

from cks_picks_cfb.ratings.possession_intended_update import IntendedUpdate, _time
from cks_picks_cfb.rebuild.errors import GateError
from cks_picks_cfb.rebuild.orchestrator import StageContext, StageOutput
from cks_picks_cfb.rebuild.published import PublishedRun
from cks_picks_cfb.rebuild.recon_common import (
    frame_digest,
    json_data,
    parquet_data,
    plan_weeks,
    read_parquet_data,
    weekly_as_of,
)
from cks_picks_cfb.rebuild.recon_foundation import FOUNDATION_SCHEDULE

STATES_SUMMARY = "rebuild/6b/{run_id}/states_at_cutoff/summary.json"
STATES_PARQUET = "rebuild/6b/{run_id}/states_at_cutoff/team_states.parquet"


def build_states_at_cutoff(context: StageContext) -> StageOutput:
    run_6a = PublishedRun(context, root_input="root_manifest_6a")

    # Load priors, terminal, and 6A pregame team states
    terminal = run_6a.frame("ratings/terminal.parquet")
    priors = run_6a.frame("states_2026/priors.parquet")
    pregame_6a = run_6a.frame("states_2026/pregame_teams.parquet")

    # Load schedule and observations
    sched_key = FOUNDATION_SCHEDULE.format(run_id=context.plan.run_id)
    schedule = read_parquet_data(context.read_artifact("foundation", sched_key))

    obs_key = (
        f"rebuild/6b/{context.plan.run_id}/scoring_events_2026/observations.parquet"
    )
    observations = read_parquet_data(
        context.read_artifact("scoring_events_2026", obs_key)
    )

    engine = IntendedUpdate(
        schedule=schedule,
        observations=observations,
        priors=priors,
        historical_terminal=terminal,
    )

    # Evaluate rating engine at each original week's as_of
    weekly_states: list[pd.DataFrame] = []
    for w in plan_weeks(context):
        as_of_str = weekly_as_of(context)[w]
        as_of_dt = _time(as_of_str)
        if w == 0:
            gen = engine._states(
                week=0,
                cutoff=as_of_dt,
                game_id=None,
                teams=engine.teams,
            )
        else:
            gen = engine.current(post_week=w - 1, cutoff_utc=as_of_str)

        states_w = gen.team_states.copy()
        states_w["target_week"] = w
        weekly_states.append(states_w)

    combined_states = pd.concat(weekly_states, ignore_index=True)

    if (
        combined_states.duplicated(["target_week", "team"]).any()
        or not np.isfinite(
            combined_states[["offense_rating", "defense_rating"]].to_numpy()
        ).all()
    ):
        raise GateError("states contain duplicate keys or nonfinite ratings")
    # Hard gate: compare ratings against 6A pregame_teams for every game
    rating_mismatches: list[dict[str, Any]] = []
    pregame_by_game = pregame_6a.set_index(["game_id", "team"])

    for game in schedule.itertuples(index=False):
        game_id = int(game.game_id)
        w = int(game.week)
        w_states = combined_states[combined_states["target_week"].eq(w)].set_index(
            "team"
        )

        for side, team in (
            ("home", str(game.home_team)),
            ("away", str(game.away_team)),
        ):
            actual_state = w_states.loc[team]
            expected_state = pregame_by_game.loc[(game_id, team)]

            off_delta = abs(
                float(actual_state["offense_rating"])
                - float(expected_state["offense_rating"])
            )
            def_delta = abs(
                float(actual_state["defense_rating"])
                - float(expected_state["defense_rating"])
            )

            if (
                not np.isfinite([off_delta, def_delta]).all()
                or off_delta > 1e-9
                or def_delta > 1e-9
            ):
                rating_mismatches.append(
                    {
                        "game_id": game_id,
                        "week": w,
                        "team": team,
                        "side": side,
                        "actual_offense": float(actual_state["offense_rating"]),
                        "expected_offense": float(expected_state["offense_rating"]),
                        "off_delta": off_delta,
                        "actual_defense": float(actual_state["defense_rating"]),
                        "expected_defense": float(expected_state["defense_rating"]),
                        "def_delta": def_delta,
                    }
                )

    if rating_mismatches:
        raise GateError(
            f"states-at-cutoff gate failed: {len(rating_mismatches)} team-ratings differ from 6A pregame_teams"
        )

    summary = {
        "status": "passed",
        "total_team_states": len(combined_states),
        "evaluated_weeks": list(plan_weeks(context)),
        "teams_count": len(engine.teams),
        "rating_mismatches_count": len(rating_mismatches),
        "pregame_teams_identity_gate": "passed",
        "states_digest": frame_digest(combined_states),
    }

    prefix_st = STATES_PARQUET.format(run_id=context.plan.run_id)
    prefix_sum = STATES_SUMMARY.format(run_id=context.plan.run_id)

    artifacts = [
        (prefix_st, parquet_data(combined_states)),
        (prefix_sum, json_data(summary)),
    ]
    return StageOutput(
        artifacts=artifacts, metrics={"team_states": len(combined_states)}
    )


def verify_states_at_cutoff(context: StageContext) -> list[str]:
    problems: list[str] = []
    prefix_sum = STATES_SUMMARY.format(run_id=context.plan.run_id)
    prefix_st = STATES_PARQUET.format(run_id=context.plan.run_id)
    try:
        summary = json.loads(context.read_artifact("states_at_cutoff", prefix_sum))
        states = read_parquet_data(context.read_artifact("states_at_cutoff", prefix_st))
    except Exception as exc:
        return [f"failed to read states artifacts: {exc}"]

    if (
        summary.get("rating_mismatches_count") != 0
        or summary.get("pregame_teams_identity_gate") != "passed"
    ):
        problems.append("states-at-cutoff gate reported rating mismatches")
    if frame_digest(states) != summary["states_digest"]:
        problems.append("states frame digest mismatch")
    return problems
