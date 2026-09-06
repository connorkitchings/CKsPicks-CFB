"""Pure contracts for data-first Phase 2 repair, capture, and eligibility."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from typing import Any, Callable, Iterable, Mapping, Sequence, TypeVar

import pandas as pd

DEVELOPMENT_SEASONS = (2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024, 2025)
FORBIDDEN_SEASONS = (2020,)
SEASON_TYPES = ("regular", "postseason")
PREGAME_FAMILIES = ("games", "returning_production", "recruiting", "coaching")
T = TypeVar("T")


@dataclass(frozen=True)
class CaptureRequest:
    provider: str
    entity: str
    endpoint: str
    parameters: Mapping[str, Any]

    @property
    def request_sha(self) -> str:
        return hashlib.sha256(
            json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


def historical_request_plan(
    schedules: pd.DataFrame,
    *,
    existing_request_shas: Iterable[str] = (),
) -> list[CaptureRequest]:
    """Plan provider requests; one returned row never counts as one API call."""
    required = {"season", "week", "season_type"}
    if missing := sorted(required - set(schedules)):
        raise ValueError(f"schedule is missing request dimensions: {missing}")
    frame = schedules.copy()
    frame["season"] = pd.to_numeric(frame["season"], errors="raise").astype(int)
    if frame["season"].isin(FORBIDDEN_SEASONS).any():
        raise ValueError("historical request plan rejects 2020")
    frame["season_type"] = frame["season_type"].astype(str).str.casefold()
    unknown = sorted(set(frame["season_type"]) - set(SEASON_TYPES))
    if unknown:
        raise ValueError(f"unsupported season types: {unknown}")
    requests: list[CaptureRequest] = []
    # Schedule requests are unconditional so an incomplete denominator cannot hide
    # an entirely absent season or postseason. Weekly endpoints are added only for
    # weeks actually established by the current denominator; rerunning after the
    # schedule capture expands the plan deterministically.
    for season in DEVELOPMENT_SEASONS:
        season_rows = frame[frame["season"].eq(season)]
        for season_type in SEASON_TYPES:
            requests.append(
                CaptureRequest(
                    "cfbd",
                    "games",
                    "GamesApi.get_games",
                    {
                        "year": season,
                        "season_type": season_type,
                        "classification": "fbs",
                    },
                )
            )
            typed = season_rows[season_rows["season_type"].eq(season_type)]
            if typed.empty:
                continue
            for week in sorted(
                pd.to_numeric(typed["week"], errors="raise").astype(int).unique()
            ):
                requests.extend(
                    [
                        CaptureRequest(
                            "cfbd",
                            "plays",
                            "PlaysApi.get_plays",
                            {
                                "year": season,
                                "week": int(week),
                                "season_type": season_type,
                                "classification": "fbs",
                            },
                        ),
                        CaptureRequest(
                            "cfbd",
                            "game_stats",
                            "GamesApi.get_game_team_stats",
                            {
                                "year": season,
                                "week": int(week),
                                "season_type": season_type,
                                "classification": "fbs",
                            },
                        ),
                    ]
                )
        requests.append(
            CaptureRequest("cfbd", "teams", "TeamsApi.get_teams", {"year": season})
        )
    existing = set(existing_request_shas)
    unique = {request.request_sha: request for request in requests}
    return [unique[key] for key in sorted(unique) if key not in existing]


def active_pregame_request_plan(season: int) -> list[CaptureRequest]:
    if season in FORBIDDEN_SEASONS:
        raise ValueError("pregame capture rejects 2020")
    requests = [
        CaptureRequest(
            "cfbd",
            "games",
            "GamesApi.get_games",
            {"year": season, "season_type": "both", "classification": "fbs"},
        ),
        CaptureRequest(
            "cfbd",
            "returning_production",
            "PlayersApi.get_returning_production",
            {"year": season},
        ),
        CaptureRequest("cfbd", "coaching", "CoachesApi.get_coaches", {"year": season}),
    ]
    requests.extend(
        CaptureRequest(
            "cfbd",
            "recruiting",
            "RecruitingApi.get_team_recruiting_rankings",
            {"year": year},
        )
        for year in range(season - 3, season + 1)
    )
    return requests


def execute_with_bounded_retries(
    operation: Callable[[], T],
    *,
    max_attempts: int,
    sleeper: Callable[[float], None] = time.sleep,
) -> tuple[T, int, list[dict[str, Any]]]:
    """Run one request with bounded retries and return its attempt evidence."""
    if not 1 <= max_attempts <= 5:
        raise ValueError("max_attempts must be between 1 and 5")
    errors: list[dict[str, Any]] = []
    for attempt in range(1, max_attempts + 1):
        try:
            return operation(), attempt, errors
        except Exception as exc:
            errors.append(
                {
                    "attempt": attempt,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[-2000:],
                }
            )
            if attempt < max_attempts:
                sleeper(min(2 ** (attempt - 1), 4))
    raise RuntimeError(f"request exhausted {max_attempts} attempts: {errors[-1]}")


def deduplicate_preseason_rows(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Collapse identical key duplicates and quarantine conflicting values."""
    keys = ["season", "team", "as_of"]
    if missing := sorted(set(keys) - set(frame)):
        raise ValueError(f"preseason inputs missing declared keys: {missing}")
    values = [column for column in frame if column not in keys]
    keep: list[pd.DataFrame] = []
    conflicts: list[pd.DataFrame] = []
    for _, group in frame.groupby(keys, dropna=False, sort=True):
        distinct = group.drop_duplicates(values if values else None)
        if len(distinct) == 1:
            keep.append(group.iloc[[0]])
        else:
            conflicts.append(group)
    clean = pd.concat(keep, ignore_index=True) if keep else frame.iloc[0:0].copy()
    quarantine = (
        pd.concat(conflicts, ignore_index=True) if conflicts else frame.iloc[0:0].copy()
    )
    return clean.sort_values(keys).reset_index(drop=True), quarantine.sort_values(
        keys
    ).reset_index(drop=True)


