"""Reconciliation of the three chart tables against each other and team stats.

Used by the ``team_chart_reconciliation`` release verification check. The
adjusted table is verified by full recomputation through the same entry point
that built it, so the check cannot drift from the builder.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from cks_picks_cfb.charts.adjusted_epa import (
    ADJUSTED_COLUMNS,
    FIRST_ADJUSTED_WEEK,
    build_team_adjusted_epa,
)
from cks_picks_cfb.charts.team_game_stats import STAT_FIELDS

TOLERANCE = 1e-9
#: Float columns compare within tolerance; every other column compares exactly.
_FLOATS = (
    "raw_epa_per_play",
    "venue_correction",
    "neutral_epa_per_play",
    "opponent_adjustment",
    "adjusted_epa_per_play",
    "venue_coefficient",
)
_SITE_MIRROR = {"home": "away", "away": "home", "neutral": "neutral"}


def _close(a: Any, b: Any) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return math.isfinite(float(a)) and abs(float(a) - float(b)) <= TOLERANCE


def chart_problems(
    *,
    roster: Sequence[Mapping[str, Any]],
    game_rows: Sequence[Mapping[str, Any]],
    adjusted_rows: Sequence[Mapping[str, Any]],
    stats_rows: Sequence[Mapping[str, Any]],
    games: Sequence[Mapping[str, Any]] | None = None,
    results: Sequence[Mapping[str, Any]] | None = None,
    season: int,
    active_week: int,
) -> tuple[list[str], dict[str, Any]]:
    problems: list[str] = []
    teams = [row["team"] for row in roster]
    team_set = set(teams)
    if not roster:
        problems.append("roster is empty")
    if len(team_set) != len(teams):
        problems.append("roster teams are not unique")
    if active_week > 0 and not game_rows:
        problems.append("team_game_stats is empty")

    # ------------------------------------------------------------ game rows
    by_game: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for row in game_rows:
        by_game[row["game_id"]].append(row)
        if row["team"] not in team_set or row["opponent"] not in team_set:
            problems.append(f"game {row['game_id']}: team outside the roster")
        if row["week"] >= active_week:
            problems.append(f"game {row['game_id']}: week {row['week']} not completed")
    for game_id, pair in sorted(by_game.items()):
        if len(pair) != 2:
            problems.append(f"game {game_id}: {len(pair)} rows, expected 2")
            continue
        a, b = pair
        if (a["team"], a["opponent"]) != (b["opponent"], b["team"]):
            problems.append(f"game {game_id}: opponents are not mirrored")
        if a["week"] != b["week"]:
            problems.append(f"game {game_id}: weeks differ")
        if (a["points_for"], a["points_against"]) != (
            b["points_against"],
            b["points_for"],
        ):
            problems.append(f"game {game_id}: points are not mirrored")
        if _SITE_MIRROR.get(a["site"]) != b["site"]:
            problems.append(f"game {game_id}: sites are not mirrored")
        for field in STAT_FIELDS:
            if not (
                _close(a[f"off_{field}"], b[f"def_{field}"])
                and _close(b[f"off_{field}"], a[f"def_{field}"])
            ):
                problems.append(f"game {game_id}: off/def {field} are not mirrored")

    # ------------------------------ agreement with the release's own games/finals
    if games is not None and results is not None:
        schedule = {g["game_id"]: g for g in games}
        finals = {r["game_id"]: r for r in results}
        for game_id, pair in sorted(by_game.items()):
            game, final = schedule.get(game_id), finals.get(game_id)
            if game is None or final is None:
                problems.append(
                    f"game {game_id}: absent from the release games or finals"
                )
                continue
            for row in pair:
                home = row["team"] == game["home_team"]
                if {row["team"], row["opponent"]} != {
                    game["home_team"],
                    game["away_team"],
                }:
                    problems.append(
                        f"game {game_id}: teams differ from the release game"
                    )
                if row["week"] != game["week"]:
                    problems.append(
                        f"game {game_id}: week differs from the release game"
                    )
                if row["site"] != "neutral" and row["site"] != (
                    "home" if home else "away"
                ):
                    problems.append(
                        f"game {game_id}: site contradicts the release game"
                    )
                scored, allowed = (
                    (final["home_points"], final["away_points"])
                    if home
                    else (final["away_points"], final["home_points"])
                )
                if (row["points_for"], row["points_against"]) != (scored, allowed):
                    problems.append(
                        f"game {game_id}: points differ from the release final"
                    )

    # ------------------------------------------ cumulative vs team season stats
    window_cache: dict[tuple[int, str], dict[str, float]] = {}

    def window(as_of_week: int, team: str) -> dict[str, float]:
        key = (as_of_week, team)
        if key not in window_cache:
            totals: dict[str, float] = defaultdict(float)
            for row in game_rows:
                if row["team"] == team and row["week"] < as_of_week:
                    totals["games"] += 1
                    for role in ("off", "def"):
                        for field in STAT_FIELDS:
                            totals[f"{role}_{field}"] += row[f"{role}_{field}"]
            window_cache[key] = totals
        return window_cache[key]

    metric_fields = {
        "success_rate": ("success_sum", "success_n"),
        "ppa_per_play": ("epa_sum", "epa_n"),
    }
    for row in stats_rows:
        totals = window(row["as_of_week"], row["team"])
        label = (
            f"stats {row['team']} w{row['as_of_week']} {row['role']} {row['metric']}"
        )
        if row["games"] != int(totals.get("games", 0)):
            problems.append(
                f"{label}: games {row['games']} != {totals.get('games', 0)}"
            )
        if row["metric"] in metric_fields:
            total_field, count_field = metric_fields[row["metric"]]
            prefix = "off" if row["role"] == "offense" else "def"
            n = int(totals.get(f"{prefix}_{count_field}", 0))
            expected = totals[f"{prefix}_{total_field}"] / n if n else None
            if row["n"] != n:
                problems.append(f"{label}: n {row['n']} != {n}")
            if not _close(row["value"], expected):
                problems.append(f"{label}: value {row['value']} != {expected}")

    # ------------------------------------------ adjusted: full recomputation
    expected_rows: list[dict[str, Any]] = []
    if game_rows and active_week >= FIRST_ADJUSTED_WEEK:
        try:
            expected_rows = build_team_adjusted_epa(
                list(game_rows), team_set, season=season, active_week=active_week
            )
        except ValueError as error:
            problems.append(f"adjusted recomputation failed: {error}")
    keyed = {(r["as_of_week"], r["team"], r["role"]): r for r in adjusted_rows}
    if len(keyed) != len(adjusted_rows):
        problems.append("adjusted rows repeat a natural key")
    wanted = {(r["as_of_week"], r["team"], r["role"]): r for r in expected_rows}
    for key in sorted(set(wanted) - set(keyed)):
        problems.append(f"adjusted row missing: {key}")
    for key in sorted(set(keyed) - set(wanted)):
        problems.append(f"adjusted row unexpected: {key}")
    for key in sorted(set(wanted) & set(keyed)):
        stored, fresh = keyed[key], wanted[key]
        if set(stored) != set(ADJUSTED_COLUMNS):
            problems.append(f"adjusted {key}: columns differ")
            continue
        for column in ADJUSTED_COLUMNS:
            same = (
                _close(stored[column], fresh[column])
                if column in _FLOATS
                else stored[column] == fresh[column]
            )
            if not same:
                problems.append(
                    f"adjusted {key} {column}: {stored[column]} != {fresh[column]}"
                )
    return problems, {
        "roster": len(team_set),
        "team_game_rows": len(game_rows),
        "games": len(by_game),
        "adjusted_rows": len(adjusted_rows),
        "adjusted_windows": len({k[0] for k in wanted}),
    }
