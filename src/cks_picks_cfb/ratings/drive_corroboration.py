"""CFBD drive corroboration for the Window 2 Step 5A sizing. Read-only analysis helpers.

Implements the four usability checks and the group corroboration rule frozen in
``docs/plans/2026-10-03/window2/5a-frozen-definitions.md``. Nothing here serves data.

A game's drives are usable only if all four checks pass:
1. reconcile with the certified quarter and final totals (non-drive scores explicit);
2. drive boundaries and team identities match the possession ledger;
3. touchdowns and conversions have consistent associations (valid drive point deltas);
4. no unexplained regression, excess points, duplicate allocation or timing conflict.
A final-total match alone never establishes usability.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

import pandas as pd

OFFENSE_DELTAS = {0, 3, 6, 7, 8}
DEFENSE_DELTAS = {0, 2, 6, 7, 8}
STATUSES = (
    "corroborated",
    "cfbd_supports_baseline",
    "indistinguishable_at_drive_level",
    "cfbd_matches_neither",
    "game_unusable",
    "no_regulation_drive",
    "no_cfbd_data",
)


def parse_drives(rows: Sequence[Mapping[str, Any]], canonical) -> pd.DataFrame:
    """CFBD drive rows to a frame with canonical team names, one row per drive id."""
    frame = pd.DataFrame(list(rows))
    if frame.empty:
        return frame
    frame = frame.drop_duplicates("id").copy()
    frame["offense"] = frame["offense"].map(canonical)
    frame["defense"] = frame["defense"].map(canonical)
    return frame


def _line_scores(value: Any) -> list[float]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    if isinstance(value, str):
        value = json.loads(value)
    return [float(v) for v in list(value)]


def _scores(
    drive: Mapping[str, Any], when: str, home_offense: bool
) -> tuple[float, float]:
    offense = drive[f"{when}OffenseScore"]
    defense = drive[f"{when}DefenseScore"]
    return (offense, defense) if home_offense else (defense, offense)


def check_game(
    drives: pd.DataFrame,
    *,
    home: str,
    away: str,
    final_home: float,
    final_away: float,
    home_line_scores: Any,
    away_line_scores: Any,
    ledger_regulation_all: set[tuple[int, str]],
    ledger_regulation_eligible: set[tuple[int, str]],
) -> dict[str, Any]:
    """Run the four frozen checks on one game's CFBD drives. Reasons are recorded per check."""
    result: dict[str, Any] = {
        "c1": True,
        "c2": True,
        "c3": True,
        "c4": True,
        "reasons": [],
    }

    def fail(check: str, reason: str) -> None:
        result[check] = False
        result["reasons"].append(f"{check}:{reason}")

    if drives.empty:
        for check in ("c1", "c2", "c3", "c4"):
            result[check] = False
        result["reasons"].append("no_drives")
        result["usable"] = False
        return result

    ordered = drives.sort_values("driveNumber").reset_index(drop=True)
    rows = ordered.to_dict("records")
    for row in rows:
        row["home_off"] = bool(row["isHomeOffense"])
        row["start_h"], row["start_a"] = _scores(row, "start", row["home_off"])
        row["end_h"], row["end_a"] = _scores(row, "end", row["home_off"])

    # Check 1: opening score, final score, and the quarter totals the drives imply.
    # Drive scoring is attributed to the period the drive ends in (a scoring drive ends at
    # the score). Points between drives (the next drive's start minus the previous end) are
    # the explicit non-drive scores; when there are any, only halftime and the end of
    # regulation are required to match the line scores.
    if (rows[0]["start_h"], rows[0]["start_a"]) != (0, 0):
        fail("c1", "first_drive_not_0_0")
    if (rows[-1]["end_h"], rows[-1]["end_a"]) != (final_home, final_away):
        fail("c1", "last_drive_end_differs_from_certified_final")
    non_drive = sum(
        (b["start_h"] - a["end_h"]) + (b["start_a"] - a["end_a"])
        for a, b in zip(rows, rows[1:])
    )
    result["non_drive_points"] = non_drive
    home_lines, away_lines = (
        _line_scores(home_line_scores),
        _line_scores(away_line_scores),
    )
    required_periods = (1, 2, 3, 4) if non_drive == 0 else (2, 4)
    for period in required_periods:
        if len(home_lines) < period or len(away_lines) < period:
            continue
        # Score after the last drive that ends in or before this period; it already includes
        # any non-drive points before that drive, and equals the sum of drive deltas otherwise.
        ended = [r for r in rows if r["endPeriod"] <= period]
        got_h, got_a = (ended[-1]["end_h"], ended[-1]["end_a"]) if ended else (0, 0)
        if (got_h, got_a) != (sum(home_lines[:period]), sum(away_lines[:period])):
            fail("c1", f"cumulative_through_period_{period}_differs_from_line_scores")

    # Check 2: drive boundaries and team identities agree with the possession ledger.
    # Every CFBD regulation drive must be a ledger possession, and every ledger possession
    # that carries eligible plays must be a CFBD drive. Ledger-only possessions with no
    # eligible plays (returns and other special-teams-only possessions) are not drives.
    cfbd_regulation = {
        (int(r["driveNumber"]), r["offense"]) for r in rows if r["startPeriod"] <= 4
    }
    result["c2_strict"] = cfbd_regulation == ledger_regulation_all
    result["c2_cfbd_not_in_ledger"] = len(cfbd_regulation - ledger_regulation_all)
    result["c2_eligible_not_in_cfbd"] = len(
        ledger_regulation_eligible - cfbd_regulation
    )
    if result["c2_cfbd_not_in_ledger"]:
        fail("c2", "cfbd_drive_missing_from_ledger")
    if result["c2_eligible_not_in_cfbd"]:
        fail("c2", "eligible_ledger_possession_missing_from_cfbd")

    # Check 3: every drive's point deltas are valid (touchdown and conversion association).
    for row in rows:
        off_delta = (
            (row["end_h"] - row["start_h"])
            if row["home_off"]
            else (row["end_a"] - row["start_a"])
        )
        def_delta = (
            (row["end_a"] - row["start_a"])
            if row["home_off"]
            else (row["end_h"] - row["start_h"])
        )
        if off_delta not in OFFENSE_DELTAS or def_delta not in DEFENSE_DELTAS:
            fail(
                "c3",
                f"drive_{int(row['driveNumber'])}_delta_{off_delta:g}_{def_delta:g}",
            )
            break

    # Check 4: no regression, excess, duplicate or timing conflict.
    numbers = [int(r["driveNumber"]) for r in rows]
    if len(set(numbers)) != len(numbers):
        fail("c4", "duplicate_drive_number")
    for previous, current in zip(rows, rows[1:]):
        if (
            current["start_h"] < previous["end_h"]
            or current["start_a"] < previous["end_a"]
        ):
            fail("c4", "score_regression_between_drives")
            break
    if any(r["end_h"] < r["start_h"] or r["end_a"] < r["start_a"] for r in rows):
        fail("c4", "score_regression_within_drive")
    if (
        max(r["end_h"] for r in rows) > final_home
        or max(r["end_a"] for r in rows) > final_away
    ):
        fail("c4", "excess_points_over_certified_final")
    if any(r["endPeriod"] < r["startPeriod"] for r in rows) or any(
        b["startPeriod"] < a["startPeriod"] for a, b in zip(rows, rows[1:])
    ):
        fail("c4", "period_order_conflict")

    result["usable"] = all(result[c] for c in ("c1", "c2", "c3", "c4"))
    return result


