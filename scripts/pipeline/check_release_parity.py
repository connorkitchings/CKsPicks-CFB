#!/usr/bin/env python3
"""Gate: a prepared weekly candidate must match the active Preview release.

Run after ``run_season.py prepare`` and before the Preview release. It compares
the candidate's ``serving-projections.json`` with the projection tables of the
ACTIVE Preview release (read-only, ``DATABASE_URL``) and fails closed unless only
the expected parts of the release changed.

Modes
-----
``close-week`` (``--completed-week N``): weeks ``0..N-1`` were already completed
in the active release (it was activated with ``N`` as its active week), so their
predictions (including variances), grades and pregame rating snapshots must be
identical within ``1e-9``.

``market-refresh``: the same week is re-published with fresher lines. Every table
must be identical except, for the upcoming week only, the line, edge, lean and
high-confidence columns of ``games``/``predictions`` and the rows of the market
tables (quotes, snapshots, selections) of that week's games.

Identity columns never count as differences: run ids embedded in any string
(``season-<year>-<hex>``), hex digests of 12+ characters in any string or row key
(model versions, ``source_versions``, hash-prefixed resume periods, publication
ids), source run ids, manifest hashes/URIs and audit stamps (``created_at``,
``graded_at``, ...). In ``market-refresh`` the ``cutoff_utc`` of the upcoming
week's rows may also differ (the refresh moves that cutoff); completed weeks'
cutoffs must match. In both modes the upcoming week must be 100%
predicted; lined-game coverage is reported but never blocks.

``--accept-cutoff-correction WEEK`` (close-week only, one run at a time): the
``cutoff_utc`` of week ``WEEK``'s pregame ``v5_rating_snapshots`` may differ; every
other column of those rows still compares strictly. It exists for an owner-chosen
one-off correction of a stale completed-week cutoff (the Week 9 manifests carried
Week 8 at 18:00Z against the certified 14:39Z) and is never set by the schedule.

Retrospective lines (one-off, automatic): when the candidate's revision manifest
carries the ``historical_lines`` input, three Week 6 games that had no pre-kickoff
quote (``RETROSPECTIVE_GAMES``) may gain CFBD ``cfbd_retrospective`` grades. For
exactly those games, and only while the active release holds no market rows for
them, the candidate may add their quotes, snapshots, selections and grades, move
the market columns of their ``games``/``predictions`` rows and the result columns
of their ``game_results`` rows, and move ``system_stats`` by exactly the new
grades' wins, losses, pushes and profit. Everything else, including every
prediction mean, variance and rating, still compares strictly. Once the active
release holds the grades, they compare strictly like any other grade.

Overtime success counts: ``team_game_stats.off_success_ot_n``/``off_success_ot_sum``
(migration 0029) may differ only where the active release holds NULL; the
candidate must carry both on every row and not below ``off_success_n``/
``off_success_sum``. Once the active release holds values they compare strictly.

``team_resume.sor_rank`` may permute only among teams whose ``sor`` values tie
within 1e-9 (platform rounding decides their order), and only inside that tied
group's span of ranks; ``sor`` itself is always compared.

The report holds only table names, counts, game ids and column names, so it is
safe to print in public CI logs.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from cks_picks_cfb.season.release import PROJECTION_KEYS

TOLERANCE = 1e-9
MODES = ("close-week", "market-refresh")

#: Audit stamps: deterministic per build or ``now()``; never data.
STAMP_COLUMNS = frozenset(
    {
        "created_at",
        "inserted_at",
        "updated_at",
        "graded_at",
        "scored_at",
        "selected_at",
        "published_at",
    }
)
#: Columns naming the producing run rather than describing the data.
IDENTITY_COLUMNS = frozenset({"run_id", "source_ref", "source_run_id", "code_sha"})
IDENTITY_SUFFIXES = ("_manifest_sha256", "_manifest_uri")
#: Week-scoped columns a market-only refresh may change on the upcoming week.
MARKET_COLUMNS = frozenset(
    {
        "home_team_spread_line",
        "total_line",
        "spread_lean",
        "total_lean",
        "edge_spread",
        "edge_total",
        "high_confidence",
        "market_snapshot_id",
    }
)
#: Tables whose upcoming-week rows are wholly market data in a market refresh.
MARKET_TABLES = frozenset(
    {
        "market_quotes",
        "market_snapshots",
        "market_snapshot_quotes",
        "prediction_market_selections",
    }
)
#: Tables every release must carry for the parity decision to mean anything.
REQUIRED_TABLES = ("games", "predictions", "prediction_grades", "v5_rating_snapshots")

#: Week 6 games with no retained pre-kickoff quote, graded from CFBD lines fetched
#: after kickoff (Southern Miss at Troy, Jacksonville State at Kennesaw State and
#: New Mexico State at Florida International).
RETROSPECTIVE_GAMES = frozenset({"401871090", "401871051", "401871066"})
RETROSPECTIVE_GRADING_VERSION = "model_side_best_quote_v2:cfbd_retrospective"
#: Tables of per-game market rows that the retrospective lines add.
RETROSPECTIVE_ROW_TABLES = (
    "market_quotes",
    "market_snapshots",
    "prediction_market_selections",
    "prediction_grades",
)
RESULT_COLUMNS = frozenset({"spread_result", "total_result"})
TARGETS = ("spread", "total")
STATS_KINDS = ("wins", "losses", "pushes", "profit_units")
STATS_COLUMNS = frozenset(f"{t}_{kind}" for t in TARGETS for kind in STATS_KINDS)
STATS_TOLERANCE = 1e-3

_RUN_ID = re.compile(r"season-\d{4}-[0-9a-f]{16,}")
#: Hex digests (model versions, source/manifest hashes, hash-prefixed keys). Needs
#: a digit and a letter so plain numbers and ordinary words never match.
_HASH = re.compile(r"(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{12,}")
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")

Row = dict[str, Any]
Tables = dict[str, list[Row]]


@dataclass
class ParityReport:
    mode: str
    completed_week: int
    upcoming_week: int
    failures: list[str] = field(default_factory=list)
    compared: dict[str, int] = field(default_factory=dict)
    upcoming_games: int = 0
    upcoming_predicted: int = 0
    upcoming_lined: int = 0
    accepted_cutoff_corrections: list[int] = field(default_factory=list)
    accepted_retrospective_games: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "completed_week": self.completed_week,
            "upcoming_week": self.upcoming_week,
            "passed": self.passed,
            "failures": self.failures,
            "rows_compared": self.compared,
            "upcoming_week_games": self.upcoming_games,
            "upcoming_week_predicted": self.upcoming_predicted,
            "upcoming_week_lined": self.upcoming_lined,
            "accepted_cutoff_corrections": self.accepted_cutoff_corrections,
            "accepted_retrospective_games": self.accepted_retrospective_games,
        }


# --- value normalization ---------------------------------------------------


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")


def normalize_value(value: Any) -> Any:
    """A comparable form: run ids and hashes masked, UTC timestamps, float numbers.

    Masking applies to row keys as well as values, so rows whose key embeds a
    release-specific hash (``<hash>@<period>``, ``<year>:<kind>:<hash>:<hash>``)
    still pair up between releases.
    """
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, int):
        return float(value)
    if isinstance(value, datetime):
        return _timestamp(value)
    if isinstance(value, str):
        if _TIMESTAMP.match(value):
            try:
                return _timestamp(datetime.fromisoformat(value.replace("Z", "+00:00")))
            except ValueError:
                pass
        return _HASH.sub("<hash>", _RUN_ID.sub("<run>", value))
    if isinstance(value, (list, tuple)):
        return [normalize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: normalize_value(item) for key, item in value.items()}
    return value


def values_equal(left: Any, right: Any) -> bool:
    if isinstance(left, float) and isinstance(right, float):
        if math.isnan(left) and math.isnan(right):
            return True
        return abs(left - right) <= TOLERANCE
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(map(values_equal, left, right))
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(
            values_equal(left[k], right[k]) for k in left
        )
    return left == right


def is_identity_column(column: str) -> bool:
    return (
        column in STAMP_COLUMNS
        or column in IDENTITY_COLUMNS
        or column.endswith(IDENTITY_SUFFIXES)
    )


# --- row comparison --------------------------------------------------------


def _key(table: str, row: Row) -> tuple:
    return tuple(normalize_value(row[column]) for column in PROJECTION_KEYS[table])


def _label(table: str, key: tuple) -> str:
    parts = (int(p) if isinstance(p, float) and p.is_integer() else p for p in key)
    return f"{table} {'/'.join(map(str, parts))}"


def _within(value: Any, span: tuple[float, float]) -> bool:
    return isinstance(value, float) and span[0] <= value <= span[1]


def _tied_rank_spans(old: dict[tuple, Row]) -> dict[tuple, tuple[float, float]]:
    """Rank span of each ``team_resume`` row's group of tied ``sor`` values.

    Within a period, teams whose ``sor`` values chain within ``TOLERANCE`` of each
    other (exactly equal, or equal up to platform rounding such as a clamped 0.0
    next to 1.1e-14) are tied. Their relative order is decided by rounding noise,
    so ``sor_rank`` may permute inside the group's span of previous ranks, and
    nowhere else.
    """
    by_period: dict[Any, list[tuple[float, float, tuple]]] = {}
    for key, row in old.items():
        sor, rank = (
            normalize_value(row.get("sor")),
            normalize_value(row.get("sor_rank")),
        )
        if isinstance(sor, float) and isinstance(rank, float):
            by_period.setdefault(key[0], []).append((sor, rank, key))
    spans: dict[tuple, tuple[float, float]] = {}
    for rows in by_period.values():
        rows.sort(key=lambda item: -item[0])
        group: list[tuple[float, float, tuple]] = []
        for item in [*rows, None]:
            if group and (item is None or group[-1][0] - item[0] > TOLERANCE):
                span = (min(r[1] for r in group), max(r[1] for r in group))
                spans.update({r[2]: span for r in group})
                group = []
            if item is not None:
                group.append(item)
    return spans


def compare_rows(
    table: str,
    previous: list[Row],
    candidate: list[Row],
    *,
    ignore: frozenset[str] = frozenset(),
) -> list[str]:
    """One message per missing, extra or changed row; columns named, values not."""
    old = {_key(table, row): row for row in previous}
    new = {_key(table, row): row for row in candidate}
    problems = [
        f"{_label(table, key)}: missing from the candidate"
        for key in sorted(old.keys() - new.keys(), key=str)
    ]
    problems += [
        f"{_label(table, key)}: new in the candidate"
        for key in sorted(new.keys() - old.keys(), key=str)
    ]
    tied = _tied_rank_spans(old) if table == "team_resume" else {}
    for key in sorted(old.keys() & new.keys(), key=str):
        columns = (old[key].keys() | new[key].keys()) - ignore
        changed = sorted(
            column
            for column in columns
            if not is_identity_column(column)
            and not values_equal(
                normalize_value(old[key].get(column)),
                normalize_value(new[key].get(column)),
            )
            and not (
                column == "sor_rank"
                and key in tied
                and _within(normalize_value(new[key].get(column)), tied[key])
            )
        )
        if changed:
            problems.append(f"{_label(table, key)}: changed columns {changed}")
    return problems


def _game_weeks(*tables: Tables) -> dict[Any, int]:
    weeks: dict[Any, int] = {}
    for release in tables:
        for row in release.get("games", []):
            weeks[row["game_id"]] = int(row["week"])
    return weeks


def _snapshot_games(*tables: Tables) -> dict[str, Any]:
    games: dict[str, Any] = {}
    for release in tables:
        for row in release.get("market_snapshots", []):
            games[normalize_value(row["snapshot_id"])] = row["game_id"]
    return games


def _row_game(table: str, row: Row, snapshot_games: dict[str, Any]) -> Any:
    if "game_id" in row:
        return row["game_id"]
    if table == "market_snapshot_quotes":
        return snapshot_games.get(normalize_value(row["snapshot_id"]))
    return None


# --- one-off retrospective lines -----------------------------------------------


def _retrospective_problems(candidate: Tables, game: str) -> list[str]:
    """Why the candidate's rows for ``game`` are not complete CFBD retrospective rows."""

    def mine(table: str) -> list[Row]:
        return [r for r in candidate.get(table, []) if str(r["game_id"]) == game]

    quotes = {r["quote_id"] for r in mine("market_quotes")}
    snapshots = {r["snapshot_id"] for r in mine("market_snapshots")}
    problems = [f"{t} has no rows" for t in RETROSPECTIVE_ROW_TABLES if not mine(t)]
    for grade in mine("prediction_grades"):
        if (
            grade.get("grading_version") != RETROSPECTIVE_GRADING_VERSION
            or grade.get("target") not in TARGETS
            or grade.get("market_quote_id") not in quotes
            or grade.get("market_snapshot_id") not in snapshots
        ):
            problems.append(f"{grade.get('target')} grade is not a retrospective grade")
    for pick in mine("prediction_market_selections"):
        if (
            pick.get("quote_id") not in quotes
            or pick.get("snapshot_id") not in snapshots
        ):
            problems.append(f"{pick.get('target')} selection cites a foreign quote")
    for pred in mine("predictions"):
        if pred.get("market_snapshot_id") not in snapshots | {None}:
            problems.append("prediction cites a foreign snapshot")
    return problems


