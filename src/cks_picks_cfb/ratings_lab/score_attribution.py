"""Read-only reconstruction of per-possession points from a running-score stream.

The V5 pipeline attributes points to possessions from the play-by-play running
score (`ratings.observations.true_drive_points`). When that stream is not
monotone the offense is quarantined. This module studies the stream and
evaluates candidate repair rules without touching production code:

* `order_plays` uses the production sort order.
* `team_stream` and `find_drops` classify every running-score regression with
  the taxonomy of known issue 1.
* `rule_baseline`, `rule_envelope` (R1) and `rule_isotonic` (R2) each map an
  observed stream plus the game final to a reconstructed stream. Every rule is
  capped by the final and is resolved only when it reaches the final.
* `drive_points` attributes stream increments to possessions exactly as the
  production builder does.

Nothing here writes ratings, Silver data or any stored table.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

PLAY_ORDER = ("drive_number", "quarter", "play_number")
MAX_DRIVE_POINTS = 8
SCORING_TYPE_MARKERS = (
    "Touchdown",
    "Field Goal Good",
    "Safety",
    "Extra Point Good",
    "Two Point",
)

DROP_PATTERNS = (
    "drop_to_zero",
    "point_after_before_kick",
    "after_scoring_row",
    "penalty_adjacent",
    "scoring_credited_then_reversed",
)


def order_plays(plays: pd.DataFrame) -> pd.DataFrame:
    """Return one game's plays in the production order (drive, quarter, play)."""
    ordered = plays.copy()
    for column in PLAY_ORDER:
        ordered[column] = pd.to_numeric(ordered[column], errors="coerce")
    return ordered.sort_values(list(PLAY_ORDER), kind="mergesort").reset_index(
        drop=True
    )


def team_stream(ordered: pd.DataFrame, team: str) -> np.ndarray:
    """Running score of `team` on every ordered row (offense or defense side)."""
    values = np.where(
        ordered["offense"].eq(team),
        ordered["offense_score"],
        np.where(ordered["defense"].eq(team), ordered["defense_score"], np.nan),
    )
    return values.astype(float)


def is_scoring_row(ordered: pd.DataFrame) -> np.ndarray:
    flag = ordered["scoring"].fillna(False).astype(bool).to_numpy()
    kind = ordered["play_type"].astype(str)
    marked = np.zeros(len(ordered), dtype=bool)
    for marker in SCORING_TYPE_MARKERS:
        marked |= kind.str.contains(marker, regex=False).to_numpy()
    return flag | marked


@dataclass(frozen=True)
class Drop:
    """One regression of a team's running score between consecutive rows."""

    row: int
    before: int
    after: int
    pattern: str
    restored: bool
    rows_until_restored: int | None


def classify_drop(
    stream: np.ndarray, ordered: pd.DataFrame, scoring: np.ndarray, row: int
) -> Drop:
    before, after = int(stream[row - 1]), int(stream[row])
    kinds = ordered["play_type"].astype(str).to_numpy()
    penalty = kinds[row] == "Penalty" or kinds[row - 1] == "Penalty"
    if after == 0:
        pattern = "drop_to_zero"
    elif scoring[row - 1] and before - after in (1, 2):
        pattern = "point_after_before_kick"
    elif scoring[row - 1]:
        pattern = "after_scoring_row"
    elif penalty:
        pattern = "penalty_adjacent"
    else:
        pattern = "scoring_credited_then_reversed"
    later = np.flatnonzero(stream[row:] >= before)
    return Drop(
        row=row,
        before=before,
        after=after,
        pattern=pattern,
        restored=bool(later.size),
        rows_until_restored=int(later[0]) if later.size else None,
    )


def find_drops(stream: np.ndarray, ordered: pd.DataFrame) -> list[Drop]:
    scoring = is_scoring_row(ordered)
    return [
        classify_drop(stream, ordered, scoring, int(row))
        for row in np.flatnonzero(np.diff(stream) < 0) + 1
    ]


