"""Step 2 verification report ``season_verification_v2`` (owner: P3).

Check entry schema::

    {"passed": bool, "observed": {...}, "source": "projection" | "prepare"}

Report schema (see also :mod:`cks_picks_cfb.season.projection_common`)::

    {
      "schema_version": "season_verification_v2",
      "checks": {name: check_entry},   # keys == REQUIRED_PROJECTION_CHECKS
                                       #       | REQUIRED_PREPARE_CHECKS
      "projection_checks": {table: {"rows": int, "sha256": str}},
      "row_counts": {table: int},
    }
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

SCHEMA_VERSION = "season_verification_v2"

REQUIRED_PROJECTION_CHECKS: frozenset[str] = frozenset(
    {
        "tables_complete",
        "weeks_and_slate",
        "predictions_in_games",
        "prior_finals_complete",
        "grades_recomputed",
        "selection_matches_prediction",
        "market_links",
        "system_stats_match",
        "rating_lineage",
        "rating_snapshots",
        "stats_games",
        "completed_counts_regime",
        "matchup_publication",
        "venues_cover",
    }
)
REQUIRED_PREPARE_CHECKS: frozenset[str] = frozenset(
    {
        "required_prior_week_data",
        "score_reconciliation",
        "earlier_week_only",
        "fixed_model_no_refit",
        "no_market_in_features",
        "ratings_equal_features",
        "paired_predictions",
        "checksums_at_read",
    }
)


def derive_checks(
    projections: Mapping[str, list[dict]], manifest: Mapping[str, Any]
) -> dict[str, dict]:
    """Return ``{name: check_entry}`` for exactly ``REQUIRED_PROJECTION_CHECKS``."""
    raise NotImplementedError


def validate_report(
    report: Mapping[str, Any], *, projections: Mapping[str, list[dict]]
) -> None:
    """Raise ``ValueError`` unless ``report`` is a passing ``season_verification_v2``
    whose ``projection_checks``/``row_counts`` match ``projections``."""
    raise NotImplementedError
