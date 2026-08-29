"""Successor-v2 historical ref-set and coverage certification contracts.

These helpers deliberately work from immutable refs and already-materialized
coverage evidence.  They never fetch data or infer coverage from a future
season, which makes the resulting report safe to persist under the isolated
successor-v2 research prefix.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from cks_picks_cfb.data.lake import DatasetRef
from cks_picks_cfb.data.season_lineage import SeasonLineagePolicy

HISTORY_REF_SET_VERSION = "expanded_rating_history_ref_set_v1"
HISTORY_COVERAGE_REPORT_VERSION = "expanded_rating_history_coverage_v1"
DERIVED_REF_SET_VERSION = "successor-history-derived-ref-set-v2"
REQUIRED_DATASETS = (
    "games",
    "plays",
    "team_game_stats",
    "reconciled_team_game",
    "teams",
    "venues",
)
R1_REQUIRED_DATASETS = (
    "games",
    "game_outcomes",
    "plays",
    "team_game_stats",
    "teams",
    "venues",
    "byplay",
    "drives",
    "reconciled_team_game",
    "source_reconciliation",
)


class SuccessorHistoryError(ValueError):
    """Raised when expanded-history evidence is incomplete or inconsistent."""


def _canonical_sha(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class SeasonCoverageEvidence:
    """Precomputed, auditable coverage counts for one historical season."""

    season: int
    completed_game_count: int
    completed_games_with_plays: int
    score_reconciled_game_count: int
    representative_terminal_team_count: int
    representative_team_count: int
    stable_schema: bool

    def validate(self, policy: SeasonLineagePolicy) -> None:
        policy.assert_allowed(self.season)
        if not policy.is_historical(self.season):
            raise SuccessorHistoryError(
                f"Coverage evidence season {self.season} is not historical development"
            )
        values = (
            self.completed_game_count,
            self.completed_games_with_plays,
            self.score_reconciled_game_count,
            self.representative_terminal_team_count,
            self.representative_team_count,
        )
        if any(value < 0 for value in values):
            raise SuccessorHistoryError("Coverage counts may not be negative")
        if self.completed_games_with_plays > self.completed_game_count:
            raise SuccessorHistoryError("Play-covered games exceed completed games")
        if self.score_reconciled_game_count > self.completed_game_count:
            raise SuccessorHistoryError("Reconciled games exceed completed games")
        if self.representative_terminal_team_count > self.representative_team_count:
            raise SuccessorHistoryError("Terminal teams exceed representative teams")


def _fraction(numerator: int, denominator: int) -> float:
    return float(numerator / denominator) if denominator else 0.0


def coverage_report(
    policy: SeasonLineagePolicy,
    evidence: Sequence[SeasonCoverageEvidence],
    *,
    minimum_score_reconciliation_fraction: float = 0.94,
) -> dict[str, Any]:
    """Return a deterministic eligibility report for the expanded corpus."""

    if not 0.0 < minimum_score_reconciliation_fraction <= 1.0:
        raise SuccessorHistoryError("Score reconciliation threshold must be in (0, 1]")
    by_season = {item.season: item for item in evidence}
    if len(by_season) != len(evidence):
        raise SuccessorHistoryError("Coverage evidence may contain each season once")
    forbidden = set(by_season) & set(policy.forbidden_seasons)
    if forbidden:
        raise SuccessorHistoryError(
            f"Coverage evidence includes forbidden seasons {sorted(forbidden)}"
        )
    unknown = set(by_season) - set(policy.historical_development_seasons)
    if unknown:
        raise SuccessorHistoryError(
            f"Coverage evidence includes unsupported seasons {sorted(unknown)}"
        )

    seasons: list[dict[str, Any]] = []
    eligible_legacy: list[int] = []
    for season in policy.historical_development_seasons:
        item = by_season.get(season)
        if item is None:
            seasons.append({"season": season, "present": False, "eligible": False})
            continue
        item.validate(policy)
        play_fraction = _fraction(
            item.completed_games_with_plays, item.completed_game_count
        )
        reconciliation_fraction = _fraction(
            item.score_reconciled_game_count, item.completed_game_count
        )
        terminal_fraction = _fraction(
            item.representative_terminal_team_count,
            item.representative_team_count,
        )
        checks = {
            "completed_game_play_coverage": play_fraction
            >= policy.minimum_fbs_coverage_fraction,
            "score_stream_reconciliation": reconciliation_fraction
            >= minimum_score_reconciliation_fraction,
            "representative_terminal_team_coverage": terminal_fraction
            >= policy.minimum_fbs_coverage_fraction,
            "stable_schema": bool(item.stable_schema),
            "zero_2020_lineage": season != 2020,
        }
        eligible = all(checks.values())
        if 2015 <= season <= 2019 and eligible:
            eligible_legacy.append(season)
        seasons.append(
            {
                "season": season,
                "present": True,
                "eligible": eligible,
                "checks": checks,
                "completed_game_count": item.completed_game_count,
                "play_coverage_fraction": play_fraction,
                "score_reconciliation_fraction": reconciliation_fraction,
                "terminal_team_coverage_fraction": terminal_fraction,
            }
        )
    return {
        "contract_version": HISTORY_COVERAGE_REPORT_VERSION,
        "season_lineage_policy_version": policy.version,
        "minimum_fbs_coverage_fraction": policy.minimum_fbs_coverage_fraction,
        "minimum_score_reconciliation_fraction": minimum_score_reconciliation_fraction,
        "seasons": seasons,
        "eligible_2015_2019_seasons": eligible_legacy,
        "at_least_three_legacy_seasons_eligible": len(eligible_legacy) >= 3,
        "tournaments_permitted": len(eligible_legacy) >= 3
        and all(item.get("eligible", False) for item in seasons),
    }


def expanded_history_ref_set(
    policy: SeasonLineagePolicy,
    refs: Mapping[tuple[int, str], DatasetRef],
) -> dict[str, Any]:
    """Build the checksummed immutable ref-set payload from exact dataset refs."""

    expected = {
        (season, dataset)
        for season in policy.historical_development_seasons
        for dataset in REQUIRED_DATASETS
    }
    actual = set(refs)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        raise SuccessorHistoryError(
            f"Expanded history refs differ from policy; missing={missing}, extra={extra}"
        )
    entries = []
    for season, dataset in sorted(refs):
        policy.assert_allowed(season)
        ref = refs[(season, dataset)]
        if not ref.content_sha or not ref.uri or not ref.version_id:
            raise SuccessorHistoryError(f"Invalid immutable ref for {season}/{dataset}")
        entries.append({"season": season, "dataset": dataset, **asdict(ref)})
    payload = {
        "contract_version": HISTORY_REF_SET_VERSION,
        "season_lineage_policy_version": policy.version,
        "research_prefix": policy.research_prefix,
        "entries": entries,
    }
    return {**payload, "ref_set_sha256": _canonical_sha(payload)}


def derived_history_ref_set(
    policy: SeasonLineagePolicy,
    refs: Mapping[tuple[int, str], DatasetRef],
    *,
    source_set_uri: str,
    source_set_sha256: str,
    identity: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind every R1 Silver parent and output to its closed source set."""

    expected = {
        (season, dataset)
        for season in policy.historical_development_seasons
        for dataset in R1_REQUIRED_DATASETS
    }
    actual = set(refs)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        raise SuccessorHistoryError(
            f"R1 derived refs differ from policy; missing={missing}, extra={extra}"
        )
    entries = []
    for season, dataset in sorted(refs):
        policy.assert_allowed(season)
        ref = refs[(season, dataset)]
        if not ref.content_sha or not ref.uri or not ref.version_id:
            raise SuccessorHistoryError(f"Invalid immutable ref for {season}/{dataset}")
        entries.append({"season": season, "dataset": dataset, **asdict(ref)})
    payload = {
        "contract_version": DERIVED_REF_SET_VERSION,
        "state": "complete",
        "season_lineage_policy_version": policy.version,
        "research_prefix": policy.research_prefix,
        "source_set_uri": source_set_uri,
        "source_set_sha256": source_set_sha256,
        "identity": dict(identity),
        "entries": entries,
    }
    return {**payload, "ref_set_sha256": _canonical_sha(payload)}


def derived_history_dataset_refs(
    payload: Mapping[str, Any],
) -> dict[tuple[int, str], DatasetRef]:
    """Parse derived-ref-set entries into season-scoped immutable dataset refs.

    Entries carry a ``season`` scope field alongside the dataset-ref fields;
    callers must not pass the scope field through to ``DatasetRef``.
    """

    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise SuccessorHistoryError("R1 derived-ref set entries are invalid")
    refs: dict[tuple[int, str], DatasetRef] = {}
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise SuccessorHistoryError("R1 derived-ref set entries are invalid")
        try:
            season = int(entry["season"])
            ref = DatasetRef(
                dataset=str(entry["dataset"]),
                version_id=str(entry["version_id"]),
                schema_version=str(entry["schema_version"]),
                content_sha=str(entry["content_sha"]),
                uri=str(entry["uri"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SuccessorHistoryError(
                "R1 derived-ref set entry lacks immutable dataset fields"
            ) from exc
        refs[(season, ref.dataset)] = ref
    return refs
