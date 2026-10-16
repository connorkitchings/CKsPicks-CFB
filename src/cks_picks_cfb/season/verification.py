"""Step 2 verification report ``season_verification_v2`` (owner: P3).

Every check is COMPUTED, never self-reported. Projection checks are pure functions of
the serving-projection payload plus the run identity, so staging re-derives them
from the exact payload bytes it inserts (:func:`validate_report`). Prepare checks
are pure functions of the prepared frames; they cannot be re-derived at staging and
are bound to the run by the verification sha in the run manifest.

Check entry schema::

    {"passed": bool, "observed": {...}, "source": "projection" | "prepare"}

``observed`` is a small deterministic summary that always contains ``violations``
(int) and ``examples`` (the first five sorted violation strings), plus check-specific
counts. Report schema (see also :mod:`cks_picks_cfb.season.projection_common`)::

    {
      "schema_version": "season_verification_v2",
      "state": "passed",
      "identity": {...run identity...},
      "output_refs": {name: {"uri", "logical_uri", "sha256", "rows"}},
      "checks": {name: check_entry},   # keys == REQUIRED_PROJECTION_CHECKS
                                       #       | REQUIRED_PREPARE_CHECKS
      "projection_checks": {table: {"rows": int, "sha256": str}},
      "row_counts": {table: int},
    }

Derivation context
------------------
Projection checks need the run context. It is derived (never trusted) from the run
``identity`` and ``output_refs`` (:func:`context_from_manifest`):

* ``release_id`` = :func:`run_id_for` ``(identity)``;
* ``season``, ``through_week``, ``active_week``, ``as_of``, ``next_week_mode`` from
  ``identity``;
* ``identities`` = :func:`lineage_identities` ``(identity, output_refs)`` =
  ``{"rating": projection_common.rating_identity(...),
  "measurement": projection_common.measurement_identity(...)}``. The run manifest
  stores the same value as ``manifest["identities"]``; when present it must match.

Payload conventions these checks assume (builders must satisfy them)
--------------------------------------------------------------------
* ``prediction_market_selections.point`` is home-signed for spreads (the
  ``games``/``predictions.home_team_spread_line``) and the total for totals; it
  equals the linked quote's ``spread``/``total``. ``price`` equals the quote's
  side price, or -110 when the quote has none (``market_grading._side_price``).
* A selection's benchmark is the suffix of its grade's ``grading_version``
  (``retained_prekickoff`` / ``cfbd_retrospective``). Retained (and ungraded
  live-week) selections use a quote captured strictly before kickoff.
* ``system_stats.as_of_week`` is the latest week with a graded game, ``0`` when
  nothing is graded (legacy ``score_to_db``: ``COALESCE(MAX(g.week), 0)``).
* Stats/measurement tables use ``games`` (provider) team names; rating tables use
  canonical names and ``team_rating_components.rating_team`` matches
  ``v5_rating_snapshots.team``.
* ``predictions.regime`` is ``features.regimes.completed_game_regime`` or
  ``upcoming_game_regime`` of ``min(home_completed_games, away_completed_games)``.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from functools import cached_property
from typing import Any

from cks_picks_cfb.season.inputs import score_reconciliation_problems
from cks_picks_cfb.season.projection_common import (
    MARKET_POLICY_VERSION,
    PROJECTION_ORDER,
    SELECTION_POLICY_VERSION,
    SERVER_COLUMNS,
    benchmark_grading_version,
    canonical_bytes,
    measurement_identity,
    quantize4,
    rating_identity,
    sha256_hex,
    weekly_run_id,
)

SCHEMA_VERSION = "season_verification_v2"

REQUIRED_PROJECTION_CHECKS: frozenset[str] = frozenset(
    {
        "tables_complete",
        "weeks_and_slate",
        "predictions_in_games",
        "prior_finals_complete",
        "grades_recomputed",
        "selection_matches_prediction",
        "market_links",
        "system_stats_match",
        "rating_lineage",
        "rating_snapshots",
        "stats_games",
        "completed_counts_regime",
        "matchup_publication",
        "venues_cover",
        "team_chart_reconciliation",
    }
)
REQUIRED_PREPARE_CHECKS: frozenset[str] = frozenset(
    {
        "required_prior_week_data",
        "score_reconciliation",
        "earlier_week_only",
        "fixed_model_no_refit",
        "no_market_in_features",
        "ratings_equal_features",
        "paired_predictions",
        "checksums_at_read",
    }
)
REQUIRED_CHECKS = REQUIRED_PROJECTION_CHECKS | REQUIRED_PREPARE_CHECKS
PAYLOAD_TABLES = frozenset({"prediction_runs", *PROJECTION_ORDER})

#: The accepted B2 bridge bytes (``manifest.validate_model`` pins the same value).
PINNED_BRIDGE_SHA256 = (
    "a507d0c7cba5419868eac5c0955853d3e2855fc857aabf36f5cd192d5e7a90f1"
)
BENCHMARK_TYPES = ("retained_prekickoff", "cfbd_retrospective")
MATCHUP_TABLES = (
    "team_game_measurements",
    "team_possession_stats",
    "team_possession_adjusted",
    "team_rating_components",
)
#: Tables that must be non-empty in every release / once a week has completed.
REQUIRED_NONEMPTY = (
    "prediction_runs",
    "games",
    "predictions",
    "site_week_selections",
    "system_stats",
    "v5_rating_snapshots",
)
FOOTBALL_NONEMPTY = ("team_season_stats", *MATCHUP_TABLES, "matchup_data_publications")
#: Feature/bridge column-name fragments that would indicate market information.
MARKET_TOKENS = (
    "line",
    "price",
    "quote",
    "snapshot",
    "provider",
    "market",
    "odds",
    "consensus",
    "moneyline",
    "spread",
    "vig",
)
AVAILABILITY = timedelta(hours=6)
RATING_TOLERANCE = 1e-12
FLOAT_TOLERANCE = 1e-9
_HEX64 = re.compile(r"[0-9a-f]{64}")
_PREDICTION_GAME_COLUMNS = (
    "home_team_spread_line",
    "total_line",
    "predicted_spread",
    "predicted_total",
    "predicted_spread_std_dev",
    "predicted_total_std_dev",
    "spread_lean",
    "total_lean",
    "edge_spread",
    "edge_total",
    "high_confidence",
)
_GAME_ONLY_PREDICTION_COLUMNS = ("source_config", "system_name", "model_id")
_SIDES = {"spread": ("home", "away"), "total": ("over", "under")}
#: target -> (line column, lean column, edge column, prediction column)
_TARGET_COLUMNS = {
    "spread": (
        "home_team_spread_line",
        "spread_lean",
        "edge_spread",
        "predicted_spread",
    ),
    "total": ("total_line", "total_lean", "edge_total", "predicted_total"),
}


class VerificationError(ValueError):
    """A season verification report or its derivation context is invalid."""


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------


def run_id_for(identity: Mapping[str, Any]) -> str:
    """The prepared run id (``release_id`` in the run manifest) of ``identity``."""
    return (
        f"season-{identity['season']}-"
        + sha256_hex(canonical_bytes(dict(identity)))[:24]
    )


def lineage_identities(
    identity: Mapping[str, Any], output_refs: Mapping[str, Mapping[str, Any]]
) -> dict[str, str]:
    """``{"rating": ..., "measurement": ...}`` from the prepared output shas."""
    shas = {name: ref["sha256"] for name, ref in output_refs.items()}
    return {
        "rating": rating_identity(
            model_sha=identity["model_manifest_sha256"],
            revision_sha=identity["revision_manifest_sha256"],
            workflow=identity["workflow_version"],
            output_shas=shas,
        ),
        "measurement": measurement_identity(
            revision_sha=identity["revision_manifest_sha256"], output_shas=shas
        ),
    }


def context_from_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Derivation context from ``manifest["identity"]`` and ``["output_refs"]``.

    Any ``release_id`` / ``identities`` the manifest also carries must agree.
    """
    try:
        identity = manifest["identity"]
        context = {
            "release_id": run_id_for(identity),
            "season": int(identity["season"]),
            "through_week": int(identity["through_week"]),
            "active_week": int(identity["active_week"]),
            "as_of": _ts(identity["as_of"]),
            "next_week_mode": identity["next_week_mode"],
            "identities": lineage_identities(identity, manifest["output_refs"]),
        }
    except (KeyError, TypeError, ValueError) as error:
        raise VerificationError(f"invalid verification context: {error!r}") from error
    for key in ("release_id", "identities"):
        if key in manifest and manifest[key] != context[key]:
            raise VerificationError(f"manifest {key} differs from its identity")
    if context["next_week_mode"] not in {"live", "reconstructed"}:
        raise VerificationError("invalid next_week_mode")
    return context


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _ts(value: Any) -> datetime:
    if isinstance(value, datetime):
        stamp = value
    elif isinstance(value, str):
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise TypeError(f"not a timestamp: {value!r}")
    if stamp.tzinfo is None:
        raise ValueError(f"naive timestamp: {value!r}")
    return stamp


