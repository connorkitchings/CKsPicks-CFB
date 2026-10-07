"""Stage: eligible 2026 rating states up to the plan's exact cutoff (weeks per the lock).

2026 scoring stays at baseline (no 2026 allocation has independent admission evidence), and
no 2026 outcome reaches any fit or calibration: this stage only updates chronological
rating states with games whose kickoff plus six hours is at or before the cutoff. Priors and
scale come from the corrected 2025 terminal state.
"""

from __future__ import annotations

import io
import json
from collections.abc import Iterator
from typing import Any

import pandas as pd

from cks_picks_cfb.rebuild import common, forecast_refit, measurements, silver_2026
from cks_picks_cfb.rebuild.errors import GateError
from cks_picks_cfb.rebuild.orchestrator import StageContext, StageOutput

PREFIX = "rebuild/6a/{run_id}/states_2026/"
AVAILABILITY_HOURS = 6
FILES = (
    "population",
    "observations",
    "priors",
    "pregame_roles",
    "pregame_teams",
    "current_roles",
    "current_teams",
    "final_roles",
    "final_teams",
)
STATE_KEY = ["season", "team", "unit_role"]


def _parquet(frame: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    frame.to_parquet(buffer)
    return buffer.getvalue()


def locked_schedule(games: pd.DataFrame, lock: dict[str, Any]) -> pd.DataFrame:
    """The locked 2026 games (weeks 0-5), checked against the lock's week and kickoff."""
    names = lock["games"]["columns"]
    rows = [dict(zip(names, row, strict=True)) for row in lock["games"]["rows"]]
    ids = {int(row["game_id"]) for row in rows}
    schedule = games[games["game_id"].astype(int).isin(ids)].copy()
    if len(schedule) != len(ids) or set(schedule["game_id"].astype(int)) != ids:
        raise GateError("pinned 2026 schedule differs from the locked game ids")
    schedule["kickoff_utc"] = pd.to_datetime(schedule["kickoff_utc"], utc=True)
    by_id = schedule.set_index(schedule["game_id"].astype(int))
    for row in rows:
        game = by_id.loc[int(row["game_id"])]
        if int(game["week"]) != int(row["week"]) or pd.Timestamp(
            game["kickoff_utc"]
        ) != pd.Timestamp(row["start_date"]):
            raise GateError(f"2026 game {row['game_id']} differs from the lock")
    # Observations and priors use canonical team names; the lock check above used raw ones.
    from cks_picks_cfb.preseason_features import canonical_team

    for column in ("home_team", "away_team"):
        schedule[column] = schedule[column].map(canonical_team)
    return schedule


def available_by(schedule: pd.DataFrame, cutoff: str) -> pd.DataFrame:
    limit = pd.Timestamp(cutoff)
    return schedule[
        schedule["kickoff_utc"] + pd.Timedelta(hours=AVAILABILITY_HOURS) <= limit
    ]


def build(context: StageContext) -> StageOutput:
    from cks_picks_cfb.data.data_first_possession_v1 import build_population
    from cks_picks_cfb.data.data_first_repair_v2 import reconcile_population
    from cks_picks_cfb.data.lake import read_dataset
    from cks_picks_cfb.ratings import possession_measurements as pm
    from cks_picks_cfb.ratings.possession_intended_update import IntendedUpdate
    from cks_picks_cfb.ratings.possession_live_replay import _priors

    cutoff = context.plan.cutoff_2026
    if not cutoff:
        raise GateError("the plan has no 2026 cutoff")
    storage = common.preview_storage(context)
    pin_file = json.loads(context.read_input("silver_2026_parents"))
    lock = json.loads(context.read_input("source_lock_2026"))
    games_ref = silver_2026.silver._ref(
        next(p for p in pin_file["parents"] if p["dataset"] == "games")
    )
    games = read_dataset(storage, games_ref)
    outcomes = read_dataset(storage, silver_2026.silver._ref(pin_file["game_outcomes"]))
    schedule = locked_schedule(games, lock)
    completed = schedule[schedule["completed"].astype(bool)]
    expected_completed = int(lock["research_2026_prediction_keys"]["completed_games"])
    if len(completed) != expected_completed:
        raise GateError(
            f"{len(completed)} completed games, lock says {expected_completed}"
        )
    if available_by(schedule, cutoff).shape[0] != len(completed):
        raise GateError("games available by the cutoff differ from the completed games")

    reconciliation = silver_2026.staged(context, "source_reconciliation")
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
    byplay = silver_2026.staged(context, "byplay")
    result = pm.build_measurements(
        byplay=byplay, population=population, outcomes=outcomes, scope="season_2026"
    )
    terminal = pd.read_parquet(
        io.BytesIO(
            context.read_artifact(
                "measurements_ratings",
                measurements.PREFIX.format(run_id=context.plan.run_id)
                + "terminal.parquet",
            )
        )
    )
    priors, _ = _priors(schedule, terminal)
    engine = IntendedUpdate(
        schedule=schedule,
        observations=result.observations,
        priors=priors,
        historical_terminal=terminal,
    )
    pregame = engine.pregame()
    cutoffs = {int(w): str(c) for w, c in lock["post_week_cutoffs"].items()}
    roles, teams = [], []
    for week, week_cutoff in sorted(cutoffs.items()):
        generation = engine.current(post_week=week, cutoff_utc=week_cutoff)
        roles.append(generation.rating_states)
        teams.append(generation.team_states)
    final = engine.current(post_week=max(cutoffs), cutoff_utc=cutoff)
    frames = {
        "population": population,
        "observations": result.observations,
        "priors": priors,
        "pregame_roles": pregame.rating_states,
        "pregame_teams": pregame.team_states,
        "current_roles": pd.concat(roles, ignore_index=True),
        "current_teams": pd.concat(teams, ignore_index=True),
        "final_roles": final.rating_states,
        "final_teams": final.team_states,
    }
    used = pd.to_datetime(result.observations["kickoff_utc"], utc=True)
    summary = {
        "cutoff_utc": cutoff,
        "post_week_cutoffs": cutoffs,
        "scheduled_games": int(len(schedule)),
        "completed_games": int(len(completed)),
        "rows": {name: int(len(frame)) for name, frame in frames.items()},
        "digests": {
            name: forecast_refit.frame_digest(frames[name])
            for name in ("priors", "pregame_teams", "current_teams", "final_teams")
        },
        "leakage": {
            "max_observation_kickoff_utc": str(used.max()),
            "latest_usable_utc": str(
                used.max() + pd.Timedelta(hours=AVAILABILITY_HOURS)
            ),
            "observations_after_cutoff": int(
                (
                    used + pd.Timedelta(hours=AVAILABILITY_HOURS) > pd.Timestamp(cutoff)
                ).sum()
            ),
        },
        "terminal_season_for_priors": 2025,
        "scoring": "baseline (no 2026 allocation admitted)",
    }
    prefix = PREFIX.format(run_id=context.plan.run_id)

    def artifacts() -> Iterator[tuple[str, bytes]]:
        for name in FILES:
            yield f"{prefix}{name}.parquet", _parquet(frames[name])
        yield (
            f"{prefix}summary.json",
            json.dumps(summary, indent=2, sort_keys=True, default=str).encode(),
        )

    return StageOutput(artifacts=artifacts(), metrics=summary["rows"])


def verify(context: StageContext) -> list[str]:
    stage = context.stage.name
    prefix = PREFIX.format(run_id=context.plan.run_id)
    summary = json.loads(context.read_artifact(stage, prefix + "summary.json"))
    frames = {
        name: pd.read_parquet(
            io.BytesIO(context.read_artifact(stage, f"{prefix}{name}.parquet"))
        )
        for name in FILES
    }
    problems: list[str] = []
    scheduled, weeks = summary["scheduled_games"], len(summary["post_week_cutoffs"])
    teams = int(frames["final_teams"]["team"].nunique())
    expected = {
        "pregame_roles": 4 * scheduled,
        "pregame_teams": 2 * scheduled,
        "current_roles": 2 * teams * weeks,
        "current_teams": teams * weeks,
        "final_roles": 2 * teams,
        "final_teams": teams,
        "priors": 2 * teams,
    }
    for name, count in expected.items():
        if len(frames[name]) != count:
            problems.append(f"{name}: {len(frames[name])} rows, expected {count}")
    if summary["leakage"]["observations_after_cutoff"] != 0:
        problems.append("an observation became usable only after the cutoff")
    if pd.Timestamp(summary["leakage"]["latest_usable_utc"]) > pd.Timestamp(
        summary["cutoff_utc"]
    ):
        problems.append("latest usable observation is after the cutoff")
    for name, frame in frames.items():
        if name in ("population",):
            continue
        if set(int(s) for s in frame["season"]) != {2026}:
            problems.append(f"{name} is not 2026 only")
    final_cutoff = set(
        frames["final_teams"]["cutoff_utc"].astype(str).map(pd.Timestamp)
    )
    if final_cutoff != {pd.Timestamp(summary["cutoff_utc"])}:
        problems.append("final states do not carry the selected cutoff")
    # The selected cutoff only follows the last lock cutoff: states must be identical.
    last = frames["current_teams"]
    week = int(last["week"].max())
    lock_week = last[last["week"].eq(week)].sort_values("team").reset_index(drop=True)
    final = frames["final_teams"].sort_values("team").reset_index(drop=True)
    columns = [c for c in final.columns if c != "cutoff_utc"]
    if len(lock_week) != len(final):
        problems.append("last post-week state differs in size between the two cutoffs")
    else:
        try:
            pd.testing.assert_frame_equal(
                lock_week[columns], final[columns], check_dtype=False
            )
        except AssertionError:
            problems.append(
                "states at the selected cutoff differ from the last lock cutoff"
            )
    for name in ("pregame_teams", "current_teams", "final_teams"):
        ratings = frames[name][["offense_rating", "defense_rating"]]
        variances = frames[name][["offense_variance", "defense_variance"]]
        if not ratings.map(lambda v: v == v and abs(v) != float("inf")).all().all():
            problems.append(f"{name}: non-finite ratings")
        if (variances <= 0).any().any():
            problems.append(f"{name}: non-positive variances")
    obs = frames["observations"]
    if len(obs) != 32 * summary["completed_games"]:
        problems.append("observation count is not 32 per completed game")
    return problems
