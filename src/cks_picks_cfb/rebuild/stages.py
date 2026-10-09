"""Stage implementations for the 6A rebuild; unimplemented stages fail closed."""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

from cks_picks_cfb.rebuild import (
    attribution,
    baseline,
    common,
    comparison,
    eligibility,
    forecast_refit,
    gold,
    measurements,
    parity,
    published_comparison,
    receipt,
    silver,
    silver_2026,
    states_2026,
)
from cks_picks_cfb.rebuild.errors import GateError
from cks_picks_cfb.rebuild.orchestrator import Stage, StageContext, StageOutput
from cks_picks_cfb.rebuild.plan import RebuildPlan
from cks_picks_cfb.rebuild.recon_stages import SIX_B_STAGE_BUILDERS

#: Stages whose inputs or pins are tied to the superseded sequence identity (legacy
#: ``season:game:drive:play`` ids, the pinned 5C decision hashes, v1 published artifacts).
#: They refuse a plan whose ``play_identity`` policy is ``byplay_v2`` instead of silently
#: mixing identities.
V1_PINNED_STAGES = frozenset(
    {
        "baseline_reproduction",
        "measurements_parity",
        "ratings_parity",
        "silver_2026",
        "states_2026",
        "attribution",
        "published_comparison",
        "receipt",
    }
)


def _v1_pinned(
    name: str, function: Callable[[StageContext], Any]
) -> Callable[[StageContext], Any]:
    @functools.wraps(function)
    def guarded(context: StageContext) -> Any:
        common.require_v1_identity(context, name)
        return function(context)

    return guarded


#: name -> (build, verify). Task 3 registers each stage as it is implemented.
_REGISTERED: dict[
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
    "attribution": (attribution.build, attribution.verify),
    "published_comparison": (published_comparison.build, published_comparison.verify),
    "receipt": (receipt.build, receipt.verify),
}
STAGE_BUILDERS: dict[
    str,
    tuple[Callable[[StageContext], StageOutput], Callable[[StageContext], list[str]]],
] = {
    name: (_v1_pinned(name, build), _v1_pinned(name, verify))
    if name in V1_PINNED_STAGES
    else (build, verify)
    for name, (build, verify) in _REGISTERED.items()
}


def _unimplemented(name: str) -> Callable[[StageContext], StageOutput]:
    def build(_context: StageContext) -> StageOutput:
        raise GateError(f"stage {name} is not implemented")

    return build


def get_stages(plan: RebuildPlan) -> list[Stage]:
    registry = (
        SIX_B_STAGE_BUILDERS if plan.namespace == "rebuild/6b/" else STAGE_BUILDERS
    )
    stages = []
    for stage_plan in plan.stages:
        build, verify = registry.get(
            stage_plan.name,
            (_unimplemented(stage_plan.name), lambda _c: ["stage not implemented"]),
        )
        stages.append(Stage(stage_plan, build, verify))
    return stages