def coverage_gate(
    coverage: pd.DataFrame,
    *,
    fbs_fbs_threshold: float = 0.95,
    fbs_fcs_threshold: float = 0.90,
) -> dict[str, Any]:
    """Apply gates per season, season type, population, and stage."""
    required = {"season", "season_type", "population", "stage", "coverage_rate"}
    if missing := sorted(required - set(coverage)):
        raise ValueError(f"coverage report missing gate dimensions: {missing}")
    evaluated = coverage[coverage["population"].isin({"fbs_fbs", "fbs_fcs"})].copy()
    evaluated["threshold"] = evaluated["population"].map(
        {"fbs_fbs": fbs_fbs_threshold, "fbs_fcs": fbs_fcs_threshold}
    )
    evaluated["passed"] = evaluated["coverage_rate"] > evaluated["threshold"]
    failures = evaluated[~evaluated["passed"]]
    return {
        "passed": bool(not evaluated.empty and failures.empty),
        "evaluated_rows": int(len(evaluated)),
        "failed_rows": failures.to_dict("records"),
        "comparison": "strictly_greater_than",
        "thresholds": {"fbs_fbs": fbs_fbs_threshold, "fbs_fcs": fbs_fcs_threshold},
    }


def build_eligibility_manifest(
    *,
    audit_summary: Mapping[str, Any],
    dataset_rows: Sequence[Mapping[str, Any]],
    issues: Sequence[Mapping[str, Any]],
    coverage_result: Mapping[str, Any],
) -> dict[str, Any]:
    dataset_version_ids = {str(row["version_id"]) for row in dataset_rows}
    blocking_versions = {
        str(version)
        for issue in issues
        if issue.get("severity") in {"critical", "high"}
        for version in issue.get("affected_descendants", [])
    }
    global_blockers = [
        str(issue.get("issue_id") or issue.get("category") or "unknown")
        for issue in issues
        if issue.get("severity") in {"critical", "high"}
        and not (
            dataset_version_ids
            & {str(version) for version in issue.get("affected_descendants", [])}
        )
    ]
    inputs = []
    for row in dataset_rows:
        version_id = str(row["version_id"])
        inputs.append(
            {
                "dataset": row["dataset"],
                "version_id": version_id,
                "schema_version": row["schema_version"],
                "content_sha": row["content_sha"],
                "uri": row["uri"],
                "parent_versions": list(row.get("parent_versions") or []),
                "timing_class": row.get("timing_class", "unresolved"),
                "null_policy": row.get("null_policy", "preserve_with_reason"),
                "permitted_uses": (
                    []
                    if version_id in blocking_versions
                    else ["phase3_measurement_validation"]
                ),
                "eligible": version_id not in blocking_versions,
            }
        )
    admitted = [row for row in inputs if row["eligible"]]
    return {
        "schema_version": "data_first_phase2_eligibility_v1",
        "state": (
            "eligible"
            if admitted and coverage_result.get("passed") and not global_blockers
            else "blocked"
        ),
        "audit_run_id": audit_summary.get("run_id"),
        "development_seasons": list(DEVELOPMENT_SEASONS),
        "forbidden_seasons": list(FORBIDDEN_SEASONS),
        "populations": ["fbs_fbs", "fbs_fcs", "unresolved"],
        "coverage_gate": dict(coverage_result),
        "inputs": inputs,
        "phase3_input_version_ids": sorted(row["version_id"] for row in admitted),
        "global_blocking_issue_ids": sorted(global_blockers),
        "production_activation_authorized": False,
        "model_selection_authorized": False,
    }