def large_jumps(stream: np.ndarray) -> list[int]:
    """Rows where the score rises by more than one possession can score."""
    return [int(row) for row in np.flatnonzero(np.diff(stream) > MAX_DRIVE_POINTS) + 1]


# ---------------------------------------------------------------- rules


def rule_baseline(stream: np.ndarray, final: int) -> np.ndarray:
    """Today's behaviour: the observed stream, unchanged."""
    del final
    return stream.copy()


def rule_envelope(stream: np.ndarray, final: int) -> np.ndarray:
    """R1: running maximum, capped by the game final."""
    return np.minimum(np.maximum.accumulate(stream), final)


def _isotonic_levels(
    stream: np.ndarray,
    final: int,
    lower: np.ndarray | None,
    upper: np.ndarray | None,
) -> np.ndarray | None:
    """Non-decreasing path minimising absolute error inside optional row bounds."""
    extra = set() if lower is None else {int(v) for v in np.unique(lower)}
    extra |= set() if upper is None else {int(v) for v in np.unique(upper)}
    levels = np.array(
        sorted(
            {0, int(final)}
            | {int(v) for v in np.unique(stream) if 0 <= v <= final}
            | {v for v in extra if 0 <= v <= final}
        ),
        dtype=float,
    )
    observed = np.minimum(stream, final)
    cost = np.abs(observed[:, None] - levels[None, :])
    if lower is not None and upper is not None:
        outside = (levels[None, :] < lower[:, None]) | (
            levels[None, :] > upper[:, None]
        )
        cost = np.where(outside, np.inf, cost)
    best = cost[0].copy()
    back = np.zeros((len(stream), len(levels)), dtype=int)
    for row in range(1, len(stream)):
        running = np.minimum.accumulate(best)
        argmin = np.zeros(len(levels), dtype=int)
        for k in range(1, len(levels)):
            argmin[k] = k if best[k] < running[k - 1] else argmin[k - 1]
        back[row] = argmin
        best = running + cost[row]
    if not np.isfinite(best.min()):
        return None
    level = int(np.argmin(best))
    result = np.empty(len(stream))
    for row in range(len(stream) - 1, -1, -1):
        result[row] = levels[level]
        level = back[row][level] if row else level
    return result


def rule_isotonic(stream: np.ndarray, final: int) -> np.ndarray:
    """R2: non-decreasing stream closest to the observed one in total absolute error.

    Values are restricted to scores seen in the stream (plus 0 and the final) and
    never exceed the final. A short run of spurious values, high or low, is
    outvoted by the rows around it. Ties choose the lowest value, so the result
    is deterministic.
    """
    result = _isotonic_levels(stream, final, None, None)
    assert result is not None
    return result


def quarter_bounds(
    quarters: np.ndarray, line_scores: list[int]
) -> tuple[np.ndarray, np.ndarray]:
    """Per-row score bounds implied by a team's quarter line scores.

    A row in quarter q cannot show fewer points than were scored before q or
    more than were scored through q. Overtime rows may reach the final.
    """
    cumulative = np.concatenate([[0], np.cumsum(line_scores)])
    regulation = min(4, len(line_scores))
    lower = np.zeros(len(quarters))
    upper = np.zeros(len(quarters))
    for row, quarter in enumerate(quarters):
        q = int(quarter)
        if q <= regulation:
            lower[row], upper[row] = cumulative[q - 1], cumulative[q]
        else:
            lower[row], upper[row] = cumulative[regulation], cumulative[-1]
    return lower, upper


def rule_quarter_anchored(
    stream: np.ndarray,
    final: int,
    quarters: np.ndarray,
    line_scores: list[int],
) -> np.ndarray | None:
    """R3: R2 constrained by the quarter line scores; None when no path fits."""
    if sum(line_scores) != final:
        return None
    lower, upper = quarter_bounds(quarters, line_scores)
    return _isotonic_levels(stream, final, lower, upper)