def cfbd_points_by_drive(
    drives: pd.DataFrame, home: str, away: str
) -> dict[tuple[str, int], tuple[float, float]]:
    """``{(team, drive_number): (points while on offense, points while on defense)}``."""
    table: dict[tuple[str, int], tuple[float, float]] = {}
    for row in drives.to_dict("records"):
        home_off = bool(row["isHomeOffense"])
        off_team, def_team = (home, away) if home_off else (away, home)
        off_delta = row["endOffenseScore"] - row["startOffenseScore"]
        def_delta = row["endDefenseScore"] - row["startDefenseScore"]
        number = int(row["driveNumber"])
        table[(off_team, number)] = (
            off_delta,
            table.get((off_team, number), (0, 0))[1],
        )
        table[(def_team, number)] = (
            table.get((def_team, number), (0, 0))[0],
            def_delta,
        )
    return table


def ledger_points_by_drive(
    events: pd.DataFrame,
) -> dict[tuple[str, int], tuple[float, float]]:
    """``{(team, drive_number): (offense-unit points, non-offense points)}`` from a scoring ledger."""
    table: dict[tuple[str, int], tuple[float, float]] = {}
    for row in events.to_dict("records"):
        if row.get("period_class") != "regulation":
            continue
        key = (row["team"], int(row["drive_number"]))
        off, non = table.get(key, (0.0, 0.0))
        increment = float(row["score_increment"] or 0)
        if row["unit_category"] == "offense":
            off += increment
        elif row["unit_category"] == "non_offense":
            non += increment
        table[key] = (off, non)
    return table


def classify_group(
    touched_drives: set[int],
    team: str,
    cfbd: Mapping[tuple[str, int], tuple[float, float]],
    baseline: Mapping[tuple[str, int], tuple[float, float]],
    candidate: Mapping[tuple[str, int], tuple[float, float]],
    *,
    game_usable: bool,
    has_cfbd: bool,
) -> str:
    """Status of one changed group under the frozen corroboration rule."""
    if not has_cfbd:
        return "no_cfbd_data"
    if not game_usable:
        return "game_unusable"
    drives = {
        d
        for d in touched_drives
        if (team, d) in cfbd or (team, d) in candidate or (team, d) in baseline
    }
    if not drives:
        return "no_regulation_drive"
    zero = (0.0, 0.0)
    cand_match = all(
        tuple(candidate.get((team, d), zero)) == tuple(cfbd.get((team, d), zero))
        for d in drives
    )
    base_match = all(
        tuple(baseline.get((team, d), zero)) == tuple(cfbd.get((team, d), zero))
        for d in drives
    )
    if cand_match and not base_match:
        return "corroborated"
    if cand_match and base_match:
        return "indistinguishable_at_drive_level"
    if base_match:
        return "cfbd_supports_baseline"
    return "cfbd_matches_neither"
