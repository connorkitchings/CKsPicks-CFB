"""Stage: corrected measurements, replay states and selected-design ratings.

Runs the unchanged V5 measurement and adjustment code on the corrected Silver, with the
verified admitted scoring ledger injected (possessions stay in legacy form, so the PPP
denominator keeps its accepted population rules). The adjusted history (~26M rows) is
streamed: only row counts and digests are retained. Ratings are only the selected design
``ppp__rho_0_60__exposure``.
"""

from __future__ import annotations

import hashlib
import io
import json
from collections.abc import Iterator
from typing import Any

import pandas as pd

from cks_picks_cfb.rebuild import common, comparison, eligibility
from cks_picks_cfb.rebuild.errors import GateError
from cks_picks_cfb.rebuild.orchestrator import StageContext, StageOutput
from cks_picks_cfb.rebuild.silver import identity_of

PREFIX = "rebuild/6a/{run_id}/ratings/"
SELECTED_CANDIDATE = "ppp__rho_0_60__exposure"
FRAMES = (
    "observations",
    "coverage",
    "snapshots",
    "terminal",
    "priors",
    "rating_states",
    "team_states",
)
JSON_FILES = ("reconciliation.json", "history_evidence.json", "summary.json")
MEASUREMENTS_PER_TEAM_GAME = 8  # eight measurements, two roles, two teams per game