def _system_stats_problems(
    previous: Tables, candidate: Tables, grades: list[Row]
) -> list[str]:
    """``system_stats`` columns that moved by anything but the new grades."""
    outcome = {"win": "wins", "loss": "losses", "push": "pushes"}
    expected = dict.fromkeys(STATS_COLUMNS, 0.0)
    for grade in (g for g in grades if g.get("target") in TARGETS):
        if grade.get("result") in outcome:
            expected[f"{grade['target']}_{outcome[grade['result']]}"] += 1
        expected[f"{grade['target']}_profit_units"] += float(
            grade.get("profit_units") or 0.0
        )
    before = {r["season"]: r for r in previous.get("system_stats", [])}
    return [
        f"system_stats {column} moved {moved:+g}, not {expected[column]:+g}"
        for row in candidate.get("system_stats", [])
        if row["season"] in before
        for column in sorted(STATS_COLUMNS)
        for moved in [float(row[column]) - float(before[row["season"]][column])]
        if abs(moved - expected[column]) > STATS_TOLERANCE
    ]


def _reset_columns(
    previous: list[Row], candidate: list[Row], key: str, keys: set[str], columns
) -> list[Row]:
    """Candidate rows whose ``key`` is in ``keys`` take ``columns`` from ``previous``."""
    before = {str(r[key]): r for r in previous}
    return [
        {**r, **{c: before[str(r[key])].get(c) for c in columns & r.keys()}}
        if str(r[key]) in keys and str(r[key]) in before
        else r
        for r in candidate
    ]


