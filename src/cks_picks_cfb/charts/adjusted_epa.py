"""Venue-neutralized, opponent-adjusted EPA/play per cumulative window.

For each ``as_of_week`` (games in weeks ``< as_of_week``):

1. One observation per team-game offense: ``y = epa_sum / epa_n``, weight
   ``w = epa_n``, venue sign ``s`` (+1 home, -1 away, 0 neutral).
2. A single venue coefficient ``h`` comes from weighted least squares
   ``y = mu + o_i + d_j + h*s`` on the row-weighted design
   ``X_weighted = X * sqrt(w)[:, None]``, ``y_weighted = y * sqrt(w)``. ``h`` is used
   only when the rank condition identifies it, otherwise ``h = 0``.
3. Offense numerators become ``epa_sum - s*h*epa_n`` and defense numerators
   (EPA allowed, ``s`` from the defender's side) ``epa_sum + s*h*epa_n``.
4. The unchanged V5 ``adjust_possession_history`` adjusts those neutral values.
   Its first return value is therefore the *neutral* baseline.

``games`` counts the games that contributed role-specific EPA observations
(``epa_n > 0``) to the window.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from typing import Any, NamedTuple

import numpy as np
import pandas as pd

from cks_picks_cfb.ratings.possession_measurements import adjust_possession_history

ADJUSTMENT_METHOD = "iterative_4pass_venue_v1"
MEASUREMENT = "epa_per_play"
FIRST_ADJUSTED_WEEK = 3
_SIGN = {"home": 1.0, "away": -1.0, "neutral": 0.0}
ADJUSTED_COLUMNS = (
    "season",
    "as_of_week",
    "team",
    "role",
    "raw_epa_per_play",
    "venue_correction",
    "neutral_epa_per_play",
    "opponent_adjustment",
    "adjusted_epa_per_play",
    "venue_coefficient",
    "venue_identified",
    "epa_n",
    "games",
    "adjusted_rank",
    "cohort_size",
    "adjustment_method",
)


class VenueFit(NamedTuple):
    coefficient: float
    identified: bool


def venue_design(
    offense: Sequence[str], defense: Sequence[str], sign: Sequence[float]
) -> tuple[np.ndarray, list[str]]:
    """``X = [intercept, off_0..off_{N-1}, def_0..def_{N-1}, s]`` and the sorted teams."""
    teams = sorted(set(offense) | set(defense))
    index = {team: i for i, team in enumerate(teams)}
    n = len(teams)
    design = np.zeros((len(offense), 2 * n + 2))
    design[:, 0] = 1.0
    for row, (off, deff) in enumerate(zip(offense, defense, strict=True)):
        design[row, 1 + index[off]] = 1.0
        design[row, 1 + n + index[deff]] = 1.0
    design[:, -1] = np.asarray(sign, dtype=float)
    return design, teams


def estimate_venue_coefficient(
    offense: Sequence[str],
    defense: Sequence[str],
    sign: Sequence[float],
    y: Sequence[float],
    weight: Sequence[float],
) -> VenueFit:
    """Weighted least-squares venue coefficient under one tolerance policy.

    ``h`` is identified iff ``rank(Xw) == rank(Xw without the s column) + 1``; the
    intercept with full offense and defense indicator sets is deliberately
    rank-deficient, so only this condition decides identification.
    """
    if len(y) == 0:
        return VenueFit(0.0, False)
    design, _ = venue_design(offense, defense, sign)
    root = np.sqrt(np.asarray(weight, dtype=float))
    weighted_x = design * root[:, None]
    weighted_y = np.asarray(y, dtype=float) * root
    rcond = max(weighted_x.shape) * np.finfo(np.float64).eps
    full = np.linalg.matrix_rank(weighted_x, rtol=rcond)
    without = np.linalg.matrix_rank(weighted_x[:, :-1], rtol=rcond)
    if full != without + 1:
        return VenueFit(0.0, False)
    solution = np.linalg.lstsq(weighted_x, weighted_y, rcond=rcond)[0]
    return VenueFit(float(solution[-1]), True)


def _window_rows(game_rows: pd.DataFrame, as_of_week: int) -> pd.DataFrame:
    window = game_rows[game_rows["week"] < as_of_week]
    return window.sort_values(["game_id", "team"], kind="mergesort")


class TeamGameValue(NamedTuple):
    """One team-game observation of a ratio measurement for one role."""

    team: str
    opponent: str
    site: str
    role: str
    numerator: float
    denominator: float


class AdjustedValue(NamedTuple):
    raw: float
    neutral: float
    adjusted: float
    n: float
    games: int


class AdjustedValues(NamedTuple):
    fit: VenueFit
    values: dict[tuple[str, str], AdjustedValue]


def adjust_team_game_values(
    observations: Sequence[TeamGameValue], *, measurement: str = MEASUREMENT
) -> AdjustedValues:
    """Venue-neutralize then opponent-adjust ratio observations, keyed by (team, role).

    Observations need ``denominator > 0``. The venue coefficient is fit on the
    offense rows; defense numerators take the opposite sign (``s`` is from the
    defender's side, as in the module docstring). ``raw`` is the unneutralized
    ratio of sums.
    """
    offense = [o for o in observations if o.role == "offense"]
    fit = estimate_venue_coefficient(
        [o.team for o in offense],
        [o.opponent for o in offense],
        [_SIGN[o.site] for o in offense],
        [o.numerator / o.denominator for o in offense],
        [float(o.denominator) for o in offense],
    )
    if not observations:
        return AdjustedValues(fit, {})
    raw_sums: dict[tuple[str, str], list[float]] = {}
    games: dict[tuple[str, str], int] = {}
    history = []
    for obs in observations:
        key = (obs.team, obs.role)
        totals = raw_sums.setdefault(key, [0.0, 0.0])
        totals[0] += obs.numerator
        totals[1] += obs.denominator
        games[key] = games.get(key, 0) + 1
        direction = -1.0 if obs.role == "offense" else 1.0
        history.append(
            {
                "team": obs.team,
                "unit_role": obs.role,
                "measurement_id": measurement,
                "opponent": obs.opponent,
                "numerator": obs.numerator
                + direction * _SIGN[obs.site] * fit.coefficient * obs.denominator,
                "denominator": float(obs.denominator),
            }
        )
    neutral, adjusted = adjust_possession_history(pd.DataFrame(history))
    values = {
        key: AdjustedValue(
            total / count,
            neutral[(*key, measurement)],
            adjusted[(*key, measurement)],
            count,
            games[key],
        )
        for key, (total, count) in sorted(raw_sums.items())
    }
    return AdjustedValues(fit, values)


def adjusted_epa_window(
    game_rows: pd.DataFrame,
    roster: Collection[str],
    *,
    season: int,
    as_of_week: int,
) -> list[dict[str, Any]]:
    """Adjusted rows (team, role) of one window, ranked among roster teams."""
    window = _window_rows(game_rows, as_of_week)
    roster_set = set(roster)
    observations = [
        TeamGameValue(
            row.team,
            row.opponent,
            row.site,
            role,
            float(getattr(row, f"{prefix}_epa_sum")),
            float(getattr(row, f"{prefix}_epa_n")),
        )
        for row in window.itertuples(index=False)
        for role, prefix in (("offense", "off"), ("defense", "def"))
        if getattr(row, f"{prefix}_epa_n") > 0
    ]
    if not observations:
        return []
    fit, values = adjust_team_game_values(observations)
    rows = []
    for (team, role), value in values.items():
        if team not in roster_set:
            raise ValueError(f"team outside the roster: {team}")
        rows.append(
            {
                "season": season,
                "as_of_week": as_of_week,
                "team": team,
                "role": role,
                "raw_epa_per_play": value.raw,
                "venue_correction": value.raw - value.neutral,
                "neutral_epa_per_play": value.neutral,
                "opponent_adjustment": value.neutral - value.adjusted,
                "adjusted_epa_per_play": value.adjusted,
                "venue_coefficient": fit.coefficient,
                "venue_identified": fit.identified,
                "epa_n": int(value.n),
                "games": value.games,
                "adjusted_rank": None,
                "cohort_size": None,
                "adjustment_method": ADJUSTMENT_METHOD,
            }
        )
    frame = pd.DataFrame(rows)
    for role, ascending in (("offense", False), ("defense", True)):
        mask = frame["role"] == role
        ranks = frame.loc[mask, "adjusted_epa_per_play"].rank(
            method="min", ascending=ascending
        )
        for position, rank in zip(frame.index[mask], ranks, strict=True):
            rows[position]["adjusted_rank"] = int(rank)
            rows[position]["cohort_size"] = int(mask.sum())
    return rows


def build_team_adjusted_epa(
    game_rows: pd.DataFrame | Sequence[Mapping[str, Any]],
    roster: Collection[str],
    *,
    season: int,
    active_week: int,
) -> list[dict[str, Any]]:
    """Rows for every ``as_of_week`` from 3 through ``active_week``."""
    frame = pd.DataFrame(game_rows)
    if frame.empty:
        return []
    rows: list[dict[str, Any]] = []
    for as_of_week in range(FIRST_ADJUSTED_WEEK, active_week + 1):
        rows += adjusted_epa_window(frame, roster, season=season, as_of_week=as_of_week)
    return rows
