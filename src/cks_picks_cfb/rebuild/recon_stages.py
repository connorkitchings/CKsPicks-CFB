"""Stage implementations for Stage 6B reconstruction stages."""

from __future__ import annotations

from collections.abc import Callable

from cks_picks_cfb.rebuild import (
    recon_comparison,
    recon_forecast,
    recon_foundation,
    recon_grades,
    recon_markets,
    recon_offsets,
    recon_receipt,
    recon_states,
)
from cks_picks_cfb.rebuild.orchestrator import StageContext, StageOutput
from cks_picks_cfb.rebuild.recon_common import verify_rederived

SIX_B_STAGE_BUILDERS: dict[
    str,
    tuple[Callable[[StageContext], StageOutput], Callable[[StageContext], list[str]]],
] = {
    "foundation": (
        recon_foundation.build_foundation,
        recon_foundation.verify_foundation,
    ),
    "scoring_events_2026": (
        recon_foundation.build_scoring_events_2026,
        recon_foundation.verify_scoring_events_2026,
    ),
    "offsets_2026": (
        recon_offsets.build_offsets_2026,
        recon_offsets.verify_offsets_2026,
    ),
    "states_at_cutoff": (
        recon_states.build_states_at_cutoff,
        recon_states.verify_states_at_cutoff,
    ),
    "application_frames": (
        recon_forecast.build_application_frames,
        recon_forecast.verify_application_frames,
    ),
    "predictions": (
        recon_forecast.build_predictions,
        recon_forecast.verify_predictions,
    ),
    "markets": (
        recon_markets.build_markets,
        recon_markets.verify_markets,
    ),
    "finals": (
        recon_markets.build_finals,
        recon_markets.verify_finals,
    ),
    "old_grade_reproduction": (
        recon_grades.build_old_grade_reproduction,
        recon_grades.verify_old_grade_reproduction,
    ),
    "retrospective_grades": (
        recon_grades.build_retrospective_grades,
        recon_grades.verify_retrospective_grades,
    ),
    "comparison": (
        recon_comparison.build_comparison,
        recon_comparison.verify_comparison,
    ),
    "receipt": (
        recon_receipt.build_receipt,
        recon_receipt.verify_receipt,
    ),
}


def _persisted_verifier(build, verify):
    def persisted(context):
        return verify_rederived(context, build, verify)

    return persisted


SIX_B_STAGE_BUILDERS = {
    name: (build, _persisted_verifier(build, verify))
    for name, (build, verify) in SIX_B_STAGE_BUILDERS.items()
}

__all__ = ["SIX_B_STAGE_BUILDERS"]