def _accept_retrospective_lines(
    previous: Tables, candidate: Tables, report: ParityReport
) -> Tables:
    """The candidate with the retrospective-line additions reset to ``previous``.

    Only games the active release holds no market rows for qualify. Their new rows
    must be complete and cite only each other, and ``system_stats`` must move by
    exactly their grades. Any problem is a failure and the candidate is returned
    untouched, so the strict comparison reports the same rows as well.
    """
    held = {
        str(r["game_id"]) for t in RETROSPECTIVE_ROW_TABLES for r in previous.get(t, [])
    }
    graded = {str(r["game_id"]) for r in candidate["prediction_grades"]}
    fresh = graded & (RETROSPECTIVE_GAMES - held)
    if not fresh:
        return candidate
    grades = [r for r in candidate["prediction_grades"] if str(r["game_id"]) in fresh]
    problems = [
        f"retrospective game {game}: {problem}"
        for game in sorted(fresh)
        for problem in _retrospective_problems(candidate, game)
    ] + _system_stats_problems(previous, candidate, grades)
    if problems:
        report.failures += problems
        return candidate
    report.accepted_retrospective_games = sorted(fresh)
    snapshots = {
        r["snapshot_id"]
        for r in candidate["market_snapshots"]
        if str(r["game_id"]) in fresh
    }
    out = {
        table: [r for r in candidate[table] if str(r["game_id"]) not in fresh]
        for table in RETROSPECTIVE_ROW_TABLES
    }
    out["market_snapshot_quotes"] = [
        r
        for r in candidate.get("market_snapshot_quotes", [])
        if r["snapshot_id"] not in snapshots
    ]
    for table, columns in (
        ("games", MARKET_COLUMNS),
        ("predictions", MARKET_COLUMNS),
        ("game_results", RESULT_COLUMNS),
    ):
        out[table] = _reset_columns(
            previous.get(table, []), candidate.get(table, []), "game_id", fresh, columns
        )
    out["system_stats"] = _reset_columns(
        previous.get("system_stats", []),
        candidate.get("system_stats", []),
        "season",
        {str(r["season"]) for r in candidate.get("system_stats", [])},
        STATS_COLUMNS,
    )
    return {**candidate, **out}


