"""Versioned canonical-week policy assignments.

A policy file explicitly assigns ``canonical_week`` for the games whose
provider week must not be used directly (e.g. CFBD labels the 2026 August 29
opening slate as provider week 1). Every other game retains its provider
week. A schedule revision requires a new policy file version.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import pandas as pd
import yaml

KICKOFF_TOLERANCE = pd.Timedelta(hours=6)


@dataclass(frozen=True)
class WeekAssignment:
    game_id: int
    kickoff_utc: pd.Timestamp
    canonical_week: int


@dataclass(frozen=True)
class WeekPolicySpec:
    policy_version: str
    season: int
    assignments: tuple[WeekAssignment, ...]

    @property
    def by_game(self) -> dict[int, WeekAssignment]:
        return {assignment.game_id: assignment for assignment in self.assignments}


def load_week_policy_spec(path: str | Path) -> WeekPolicySpec:
    """Load and validate an explicit canonical-week policy file."""
    payload = yaml.safe_load(Path(path).read_text())
    if not isinstance(payload, Mapping):
        raise ValueError(f"Week policy file is not a mapping: {path}")
    policy_version = payload.get("policy_version")
    season = payload.get("season")
    if not policy_version or not isinstance(policy_version, str):
        raise ValueError("Week policy file requires a policy_version string")
    if not isinstance(season, int):
        raise ValueError("Week policy file requires an integer season")
    assignments: list[WeekAssignment] = []
    seen: set[int] = set()
    for entry in payload.get("assignments") or []:
        game_id = entry.get("game_id")
        kickoff = pd.to_datetime(entry.get("kickoff_utc"), utc=True, errors="raise")
        canonical_week = entry.get("canonical_week")
        if game_id is None or canonical_week is None:
            raise ValueError(f"Week policy assignment is incomplete: {entry!r}")
        game_id = int(game_id)
        if game_id in seen:
            raise ValueError(f"Duplicate week policy assignment for game {game_id}")
        seen.add(game_id)
        if int(canonical_week) < 0:
            raise ValueError(f"Week policy assignment has negative week: {entry!r}")
        assignments.append(
            WeekAssignment(
                game_id=game_id,
                kickoff_utc=kickoff,
                canonical_week=int(canonical_week),
            )
        )
    return WeekPolicySpec(
        policy_version=policy_version,
        season=season,
        assignments=tuple(assignments),
    )


def build_policy_rows(
    games: pd.DataFrame, spec: WeekPolicySpec, *, season: int
) -> pd.DataFrame:
    """Assign one canonical week per game from a provider-week schedule.

    ``games`` must be normalized provider-week rows (``season``, ``game_id``,
    ``provider_week``, ``kickoff_utc``) for exactly one season. Assignments
    are validated against the schedule by game ID and kickoff timestamp.
    """
    if spec.season != season:
        raise ValueError(
            f"Week policy {spec.policy_version} targets season {spec.season}, "
            f"not {season}"
        )
    schedule = games[games["season"].astype(int) == season]
    if schedule.empty:
        raise ValueError(f"No schedule rows found for season {season}")
    by_id: dict[int, Mapping[str, Any]] = {
        int(row.game_id): row for row in schedule.itertuples()
    }
    for assignment in spec.assignments:
        game = by_id.get(assignment.game_id)
        if game is None:
            raise ValueError(
                f"Week policy assignment references unknown game {assignment.game_id}"
            )
        scheduled = pd.to_datetime(game.kickoff_utc, utc=True)
        if abs(scheduled - assignment.kickoff_utc) > KICKOFF_TOLERANCE:
            raise ValueError(
                f"Week policy kickoff for game {assignment.game_id} is "
                f"{assignment.kickoff_utc.isoformat()} but schedule has "
                f"{scheduled.isoformat()}; create a new policy version instead"
            )
    overrides = {a.game_id: a.canonical_week for a in spec.assignments}
    rows: list[dict[str, Any]] = []
    for game in schedule.itertuples():
        provider_week = int(game.provider_week)
        rows.append(
            {
                "season": season,
                "game_id": int(game.game_id),
                "provider_week": provider_week,
                "canonical_week": overrides.get(int(game.game_id), provider_week),
                "kickoff_utc": pd.to_datetime(game.kickoff_utc, utc=True),
            }
        )
    return pd.DataFrame.from_records(rows)


def policy_config_sha(spec: WeekPolicySpec, *, season: int) -> str:
    payload = json.dumps(
        {
            "policy_version": spec.policy_version,
            "season": season,
            "assignments": [
                {
                    "game_id": a.game_id,
                    "kickoff_utc": a.kickoff_utc.isoformat(),
                    "canonical_week": a.canonical_week,
                }
                for a in sorted(spec.assignments, key=lambda item: item.game_id)
            ],
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()
