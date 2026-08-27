"""Central season-lineage policy for successor-v2 historical research.

The policy deliberately separates the 2019-to-2021 COVID gap from normal
one-year offseason transitions.  It is data/model research metadata, never a
V4 training policy or production routing input.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml


class SeasonLineageError(ValueError):
    """Raised when a successor-v2 season policy is malformed or misused."""


POLICY_VERSION = "rating_successor_v2_season_lineage_v1"


def _ints(value: Any, label: str) -> tuple[int, ...]:
    if not isinstance(value, list) or any(isinstance(item, bool) for item in value):
        raise SeasonLineageError(f"{label} must be a list of integer seasons")
    try:
        parsed = tuple(int(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise SeasonLineageError(f"{label} must be a list of integer seasons") from exc
    if len(set(parsed)) != len(parsed):
        raise SeasonLineageError(f"{label} may not contain duplicate seasons")
    return parsed


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SeasonLineageError(f"{label} must be a mapping")
    return value


@dataclass(frozen=True)
class PriorTransition:
    """One terminal-state carryover relationship."""

    source_season: int
    target_season: int
    annual_decay_steps: int
    normal: bool


@dataclass(frozen=True)
class SeasonLineagePolicy:
    """Validated historical/research season boundaries and temporal folds."""

    version: str
    historical_development_seasons: tuple[int, ...]
    protected_seasons: tuple[int, ...]
    forbidden_seasons: tuple[int, ...]
    seed_season: int
    normal_transition_targets: tuple[int, ...]
    gap_transition: PriorTransition
    prior_selection_target_seasons: tuple[int, ...]
    prior_locked_season: int
    update_selection_target_seasons: tuple[int, ...]
    update_locked_season: int
    minimum_fbs_coverage_fraction: float
    football_only: bool
    required_2026_authentic_capture: bool
    research_prefix: str

    @property
    def known_seasons(self) -> tuple[int, ...]:
        return self.historical_development_seasons + self.protected_seasons

    @property
    def normal_transitions(self) -> tuple[PriorTransition, ...]:
        return tuple(
            PriorTransition(
                source_season=target - 1,
                target_season=target,
                annual_decay_steps=1,
                normal=True,
            )
            for target in self.normal_transition_targets
        )

    def prior_transition_for(self, season: int) -> PriorTransition | None:
        if season == self.seed_season:
            return None
        if season == self.gap_transition.target_season:
            return self.gap_transition
        for transition in self.normal_transitions:
            if transition.target_season == season:
                return transition
        raise SeasonLineageError(f"Season {season} has no permitted prior transition")

    def is_historical(self, season: int) -> bool:
        return season in self.historical_development_seasons

    def assert_allowed(self, season: int) -> None:
        if season in self.forbidden_seasons:
            raise SeasonLineageError(f"Season {season} is forbidden")
        if season not in self.known_seasons:
            raise SeasonLineageError(f"Season {season} is outside the lineage policy")


def load_season_lineage_policy(path: str | Path) -> SeasonLineagePolicy:
    """Load the immutable successor-v2 season policy from YAML."""

    raw = yaml.safe_load(Path(path).read_text())
    root = _mapping(raw, "root")
    version = root.get("season_lineage_policy_version")
    if version != POLICY_VERSION:
        raise SeasonLineageError(f"Unsupported season lineage policy: {version!r}")

    seasons = _mapping(root.get("seasons"), "seasons")
    historical = _ints(seasons.get("historical_development"), "historical_development")
    protected = _ints(seasons.get("protected"), "protected")
    forbidden = _ints(seasons.get("forbidden"), "forbidden")
    if 2020 not in forbidden:
        raise SeasonLineageError("2020 must be forbidden")
    if set(historical) & (set(protected) | set(forbidden)) or set(protected) & set(
        forbidden
    ):
        raise SeasonLineageError("Season scopes must not overlap")
    expected_historical = (
        2015,
        2016,
        2017,
        2018,
        2019,
        2021,
        2022,
        2023,
        2024,
        2025,
    )
    if historical != expected_historical:
        raise SeasonLineageError(
            "successor-v2 historical development seasons must be 2015–2019 and 2021–2025"
        )
    if protected != (2026,):
        raise SeasonLineageError("successor-v2 protected season must be 2026")

    between = _mapping(root.get("between_season"), "between_season")
    seed = int(between.get("seed_season"))
    normal_targets = _ints(
        between.get("normal_transition_targets"), "normal_transition_targets"
    )
    expected_normal = (2016, 2017, 2018, 2019, 2022, 2023, 2024, 2025)
    if seed != 2015 or normal_targets != expected_normal:
        raise SeasonLineageError("Unexpected normal successor-v2 transition policy")
    gap = _mapping(between.get("gap_transition"), "gap_transition")
    gap_transition = PriorTransition(
        source_season=int(gap.get("source_season")),
        target_season=int(gap.get("target_season")),
        annual_decay_steps=int(gap.get("annual_decay_steps")),
        normal=False,
    )
    if gap_transition != PriorTransition(2019, 2021, 2, False):
        raise SeasonLineageError("2019-to-2021 must be the explicit two-year gap")

    prior_selection = _ints(
        between.get("selection_target_seasons"), "prior selection_target_seasons"
    )
    prior_locked = int(between.get("locked_season"))
    if prior_selection != (2018, 2019, 2022, 2023, 2024) or prior_locked != 2025:
        raise SeasonLineageError("Unexpected prior tournament fold policy")

    updates = _mapping(root.get("within_season"), "within_season")
    update_selection = _ints(
        updates.get("selection_target_seasons"), "update selection_target_seasons"
    )
    update_locked = int(updates.get("locked_season"))
    expected_update_selection = (2017, 2018, 2019, 2021, 2022, 2023, 2024)
    if update_selection != expected_update_selection or update_locked != 2025:
        raise SeasonLineageError("Unexpected update tournament fold policy")

    context = _mapping(root.get("context_admission"), "context_admission")
    coverage = float(context.get("minimum_fbs_coverage_fraction"))
    if not 0.0 < coverage <= 1.0:
        raise SeasonLineageError("minimum_fbs_coverage_fraction must be in (0, 1]")
    if context.get("football_only") is not True:
        raise SeasonLineageError("successor-v2 context must be football-only")
    if context.get("required_2026_authentic_capture") is not True:
        raise SeasonLineageError("2026 context must require authentic capture")
    prefix = root.get("research_prefix")
    if not isinstance(prefix, str) or not prefix:
        raise SeasonLineageError("research_prefix must be a nonempty string")

    return SeasonLineagePolicy(
        version=version,
        historical_development_seasons=historical,
        protected_seasons=protected,
        forbidden_seasons=forbidden,
        seed_season=seed,
        normal_transition_targets=normal_targets,
        gap_transition=gap_transition,
        prior_selection_target_seasons=prior_selection,
        prior_locked_season=prior_locked,
        update_selection_target_seasons=update_selection,
        update_locked_season=update_locked,
        minimum_fbs_coverage_fraction=coverage,
        football_only=True,
        required_2026_authentic_capture=True,
        research_prefix=prefix.rstrip("/"),
    )
