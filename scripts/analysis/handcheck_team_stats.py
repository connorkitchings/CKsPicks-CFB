#!/usr/bin/env python3
"""Independent recompute of three team-stats drive metrics from raw plays.

Recomputes ``avg_start_field_pos``, ``scoring_opp_rate`` and
``pts_per_scoring_opp`` for chosen teams straight from Silver ``byplay`` using the
written definitions, without calling ``data/team_stats.py``, ``aggregate_drives``
or ``true_drive_points``, and compares them with the published values.

Definitions used (see ``data/play_filters.py`` and the team-stats docs):

* A *drive* is a ``(game_id, drive_number, offense, defense)`` group, counted only
  when it has at least one eligible scrimmage play (regulation, not special
  teams, penalty, two-point try, garbage time, dead play or kicking play).
* Drive start = ``yards_to_goal`` of the group's first row in
  (``quarter``, ``play_number``) order; field position = ``100 - start``.
* A scoring-opportunity drive has at least one row with ``eckel == 1``.
* ``pts_per_scoring_opp`` = mean points of scoring-opportunity drives, where a
  drive's points are the offense's running score at its last row minus its score
  on the row before the drive (0 at game start). A game is skipped for the
  offense when that team's running score ever decreases.

Read-only. Published values come from ``--published`` (csv/parquet with columns
``team, role, metric, value``) or ``--neon-preview`` (PREVIEW_DATABASE_URL,
read-only transaction). Exit status is 0 only if every compared value is within
``--tolerance`` (default 1e-4), so any difference must be explained.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass

import numpy as np
import pandas as pd

METRICS = ("avg_start_field_pos", "scoring_opp_rate", "pts_per_scoring_opp")
_DEAD_MARKERS = ("timeout", "end of", "period end", "game end", "delay of game")
_KICK_PREFIXES = ("Punt", "Kickoff", "Field Goal", "Extra Point")
REQUIRED = (
    "game_id",
    "week",
    "drive_number",
    "play_number",
    "quarter",
    "offense",
    "defense",
    "offense_score",
    "defense_score",
    "yards_to_goal",
    "eckel",
    "st",
    "penalty",
    "twopoint",
    "garbage",
    "play_type",
)


def eligible_scrimmage(plays: pd.DataFrame) -> pd.Series:
    """Eligible scrimmage plays, written from the documented rules."""
    quarter = pd.to_numeric(plays["quarter"], errors="coerce")
    regulation = quarter.between(1, 4) & (quarter == quarter.round())
    flags_clear = (
        (pd.to_numeric(plays["st"], errors="coerce") == 0)
        & (pd.to_numeric(plays["penalty"], errors="coerce") == 0)
        & (pd.to_numeric(plays["twopoint"], errors="coerce") == 0)
        & (pd.to_numeric(plays["garbage"], errors="coerce") == 0)
    )
    play_type = plays["play_type"].astype(str)
    dead = play_type.str.casefold().apply(
        lambda text: any(marker in text for marker in _DEAD_MARKERS)
    )
    kicking = (play_type == "Punt Return") | play_type.str.startswith(_KICK_PREFIXES)
    return regulation & flags_clear & ~dead & ~kicking


def _drive_points(game: pd.DataFrame) -> dict[tuple[int, str], float | None]:
    """Points per (drive_number, offense) from running-score differences.

    ``None`` when that offense's running score decreases anywhere in the game.
    """
    points: dict[tuple[int, str], float | None] = {}
    for team in set(game["offense"]):
        mine = game[(game["offense"] == team) | (game["defense"] == team)]
        score = np.where(
            mine["offense"] == team, mine["offense_score"], mine["defense_score"]
        ).astype(float)
        clean = bool((np.diff(score) >= 0).all()) if len(score) > 1 else True
        position = {index: pos for pos, index in enumerate(mine.index)}
        for (drive, off), rows in game[game["offense"] == team].groupby(
            ["drive_number", "offense"], sort=False
        ):
            last = position[rows.index[-1]]
            first = position[rows.index[0]]
            before = score[first - 1] if first > 0 else 0.0
            points[(int(drive), str(off))] = (
                float(score[last] - before) if clean else None
            )
    return points


def build_drives(plays: pd.DataFrame) -> pd.DataFrame:
    """One row per drive group with start, opportunity flag and points."""
    missing = sorted(set(REQUIRED) - set(plays.columns))
    if missing:
        raise ValueError(f"byplay missing columns: {missing}")
    plays = plays.copy()
    plays["_eligible"] = eligible_scrimmage(plays)
    plays = plays.sort_values(
        ["game_id", "drive_number", "quarter", "play_number"], kind="mergesort"
    )
    records = []
    for game_id, game in plays.groupby("game_id", sort=False):
        points = _drive_points(game)
        for (drive, off, de), rows in game.groupby(
            ["drive_number", "offense", "defense"], sort=False
        ):
            if not bool(rows["_eligible"].any()):
                continue
            records.append(
                {
                    "game_id": int(game_id),
                    "drive_number": int(drive),
                    "offense": str(off),
                    "defense": str(de),
                    "start_yards_to_goal": float(rows["yards_to_goal"].iloc[0]),
                    "opportunity": bool((rows["eckel"] == 1).any()),
                    "points": points.get((int(drive), str(off))),
                }
            )
    return pd.DataFrame.from_records(
        records,
        columns=[
            "game_id",
            "drive_number",
            "offense",
            "defense",
            "start_yards_to_goal",
            "opportunity",
            "points",
        ],
    )


def recompute(
    drives: pd.DataFrame, team: str, role: str
) -> dict[str, tuple[float | None, int]]:
    """The three metrics for one team and role: (value, n)."""
    column = "offense" if role == "offense" else "defense"
    mine = drives[drives[column] == team]
    if mine.empty:
        return {metric: (None, 0) for metric in METRICS}
    start = (100.0 - mine["start_yards_to_goal"]).dropna()
    opp = mine[mine["opportunity"]]
    valid = opp["points"].dropna()
    return {
        "avg_start_field_pos": (
            float(start.mean()) if len(start) else None,
            int(len(start)),
        ),
        "scoring_opp_rate": (float(len(opp)) / len(mine), int(len(mine))),
        "pts_per_scoring_opp": (
            float(valid.mean()) if len(valid) else None,
            int(len(valid)),
        ),
    }


@dataclass(frozen=True)
class Comparison:
    team: str
    role: str
    metric: str
    recomputed: float | None
    published: float | None
    n: int
    ok: bool


def compare(
    drives: pd.DataFrame,
    published: pd.DataFrame,
    teams: list[str],
    tolerance: float = 1e-4,
) -> list[Comparison]:
    table = {
        (str(r.team), str(r.role), str(r.metric)): (
            None if pd.isna(r.value) else float(r.value)
        )
        for r in published.itertuples(index=False)
    }
    out: list[Comparison] = []
    for team in teams:
        for role in ("offense", "defense"):
            values = recompute(drives, team, role)
            for metric in METRICS:
                mine, n = values[metric]
                theirs = table.get((team, role, metric))
                if mine is None or theirs is None:
                    ok = mine is None and theirs is None
                else:
                    ok = abs(mine - theirs) <= tolerance
                out.append(Comparison(team, role, metric, mine, theirs, n, ok))
    return out


def _read(path: str) -> pd.DataFrame:
    return pd.read_csv(path) if path.endswith(".csv") else pd.read_parquet(path)


def _neon_published(season: int, as_of_week: int, teams: list[str]) -> pd.DataFrame:
    import psycopg

    url = os.environ["PREVIEW_DATABASE_URL"]
    query = (
        "select team, role, metric, value::float8 as value from team_season_stats "
        "where season=%s and as_of_week=%s and team = any(%s) and metric = any(%s)"
    )
    with psycopg.connect(url, options="-c default_transaction_read_only=on") as conn:
        cur = conn.execute(query, (season, as_of_week, teams, list(METRICS)))
        return pd.DataFrame(cur.fetchall(), columns=[c.name for c in cur.description])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--byplay", required=True)
    parser.add_argument("--teams", nargs="+", required=True)
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--as-of-week", type=int, required=True)
    parser.add_argument("--published")
    parser.add_argument("--neon-preview", action="store_true")
    parser.add_argument("--tolerance", type=float, default=1e-4)
    args = parser.parse_args()
    if bool(args.published) == bool(args.neon_preview):
        parser.error("give exactly one of --published or --neon-preview")

    plays = _read(args.byplay)
    plays = plays[(plays["season"] == args.season) & (plays["week"] < args.as_of_week)]
    published = (
        _read(args.published)
        if args.published
        else _neon_published(args.season, args.as_of_week, args.teams)
    )
    results = compare(build_drives(plays), published, args.teams, args.tolerance)
    for r in results:
        flag = "PASS" if r.ok else "DIFF"
        print(
            f"{flag} {r.team:20s} {r.role:8s} {r.metric:20s} "
            f"recomputed={r.recomputed} published={r.published} n={r.n}"
        )
    bad = [r for r in results if not r.ok]
    print(f"{len(results) - len(bad)}/{len(results)} within tolerance")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