#: Overtime-inclusive success counts added to ``team_game_stats`` by migration 0029,
#: with the regulation counts each must not fall below.
OVERTIME_COLUMNS = {
    "off_success_ot_n": "off_success_n",
    "off_success_ot_sum": "off_success_sum",
}


def _accept_overtime_columns(
    previous: Tables, candidate: Tables, report: ParityReport
) -> Tables:
    """The candidate with first-time overtime success counts reset to ``previous``.

    A candidate value may differ only where the active release holds NULL for it
    (a release built before migration 0029). Every candidate row must carry both
    counts and not fall below its regulation counts. A value the active release
    already holds, and every other column, still compares strictly.
    """
    rows = candidate.get("team_game_stats")
    if not rows:
        return candidate
    old = {_key("team_game_stats", r): r for r in previous.get("team_game_stats", [])}
    problems, out = [], []
    for row in rows:
        key = _key("team_game_stats", row)
        for column, floor in OVERTIME_COLUMNS.items():
            value, base = row.get(column), row.get(floor)
            if value is None:
                problems.append(f"{_label('team_game_stats', key)}: {column} is NULL")
            elif base is not None and value < base:
                problems.append(
                    f"{_label('team_game_stats', key)}: {column} is below {floor}"
                )
        held = old.get(key)
        if held is None:
            out.append(row)
            continue
        reset = {c: held.get(c) for c in OVERTIME_COLUMNS if held.get(c) is None}
        out.append({**row, **reset})
    report.failures += problems
    return {**candidate, "team_game_stats": out}


