"""Versioned metric registry for ``team_game_metrics_v1``.

Each entry fixes the numerator rule, denominator rule, eligible population, coverage
dependency, unit, aggregation and rank direction. A required input missing from a
population fails contract validation; no alternate formula silently replaces it.
Definitions preserve the existing website team-stat definitions (``data/team_stats.py``)
and the V5 possession definitions; they do not unify the two populations.

Populations (``docs/plans/2026-10-03/window2/data-contracts-and-certification.md``):

- ``P``: corrected eligible regulation scrimmage plays (the V5 filter minus kicking
  plays; no penalties, conversions, dead plays or garbage time).
- ``D``: eligible, unambiguous regulation possessions.
- ``O``: eligible drives with the first-down, inside-the-opponent-40 scoring-opportunity flag.
- ``Q``: admitted points assigned to eligible regulation offense.
- ``E``: provider PPA summed over the required play population, with complete coverage.
- ``N``: admitted regulation non-offense points.
- ``G``: the game itself (certified outcome).

Garbage-time eligibility is not recomputed from any R1 score envelope.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

REGISTRY_VERSION = "team_game_metrics_registry_v1"
COVERAGE_UNITS = ("plays", "possessions", "drives", "events", "games")
KINDS = ("count", "sum", "ratio")
AGGREGATIONS = ("sum", "weighted_ratio", "per_game")


@dataclass(frozen=True)
class MetricDef:
    metric: str
    definition_version: str
    population_id: str
    coverage_unit: str
    kind: str
    numerator: str
    denominator: str
    aggregation: str
    #: (offense higher is better, defense higher is better); None = not ranked.
    rank_higher_is_better: tuple[bool, bool] | None
    requires_ppa: bool = False
    #: Metrics this one is an alias of (e.g. ``epa_per_play`` for ``ppa_per_play``).
    alias_of: str | None = None

    def __post_init__(self) -> None:
        if self.coverage_unit not in COVERAGE_UNITS:
            raise ValueError(
                f"{self.metric}: unknown coverage unit {self.coverage_unit}"
            )
        if self.kind not in KINDS or self.aggregation not in AGGREGATIONS:
            raise ValueError(f"{self.metric}: unknown kind or aggregation")


def _m(
    metric, pop, unit, kind, num, den, agg, rank, ppa=False, alias=None
) -> MetricDef:
    return MetricDef(metric, "v1", pop, unit, kind, num, den, agg, rank, ppa, alias)


_UP = (True, False)  # offense higher is better, defense lower is better

METRICS: tuple[MetricDef, ...] = (
    _m(
        "eligible_possessions", "D", "possessions", "count", "count D", "1", "sum", None
    ),
    _m("offensive_possession_points", "Q", "possessions", "sum", "Q", "1", "sum", None),
    _m("ppp", "D", "possessions", "ratio", "Q", "count D", "weighted_ratio", _UP),
    _m("eligible_epa", "E", "plays", "sum", "E", "1", "sum", None, ppa=True),
    _m(
        "epa_per_possession",
        "D",
        "possessions",
        "ratio",
        "E",
        "count D",
        "weighted_ratio",
        _UP,
        ppa=True,
    ),
    _m("eligible_scrimmage_plays", "P", "plays", "count", "count P", "1", "sum", None),
    _m(
        "plays_per_possession",
        "D",
        "possessions",
        "ratio",
        "count P",
        "count D",
        "weighted_ratio",
        None,
    ),
    _m("non_offense_points", "N", "events", "sum", "N", "1", "sum", None),
    _m(
        "ppa_per_play",
        "P",
        "plays",
        "ratio",
        "E",
        "count P",
        "weighted_ratio",
        _UP,
        ppa=True,
    ),
    _m(
        "epa_per_play",
        "P",
        "plays",
        "ratio",
        "E",
        "count P",
        "weighted_ratio",
        _UP,
        ppa=True,
        alias="ppa_per_play",
    ),
    _m(
        "epa_pass",
        "P",
        "plays",
        "ratio",
        "PPA sum over eligible dropbacks",
        "count of eligible dropbacks",
        "weighted_ratio",
        _UP,
        ppa=True,
    ),
    _m(
        "epa_rush",
        "P",
        "plays",
        "ratio",
        "PPA sum over eligible rush attempts excluding dropbacks",
        "count of those attempts",
        "weighted_ratio",
        _UP,
        ppa=True,
    ),
    _m(
        "early_down_epa",
        "P",
        "plays",
        "ratio",
        "PPA sum over eligible downs 1-2",
        "count of eligible downs 1-2",
        "weighted_ratio",
        _UP,
        ppa=True,
    ),
    _m(
        "success_rate",
        "P",
        "plays",
        "ratio",
        "successful eligible plays",
        "eligible plays",
        "weighted_ratio",
        _UP,
    ),
    _m(
        "explosive_rate",
        "P",
        "plays",
        "ratio",
        "eligible plays gaining at least 20 yards",
        "eligible plays",
        "weighted_ratio",
        _UP,
    ),
    _m(
        "conv_rate_3rd_4th",
        "P",
        "plays",
        "ratio",
        "conversions on eligible third and fourth downs",
        "eligible third and fourth-down attempts",
        "weighted_ratio",
        _UP,
    ),
    _m(
        "turnover_rate",
        "P",
        "plays",
        "ratio",
        "turnovers on eligible plays",
        "eligible plays",
        "weighted_ratio",
        (False, True),
    ),
    _m(
        "scoring_opp_rate",
        "O",
        "drives",
        "ratio",
        "count O",
        "eligible drives",
        "weighted_ratio",
        _UP,
    ),
    _m(
        "pts_per_scoring_opp",
        "O",
        "drives",
        "ratio",
        "admitted offensive points on O",
        "count O",
        "weighted_ratio",
        _UP,
    ),
    _m(
        "avg_start_field_pos",
        "O",
        "drives",
        "ratio",
        "sum of (100 - start_yards_to_goal) over eligible drives",
        "eligible drives",
        "weighted_ratio",
        _UP,
    ),
    # Team scores: the certified final, so a reconciliation always has an explicit points
    # column to compare (known issue 7). Added to the contract on user instruction.
    _m(
        "points_scored",
        "G",
        "games",
        "sum",
        "certified final points scored",
        "1",
        "sum",
        None,
    ),
    # Per-game aggregates of the totals above, computed at aggregation time.
    _m(
        "possessions_per_game",
        "D",
        "games",
        "ratio",
        "eligible possessions",
        "included games",
        "per_game",
        None,
    ),
    _m(
        "non_offense_points_per_game",
        "N",
        "games",
        "ratio",
        "regulation non-offense points",
        "included games",
        "per_game",
        None,
    ),
)

BY_NAME: dict[str, MetricDef] = {m.metric: m for m in METRICS}
RANKED = {m.metric: m.rank_higher_is_better for m in METRICS if m.rank_higher_is_better}


def registry_payload() -> dict[str, Any]:
    return {"version": REGISTRY_VERSION, "metrics": [asdict(m) for m in METRICS]}


def registry_checksum() -> str:
    """SHA-256 of the canonical registry; bound into every dataset manifest."""
    return hashlib.sha256(
        json.dumps(registry_payload(), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def registry_problems() -> list[str]:
    """Integrity problems: duplicate names, dangling aliases, bad populations."""
    problems = []
    names = [m.metric for m in METRICS]
    problems += [
        f"duplicate metric {n}" for n in {n for n in names if names.count(n) > 1}
    ]
    for m in METRICS:
        if m.alias_of and m.alias_of not in BY_NAME:
            problems.append(f"{m.metric}: alias target {m.alias_of} missing")
        if m.population_id not in {"P", "D", "O", "Q", "E", "N", "G"}:
            problems.append(f"{m.metric}: unknown population {m.population_id}")
    return problems
