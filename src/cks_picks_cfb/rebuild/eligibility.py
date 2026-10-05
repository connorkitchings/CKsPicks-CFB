"""Stage 3: rebuild the game population and eligibility from the corrected Silver.

Uses the same pure reconciliation function as the Step 5 chain
(``reconcile_population``) on the pinned FBS-involved schedule, pinned outcomes, the
rebuilt source reconciliation and the provider-declared play omissions. Counts are
reported, then checked by ``build_population``; parity with the legacy population is the
job of ``step5_comparison``.
"""

from __future__ import annotations

import io
import json
from collections.abc import Iterator
from typing import Any

import pandas as pd

from cks_picks_cfb.rebuild import common
from cks_picks_cfb.rebuild.errors import GateError
from cks_picks_cfb.rebuild.orchestrator import StageContext, StageOutput
from cks_picks_cfb.rebuild.plan import HISTORICAL_SEASONS

PREFIX = "rebuild/6a/{run_id}/eligibility/"
POPULATION = "population_raw.parquet"
ISSUES = "population_issues.parquet"
SUMMARY = "summary.json"


def _parquet(frame: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    frame.to_parquet(buffer)
    return buffer.getvalue()


def summarize(population: pd.DataFrame) -> dict[str, Any]:
    return {
        "games": int(len(population)),
        "forecast_eligible": int(population["forecast_eligible"].sum()),
        "measurement_usable": int(population["measurement_usable"].sum()),
        "by_season": {
            str(season): int(count)
            for season, count in population.groupby("season").size().items()
        },
        "dispositions": {
            str(k): int(v) for k, v in population["disposition"].value_counts().items()
        },
    }


def build(context: StageContext) -> StageOutput:
    from cks_picks_cfb.data.data_first_possession_v1 import build_population
    from cks_picks_cfb.data.data_first_repair_v2 import reconcile_population
    from cks_picks_cfb.data.lake import read_dataset

    storage = common.preview_storage(context)
    pin_file = json.loads(context.read_input("phase2c_silver_parents"))
    source_set = json.loads(context.read_input("r1_source_set"))
    seasons = sorted(context.plan.seasons)
    if set(seasons) != set(HISTORICAL_SEASONS):
        raise GateError("eligibility seasons must be exactly 2015-2019 and 2021-2025")
    schedule = pd.concat(
        [
            read_dataset(
                storage, common.pinned_parent(pin_file, s, "fbs_involved_games")
            )
            for s in seasons
        ],
        ignore_index=True,
    )
    outcomes = pd.concat(
        [
            read_dataset(
                storage,
                common.dataset_ref(pin_file["seasons"][str(s)]["game_outcomes"]),
            )
            for s in seasons
        ],
        ignore_index=True,
    )
    reconciliation = common.staged_silver(context, "source_reconciliation")
    declared = {
        (season, game_id)
        for season in seasons
        for game_id in common.declared_missing_ids(storage, source_set, season)
    }
    keys = schedule[["season", "game_id"]].drop_duplicates()
    observed = keys[
        ~keys.apply(lambda r: (int(r.season), int(r.game_id)) in declared, axis=1)
    ]
    population, issues = reconcile_population(
        schedule=schedule,
        outcomes=outcomes,
        observed_games=observed,
        reconciliation=reconciliation,
        omissions={"plays": [{"season": s, "game_id": g} for s, g in sorted(declared)]},
        scope="historical",
    )
    build_population(population, scope="historical")  # hard count and season checks
    summary = {
        **summarize(population),
        "declared_missing": len(declared),
        "declared_missing_by_season": {
            str(s): sum(1 for season, _ in declared if season == s) for s in seasons
        },
    }
    prefix = PREFIX.format(run_id=context.plan.run_id)

    def artifacts() -> Iterator[tuple[str, bytes]]:
        yield prefix + POPULATION, _parquet(population)
        yield prefix + ISSUES, _parquet(issues)
        yield prefix + SUMMARY, json.dumps(summary, indent=2, sort_keys=True).encode()

    return StageOutput(artifacts=artifacts(), metrics=summary)


def verify(context: StageContext) -> list[str]:
    """Recompute counts from the staged population and cross-check the Silver stage."""
    stage = context.stage.name
    prefix = PREFIX.format(run_id=context.plan.run_id)
    population = pd.read_parquet(
        io.BytesIO(context.read_artifact(stage, prefix + POPULATION))
    )
    summary = json.loads(context.read_artifact(stage, prefix + SUMMARY))
    problems: list[str] = []
    if summarize(population) != {
        k: summary[k]
        for k in (
            "games",
            "forecast_eligible",
            "measurement_usable",
            "by_season",
            "dispositions",
        )
    }:
        problems.append("summary differs from the staged population")
    if sorted(population["season"].unique()) != sorted(HISTORICAL_SEASONS):
        problems.append("population seasons are not exactly 2015-2019 and 2021-2025")
    if population.duplicated(["season", "game_id"]).any():
        problems.append("duplicate season/game keys")
    if (population["season"] == 2020).any():
        problems.append("2020 rows present")
    unusable = population[~population["measurement_usable"].astype(bool)]
    if len(unusable) != summary["declared_missing"]:
        problems.append("measurement-unusable games differ from declared omissions")
    silver = common.silver_summary(context)
    for item in silver["seasons"]:
        season = item["season"]
        if item["games"] != summary["by_season"].get(str(season)):
            problems.append(f"{season}: population games differ from the silver stage")
        if (
            item["declared_missing_games"]
            != summary["declared_missing_by_season"][str(season)]
        ):
            problems.append(
                f"{season}: declared omissions differ from the silver stage"
            )
    return problems