# --- the two modes -----------------------------------------------------------


def _check_close_week(
    previous: Tables, candidate: Tables, report: ParityReport, weeks: dict[Any, int]
) -> None:
    stable = report.completed_week - 1

    def game_stable(row: Row) -> bool:
        return weeks.get(row["game_id"], 10**6) <= stable

    scopes = {
        "predictions": game_stable,
        "prediction_grades": game_stable,
        "v5_rating_snapshots": lambda row: (
            row["snapshot_class"] == "pregame" and int(row["week"]) <= stable
        ),
    }
    corrected = set(report.accepted_cutoff_corrections)

    def corrected_snapshot(row: Row) -> bool:
        return int(row["week"]) in corrected

    for table, keep in scopes.items():
        old = [row for row in previous[table] if keep(row)]
        new = [row for row in candidate[table] if keep(row)]
        report.compared[table] = len(old)
        if table != "v5_rating_snapshots" or not corrected:
            report.failures += compare_rows(table, old, new)
            continue
        # Only the named weeks' cutoffs may move; their values stay strict.
        for in_corrected in (False, True):
            report.failures += compare_rows(
                table,
                [r for r in old if corrected_snapshot(r) == in_corrected],
                [r for r in new if corrected_snapshot(r) == in_corrected],
                ignore=frozenset({"cutoff_utc"}) if in_corrected else frozenset(),
            )