def rule_scoring_rows(
    stream: np.ndarray, final: int, scoring: np.ndarray
) -> np.ndarray:
    """R4: trust the score only on scoring rows, then fit them monotonically.

    Points change on scoring plays (in clean team-games 99.6% of increments sit on
    a scoring row), while the spurious values sit mostly on ordinary plays,
    penalties and kickoffs. The rule ignores the score column on every other row,
    fits the scoring-row values with R2's capped monotone fit, and carries the
    fitted value forward.
    """
    result = np.zeros(len(stream))
    anchors = np.flatnonzero(scoring)
    if not anchors.size:
        return result
    fitted = _isotonic_levels(stream[anchors], final, None, None)
    assert fitted is not None
    position = np.searchsorted(anchors, np.arange(len(stream)), side="right") - 1
    carried = np.where(position >= 0, fitted[np.maximum(position, 0)], 0.0)
    return carried


RULES = (
    "r0_baseline",
    "r1_envelope",
    "r2_isotonic",
    "r3_quarter_anchored",
    "r4_scoring_rows",
)


# ------------------------------------------------------ possession points


def drive_points(
    ordered: pd.DataFrame, streams: dict[str, np.ndarray]
) -> dict[tuple[int, str], int]:
    """Points per (drive, offense) as the production builder attributes them.

    `before` is the offense's score on the row preceding the drive's first row
    (0 at the start of the game) and `after` its score on the drive's last row.
    """
    result: dict[tuple[int, str], int] = {}
    offense = ordered["offense"].to_numpy()
    drive = ordered["drive_number"].to_numpy()
    first: dict[tuple[int, str], int] = {}
    last: dict[tuple[int, str], int] = {}
    for row in range(len(ordered)):
        key = (int(drive[row]), str(offense[row]))
        first.setdefault(key, row)
        last[key] = row
    for key, start in first.items():
        series = streams[key[1]]
        before = series[start - 1] if start else 0.0
        result[key] = int(series[last[key]] - before)
    return result


def quarter_points(ordered: pd.DataFrame, stream: np.ndarray) -> dict[int, int]:
    """Points the stream gains in each quarter (increments by row quarter)."""
    gains: dict[int, int] = {}
    quarters = ordered["quarter"].to_numpy()
    previous = 0.0
    for row in range(len(stream)):
        step = stream[row] - previous
        if step > 0:
            gains[int(quarters[row])] = gains.get(int(quarters[row]), 0) + int(step)
        previous = max(previous, stream[row])
    return gains


def quarters_match(
    ordered: pd.DataFrame, stream: np.ndarray, line_scores: list[int]
) -> bool:
    gains = quarter_points(ordered, stream)
    regulation = min(4, len(line_scores))
    if any(gains.get(q + 1, 0) != line_scores[q] for q in range(regulation)):
        return False
    return sum(v for k, v in gains.items() if k > regulation) == sum(
        line_scores[regulation:]
    )


def placement_on_scoring_rows(
    ordered: pd.DataFrame, stream: np.ndarray, window: int = 2
) -> tuple[int, int]:
    """(increments near a scoring row, all increments) for one stream.

    An increment is a row where the stream rises above its running maximum. It is
    supported when a scoring row (the provider's `scoring` flag or a scoring play
    type) lies within `window` rows. This uses fields independent of the score
    columns, so it is not circular with the cap at the game final.
    """
    scoring = is_scoring_row(ordered)
    near = 0
    total = 0
    peak = 0.0
    for row in range(len(stream)):
        if stream[row] > peak:
            total += 1
            lo, hi = max(0, row - window), min(len(stream), row + window + 1)
            near += int(scoring[lo:hi].any())
            peak = stream[row]
    return near, total


@dataclass(frozen=True)
class TeamOutcome:
    """One rule applied to one team-game."""

    rule: str
    resolved: bool
    reason: str | None
    changed: bool
    reached: int
    stream: np.ndarray
    quarter_match: bool | None
    placed: int
    increments: int