def _close(a: Any, b: Any, tolerance: float = FLOAT_TOLERANCE) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return math.isfinite(float(a)) and abs(float(a) - float(b)) <= tolerance


def _dec(value: Any) -> Decimal:
    return Decimal(str(value))


def _is_count(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _entry(problems: list[str], source: str, **observed: Any) -> dict:
    unique = sorted(set(problems))
    return {
        "passed": not unique,
        "observed": {**observed, "violations": len(unique), "examples": unique[:5]},
        "source": source,
    }


def _run(check: Callable[..., tuple[list[str], dict]], source: str, *args) -> dict:
    """Run one check; malformed data is a failed check, never a crash."""
    try:
        problems, observed = check(*args)
    except (
        KeyError,
        TypeError,
        ValueError,
        AttributeError,
        IndexError,
        InvalidOperation,
    ) as error:
        return _entry([f"{type(error).__name__}: {error}"], source, error=True)
    return _entry(problems, source, **observed)


# ---------------------------------------------------------------------------
# Projection checks (payload only)
# ---------------------------------------------------------------------------


class _Payload:
    def __init__(self, projections: Mapping[str, Any], context: Mapping[str, Any]):
        self.raw = projections
        self.ctx = context
        self.release_id = context["release_id"]
        self.season = context["season"]
        self.through = context["through_week"]
        self.active = context["active_week"]
        self.as_of = context["as_of"]
        self.live_week = (
            self.active
            if self.active > self.through and context["next_week_mode"] == "live"
            else None
        )

    def rows(self, name: str) -> list[dict]:
        return self.raw[name]

    def week_run(self, week: int) -> str:
        return weekly_run_id(self.release_id, week)

    @cached_property
    def games(self) -> dict[int, dict]:
        return {row["game_id"]: row for row in self.rows("games")}

    @cached_property
    def results(self) -> dict[int, dict]:
        return {row["game_id"]: row for row in self.rows("game_results")}

    @cached_property
    def predictions(self) -> dict[tuple, dict]:
        return {(r["run_id"], r["game_id"]): r for r in self.rows("predictions")}

    @cached_property
    def selections(self) -> dict[tuple, dict]:
        return {
            (r["run_id"], r["game_id"], r["target"]): r
            for r in self.rows("prediction_market_selections")
        }

    @cached_property
    def grades(self) -> dict[tuple, dict]:
        return {
            (r["run_id"], r["game_id"], r["target"]): r
            for r in self.rows("prediction_grades")
        }

    @cached_property
    def quotes(self) -> dict[str, dict]:
        return {row["quote_id"]: row for row in self.rows("market_quotes")}

    @cached_property
    def snapshots(self) -> dict[str, dict]:
        return {row["snapshot_id"]: row for row in self.rows("market_snapshots")}

    def completed_before(
        self, team: str, week: int, *, fbs: set | None = None, cutoff=None
    ) -> int:
        """Completed games (with a final) of ``team`` in weeks before ``week``."""
        count = 0
        for game_id in self.results:
            game = self.games.get(game_id)
            if not game or game["week"] >= week:
                continue
            if team not in (game["home_team"], game["away_team"]):
                continue
            if fbs is not None and not {game["home_team"], game["away_team"]} <= fbs:
                continue
            if cutoff is not None and _ts(game["start_date"]) + AVAILABILITY > cutoff:
                continue
            count += 1
        return count


def _tables_complete(p: _Payload) -> tuple[list[str], dict]:
    from cks_picks_cfb.season.release import PROJECTION_KEYS

    keys = {**PROJECTION_KEYS, "prediction_runs": ("run_id",)}
    expected = PAYLOAD_TABLES
    problems = [f"missing table {t}" for t in sorted(expected - set(p.raw))]
    problems += [f"unexpected table {t}" for t in sorted(set(p.raw) - expected)]
    counts: dict[str, int] = {}
    for table in sorted(expected & set(p.raw)):
        rows = p.raw[table]
        if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
            problems.append(f"{table}: rows are not a list of objects")
            continue
        counts[table] = len(rows)
        if len({frozenset(row) for row in rows}) > 1:
            problems.append(f"{table}: rows have differing columns")
        natural = [tuple(row.get(k) for k in keys[table]) for row in rows]
        if any(None in key for key in natural):
            problems.append(f"{table}: natural key column missing or null")
            continue
        if len(set(natural)) != len(natural):
            problems.append(f"{table}: duplicate natural key")
        if natural != sorted(natural):
            problems.append(f"{table}: rows not sorted by natural key")
        if any("season" in row and row["season"] != p.season for row in rows):
            problems.append(f"{table}: foreign season")
    required = REQUIRED_NONEMPTY + (FOOTBALL_NONEMPTY if p.active > 0 else ())
    problems += [f"{t}: empty" for t in required if not counts.get(t)]
    return problems, {"row_counts": counts}


def _weeks_and_slate(p: _Payload) -> tuple[list[str], dict]:
    problems = []
    weeks = range(p.active + 1)
    runs = defaultdict(list)
    for run in p.rows("prediction_runs"):
        runs[run["week"]].append(run)
    if set(runs) != set(weeks):
        problems.append(f"run weeks {sorted(runs)} != 0..{p.active}")
    for week, records in sorted(runs.items()):
        if len(records) != 1:
            problems.append(f"week {week}: {len(records)} runs")
        run = records[0]
        live = week == p.live_week
        expected = {
            "run_id": p.week_run(week),
            "season": p.season,
            "state": "scored" if week <= p.through else "published",
            "evidence_class": "pending" if live else "replay",
            "frozen_at": None,
        }
        problems += [
            f"week {week}: {k}={run.get(k)!r} expected {v!r}"
            for k, v in expected.items()
            if run.get(k) != v
        ]
    by_week = defaultdict(set)
    for game in p.games.values():
        by_week[game["week"]].add(game["game_id"])
    problems += [f"week {w}: no scheduled games" for w in weeks if not by_week[w]]
    predicted = defaultdict(set)
    for (run_id, game_id), _ in p.predictions.items():
        game = p.games.get(game_id)
        if game is None:
            continue  # predictions_in_games
        week = game["week"]
        predicted[week].add(game_id)
        if week > p.active:
            problems.append(f"game {game_id}: predicted beyond active week")
        elif run_id != p.week_run(week):
            problems.append(
                f"game {game_id}: prediction run {run_id} is not week {week}'s"
            )
    for week in weeks:
        missing = by_week[week] - predicted[week]
        if week != p.live_week:
            problems += [f"week {week}: game {g} unpredicted" for g in sorted(missing)]
            continue
        # Live omissions are exactly the games already started at the run as-of.
        for game_id in sorted(by_week[week]):
            started = _ts(p.games[game_id]["start_date"]) <= p.as_of
            if started != (game_id in missing):
                problems.append(f"live game {game_id}: started={started} mismatch")
    selections = p.rows("site_week_selections")
    selected = Counter(row["week"] for row in selections)
    if set(selected) != set(weeks) or any(n != 1 for n in selected.values()):
        problems.append(f"site selections cover {sorted(selected.elements())}")
    for row in selections:
        if row["run_id"] != p.week_run(row["week"]) or row["season"] != p.season:
            problems.append(f"site selection week {row['week']} -> {row['run_id']}")
    return problems, {
        "weeks": len(runs),
        "games": len(p.games),
        "predicted_games": sum(map(len, predicted.values())),
        "live_week": p.live_week,
    }


def _predictions_in_games(p: _Payload) -> tuple[list[str], dict]:
    problems = []
    runs = {row["run_id"]: row for row in p.rows("prediction_runs")}
    per_run = Counter()
    lined = Counter()
    games_seen = Counter()
    for row in p.rows("predictions"):
        per_run[row["run_id"]] += 1
        games_seen[row["game_id"]] += 1
        # Legacy publish_to_db: a lined game carries BOTH a spread and a total line.
        if (
            row.get("home_team_spread_line") is not None
            and row.get("total_line") is not None
        ):
            lined[row["run_id"]] += 1
        if row["game_id"] not in p.games:
            problems.append(f"prediction game {row['game_id']} absent from games")
        if row["run_id"] not in runs:
            problems.append(f"prediction run {row['run_id']} absent from registry")
    if len(p.predictions) != len(p.rows("predictions")):
        problems.append("duplicate (run_id, game_id) prediction")
    problems += [f"game {g}: {n} predictions" for g, n in games_seen.items() if n != 1]
    for run_id, run in runs.items():
        counts = (run["expected_games"], run["predicted_games"], run["lined_games"])
        if not all(_is_count(c) for c in counts):
            problems.append(f"run {run_id}: invalid registry counts")
            continue
        if run["predicted_games"] != per_run[run_id]:
            problems.append(
                f"run {run_id}: predicted_games {run['predicted_games']} != {per_run[run_id]}"
            )
        if run["lined_games"] != lined[run_id]:
            problems.append(
                f"run {run_id}: lined_games {run['lined_games']} != {lined[run_id]}"
            )
        if max(run["predicted_games"], run["lined_games"]) > run["expected_games"]:
            problems.append(f"run {run_id}: counts exceed expected_games")
    return problems, {"predictions": len(p.rows("predictions")), "runs": len(runs)}


def _prior_finals_complete(p: _Payload) -> tuple[list[str], dict]:
    problems = []
    for game_id, game in sorted(p.games.items()):
        if game["week"] <= p.through and game_id not in p.results:
            problems.append(f"completed-week game {game_id} lacks a final")
    for game_id, result in sorted(p.results.items()):
        game = p.games.get(game_id)
        if game is None:
            problems.append(f"result {game_id} has no game")
        elif game["week"] > p.through:
            problems.append(f"result {game_id} is in an uncompleted week")
        if result.get("completion_state") != "completed":
            problems.append(
                f"result {game_id}: completion_state {result.get('completion_state')!r}"
            )
        if not (_is_count(result["home_points"]) and _is_count(result["away_points"])):
            problems.append(f"result {game_id}: invalid final score")
    return problems, {"finals": len(p.results)}


def _benchmark(grade: Mapping | None) -> str | None:
    if grade is None:
        return None
    for benchmark in BENCHMARK_TYPES:
        if grade.get("grading_version") == benchmark_grading_version(benchmark):
            return benchmark
    return "invalid"


def _grades_recomputed(p: _Payload) -> tuple[list[str], dict]:
    from cks_picks_cfb.models.market_grading import settle_quote

    problems = []
    results_by_target = Counter()
    for key, grade in sorted(p.grades.items()):
        run_id, game_id, target = key
        selection = p.selections.get(key)
        result = p.results.get(game_id)
        if selection is None or result is None:
            problems.append(f"grade {key} lacks a selection or final")
            continue
        if _benchmark(grade) == "invalid":
            problems.append(
                f"grade {key}: grading_version {grade.get('grading_version')!r}"
            )
        for column, source in (
            ("side", "side"),
            ("market_quote_id", "quote_id"),
            ("market_snapshot_id", "snapshot_id"),
        ):
            if grade.get(column) != selection[source]:
                problems.append(f"grade {key}: {column} differs from selection")
        home, away = result["home_points"], result["away_points"]
        point = float(selection["point"])
        if target == "spread" and selection["side"] == "away":
            point = -point  # settlement takes the selected-side spread
        units = settle_quote(
            target=target,
            direction=selection["side"],
            actual_spread=float(home - away),
            actual_total=float(home + away),
            point=point,
            price=selection["price"],
        )
        expected = "win" if units > 0 else "loss" if units < 0 else "push"
        results_by_target[(target, expected)] += 1
        if grade["result"] != expected:
            problems.append(
                f"grade {key}: result {grade['result']!r} expected {expected!r}"
            )
        profit = grade["profit_units"]
        if (
            isinstance(profit, bool)
            or _dec(profit) != _dec(quantize4(profit))
            or quantize4(profit) != quantize4(units)
        ):
            problems.append(
                f"grade {key}: profit_units {profit!r} expected {quantize4(units)!r}"
            )
    for key, selection in sorted(p.selections.items()):
        if key[1] in p.results and key not in p.grades:
            problems.append(f"final selection {key} is ungraded")
    for game_id, result in sorted(p.results.items()):
        game = p.games.get(game_id)
        for target in ("spread", "total"):
            stored = result.get(f"{target}_result")
            if stored is None:
                continue
            grade = (
                p.grades.get((p.week_run(game["week"]), game_id, target))
                if game
                else None
            )
            if grade is None or grade["result"] != stored:
                problems.append(
                    f"result {game_id}: {target}_result {stored!r} differs from grade"
                )
    return problems, {
        "grades": len(p.grades),
        "results": {f"{t}:{r}": n for (t, r), n in sorted(results_by_target.items())},
    }


def _selection_matches_prediction(p: _Payload) -> tuple[list[str], dict]:
    problems = []
    for (run_id, game_id), prediction in sorted(p.predictions.items()):
        for target, (line_col, lean_col, edge_col, pred_col) in _TARGET_COLUMNS.items():
            selection = p.selections.get((run_id, game_id, target))
            line, lean, edge = (
                prediction.get(c) for c in (line_col, lean_col, edge_col)
            )
            label = f"prediction {game_id} {target}"
            if selection is None:
                if (line, lean, edge) != (None, None, None):
                    problems.append(f"{label}: line/lean/edge without selection")
                continue
            point = selection["point"]
            mean = prediction[pred_col]
            expected_edge = (
                abs(mean + point) if target == "spread" else abs(mean - point)
            )
            if line != point or lean != selection["side"] or lean not in _SIDES[target]:
                problems.append(f"{label}: line/lean differ from selection")
            if not (
                _close(edge, expected_edge) and _close(selection["edge"], expected_edge)
            ):
                problems.append(f"{label}: edge differs from |prediction vs point|")
    for key in sorted(p.selections):
        if key[:2] not in p.predictions:
            problems.append(f"selection {key} has no prediction")
    predicted = {game_id: row for (_, game_id), row in p.predictions.items()}
    for game_id, game in sorted(p.games.items()):
        prediction = predicted.get(game_id)
        if prediction is None:
            nullable = set(_PREDICTION_GAME_COLUMNS + _GAME_ONLY_PREDICTION_COLUMNS)
            nullable.discard("high_confidence")
            carried = any(game.get(c) is not None for c in nullable)
            if carried or game.get("high_confidence") is not False:
                problems.append(
                    f"unpredicted game {game_id} carries prediction columns"
                )
        elif any(game.get(c) != prediction.get(c) for c in _PREDICTION_GAME_COLUMNS):
            problems.append(
                f"game {game_id}: prediction columns differ from predictions"
            )
    return problems, {"selections": len(p.selections)}


def _market_links(p: _Payload) -> tuple[list[str], dict]:
    from cks_picks_cfb.models.market_grading import _side_price

    problems = []
    for quote_id, quote in sorted(p.quotes.items()):
        if quote["game_id"] not in p.games:
            problems.append(f"quote {quote_id}: game absent")
        if _ts(quote["captured_at"]) > p.as_of:
            problems.append(f"quote {quote_id}: captured after run as-of")
        if quote.get("spread") is None and quote.get("total") is None:
            problems.append(f"quote {quote_id}: no spread or total")
    for snapshot_id, snapshot in sorted(p.snapshots.items()):
        if snapshot["game_id"] not in p.games:
            problems.append(f"snapshot {snapshot_id}: game absent")
        if _ts(snapshot["captured_at"]) > p.as_of:
            problems.append(f"snapshot {snapshot_id}: captured after run as-of")
        if snapshot["policy_version"] != MARKET_POLICY_VERSION:
            problems.append(f"snapshot {snapshot_id}: policy_version")
        sources = snapshot["source_quote_ids"]
        if not isinstance(sources, list) or any(
            p.quotes.get(q, {}).get("game_id") != snapshot["game_id"] for q in sources
        ):
            problems.append(f"snapshot {snapshot_id}: source quotes absent or foreign")
    links = set()
    for link in p.rows("market_snapshot_quotes"):
        key = (link["snapshot_id"], link["quote_id"], link["target"])
        links.add(key)
        snapshot, quote = p.snapshots.get(key[0]), p.quotes.get(key[1])
        if snapshot is None or quote is None:
            problems.append(f"link {key}: snapshot or quote absent")
        elif quote["game_id"] != snapshot["game_id"]:
            problems.append(f"link {key}: quote and snapshot games differ")
        elif key[2] not in ("spread", "total") or quote.get(key[2]) is None:
            problems.append(f"link {key}: quote has no {key[2]} point")
    for key, selection in sorted(p.selections.items()):
        run_id, game_id, target = key
        game = p.games.get(game_id)
        quote = p.quotes.get(selection["quote_id"])
        snapshot = p.snapshots.get(selection["snapshot_id"])
        if game is None or quote is None or snapshot is None:
            problems.append(f"selection {key}: game, quote or snapshot absent")
            continue
        if quote["game_id"] != game_id or snapshot["game_id"] != game_id:
            problems.append(f"selection {key}: quote/snapshot belongs to another game")
        if (selection["snapshot_id"], selection["quote_id"], target) not in links:
            problems.append(f"selection {key}: quote not linked to snapshot for target")
        if selection["policy_version"] != SELECTION_POLICY_VERSION:
            problems.append(f"selection {key}: policy_version")
        if selection["point"] != quote.get(target):
            problems.append(f"selection {key}: point differs from quote")
        if selection["side"] not in _SIDES[target]:
            problems.append(f"selection {key}: side {selection['side']!r}")
        elif selection["price"] != _side_price(quote, selection["side"], target):
            problems.append(f"selection {key}: price differs from quote side price")
        if not selection["edge"] >= 0:
            problems.append(f"selection {key}: negative edge")
        benchmark = _benchmark(p.grades.get(key))
        live = game["week"] == p.live_week
        if benchmark == "invalid":
            problems.append(f"selection {key}: invalid benchmark")
        if benchmark == "cfbd_retrospective" and (live or game["week"] > p.through):
            problems.append(f"selection {key}: retrospective line outside scored weeks")
        if benchmark == "retained_prekickoff" or (benchmark is None and live):
            if _ts(quote["captured_at"]) >= _ts(game["start_date"]):
                problems.append(
                    f"selection {key}: retained quote captured at/after kickoff"
                )
    for (run_id, game_id), prediction in sorted(p.predictions.items()):
        snapshot_id = prediction.get("market_snapshot_id")
        if (
            snapshot_id is not None
            and p.snapshots.get(snapshot_id, {}).get("game_id") != game_id
        ):
            problems.append(
                f"prediction {game_id}: market_snapshot_id absent or foreign"
            )
    return problems, {
        "quotes": len(p.quotes),
        "snapshots": len(p.snapshots),
        "links": len(links),
    }


def _system_stats_match(p: _Payload) -> tuple[list[str], dict]:
    problems = []
    rows = p.rows("system_stats")
    if len(rows) != 1:
        return [f"{len(rows)} system_stats rows"], {}
    stats = rows[0]
    columns = {"win": "wins", "loss": "losses", "push": "pushes"}
    # Legacy score_to_db: as_of_week = COALESCE(MAX(week of a graded game), 0).
    graded_weeks = [p.games[game_id]["week"] for (_, game_id, _) in p.grades]
    expected: dict[str, Any] = {
        "season": p.season,
        "as_of_week": max(graded_weeks, default=0),
    }
    expected |= {f"{t}_{c}": 0 for t in ("spread", "total") for c in columns.values()}
    profits = {"spread": Decimal(0), "total": Decimal(0)}
    for (_, _, target), grade in p.grades.items():
        expected[f"{target}_{columns[grade['result']]}"] += 1
        profits[target] += _dec(grade["profit_units"])
    for column, value in expected.items():
        if stats[column] != value or isinstance(stats[column], bool):
            problems.append(
                f"system_stats {column}={stats[column]!r} expected {value!r}"
            )
    for target, total in profits.items():
        column = f"{target}_profit_units"
        if quantize4(stats[column]) != quantize4(total) or _dec(stats[column]) != _dec(
            quantize4(stats[column])
        ):
            problems.append(
                f"system_stats {column}={stats[column]!r} expected {quantize4(total)!r}"
            )
    return problems, {"graded": len(p.grades)}


def _rating_lineage(p: _Payload) -> tuple[list[str], dict]:
    rating = p.ctx["identities"]["rating"]
    measurement = p.ctx["identities"]["measurement"]
    problems = []
    if not (_HEX64.fullmatch(rating) and _HEX64.fullmatch(measurement)):
        problems.append("lineage identities are not sha256 digests")
    expectations = {
        "prediction_runs": {"rating_manifest_sha256": rating},
        "v5_rating_snapshots": {"source_manifest_sha256": rating},
        "team_rating_components": {"source_manifest_sha256": rating},
        "team_game_measurements": {"measurement_manifest_sha256": measurement},
        "team_possession_stats": {
            "rating_manifest_sha256": rating,
            "measurement_manifest_sha256": measurement,
        },
        "team_possession_adjusted": {
            "rating_manifest_sha256": rating,
            "measurement_manifest_sha256": measurement,
        },
        "matchup_data_publications": {
            "rating_manifest_sha256": rating,
            "measurement_manifest_sha256": measurement,
            "rating_manifest_uri": f"season-run:{p.release_id}#ratings",
            "measurement_manifest_uri": f"season-run:{p.release_id}#measurements",
        },
    }
    for table, columns in expectations.items():
        for column, value in columns.items():
            found = {row.get(column) for row in p.rows(table)}
            if found - {value}:
                problems.append(f"{table}.{column} carries a foreign lineage")
    return problems, {"rating": rating, "measurement": measurement}


def _rating_snapshots(p: _Payload) -> tuple[list[str], dict]:
    problems = []
    sources = {p.release_id} | {p.week_run(w) for w in range(p.active + 1)}
    snapshots = {row["snapshot_id"]: row for row in p.rows("v5_rating_snapshots")}
    pregame, current = defaultdict(set), defaultdict(set)
    for snapshot_id, row in sorted(snapshots.items()):
        source, team, week = row["source_run_id"], row["team"], row["week"]
        if source not in sources:
            problems.append(f"snapshot {snapshot_id}: foreign source run")
        if row["season"] != p.season:
            problems.append(f"snapshot {snapshot_id}: foreign season")
        if row["snapshot_class"] == "pregame":
            suffix = "preseason" if week == 0 else f"week-{week}"
            if (
                snapshot_id != f"{source}:pregame:{team}:{suffix}"
                or row["game_id"] is not None
            ):
                problems.append(f"snapshot {snapshot_id}: pregame identity")
            pregame[week].add(team)
        elif row["snapshot_class"] == "current":
            match = re.fullmatch(
                rf"{re.escape(source)}:current:post-week-(\d+):{re.escape(team)}",
                snapshot_id,
            )
            if match is None:
                problems.append(f"snapshot {snapshot_id}: current identity")
            else:
                current[int(match.group(1))].add(team)
        else:
            problems.append(f"snapshot {snapshot_id}: class {row['snapshot_class']!r}")
        for name in ("offense", "defense", "overall"):
            mean, variance = row[f"{name}_rating"], row[f"{name}_variance"]
            if not (math.isfinite(mean) and math.isfinite(variance) and variance > 0):
                problems.append(f"snapshot {snapshot_id}: invalid {name} rating")
        _ts(row["cutoff_utc"])
    if set(pregame) != set(range(p.active + 1)):
        problems.append(f"pregame weeks {sorted(pregame)} != 0..{p.active}")
    if set(current) != set(range(p.through + 1)):
        problems.append(f"post-week snapshots {sorted(current)} != 0..{p.through}")
    teams = {frozenset(s) for s in (*pregame.values(), *current.values())}
    if len(teams) > 1:
        problems.append("snapshot weeks rate different team sets")
    for component in p.rows("team_rating_components"):
        snapshot_id = component["v5_snapshot_id"]
        if snapshot_id is None:
            continue
        snapshot = snapshots.get(snapshot_id)
        label = f"component {component['component_id']}"
        if snapshot is None:
            problems.append(f"{label}: snapshot absent")
            continue
        expected_class = (
            "current" if component["snapshot_class"] == "current" else "pregame"
        )
        role = component["unit_role"]
        if (
            snapshot["snapshot_class"] != expected_class
            or snapshot["team"] != component["rating_team"]
            or role not in ("offense", "defense")
            or not _close(
                component["rating_mean"], snapshot[f"{role}_rating"], RATING_TOLERANCE
            )
            or not _close(
                component["rating_variance"],
                snapshot[f"{role}_variance"],
                RATING_TOLERANCE,
            )
        ):
            problems.append(f"{label}: differs from snapshot {snapshot_id}")
    return problems, {
        "snapshots": len(snapshots),
        "pregame_weeks": len(pregame),
        "post_weeks": len(current),
    }


def _stats_games(p: _Payload) -> tuple[list[str], dict]:
    problems = []
    fbs = {
        row["team"]
        for table in ("team_season_stats", *MATCHUP_TABLES[:3])
        for row in p.rows(table)
    }
    for row in p.rows("team_season_stats"):
        expected = p.completed_before(row["team"], row["as_of_week"], fbs=fbs)
        if row["games"] != expected:
            problems.append(
                f"season stats {row['team']} w{row['as_of_week']} {row['metric']}: games {row['games']} != {expected}"
            )
    for row in p.rows("team_possession_stats"):
        cutoff = _ts(row["as_of_cutoff"]) if row.get("as_of_cutoff") else None
        team, week = row["team"], row["as_of_week"]
        available = p.completed_before(team, week, fbs=fbs, cutoff=cutoff)
        excluded = {item["game_id"] for item in row["excluded"]}
        total = row["games"] + row["games_excluded"]
        label = f"possession stats {team} w{week} {row['role']} {row['metric']}"
        if len(excluded) != row["games_excluded"]:
            problems.append(f"{label}: games_excluded != excluded games")
        if any(
            g not in p.results
            or p.games[g]["week"] >= week
            or team not in (p.games[g]["home_team"], p.games[g]["away_team"])
            for g in excluded
        ):
            problems.append(f"{label}: excluded game outside the window")
        # Every completed team-game carries PPP; other measures may be partial.
        if total > available or (row["metric"] == "ppp" and total != available):
            problems.append(f"{label}: games+excluded {total} vs {available} available")
    for row in p.rows("team_possession_adjusted"):
        cutoff = _ts(row["as_of_cutoff"]) if row.get("as_of_cutoff") else None
        available = p.completed_before(
            row["team"], row["as_of_week"], fbs=fbs, cutoff=cutoff
        )
        if row["games"] > available:
            problems.append(
                f"adjusted {row['team']} w{row['as_of_week']}: games {row['games']} > {available}"
            )
    return problems, {"fbs_teams": len(fbs)}


def _completed_counts_regime(p: _Payload) -> tuple[list[str], dict]:
    from cks_picks_cfb.features.regimes import (
        completed_game_regime,
        upcoming_game_regime,
    )

    problems = []
    regimes = Counter()
    for (_, game_id), prediction in sorted(p.predictions.items()):
        game = p.games[game_id]
        home = p.completed_before(game["home_team"], game["week"])
        away = p.completed_before(game["away_team"], game["week"])
        if (prediction["home_completed_games"], prediction["away_completed_games"]) != (
            home,
            away,
        ):
            problems.append(
                f"prediction {game_id}: completed games != ({home}, {away})"
            )
        stage = min(home, away)
        if prediction["regime"] not in {
            completed_game_regime(stage),
            upcoming_game_regime(stage),
        }:
            problems.append(
                f"prediction {game_id}: regime {prediction['regime']!r} for stage {stage}"
            )
        regimes[prediction["regime"]] += 1
    return problems, {"regimes": dict(sorted(regimes.items()))}


def _matchup_publication(p: _Payload) -> tuple[list[str], dict]:
    problems = []
    for table in sorted(p.raw):
        rows = p.raw[table]
        if any(SERVER_COLUMNS & set(row) for row in rows):
            problems.append(f"{table}: rows carry server columns")
    publications = p.rows("matchup_data_publications")
    has_data = any(p.rows(t) for t in MATCHUP_TABLES)
    if len(publications) > 1 or (len(publications) == 0 and (has_data or p.active > 0)):
        problems.append(f"{len(publications)} matchup publications")
    counts = {t: len(p.rows(t)) for t in MATCHUP_TABLES}
    weeks = {
        row["as_of_week"]
        for t in (
            "team_possession_stats",
            "team_possession_adjusted",
            "team_rating_components",
        )
        for row in p.rows(t)
    }
    for row in publications:
        label = f"publication {row['publication_id']}"
        if row["row_counts"] != counts:
            problems.append(f"{label}: row_counts differ from payload")
        as_of = row["as_of_weeks"]
        if (
            not isinstance(as_of, list)
            or as_of != sorted(set(as_of))
            or not weeks <= set(as_of)
            or not set(as_of) <= set(range(p.through + 2))
        ):
            problems.append(
                f"{label}: as_of_weeks {as_of!r} vs data weeks {sorted(weeks)}"
            )
        if row["lineage"] not in ("intended_update", "historical_replay"):
            problems.append(f"{label}: lineage")
        if not _HEX64.fullmatch(str(row["payload_sha256"])):
            problems.append(f"{label}: payload_sha256")
    return problems, {"publications": len(publications), "row_counts": counts}


def _venues_cover(p: _Payload) -> tuple[list[str], dict]:
    venues = {row["game_id"] for row in p.rows("game_venues")}
    problems = [f"venue for unknown game {g}" for g in sorted(venues - set(p.games))]
    problems += [
        f"game {g} lacks a venue"
        for g, game in sorted(p.games.items())
        if game["week"] <= p.active and g not in venues
    ]
    return problems, {"venues": len(venues)}


def _team_chart_reconciliation(p: _Payload) -> tuple[list[str], dict]:
    from cks_picks_cfb.charts.reconciliation import chart_problems

    return chart_problems(
        roster=p.rows("team_season_roster"),
        game_rows=p.rows("team_game_stats"),
        adjusted_rows=p.rows("team_adjusted_epa"),
        stats_rows=p.rows("team_season_stats"),
        games=p.rows("games"),
        results=p.rows("game_results"),
        season=p.season,
        active_week=p.active,
    )


_PROJECTION_CHECKS: dict[str, Callable[[_Payload], tuple[list[str], dict]]] = {
    "tables_complete": _tables_complete,
    "weeks_and_slate": _weeks_and_slate,
    "predictions_in_games": _predictions_in_games,
    "prior_finals_complete": _prior_finals_complete,
    "grades_recomputed": _grades_recomputed,
    "selection_matches_prediction": _selection_matches_prediction,
    "market_links": _market_links,
    "system_stats_match": _system_stats_match,
    "rating_lineage": _rating_lineage,
    "rating_snapshots": _rating_snapshots,
    "stats_games": _stats_games,
    "completed_counts_regime": _completed_counts_regime,
    "matchup_publication": _matchup_publication,
    "venues_cover": _venues_cover,
    "team_chart_reconciliation": _team_chart_reconciliation,
}
assert set(_PROJECTION_CHECKS) == REQUIRED_PROJECTION_CHECKS


def derive_checks(
    projections: Mapping[str, list[dict]], manifest: Mapping[str, Any]
) -> dict[str, dict]:
    """Return ``{name: check_entry}`` for exactly ``REQUIRED_PROJECTION_CHECKS``.

    ``projections`` is the FULL payload (``prediction_runs`` plus the ``charts_v1`` tables);
    ``manifest`` is the run manifest (or any mapping with its ``identity`` and
    ``output_refs``), see :func:`context_from_manifest`.
    """
    if not isinstance(projections, Mapping):
        raise VerificationError("projections must be an object")
    payload = _Payload(projections, context_from_manifest(manifest))
    return {
        name: _run(check, "projection", payload)
        for name, check in sorted(_PROJECTION_CHECKS.items())
    }


# ---------------------------------------------------------------------------
# Prepare checks (prepared frames; hash-bound, not re-derivable at staging)
# ---------------------------------------------------------------------------


def _teams(schedule) -> dict[int, tuple[str, str]]:
    return {
        int(g.game_id): (str(g.home_team), str(g.away_team))
        for g in schedule.itertuples()
    }


def _earlier_counts(schedule, week: int) -> Counter:
    counts = Counter()
    for game in schedule[schedule.week.lt(week)].itertuples():
        counts[game.home_team] += 1
        counts[game.away_team] += 1
    return counts


def _required_prior_week_data(frames, through_week: int) -> tuple[list[str], dict]:
    """Per completed week: games, finals and PPP team-role coverage.

    Plays and drives are not retained in the prepared frames: ``inputs.load_inputs``
    already refuses a revision whose plays/drives miss a completed game. The frame
    evidence here is the PPP measurement coverage derived from those plays and the
    scoring events reconciled against them.
    """
    schedule, finals = frames["schedule"], frames["finals"]
    measurements, events = frames["measurements"], frames["scoring_events"]
    final_ids = set(finals.game_id.astype(int))
    ppp = measurements[measurements.measurement_id.eq("ppp")]
    covered = set(zip(ppp.game_id.astype(int), ppp.team, ppp.unit_role, strict=True))
    event_games = set(events.game_id.astype(int))
    problems, weeks = [], {}
    for week in range(through_week + 1):
        games = schedule[schedule.week.eq(week)]
        ids = set(games.game_id.astype(int))
        roles = {
            (int(g.game_id), team, role)
            for g in games.itertuples()
            for team in (g.home_team, g.away_team)
            for role in ("offense", "defense")
        }
        weeks[str(week)] = {
            "games": len(ids),
            "finals": len(ids & final_ids),
            "ppp_team_roles": len(roles & covered),
            "scoring_event_games": len(ids & event_games),
        }
        if not ids:
            problems.append(f"week {week}: no games")
        problems += [
            f"week {week}: game {g} lacks a final" for g in sorted(ids - final_ids)
        ]
        problems += [f"week {week}: PPP missing {r}" for r in sorted(roles - covered)]
    return problems, {"weeks": weeks}


def _score_reconciliation(frames, inputs, through_week: int) -> tuple[list[str], dict]:
    schedule, finals, events = (
        frames["schedule"],
        frames["finals"],
        frames["scoring_events"],
    )
    completed = schedule[schedule.week.le(through_week)]
    teams = _teams(completed)
    increments = events.score_increment.astype(float)
    problems = []
    if not increments.map(math.isfinite).all() or increments.lt(0).any():
        problems.append("non-finite or negative score increment")
    scored = events.groupby(["game_id", "team"]).size().index
    foreign = [(int(g), t) for g, t in scored if t not in teams.get(int(g), ())]
    problems += [f"scoring event for foreign participant {k}" for k in foreign]
    exceptions = inputs.score_exceptions
    problems += score_reconciliation_problems(completed, finals, events, exceptions)
    return problems, {"team_games": 2 * len(teams), "exceptions": len(exceptions)}


def _evidence(explanation: Any) -> list[dict]:
    parsed = json.loads(explanation) if isinstance(explanation, str) else explanation
    return list(parsed.get("evidence_contributions", []))


def _earlier_week_only(frames) -> tuple[list[str], dict]:
    """Ratings, role evidence and offsets use only games of earlier weeks.

    Pregame role evidence must come from ``source_week < target_week`` and be
    available by the rating cutoff; post-week evidence from ``source_week <=
    post_week``; offset usable-game counts cannot exceed each team's earlier-week
    games; every predicted game kicks off after its forecast cutoff.
    """
    schedule = frames["schedule"]
    week_of = dict(
        zip(schedule.game_id.astype(int), schedule.week.astype(int), strict=True)
    )
    problems, contributions = [], 0
    for frame_name, week_column, bound in (
        ("rating_roles", "target_week", lambda source, week: source < week),
        ("current_rating_roles", "post_week", lambda source, week: source <= week),
    ):
        for row in frames[frame_name].itertuples():
            week = int(getattr(row, week_column))
            cutoff = _ts(row.cutoff_utc)
            for item in _evidence(row.explanation):
                contributions += 1
                game_week = week_of.get(int(item["game_id"]))
                if (
                    not bound(int(item["source_week"]), week)
                    or game_week is None
                    or not bound(game_week, week)
                    or _ts(item["available_utc"]) > cutoff
                ):
                    problems.append(
                        f"{frame_name} week {week} {row.team}: game {item['game_id']} not earlier/available"
                    )
    teams = _teams(schedule)
    for row in frames["offsets"].itertuples():
        counts = _earlier_counts(schedule, int(row.week))
        home, away = teams[int(row.game_id)]
        if row.home_usable_games > counts[home] or row.away_usable_games > counts[away]:
            problems.append(
                f"offset game {row.game_id}: uses games outside earlier weeks"
            )
    kickoff = dict(zip(schedule.game_id.astype(int), schedule.kickoff_utc, strict=True))
    for row in frames["features"].itertuples():
        if _ts(str(row.forecast_cutoff)) >= kickoff[int(row.game_id)]:
            problems.append(f"feature game {row.game_id}: cutoff not before kickoff")
    return problems, {
        "evidence_contributions": contributions,
        "offsets": len(frames["offsets"]),
    }


def _fixed_model_no_refit(frames, inputs, model, identity) -> tuple[list[str], dict]:
    from cks_picks_cfb.forecast.live import DEVELOPMENT_SEASONS

    allowed = set(DEVELOPMENT_SEASONS)
    problems = []
    if model["inputs"]["bridge"]["sha256"] != PINNED_BRIDGE_SHA256:
        problems.append("bridge bytes differ from the pinned B2 bundle")
    if model.get("development_seasons") != list(DEVELOPMENT_SEASONS):
        problems.append("model development seasons changed")
    if not set(inputs.bridge.get("development_seasons", [])) <= allowed:
        problems.append("bridge trained on a forbidden season")
    for name in ("terminal", "historical_population", "historical_events"):
        if not set(getattr(inputs, name).season.astype(int)) <= allowed:
            problems.append(f"{name} includes a forbidden season")
    prefix = f"model:{identity['model_manifest_sha256']}#"
    if not frames["predictions"].model_ref.astype(str).str.startswith(prefix).all():
        problems.append("prediction model_ref differs from the fixed model")
    return problems, {"bridge_sha256": model["inputs"]["bridge"]["sha256"]}


def _no_market_in_features(frames, inputs) -> tuple[list[str], dict]:
    names = set(frames["features"].columns) | set(frames["offsets"].columns)
    names |= set(inputs.bridge.get("feature_order", []))
    for spec in inputs.bridge.get("targets", {}).values():
        names |= set(spec.get("feature_names", []))
    problems = [
        f"market column {name}"
        for name in sorted(names)
        if any(token in name.lower() for token in MARKET_TOKENS)
    ]
    return problems, {"feature_columns": len(names)}


def _ratings_equal_features(frames) -> tuple[list[str], dict]:
    """Bridge inputs equal the pregame team ratings ``build_live_application_frame``
    selects: the latest target-week state at/before the cutoff and before kickoff."""
    schedule, ratings = frames["schedule"], frames["ratings"]
    teams = _teams(schedule)
    kickoff = dict(zip(schedule.game_id.astype(int), schedule.kickoff_utc, strict=True))
    problems = []
    for row in frames["features"].itertuples():
        game_id = int(row.game_id)
        cutoff = _ts(str(row.forecast_cutoff))
        for side, team in zip(("home", "away"), teams[game_id], strict=True):
            states = ratings[
                ratings.target_week.eq(row.week)
                & ratings.team.eq(team)
                & ratings.cutoff_utc.le(cutoff)
                & ratings.cutoff_utc.lt(kickoff[game_id])
            ].sort_values(["cutoff_utc", "game_id"], kind="mergesort")
            if states.empty:
                problems.append(f"game {game_id} {side}: no pregame rating")
                continue
            state = states.iloc[-1]
            for unit in ("offense", "defense"):
                if not _close(
                    getattr(row, f"{side}_{unit}"),
                    state[f"{unit}_rating"],
                    RATING_TOLERANCE,
                ):
                    problems.append(f"game {game_id} {side}_{unit} differs from rating")
    return problems, {"feature_rows": len(frames["features"])}


def _paired_predictions(frames, through_week: int) -> tuple[list[str], dict]:
    predictions, schedule = frames["predictions"], frames["schedule"]
    problems = []
    for (week, game_id), group in predictions.groupby(["week", "game_id"]):
        if sorted(group.target) != ["margin", "total"] or group.run_id.nunique() != 1:
            problems.append(f"game {game_id}: targets/run not paired")
        if not (
            group["mean"].map(math.isfinite).all()
            and group.variance.map(math.isfinite).all()
            and group.variance.gt(0).all()
        ):
            problems.append(f"game {game_id}: non-finite mean or non-positive variance")
    predicted = {
        (int(w), int(g))
        for w, g in zip(predictions.week, predictions.game_id, strict=True)
    }
    featured = {
        (int(w), int(g))
        for w, g in zip(
            frames["features"].week, frames["features"].game_id, strict=True
        )
    }
    if predicted != featured:
        problems.append("predicted games differ from feature rows")
    completed = schedule[schedule.week.le(through_week)]
    expected = {
        (int(w), int(g)) for w, g in zip(completed.week, completed.game_id, strict=True)
    }
    problems += [
        f"completed game {g} unpredicted" for g in sorted(expected - predicted)
    ]
    return problems, {"games": len(predicted)}


def _checksums_at_read(output_refs, verified) -> tuple[list[str], dict]:
    names, verified = set(output_refs), set(verified)
    problems = [f"output {n} not re-read after write" for n in sorted(names - verified)]
    problems += [f"unknown verified output {n}" for n in sorted(verified - names)]
    if not names:
        problems.append("no outputs")
    return problems, {"outputs": sorted(names)}


def derive_prepare_checks(
    frames: Mapping[str, Any],
    *,
    inputs: Any,
    model: Mapping[str, Any],
    identity: Mapping[str, Any],
    output_refs: Mapping[str, Mapping[str, Any]],
    verified_outputs: list[str] | set[str],
) -> dict[str, dict]:
    """Return ``{name: check_entry}`` for exactly ``REQUIRED_PREPARE_CHECKS``.

    ``frames`` are the ``prepare.compute`` outputs, ``inputs`` the
    ``inputs.SeasonInputs``, ``model`` the parsed model manifest, ``identity`` the
    run identity, and ``verified_outputs`` the names of ``output_refs`` whose
    written bytes were re-read and matched their sha256.
    """
    through = int(identity["through_week"])
    checks = {
        "required_prior_week_data": (_required_prior_week_data, frames, through),
        "score_reconciliation": (_score_reconciliation, frames, inputs, through),
        "earlier_week_only": (_earlier_week_only, frames),
        "fixed_model_no_refit": (
            _fixed_model_no_refit,
            frames,
            inputs,
            model,
            identity,
        ),
        "no_market_in_features": (_no_market_in_features, frames, inputs),
        "ratings_equal_features": (_ratings_equal_features, frames),
        "paired_predictions": (_paired_predictions, frames, through),
        "checksums_at_read": (_checksums_at_read, output_refs, verified_outputs),
    }
    assert set(checks) == REQUIRED_PREPARE_CHECKS
    return {
        name: _run(spec[0], "prepare", *spec[1:])
        for name, spec in sorted(checks.items())
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def projection_digests(projections: Mapping[str, list[dict]]) -> dict[str, dict]:
    """``release.projection_check`` of every table in ``PROJECTION_ORDER``."""
    from cks_picks_cfb.season.release import projection_check

    return {table: projection_check(projections[table]) for table in PROJECTION_ORDER}


def assemble_report(
    projections: Mapping[str, list[dict]],
    manifest: Mapping[str, Any],
    prepare_checks: Mapping[str, dict],
) -> dict[str, Any]:
    """The ``season_verification_v2`` report; ``state`` is ``"failed"`` if any
    check failed (such a report never validates)."""
    checks = {**derive_checks(projections, manifest), **prepare_checks}
    if set(checks) != REQUIRED_CHECKS:
        raise VerificationError("prepare checks are incomplete")
    passed = all(entry["passed"] is True for entry in checks.values())
    return {
        "schema_version": SCHEMA_VERSION,
        "state": "passed" if passed else "failed",
        "identity": dict(manifest["identity"]),
        "output_refs": dict(manifest["output_refs"]),
        "checks": dict(sorted(checks.items())),
        "projection_checks": projection_digests(projections),
        "row_counts": {t: len(projections[t]) for t in PROJECTION_ORDER},
    }


def failed_checks(report: Mapping[str, Any]) -> list[str]:
    return sorted(
        name
        for name, entry in report["checks"].items()
        if entry.get("passed") is not True
    )


def validate_report(
    report: Mapping[str, Any],
    *,
    projections: Mapping[str, list[dict]],
    manifest: Mapping[str, Any] | None = None,
) -> None:
    """Raise :class:`VerificationError` unless ``report`` is a passing
    ``season_verification_v2`` whose projection checks, ``projection_checks`` and
    ``row_counts`` are exactly what ``projections`` (the FULL payload) yields.

    The derivation context comes from the report's own ``identity``/``output_refs``;
    pass ``manifest`` (the run manifest) to also bind those to it. Callers that do
    not pass it must compare them to the manifest themselves.
    """
    if not isinstance(report, Mapping):
        raise VerificationError("verification report must be an object")
    if not isinstance(projections, Mapping) or set(projections) != PAYLOAD_TABLES:
        raise VerificationError("projections must be the full payload")
    if report.get("schema_version") != SCHEMA_VERSION:
        raise VerificationError("unknown verification schema")
    if report.get("state") != "passed":
        raise VerificationError("verification did not pass")
    if manifest is not None:
        for key in ("identity", "output_refs"):
            if report.get(key) != manifest.get(key):
                raise VerificationError(f"verification {key} differs from manifest")
    checks = report.get("checks")
    if not isinstance(checks, Mapping) or set(checks) != REQUIRED_CHECKS:
        raise VerificationError("verification checks are missing or unknown")
    for name, entry in checks.items():
        source = "projection" if name in REQUIRED_PROJECTION_CHECKS else "prepare"
        if (
            not isinstance(entry, Mapping)
            or entry.get("passed") is not True
            or entry.get("source") != source
            or not isinstance(entry.get("observed"), Mapping)
        ):
            raise VerificationError(f"verification check failed or malformed: {name}")
    derived = derive_checks(projections, report)
    for name in sorted(REQUIRED_PROJECTION_CHECKS):
        if checks[name] != derived[name]:
            raise VerificationError(f"projection check is not reproducible: {name}")
    if report.get("projection_checks") != projection_digests(projections):
        raise VerificationError("projection checksums differ from payload")
    if report.get("row_counts") != {t: len(projections[t]) for t in PROJECTION_ORDER}:
        raise VerificationError("row counts differ from payload")