def _check_market_refresh(
    previous: Tables, candidate: Tables, report: ParityReport, weeks: dict[Any, int]
) -> None:
    upcoming = report.upcoming_week
    snapshot_games = _snapshot_games(previous, candidate)

    def in_upcoming(table: str, row: Row) -> bool:
        return weeks.get(_row_game(table, row, snapshot_games)) == upcoming

    def upcoming_row(table: str, row: Row) -> bool:
        week = row.get("week", row.get("as_of_week"))
        if week is None:
            week = row.get("as_of_week")
        if week is not None:
            return int(week) == upcoming
        return in_upcoming(table, row)

    for table in sorted(previous.keys() & candidate.keys()):
        old, new = previous[table], candidate[table]
        report.compared[table] = len(old)
        if table in MARKET_TABLES:
            # The upcoming week's market rows are the refresh itself.
            report.failures += compare_rows(
                table,
                [r for r in old if not in_upcoming(table, r)],
                [r for r in new if not in_upcoming(table, r)],
            )
        elif table in ("games", "predictions"):
            for upcoming_rows in (False, True):
                report.failures += compare_rows(
                    table,
                    [r for r in old if in_upcoming(table, r) == upcoming_rows],
                    [r for r in new if in_upcoming(table, r) == upcoming_rows],
                    ignore=MARKET_COLUMNS if upcoming_rows else frozenset(),
                )
        else:
            # ``cutoff_utc`` legitimately moves to the refresh time for the
            # upcoming week's pregame rows (its quotes are newer); every other
            # week's cutoff, and every value column, must still match.
            for upcoming_rows in (False, True):
                report.failures += compare_rows(
                    table,
                    [r for r in old if upcoming_row(table, r) == upcoming_rows],
                    [r for r in new if upcoming_row(table, r) == upcoming_rows],
                    ignore=frozenset({"cutoff_utc"}) if upcoming_rows else frozenset(),
                )


def _check_upcoming_coverage(
    candidate: Tables, report: ParityReport, weeks: dict[Any, int]
) -> None:
    games = {g for g, week in weeks.items() if week == report.upcoming_week}
    predictions = {
        row["game_id"]: row
        for row in candidate["predictions"]
        if row["game_id"] in games
    }
    predicted = {
        g
        for g, row in predictions.items()
        if row.get("predicted_spread") is not None
        and row.get("predicted_total") is not None
    }
    report.upcoming_games = len(games)
    report.upcoming_predicted = len(predicted)
    report.upcoming_lined = sum(
        1
        for row in predictions.values()
        if row.get("home_team_spread_line") is not None
        and row.get("total_line") is not None
    )
    if not games:
        report.failures.append(f"week {report.upcoming_week}: candidate has no games")
    elif predicted != games:
        missing = sorted(games - predicted, key=str)
        report.failures.append(
            f"week {report.upcoming_week}: {len(predicted)} of {len(games)} games "
            f"predicted; unpredicted games {missing}"
        )