def _parquet(frame: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    frame.to_parquet(buffer)
    return buffer.getvalue()


def _partition_digest(frame: pd.DataFrame) -> str:
    hashed = pd.util.hash_pandas_object(frame.reset_index(drop=True), index=False)
    return hashlib.sha256(hashed.to_numpy().tobytes()).hexdigest()


class HistoryEvidence:
    """Counts and digests of the streamed adjusted history; the rows are not kept."""

    def __init__(self) -> None:
        self.partitions: list[dict[str, Any]] = []

    def add(self, partition: dict[str, Any], frame: pd.DataFrame) -> None:
        self.partitions.append(
            {
                "partition": {k: int(v) for k, v in partition.items()},
                "rows": int(len(frame)),
                "digest": _partition_digest(frame),
            }
        )

    def summary(self) -> dict[str, Any]:
        ordered = sorted(self.partitions, key=lambda p: sorted(p["partition"].items()))
        return {
            "partitions": len(ordered),
            "rows": int(sum(p["rows"] for p in ordered)),
            "digest": hashlib.sha256(
                json.dumps(ordered, sort_keys=True).encode()
            ).hexdigest(),
            "parts": ordered,
        }


def _outcomes(context: StageContext, storage, pin_file) -> pd.DataFrame:
    from cks_picks_cfb.data.lake import read_dataset

    return pd.concat(
        [
            read_dataset(
                storage,
                common.dataset_ref(pin_file["seasons"][str(s)]["game_outcomes"]),
            )
            for s in sorted(context.plan.seasons)
        ],
        ignore_index=True,
    )


def _comparison_frame(context: StageContext, key: str) -> pd.DataFrame:
    prefix = comparison.PREFIX.format(run_id=context.plan.run_id)
    return pd.read_parquet(
        io.BytesIO(
            context.read_artifact("step5_comparison", prefix + comparison.FILES[key])
        )
    )


def build(context: StageContext) -> StageOutput:
    from cks_picks_cfb.data.data_first_possession_v1 import build_population
    from cks_picks_cfb.ratings import possession_measurements as pm
    from cks_picks_cfb.ratings.possession_selected_design import compute_selected_design

    storage = common.preview_storage(context)
    pin_file = json.loads(context.read_input("phase2c_silver_parents"))
    population_raw = pd.read_parquet(
        io.BytesIO(
            context.read_artifact(
                "eligibility",
                eligibility.PREFIX.format(run_id=context.plan.run_id)
                + eligibility.POPULATION,
            )
        )
    )
    population = build_population(population_raw, scope="historical")
    outcomes = _outcomes(context, storage, pin_file)
    byplay = common.staged_silver(context, "byplay")
    possessions = _comparison_frame(context, "possessions")
    admitted = _comparison_frame(context, "admitted_events")

    result = pm.build_measurements(
        byplay=byplay,
        population=population,
        outcomes=outcomes,
        possessions=possessions,
        scoring_events=admitted,
        play_identity=identity_of(context),
    )
    snapshots: list[pd.DataFrame] = []
    terminal: list[pd.DataFrame] = []
    history = HistoryEvidence()

    def emit(name: str, partition: dict[str, Any], frame: pd.DataFrame) -> None:
        if name == "snapshots":
            snapshots.append(frame.copy())
        elif name == "terminal":
            terminal.append(frame.copy())
        elif name == "adjusted_history":
            history.add(partition, frame)  # streamed: digest only, never retained
        else:
            raise GateError(f"unexpected replay output {name}")

    replay_meta = pm.replay_partitions(
        population=population, observations=result.observations, emit=emit
    )
    snapshot_frame = pd.concat(snapshots, ignore_index=True)
    terminal_frame = pd.concat(terminal, ignore_index=True)
    design = compute_selected_design(
        population=population,
        observations=result.observations,
        snapshots=snapshot_frame,
        terminal=terminal_frame,
        candidate_id=SELECTED_CANDIDATE,
    )
    frames = {
        "observations": result.observations,
        "coverage": result.coverage,
        "snapshots": snapshot_frame,
        "terminal": terminal_frame,
        "priors": design.priors,
        "rating_states": design.rating_states,
        "team_states": design.team_states,
    }
    evidence = history.summary()
    summary = {
        "candidate_id": SELECTED_CANDIDATE,
        "rows": {name: int(len(frame)) for name, frame in frames.items()},
        "games": int(len(population)),
        "forecast_eligible": int(population["forecast_eligible"].sum()),
        "history_rows": evidence["rows"],
        "history_digest": evidence["digest"],
        "replay": {k: replay_meta[k] for k in sorted(replay_meta)},
        "ledger": {
            "possessions": int(len(possessions)),
            "scoring_events": int(len(admitted)),
        },
    }
    reconciliation = {
        str(key): value
        for key, value in sorted(result.final_reconciliation.items(), key=str)
    }
    prefix = PREFIX.format(run_id=context.plan.run_id)

    def artifacts() -> Iterator[tuple[str, bytes]]:
        for name in FRAMES:
            yield f"{prefix}{name}.parquet", _parquet(frames[name])
        yield (
            f"{prefix}reconciliation.json",
            json.dumps(reconciliation, sort_keys=True, default=str).encode(),
        )
        yield (
            f"{prefix}history_evidence.json",
            json.dumps(evidence, sort_keys=True).encode(),
        )
        yield (
            f"{prefix}summary.json",
            json.dumps(summary, indent=2, sort_keys=True, default=str).encode(),
        )

    return StageOutput(artifacts=artifacts(), metrics=summary["rows"])


def _read_frame(context: StageContext, name: str) -> pd.DataFrame:
    prefix = PREFIX.format(run_id=context.plan.run_id)
    return pd.read_parquet(
        io.BytesIO(context.read_artifact(context.stage.name, f"{prefix}{name}.parquet"))
    )


def independent_ppp_problems(
    observations: pd.DataFrame, possessions: pd.DataFrame, admitted: pd.DataFrame
) -> list[str]:
    """Recompute PPP and non-offense points from the verified ledger, not the producer.

    Denominator: legacy-eligible possessions of the offense; numerator: admitted eligible
    offensive points; a team-game with an unresolved scoring marker is unusable.
    """
    problems: list[str] = []
    key = ["season", "game_id"]
    count = (
        possessions[possessions["possession_eligible"].astype(bool)]
        .groupby([*key, "offense"])
        .size()
    )
    offense_points = (
        admitted[admitted["scoring_category"] == "eligible_regulation_offense"]
        .groupby([*key, "team"])["score_increment"]
        .sum()
    )
    other_points = (
        admitted[admitted["scoring_category"] == "regulation_non_offense"]
        .groupby([*key, "team"])["score_increment"]
        .sum()
    )
    unresolved = set(
        map(
            tuple,
            admitted.loc[admitted["scoring_category"] == "unresolved", [*key, "team"]]
            .drop_duplicates()
            .to_numpy(),
        )
    )
    offense = observations[observations["unit_role"] == "offense"]
    for measurement, points in (
        ("ppp", offense_points),
        ("non_offense_points", other_points),
    ):
        rows = offense[offense["measurement_id"] == measurement]
        for row in rows.itertuples(index=False):
            team_key = (int(row.season), int(row.game_id), row.team)
            den = float(count.get(team_key, 0))
            num = float(points.get(team_key, 0))
            held = team_key in unresolved
            usable = (den > 0 and not held) if measurement == "ppp" else (not held)
            observed = row.coverage_status == "observed"
            if observed != usable:
                problems.append(
                    f"{measurement} {team_key}: observed={observed}, expected {usable}"
                )
            elif observed and (
                abs(float(row.numerator) - num) > 1e-9
                or (measurement == "ppp" and abs(float(row.denominator) - den) > 1e-9)
            ):
                problems.append(
                    f"{measurement} {team_key}: numerator/denominator differ"
                )
            if len(problems) >= 20:
                return problems
    return problems


def verify(context: StageContext) -> list[str]:
    stage = context.stage.name
    prefix = PREFIX.format(run_id=context.plan.run_id)
    summary = json.loads(context.read_artifact(stage, prefix + "summary.json"))
    frames = {name: _read_frame(context, name) for name in FRAMES}
    problems: list[str] = []
    games = summary["games"]
    eligible = summary["forecast_eligible"]
    if summary["rows"] != {name: len(f) for name, f in frames.items()}:
        problems.append("summary row counts differ from the staged frames")
    if len(frames["observations"]) != MEASUREMENTS_PER_TEAM_GAME * 4 * games:
        problems.append(
            "observation count is not 8 measurements x 2 roles x 2 teams x games"
        )
    if (
        len(frames["team_states"]) != 2 * eligible
        or len(frames["rating_states"]) != 4 * eligible
    ):
        problems.append("rating or team state counts differ from the eligible games")
    for name in (
        "observations",
        "snapshots",
        "terminal",
        "rating_states",
        "team_states",
        "priors",
    ):
        seasons = {int(s) for s in frames[name]["season"]}
        if 2020 in seasons or 2026 in seasons:
            problems.append(f"{name} contains a forbidden season")
    for name in ("rating_states", "team_states", "priors"):
        if set(frames[name]["candidate_id"]) != {SELECTED_CANDIDATE}:
            problems.append(f"{name} is not only the selected design")
    states = frames["team_states"]
    for column in ("offense_rating", "defense_rating"):
        if not states[column].map(lambda v: v == v and abs(v) != float("inf")).all():
            problems.append(f"team_states.{column} has non-finite values")
    if (states[["offense_variance", "defense_variance"]] <= 0).any().any():
        problems.append("team state variances must be positive")
    if states.duplicated(["season", "game_id", "team"]).any():
        problems.append("duplicate team-state keys")
    evidence = json.loads(
        context.read_artifact(stage, prefix + "history_evidence.json")
    )
    if evidence["rows"] <= 0 or evidence["rows"] != summary["history_rows"]:
        problems.append("adjusted history evidence is empty or inconsistent")
    problems += independent_ppp_problems(
        frames["observations"],
        _comparison_frame(context, "possessions"),
        _comparison_frame(context, "admitted_events"),
    )
    return problems
