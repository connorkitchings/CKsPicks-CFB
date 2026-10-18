"""Chart tables of the ``charts_v2`` season release payload.

``team_season_roster``, ``team_game_stats``, ``team_adjusted_epa`` and
``team_game_yardage`` are descriptive reconstructions from the revision's pinned inputs (see
:mod:`cks_picks_cfb.charts`). They live apart from ``projection_football`` so the
existing ``core_v1`` builders stay untouched. Team names are provider (game)
names, as in ``team_season_stats``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd

from cks_picks_cfb.charts.adjusted_epa import (
    ADJUSTED_COLUMNS,
    build_team_adjusted_epa,
)
from cks_picks_cfb.charts.roster import (
    ROSTER_COLUMNS,
    RosterError,
    build_team_season_roster,
)
from cks_picks_cfb.charts.team_game_stats import (
    TEAM_GAME_COLUMNS,
    build_team_game_stats,
)
from cks_picks_cfb.charts.team_game_yardage import (
    YARDAGE_COLUMNS,
    TeamGameYardageError,
    build_team_game_yardage,
)
from cks_picks_cfb.data.game_venues import build_game_venue_rows
from cks_picks_cfb.season.projection_common import CHART_TABLES, clean_rows

CHART_KEYS = (*CHART_TABLES, "team_game_yardage")
SEASON = 2026

#: table -> natural key (``release.PROJECTION_KEYS``) used for row order.
ROW_KEYS = {
    "team_season_roster": ("season", "team"),
    "team_game_stats": ("season", "game_id", "team"),
    "team_adjusted_epa": ("season", "as_of_week", "team", "role"),
    "team_game_yardage": ("season", "game_id", "team"),
}
#: INTEGER columns per table (migrations 0026, 0027); builders may yield floats.
INTEGER_COLUMNS = {
    "team_season_roster": ("season",),
    "team_game_stats": (
        "season",
        "week",
        "game_id",
        "points_for",
        "points_against",
        "off_plays",
        "off_success_n",
        "off_epa_n",
        "def_plays",
        "def_success_n",
        "def_epa_n",
    ),
    "team_adjusted_epa": (
        "season",
        "as_of_week",
        "epa_n",
        "games",
        "adjusted_rank",
        "cohort_size",
    ),
    "team_game_yardage": (
        "season",
        "game_id",
        "off_yards_n",
        "off_explosive_n",
        "off_success_yards_n",
        "def_yards_n",
        "def_explosive_n",
        "def_success_yards_n",
    ),
}
COLUMNS = {
    "team_season_roster": ROSTER_COLUMNS,
    "team_game_stats": TEAM_GAME_COLUMNS,
    "team_adjusted_epa": ADJUSTED_COLUMNS,
    "team_game_yardage": YARDAGE_COLUMNS,
}


class ChartProjectionError(ValueError):
    """The inputs cannot produce the chart tables of a season release."""


def build_charts(
    *,
    frames: Mapping[str, pd.DataFrame],
    inputs: Any,
    revision: Mapping[str, Any],
    identity: Mapping[str, Any],
    ratings_id: str,
    measurement_id: str,
) -> dict[str, list[dict]]:
    """Return ``{key: rows}`` for exactly :data:`CHART_KEYS`.

    Arguments are as for ``projection_football.build_football``; only the pinned
    inputs and ``identity['active_week']`` are read.
    """
    active_week = int(identity["active_week"])
    roster, game_stats = _team_games(inputs, active_week)
    adjusted = pd.DataFrame(
        build_team_adjusted_epa(
            game_stats, set(roster["team"]), season=SEASON, active_week=active_week
        ),
        columns=list(ADJUSTED_COLUMNS),
    )
    tables = {
        "team_season_roster": roster,
        "team_game_stats": game_stats,
        "team_adjusted_epa": adjusted,
        "team_game_yardage": _yardage(inputs, game_stats),
    }
    return {key: _rows(key, tables[key]) for key in CHART_KEYS}


def build_yardage_rows(inputs: Any, active_week: int) -> list[dict]:
    """``team_game_yardage`` payload rows recomputed from the pinned inputs alone.

    The ``chart_yardage_recomputed`` prepare check compares the candidate's rows
    with these; ``inputs.byplay`` is the checksum-verified pinned byplay frame.
    """
    _, game_stats = _team_games(inputs, active_week)
    return _rows("team_game_yardage", _yardage(inputs, game_stats))


def _team_games(inputs: Any, active_week: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The roster and the ``team_game_stats`` frame (provider team names)."""
    try:
        roster = build_team_season_roster(inputs.teams, SEASON)
    except RosterError as error:
        raise ChartProjectionError(str(error)) from error
    schedule = inputs.schedule.copy()
    for side in ("home_team", "away_team"):
        schedule[side] = schedule[side + "_provider"]
    game_stats = build_team_game_stats(
        byplay=inputs.byplay,
        games=schedule,
        finals=inputs.finals,
        fbs_teams=set(roster["team"]),
        neutral_game_ids=_neutral_game_ids(inputs, schedule),
        season=SEASON,
        active_week=active_week,
    )
    return roster, game_stats


def _yardage(inputs: Any, game_stats: pd.DataFrame) -> pd.DataFrame:
    try:
        return build_team_game_yardage(byplay=inputs.byplay, team_games=game_stats)
    except TeamGameYardageError as error:
        raise ChartProjectionError(str(error)) from error


def _neutral_game_ids(inputs: Any, schedule: pd.DataFrame) -> set[int]:
    if inputs.venue_games is None or inputs.venues is None:
        return set()
    rows, _ = build_game_venue_rows(
        inputs.venue_games, inputs.venues, schedule.game_id.astype(int)
    )
    return {int(row["game_id"]) for row in rows if row["neutral_site"] is True}


def _rows(key: str, frame: pd.DataFrame) -> list[dict]:
    frame = frame.copy()
    for column in INTEGER_COLUMNS[key]:
        frame[column] = pd.to_numeric(frame[column]).astype("Int64")
    rows = clean_rows(frame, COLUMNS[key])
    names = ROW_KEYS[key]
    return sorted(rows, key=lambda row: tuple(row[name] for name in names))
