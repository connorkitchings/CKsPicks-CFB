"""Fail-closed eligibility decisions for preseason football context families."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from cks_picks_cfb.data.season_lineage import SeasonLineagePolicy

CONTEXT_ELIGIBILITY_VERSION = "successor_v2_preseason_context_eligibility_v1"
MARKET_TERMS = frozenset(
    {"market", "book", "bookmaker", "odds", "spread", "line", "price"}
)


@dataclass(frozen=True)
class ContextFamilyEvidence:
    """Evidence required before a context family can enter candidate selection."""

    family: str
    semantic_preseason: bool
    reconstructible_without_outcome_leakage: bool
    authentic_2026_pre_kickoff_capture: bool
    coverage_by_fold_season: Mapping[int, float]
    declared_columns: Sequence[str]


def _has_market_column(columns: Sequence[str]) -> bool:
    return any(
        term in str(column).casefold().replace("-", "_").split("_")
        for column in columns
        for term in MARKET_TERMS
    )


def evaluate_context_family(
    policy: SeasonLineagePolicy, evidence: ContextFamilyEvidence
) -> dict[str, object]:
    """Return a deterministic admitted/diagnostic-only context decision."""

    required_folds = set(policy.prior_selection_target_seasons) | {
        policy.prior_locked_season
    }
    unexpected = set(evidence.coverage_by_fold_season) - required_folds
    missing = required_folds - set(evidence.coverage_by_fold_season)
    coverage_checks = {
        season: float(evidence.coverage_by_fold_season.get(season, 0.0))
        >= policy.minimum_fbs_coverage_fraction
        for season in sorted(required_folds)
    }
    checks = {
        "semantic_preseason": evidence.semantic_preseason,
        "outcome_leakage_free": evidence.reconstructible_without_outcome_leakage,
        "coverage_all_required_folds": not missing and all(coverage_checks.values()),
        "authentic_2026_pre_kickoff_capture": evidence.authentic_2026_pre_kickoff_capture,
        "football_only": not _has_market_column(evidence.declared_columns),
        "no_unexpected_fold_coverage": not unexpected,
    }
    return {
        "contract_version": CONTEXT_ELIGIBILITY_VERSION,
        "family": evidence.family,
        "admitted": all(checks.values()),
        "diagnostic_only": not all(checks.values()),
        "checks": checks,
        "coverage_checks": coverage_checks,
        "missing_fold_seasons": sorted(missing),
        "unexpected_fold_seasons": sorted(unexpected),
    }
