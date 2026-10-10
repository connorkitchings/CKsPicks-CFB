"""Load certified final scores into ``game_results`` without grading anything.

A display-only run (for example Week 6) never produces a scored artifact, so
``score_to_db`` never writes its ``game_results`` rows and the grades-only
backfill finds no finals. This module plans and applies a scores-only load from
certified Silver ``game_outcomes``: it inserts missing rows, leaves matching
rows alone and refuses to change a stored score.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

import pandas as pd

INSERT_FINAL_SQL = """
INSERT INTO game_results (
    game_id, home_points, away_points, completion_state, scored_at
) VALUES (
    %(game_id)s, %(home_points)s, %(away_points)s, 'completed', NOW()
)
ON CONFLICT (game_id) DO NOTHING
"""

EXISTING_RESULTS_SQL = """
SELECT g.game_id, gr.home_points, gr.away_points, gr.completion_state
FROM games g
LEFT JOIN game_results gr ON gr.game_id = g.game_id
WHERE g.season = %(season)s AND g.week = %(week)s
"""


class GameFinalsError(RuntimeError):
    """The certified finals cannot be loaded as requested."""


@dataclass(frozen=True)
class FinalsPlan:
    season: int
    week: int
    inserts: list[dict[str, int]] = field(default_factory=list)
    unchanged: list[int] = field(default_factory=list)
    not_final: list[int] = field(default_factory=list)
    missing_outcome: list[int] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "season": self.season,
            "week": self.week,
            "inserts": len(self.inserts),
            "unchanged": len(self.unchanged),
            "not_final": sorted(self.not_final),
            "missing_outcome": sorted(self.missing_outcome),
            "conflicts": len(self.conflicts),
        }


def plan_finals(
    outcomes: pd.DataFrame,
    existing: Iterable[Mapping[str, Any]],
    *,
    season: int,
    week: int,
) -> FinalsPlan:
    """Compare certified outcomes with stored results for one served week.

    ``existing`` holds one row per scheduled game in the week (``game_id`` plus
    stored ``home_points``/``away_points``/``completion_state``, null when no
    result row exists).
    """
    needed = {"season", "game_id", "completed", "home_points", "away_points"}
    if not needed.issubset(outcomes.columns):
        raise GameFinalsError(
            f"game_outcomes lacks required columns: {sorted(needed - set(outcomes.columns))}"
        )
    scoped = outcomes.loc[outcomes["season"].eq(season)]
    if scoped["game_id"].duplicated().any():
        raise GameFinalsError("game_outcomes has duplicate game_id rows")
    by_game = {int(row.game_id): row for row in scoped.itertuples(index=False)}

    inserts: list[dict[str, int]] = []
    unchanged: list[int] = []
    not_final: list[int] = []
    missing: list[int] = []
    conflicts: list[dict[str, Any]] = []
    for stored in existing:
        game_id = int(stored["game_id"])
        outcome = by_game.get(game_id)
        if outcome is None:
            missing.append(game_id)
            continue
        final = (
            bool(outcome.completed)
            and not pd.isna(outcome.home_points)
            and not pd.isna(outcome.away_points)
        )
        if not final:
            not_final.append(game_id)
            continue
        home, away = int(outcome.home_points), int(outcome.away_points)
        stored_home, stored_away = stored.get("home_points"), stored.get("away_points")
        if stored_home is None and stored_away is None:
            inserts.append(
                {"game_id": game_id, "home_points": home, "away_points": away}
            )
        elif (int(stored_home), int(stored_away)) == (home, away):
            unchanged.append(game_id)
        else:
            conflicts.append(
                {
                    "game_id": game_id,
                    "stored": [stored_home, stored_away],
                    "certified": [home, away],
                }
            )
    return FinalsPlan(
        season=season,
        week=week,
        inserts=inserts,
        unchanged=unchanged,
        not_final=not_final,
        missing_outcome=missing,
        conflicts=conflicts,
    )


def fetch_existing(cur: Any, *, season: int, week: int) -> list[dict[str, Any]]:
    cur.execute(EXISTING_RESULTS_SQL, {"season": season, "week": week})
    return [
        {
            "game_id": row[0],
            "home_points": row[1],
            "away_points": row[2],
            "completion_state": row[3],
        }
        for row in cur.fetchall()
    ]


def apply_finals(cur: Any, plan: FinalsPlan) -> int:
    """Insert the planned rows; a conflicting stored score blocks the whole load."""
    if plan.conflicts:
        raise GameFinalsError(
            f"stored scores differ from certified finals for {len(plan.conflicts)} games"
        )
    written = 0
    for row in plan.inserts:
        cur.execute(INSERT_FINAL_SQL, row)
        written += cur.rowcount
    return written
