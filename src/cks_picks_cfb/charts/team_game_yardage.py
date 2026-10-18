"""One row per team per game with eligible-play yardage counts (``charts_v2``).

The key set is exactly that of ``team_game_stats``: the caller passes those rows,
so games, teams and weeks are the same by construction. Plays are the same
``scrimmage_play_mask`` plays. Per role (``off_`` offense, ``def_`` allowed):

* ``yards_n``: plays with a finite ``yards_gained``;
* ``explosive_n``: of those, plays gaining at least 20 yards;
* ``success_yards_n`` / ``success_yards_sum``: plays with ``success == 1`` and a
  finite ``yards_gained``, and the sum of those yards (no sign constraint).

These are the definitions of ``scripts/research/compare_chart_explosiveness.py``.
A role without plays stores zero counts; consumers turn a zero denominator into
a missing value, never zero.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from cks_picks_cfb.data.play_filters import scrimmage_play_mask

EXPLOSIVE_YARDS = 20
YARDAGE_FIELDS = ("yards_n", "explosive_n", "success_yards_n", "success_yards_sum")
YARDAGE_COLUMNS = (
    "season",
    "game_id",
    "team",
    *(f"{role}_{field}" for role in ("off", "def") for field in YARDAGE_FIELDS),
)
_REQUIRED_PLAYS = ("season", "game_id", "offense", "defense", "success", "yards_gained")


class TeamGameYardageError(ValueError):
    """The inputs cannot produce team-game yardage statistics."""


def _finite(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").astype(float)
    return values.where(np.isfinite(values))


def _side_yardage(plays: pd.DataFrame, team_col: str) -> dict[tuple[int, str], dict]:
    yards = _finite(plays["yards_gained"])
    success = _finite(plays["success"])
    measured = yards.notna()
    successful = measured & success.eq(1)
    frame = pd.DataFrame(
        {
            "game_id": plays["game_id"].astype(int).to_numpy(),
            "team": plays[team_col].astype(str).to_numpy(),
            "yards_n": measured.to_numpy(dtype=int),
            "explosive_n": (measured & yards.ge(EXPLOSIVE_YARDS)).to_numpy(dtype=int),
            "success_yards_n": successful.to_numpy(dtype=int),
            "success_yards_sum": yards.where(successful, 0.0).to_numpy(dtype=float),
        }
    )
    sums = frame.groupby(["game_id", "team"]).sum()
    return {
        (int(game_id), str(team)): {
            "yards_n": int(row.yards_n),
            "explosive_n": int(row.explosive_n),
            "success_yards_n": int(row.success_yards_n),
            "success_yards_sum": float(row.success_yards_sum),
        }
        for (game_id, team), row in sums.iterrows()
    }


def build_team_game_yardage(
    *, byplay: pd.DataFrame, team_games: pd.DataFrame
) -> pd.DataFrame:
    """Yardage rows keyed exactly like ``team_games`` (``build_team_game_stats`` output)."""
    if team_games.empty:
        return pd.DataFrame(columns=list(YARDAGE_COLUMNS))
    missing = [c for c in _REQUIRED_PLAYS if c not in byplay.columns]
    if missing:
        raise TeamGameYardageError(f"byplay lacks columns: {missing}")
    seasons = set(pd.to_numeric(team_games["season"]).astype(int))
    ids = set(team_games["game_id"].astype(int))
    plays = byplay[
        pd.to_numeric(byplay["season"], errors="coerce").isin(seasons)
        & byplay["game_id"].astype(int).isin(ids)
    ]
    plays = plays[scrimmage_play_mask(plays)]
    offense = _side_yardage(plays, "offense")
    defense = _side_yardage(plays, "defense")
    empty = {
        "yards_n": 0,
        "explosive_n": 0,
        "success_yards_n": 0,
        "success_yards_sum": 0.0,
    }
    rows = []
    for game in team_games.itertuples(index=False):
        key = (int(game.game_id), str(game.team))
        row = {"season": int(game.season), "game_id": key[0], "team": key[1]}
        for role, stats in (("off", offense), ("def", defense)):
            found = stats.get(key, empty)
            row.update({f"{role}_{field}": found[field] for field in YARDAGE_FIELDS})
        rows.append(row)
    frame = pd.DataFrame(rows, columns=list(YARDAGE_COLUMNS))
    return frame.sort_values(
        ["season", "game_id", "team"], kind="mergesort"
    ).reset_index(drop=True)