def stream_reason(
    stream: np.ndarray, final: int, drive_values: list[int]
) -> str | None:
    """Why the production builder would reject this stream, or None if it accepts."""
    reached = int(stream[-1]) if len(stream) else 0
    if np.any(np.diff(stream) < 0):
        return "score_regression"
    if reached > final:
        return "exceeds_final"
    if reached < final:
        return "short_of_final"
    if any(value < 0 or value > MAX_DRIVE_POINTS for value in drive_values):
        return "drive_points_outside_0_8"
    return None


def _candidate(
    rule: str,
    stream: np.ndarray,
    final: int,
    ordered: pd.DataFrame,
    line_scores: list[int] | None,
) -> np.ndarray | None:
    if rule == "r0_baseline":
        return stream.copy()
    if rule == "r1_envelope":
        return rule_envelope(stream, final)
    if rule == "r2_isotonic":
        return rule_isotonic(stream, final)
    if rule == "r4_scoring_rows":
        return rule_scoring_rows(stream, final, is_scoring_row(ordered))
    if line_scores is None:
        return None
    return rule_quarter_anchored(
        stream, final, ordered["quarter"].to_numpy(), line_scores
    )


def repaired_streams(
    ordered: pd.DataFrame,
    finals: dict[str, int],
    rule: str,
    line_scores: dict[str, list[int]] | None = None,
    only: set[str] | None = None,
) -> dict[str, np.ndarray | None]:
    """Streams a rule produces; a team the builder already accepts is unchanged.

    No rule can alter an already reconciling team-game, and every rebuilt stream
    is capped by the team's final (`None` marks a rule that has no answer). `only`
    limits rewriting to the named teams.
    """
    observed = {team: team_stream(ordered, team) for team in finals}
    points = drive_points(ordered, observed)
    result: dict[str, np.ndarray | None] = {}
    for team, final in finals.items():
        values = [v for (_, off), v in points.items() if off == team]
        if (only is not None and team not in only) or (
            stream_reason(observed[team], final, values) is None
        ):
            result[team] = observed[team].copy()
            continue
        rebuilt = _candidate(
            rule,
            observed[team],
            final,
            ordered,
            None if line_scores is None else line_scores[team],
        )
        if rebuilt is not None and rule != "r0_baseline":
            assert float(np.max(rebuilt)) <= final, "a rule must never exceed the final"
        result[team] = rebuilt
    return result


def evaluate_game(
    ordered: pd.DataFrame,
    finals: dict[str, int],
    line_scores: dict[str, list[int]] | None,
) -> dict[str, dict[str, TeamOutcome]]:
    """Apply every rule to both teams of one game and score the result."""
    observed = {team: team_stream(ordered, team) for team in finals}
    base_points = drive_points(ordered, observed)
    outcomes: dict[str, dict[str, TeamOutcome]] = {}
    for rule in RULES:
        streams = repaired_streams(ordered, finals, rule, line_scores)
        usable = {t: s if s is not None else observed[t] for t, s in streams.items()}
        points = drive_points(ordered, usable)
        outcomes[rule] = {}
        for team, final in finals.items():
            stream = streams[team]
            if stream is None:
                outcomes[rule][team] = TeamOutcome(
                    rule,
                    False,
                    "quarter_bounds_infeasible",
                    False,
                    int(observed[team][-1]),
                    observed[team],
                    None,
                    0,
                    0,
                )
                continue
            values = [v for (_, off), v in points.items() if off == team]
            base_values = [v for (_, off), v in base_points.items() if off == team]
            reason = stream_reason(stream, final, values)
            changed = stream_reason(observed[team], final, base_values) is not None
            outcomes[rule][team] = TeamOutcome(
                rule,
                reason is None,
                reason,
                changed,
                int(stream[-1]),
                stream,
                None
                if line_scores is None
                else quarters_match(ordered, stream, line_scores[team]),
                *placement_on_scoring_rows(ordered, stream),
            )
    return outcomes
