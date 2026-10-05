"""Stage implementations for the 6A rebuild; unimplemented stages fail closed."""

from __future__ import annotations

from collections.abc import Callable

from cks_picks_cfb.rebuild import (
    baseline,
    comparison,
    eligibility,
    forecast_refit,
    gold,
    measurements,
    parity,
    silver,
    silver_2026,
    states_2026,
)
from cks_picks_cfb.rebuild.errors import GateError
from cks_picks_cfb.rebuild.orchestrator import Stage, StageContext, StageOutput
from cks_picks_cfb.rebuild.plan import RebuildPlan

#: name -> (build, verify). Task 3 registers each stage as it is implemented.
STAGE_BUILDERS: dict[
    str,
    tuple[Callable[[StageContext], StageOutput], Callable[[StageContext], list[str]]],
] = {
    "baseline_reproduction": (baseline.reproduce, baseline.verify),
    "silver": (silver.build, silver.verify),
    "eligibility": (eligibility.build, eligibility.verify),
    "step5_comparison": (comparison.build, comparison.verify),
    "gold": (gold.build, gold.verify),
    "measurements_parity": (parity.build_measurements_parity, parity.verify),
    "ratings_parity": (parity.build_ratings_parity, parity.verify),
    "measurements_ratings": (measurements.build, measurements.verify),
    "offsets_refit": (forecast_refit.build, forecast_refit.verify),
    "silver_2026": (silver_2026.build, silver_2026.verify),
    "states_2026": (states_2026.build, states_2026.verify),
}


def _unimplemented(name: str) -> Callable[[StageContext], StageOutput]:
    def build(_context: StageContext) -> StageOutput:
        raise GateError(f"stage {name} is not implemented")

    return build


def get_stages(plan: RebuildPlan) -> list[Stage]:
    stages = []
    for stage_plan in plan.stages:
        build, verify = STAGE_BUILDERS.get(
            stage_plan.name,
            (_unimplemented(stage_plan.name), lambda _c: ["stage not implemented"]),
        )
        stages.append(Stage(stage_plan, build, verify))
    return stages