def compare_releases(
    previous: Tables,
    candidate: Tables,
    *,
    mode: str,
    completed_week: int,
    upcoming_week: int,
    accept_cutoff_corrections: tuple[int, ...] = (),
    retrospective_lines: bool = False,
) -> ParityReport:
    """Pure parity decision over two ``{table: [row, ...]}`` structures."""
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}")
    report = ParityReport(mode, completed_week, upcoming_week)
    if accept_cutoff_corrections:
        if mode != "close-week":
            raise ValueError("cutoff corrections apply to close-week only")
        bad = [w for w in accept_cutoff_corrections if not 0 <= w < completed_week]
        if bad:
            raise ValueError(
                f"cutoff correction weeks {bad} are not before week {completed_week}"
            )
        report.accepted_cutoff_corrections = sorted(set(accept_cutoff_corrections))
    for table in REQUIRED_TABLES:
        for name, release in (("active release", previous), ("candidate", candidate)):
            if table not in release:
                report.failures.append(f"{name} lacks table {table}")
    if report.failures:
        return report
    if retrospective_lines:
        candidate = _accept_retrospective_lines(previous, candidate, report)
    candidate = _accept_overtime_columns(previous, candidate, report)
    weeks = _game_weeks(previous, candidate)
    check = _check_close_week if mode == "close-week" else _check_market_refresh
    check(previous, candidate, report, weeks)
    _check_upcoming_coverage(candidate, report, weeks)
    return report


# --- IO ----------------------------------------------------------------------


def load_candidate(candidate_dir: Path) -> Tables:
    payload = json.loads((candidate_dir / "serving-projections.json").read_text())
    return {table: rows for table, rows in payload.items() if table in PROJECTION_KEYS}


def read_active_preview(conn) -> Tables:
    """Rows of the active Preview release's recorded tables, release columns dropped."""
    from psycopg import sql

    with conn.cursor() as cur:
        cur.execute(
            "SELECT release_id, projection_checks FROM season_releases "
            "WHERE environment = 'preview' AND status = 'active' "
            "ORDER BY season DESC LIMIT 1"
        )
        found = cur.fetchone()
        if found is None:
            raise SystemExit("no active Preview release")
        release_id, checks = found
        release: Tables = {}
        for table in sorted(set(checks) & set(PROJECTION_KEYS)):
            cur.execute(
                sql.SQL("SELECT * FROM {} WHERE release_id = %s").format(
                    sql.Identifier("season_release_" + table)
                ),
                (release_id,),
            )
            names = [column.name for column in cur.description]
            release[table] = [
                {
                    name: value
                    for name, value in zip(names, row, strict=True)
                    if name not in ("release_id", "environment")
                }
                for row in cur.fetchall()
            ]
    return release


def carries_historical_lines(candidate_dir: Path) -> bool:
    """Whether the candidate's revision manifest pins the ``historical_lines`` input."""
    path = candidate_dir / "revision-manifest.json"
    # No manifest means no allowance: the comparison stays strict.
    return (
        path.exists() and "historical_lines" in json.loads(path.read_text())["inputs"]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-dir", type=Path, required=True)
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--completed-week", type=int, required=True)
    parser.add_argument("--upcoming-week", type=int, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--accept-cutoff-correction",
        type=int,
        action="append",
        default=[],
        metavar="WEEK",
        help="close-week only: allow WEEK's pregame snapshot cutoff_utc to differ",
    )
    args = parser.parse_args(argv)
    if args.accept_cutoff_correction and args.mode != "close-week":
        parser.error("--accept-cutoff-correction applies to close-week only")
    import psycopg

    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL is required (Preview database, read-only use)")
        return 2
    candidate = load_candidate(args.candidate_dir)
    with psycopg.connect(url) as conn:
        conn.read_only = True
        previous = read_active_preview(conn)
    report = compare_releases(
        previous,
        candidate,
        mode=args.mode,
        completed_week=args.completed_week,
        upcoming_week=args.upcoming_week,
        accept_cutoff_corrections=tuple(args.accept_cutoff_correction),
        retrospective_lines=carries_historical_lines(args.candidate_dir),
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    summary = report.as_dict()
    print(
        f"parity {'PASS' if report.passed else 'FAIL'} mode={summary['mode']} "
        f"week={args.upcoming_week} predicted={report.upcoming_predicted}/"
        f"{report.upcoming_games} lined={report.upcoming_lined}"
    )
    for failure in report.failures[:50]:
        print(f"  {failure}")
    if len(report.failures) > 50:
        print(f"  ... {len(report.failures) - 50} more in the report")
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
