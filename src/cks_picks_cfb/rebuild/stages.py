"""Stage implementations for the 6A rebuild; unimplemented stages fail closed."""

from __future__ import annotations

from collections.abc import Callable

from cks_picks_cfb.rebuild import baseline
from cks_picks_cfb.rebuild.errors import GateError
from cks_picks_cfb.rebuild.orchestrator import Stage, StageContext, StageOutput
from cks_picks_cfb.rebuild.plan import RebuildPlan

#: name -> (build, verify). Task 3 registers each stage as it is implemented.
STAGE_BUILDERS: dict[
    str,
    tuple[Callable[[StageContext], StageOutput], Callable[[StageContext], list[str]]],
] = {"baseline_reproduction": (baseline.reproduce, baseline.verify)}


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
