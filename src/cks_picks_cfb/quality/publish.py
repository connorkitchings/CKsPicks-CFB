"""Publish-boundary assertions: checked before any Neon write and read back after.

Pre-write checks (``publish.pre.*``) take the exact payload the publisher is about to
write; post-write checks (``publish.post.*``) compare what the database now holds with
that payload. Structural defects block (a duplicate key, a null required field, an
impossible value, a scheduled game missing from the run, a selection that is not the
best available quote, a published game without a venue city). Nothing here repairs data.

Context keys:

- ``records``: the per-game payload dicts (``publish_to_db._row_to_record``)
- ``quote_by_id``: frozen quote dicts keyed by ``quote_id`` (``spread``, ``total``)
- ``schedule_game_ids``: game ids scheduled for the run's season and week
- ``allow_partial_slate``: operator override for coverage; it is recorded, not hidden
- ``state``: run state (``preview`` or ``published``); ``venue_rows`` for published runs
- ``readback``: ``{"prediction_game_ids": set, "selections": {(game_id, target): dict}}``
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from cks_picks_cfb.quality.checks import (
    BLOCK,
    Outcome,
    QualityRun,
    register_check,
    skipped,
)
from cks_picks_cfb.quality.receipt import build_receipt, write_receipt_local

REQUIRED_FIELDS = (
    "game_id",
    "season",
    "week",
    "home_team",
    "away_team",
    "predicted_spread",
    "predicted_total",
)
SPREAD_LEANS = {None, "home", "away"}
TOTAL_LEANS = {None, "over", "under"}
SPREAD_BOUND = 100.0
TOTAL_RANGE = (10.0, 200.0)
STD_DEV_RANGE = (0.0, 60.0)
POINT_TOLERANCE = 1e-9


class PublishQualityError(RuntimeError):
    """A blocking publish-boundary check failed; nothing was (or will be) committed."""


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def duplicate_or_missing_keys(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    ids = [r.get("game_id") for r in records]
    present = [i for i in ids if not _blank(i)]
    counts: dict[Any, int] = {}
    for i in present:
        counts[i] = counts.get(i, 0) + 1
    return {
        "rows": len(ids),
        "missing": len(ids) - len(present),
        "duplicates": sorted(i for i, n in counts.items() if n > 1),
    }


def null_required_fields(records: Sequence[Mapping[str, Any]]) -> dict[str, list[Any]]:
    out: dict[str, list[Any]] = {}
    for field in REQUIRED_FIELDS:
        bad = [r.get("game_id") for r in records if _blank(r.get(field))]
        if bad:
            out[field] = bad
    return out


def out_of_range(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    problems: list[dict[str, Any]] = []

    def flag(rec: Mapping[str, Any], field: str, why: str) -> None:
        problems.append(
            {
                "game_id": rec.get("game_id"),
                "field": field,
                "value": rec.get(field),
                "why": why,
            }
        )

    for rec in records:
        for field in (
            "predicted_spread",
            "home_team_spread_line",
            "canonical_spread_line",
        ):
            v = rec.get(field)
            if not _blank(v) and abs(float(v)) > SPREAD_BOUND:
                flag(rec, field, f"|spread| > {SPREAD_BOUND}")
        for field in ("predicted_total", "total_line", "canonical_total_line"):
            v = rec.get(field)
            if not _blank(v) and not TOTAL_RANGE[0] <= float(v) <= TOTAL_RANGE[1]:
                flag(rec, field, f"total outside {TOTAL_RANGE}")
        for field in ("predicted_spread_std_dev", "predicted_total_std_dev"):
            v = rec.get(field)
            if not _blank(v) and not STD_DEV_RANGE[0] < float(v) <= STD_DEV_RANGE[1]:
                flag(
                    rec,
                    field,
                    f"std dev outside ({STD_DEV_RANGE[0]}, {STD_DEV_RANGE[1]}]",
                )
        for field in ("edge_spread", "edge_total"):
            v = rec.get(field)
            if not _blank(v) and float(v) < 0:
                flag(rec, field, "negative edge")
        if rec.get("spread_lean") not in SPREAD_LEANS:
            flag(rec, "spread_lean", "unknown spread lean")
        if rec.get("total_lean") not in TOTAL_LEANS:
            flag(rec, "total_lean", "unknown total lean")
    return problems


def coverage_gaps(
    records: Sequence[Mapping[str, Any]], schedule: set[int]
) -> dict[str, list[int]]:
    published = {int(r["game_id"]) for r in records if not _blank(r.get("game_id"))}
    return {
        "missing": sorted(schedule - published),
        "extra": sorted(published - schedule),
    }


def _linked(rec: Mapping[str, Any]) -> list[str]:
    raw = rec.get("source_quote_ids")
    return list(json.loads(raw)) if isinstance(raw, str) else list(raw or [])


def best_quote_violations(
    records: Sequence[Mapping[str, Any]], quote_by_id: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Selected lines that are not the best available line for the selected side.

    Home spread: highest home-signed line. Away spread: lowest. Over: lowest total.
    Under: highest total. This recomputes the rule from the frozen quotes and does not
    call the selection code under test.
    """
    problems: list[dict[str, Any]] = []
    for rec in records:
        for target, lean_key, id_key, line_key, point_key in (
            (
                "spread",
                "spread_lean",
                "spread_market_quote_id",
                "home_team_spread_line",
                "spread",
            ),
            ("total", "total_lean", "total_market_quote_id", "total_line", "total"),
        ):
            side, quote_id, line = rec.get(lean_key), rec.get(id_key), rec.get(line_key)
            if side is None or _blank(quote_id) or _blank(line):
                continue
            eligible = {
                q: float(quote_by_id[q][point_key])
                for q in _linked(rec)
                if q in quote_by_id and not _blank(quote_by_id[q].get(point_key))
            }
            if str(quote_id) not in eligible:
                problems.append(
                    {
                        "game_id": rec["game_id"],
                        "target": target,
                        "why": "selected quote not among the linked quotes",
                    }
                )
                continue
            take_max = side in {"home", "under"}
            best = max(eligible.values()) if take_max else min(eligible.values())
            if (
                abs(float(line) - best) > POINT_TOLERANCE
                or abs(eligible[str(quote_id)] - best) > POINT_TOLERANCE
            ):
                problems.append(
                    {
                        "game_id": rec["game_id"],
                        "target": target,
                        "side": side,
                        "selected": float(line),
                        "best": best,
                    }
                )
    return problems


def venue_gaps(
    venue_rows: Sequence[Mapping[str, Any]], game_ids: Sequence[int]
) -> list[int]:
    have = {int(r["game_id"]) for r in venue_rows if str(r.get("city") or "").strip()}
    return sorted(int(g) for g in game_ids if int(g) not in have)


def expected_selections(
    records: Sequence[Mapping[str, Any]], quote_by_id: Mapping[str, Mapping[str, Any]]
) -> dict[tuple[int, str], dict[str, Any]]:
    """The selection rows the publisher writes: a lean, a quoted line and a known quote."""
    out: dict[tuple[int, str], dict[str, Any]] = {}
    for rec in records:
        for target, sides, id_key, line_key, lean_key in (
            (
                "spread",
                {"home", "away"},
                "spread_market_quote_id",
                "home_team_spread_line",
                "spread_lean",
            ),
            (
                "total",
                {"over", "under"},
                "total_market_quote_id",
                "total_line",
                "total_lean",
            ),
        ):
            quote_id = rec.get(id_key)
            if (
                rec.get(lean_key) in sides
                and not _blank(quote_id)
                and not _blank(rec.get(line_key))
                and str(quote_id) in quote_by_id
            ):
                out[(int(rec["game_id"]), target)] = {
                    "quote_id": str(quote_id),
                    "side": rec[lean_key],
                    "point": float(rec[line_key]),
                }
    return out


def selection_mismatches(
    expected: Mapping[tuple[int, str], Mapping[str, Any]],
    actual: Mapping[tuple[int, str], Mapping[str, Any]],
) -> dict[str, list[Any]]:
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    differing = sorted(
        k
        for k in set(expected) & set(actual)
        if expected[k]["quote_id"] != actual[k]["quote_id"]
        or expected[k]["side"] != actual[k]["side"]
        or abs(float(expected[k]["point"]) - float(actual[k]["point"]))
        > POINT_TOLERANCE
    )
    return {"missing": missing, "extra": extra, "differing": differing}


def fetch_readback(cur: Any, run_id: str) -> dict[str, Any]:
    cur.execute("SELECT game_id FROM predictions WHERE run_id = %s", (run_id,))
    prediction_ids = {int(r[0]) for r in cur.fetchall()}
    cur.execute(
        "SELECT game_id, target, quote_id, side, point FROM prediction_market_selections WHERE run_id = %s",
        (run_id,),
    )
    selections = {
        (int(g), str(t)): {"quote_id": str(q), "side": s, "point": float(p)}
        for g, t, q, s, p in cur.fetchall()
    }
    return {"prediction_game_ids": prediction_ids, "selections": selections}


def _n(d: Mapping[str, Any]) -> dict[str, Any]:
    return {
        k: (len(v) if isinstance(v, (list, set, dict)) else v) for k, v in d.items()
    }


@register_check(
    "publish.pre.keys",
    stage="publish",
    severity=BLOCK,
    description="Every game id is present and unique in the payload",
)
def _keys(ctx: Mapping[str, Any]) -> Outcome:
    if ctx.get("records") is None:
        return skipped("records not provided")
    res = duplicate_or_missing_keys(ctx["records"])
    return Outcome(
        not res["missing"] and not res["duplicates"],
        observed=_n(res),
        expected={"missing": 0, "duplicates": 0},
        detail=f"duplicates: {res['duplicates'][:10]}" if res["duplicates"] else "",
    )


@register_check(
    "publish.pre.required_fields",
    stage="publish",
    severity=BLOCK,
    description="Required payload fields are non-null",
)
def _required(ctx: Mapping[str, Any]) -> Outcome:
    if ctx.get("records") is None:
        return skipped("records not provided")
    res = null_required_fields(ctx["records"])
    return Outcome(
        not res,
        observed={k: len(v) for k, v in res.items()},
        expected="no null required field",
        detail=str({k: v[:5] for k, v in res.items()}) if res else "",
    )


@register_check(
    "publish.pre.value_ranges",
    stage="publish",
    severity=BLOCK,
    description="Spreads, totals, deviations, edges and leans are within plausible bounds",
)
def _ranges(ctx: Mapping[str, Any]) -> Outcome:
    if ctx.get("records") is None:
        return skipped("records not provided")
    res = out_of_range(ctx["records"])
    return Outcome(
        not res,
        observed={"out_of_range": len(res)},
        expected={"out_of_range": 0},
        detail=str(res[:3]) if res else "",
    )


@register_check(
    "publish.pre.schedule_coverage",
    stage="publish",
    severity=BLOCK,
    description="The run covers every game scheduled for its week (gate 2)",
)
def _coverage(ctx: Mapping[str, Any]) -> Outcome:
    if ctx.get("records") is None or ctx.get("schedule_game_ids") is None:
        return skipped("records/schedule_game_ids not provided")
    gaps = coverage_gaps(ctx["records"], set(ctx["schedule_game_ids"]))
    allowed = bool(ctx.get("allow_partial_slate")) and not gaps["extra"]
    ok = (not gaps["missing"] and not gaps["extra"]) or allowed
    detail = (
        f"missing {gaps['missing'][:10]}, extra {gaps['extra'][:10]}"
        if (gaps["missing"] or gaps["extra"])
        else ""
    )
    if allowed and gaps["missing"]:
        detail = "partial slate allowed by operator: " + detail
    return Outcome(
        ok,
        observed={
            "scheduled": len(ctx["schedule_game_ids"]),
            "missing": len(gaps["missing"]),
            "extra": len(gaps["extra"]),
            "partial_slate_allowed": allowed,
        },
        expected={"missing": 0, "extra": 0},
        detail=detail,
    )


@register_check(
    "publish.pre.best_quote",
    stage="publish",
    severity=BLOCK,
    description="Every selected line is the best available line for its side (lowest for Away and Over, highest for Home and Under)",
)
def _best_quote(ctx: Mapping[str, Any]) -> Outcome:
    if ctx.get("records") is None or ctx.get("quote_by_id") is None:
        return skipped("records/quote_by_id not provided")
    res = best_quote_violations(ctx["records"], ctx["quote_by_id"])
    return Outcome(
        not res,
        observed={"violations": len(res)},
        expected={"violations": 0},
        detail=str(res[:3]) if res else "",
    )


@register_check(
    "publish.pre.venue_city",
    stage="publish",
    severity=BLOCK,
    description="Every game of a published run has a venue city (gate 3)",
)
def _venue(ctx: Mapping[str, Any]) -> Outcome:
    if (
        ctx.get("state") != "published"
        or ctx.get("venue_rows") is None
        or ctx.get("records") is None
    ):
        return skipped("only checked for published runs with venue rows")
    ids = [int(r["game_id"]) for r in ctx["records"] if not _blank(r.get("game_id"))]
    missing = venue_gaps(ctx["venue_rows"], ids)
    return Outcome(
        not missing,
        observed={"games": len(ids), "missing_city": len(missing)},
        expected={"missing_city": 0},
        detail=f"game ids: {missing[:10]}" if missing else "",
    )


@register_check(
    "publish.post.predictions_readback",
    stage="publish",
    severity=BLOCK,
    description="The database holds exactly the payload's prediction keys after the write",
)
def _post_predictions(ctx: Mapping[str, Any]) -> Outcome:
    if ctx.get("records") is None or ctx.get("readback") is None:
        return skipped("records/readback not provided")
    expected = {int(r["game_id"]) for r in ctx["records"]}
    actual = set(ctx["readback"]["prediction_game_ids"])
    return Outcome(
        expected == actual,
        observed={
            "expected": len(expected),
            "stored": len(actual),
            "missing": len(expected - actual),
            "extra": len(actual - expected),
        },
        expected={"missing": 0, "extra": 0},
    )


@register_check(
    "publish.post.selections_readback",
    stage="publish",
    severity=BLOCK,
    description="Stored selections equal the payload's expected selections (quote, side and point)",
)
def _post_selections(ctx: Mapping[str, Any]) -> Outcome:
    if (
        ctx.get("records") is None
        or ctx.get("readback") is None
        or ctx.get("quote_by_id") is None
    ):
        return skipped("records/readback/quote_by_id not provided")
    res = selection_mismatches(
        expected_selections(ctx["records"], ctx["quote_by_id"]),
        ctx["readback"]["selections"],
    )
    return Outcome(
        not any(res.values()),
        observed=_n(res),
        expected={"missing": 0, "extra": 0, "differing": 0},
        detail=str({k: v[:3] for k, v in res.items() if v})
        if any(res.values())
        else "",
    )


def venue_payload_gaps(
    rows: Sequence[Mapping[str, Any]], game_ids: Sequence[int]
) -> dict[str, list[int]]:
    """Venue rows to publish: every wanted game needs a row with a city, once."""
    wanted = {int(g) for g in game_ids}
    have = [int(r["game_id"]) for r in rows]
    no_city = sorted(
        int(r["game_id"]) for r in rows if not str(r.get("city") or "").strip()
    )
    return {
        "missing_row": sorted(wanted - set(have)),
        "no_city": no_city,
        "duplicate": sorted({g for g in have if have.count(g) > 1}),
    }


def recompute_grade(
    target: str, side: str, point: float, home: float, away: float
) -> str:
    """The result of a frozen selection (side and point) against the certified score."""
    delta = (home - away + point) if target == "spread" else (home + away - point)
    if delta == 0:
        return "push"
    return "win" if (delta > 0) == (side in {"home", "over"}) else "loss"


def grade_mismatches(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    bad = []
    for r in rows:
        want = recompute_grade(
            r["target"],
            r["side"],
            float(r["point"]),
            float(r["home_points"]),
            float(r["away_points"]),
        )
        if want != r["result"]:
            bad.append(
                {
                    "game_id": r.get("game_id"),
                    "target": r["target"],
                    "stored": r["result"],
                    "recomputed": want,
                }
            )
    return bad


def fetch_grade_readback(cur: Any, run_id: str) -> list[dict[str, Any]]:
    """v2 grades with the frozen selection and certified score they must agree with."""
    cur.execute(
        "SELECT pg.game_id, pg.target, pg.side, s.point, pg.result, gr.home_points, gr.away_points "
        "FROM prediction_grades pg "
        "JOIN prediction_market_selections s ON s.run_id = pg.run_id AND s.game_id = pg.game_id AND s.target = pg.target "
        "JOIN game_results gr ON gr.game_id = pg.game_id "
        "WHERE pg.run_id = %s AND pg.grading_version = 'model_side_best_quote_v2'",
        (run_id,),
    )
    keys = (
        "game_id",
        "target",
        "side",
        "point",
        "result",
        "home_points",
        "away_points",
    )
    return [dict(zip(keys, row)) for row in cur.fetchall()]


@register_check(
    "publish.pre.venue_payload",
    stage="publish",
    severity=BLOCK,
    description="Every game being published to game_venues has one row with a city (gate 3)",
)
def _venue_payload(ctx: Mapping[str, Any]) -> Outcome:
    if ctx.get("venue_payload") is None or ctx.get("venue_game_ids") is None:
        return skipped("venue_payload/venue_game_ids not provided")
    res = venue_payload_gaps(ctx["venue_payload"], ctx["venue_game_ids"])
    return Outcome(
        not any(res.values()),
        observed=_n(res),
        expected={"missing_row": 0, "no_city": 0, "duplicate": 0},
        detail=str({k: v[:10] for k, v in res.items() if v})
        if any(res.values())
        else "",
    )


@register_check(
    "publish.post.venues_readback",
    stage="publish",
    severity=BLOCK,
    description="The database holds the published venue rows (keys and cities) after the write",
)
def _venues_readback(ctx: Mapping[str, Any]) -> Outcome:
    if ctx.get("venue_payload") is None or ctx.get("venue_readback") is None:
        return skipped("venue_payload/venue_readback not provided")
    expected = {
        int(r["game_id"]): bool(str(r.get("city") or "").strip())
        for r in ctx["venue_payload"]
    }
    actual = {int(g): bool(str(c or "").strip()) for g, c in ctx["venue_readback"]}
    missing, extra = (
        sorted(set(expected) - set(actual)),
        sorted(set(actual) - set(expected)),
    )
    city_lost = sorted(
        g for g in set(expected) & set(actual) if expected[g] and not actual[g]
    )
    return Outcome(
        not (missing or extra or city_lost),
        observed={
            "expected": len(expected),
            "stored": len(actual),
            "missing": len(missing),
            "extra": len(extra),
            "city_lost": len(city_lost),
        },
        expected={"missing": 0, "extra": 0, "city_lost": 0},
    )


@register_check(
    "publish.post.grades_recomputed",
    stage="publish",
    severity=BLOCK,
    description="Stored v2 grades equal a recomputation from the frozen side, point and certified score",
)
def _grades(ctx: Mapping[str, Any]) -> Outcome:
    if ctx.get("grade_readback") is None:
        return skipped("grade_readback not provided")
    bad = grade_mismatches(ctx["grade_readback"])
    return Outcome(
        not bad,
        observed={"graded": len(ctx["grade_readback"]), "mismatches": len(bad)},
        expected={"mismatches": 0},
        detail=str(bad[:3]) if bad else "",
    )


def finalize(
    run: QualityRun,
    *,
    identity: Mapping[str, Any],
    code_sha: str = "unknown",
    inputs: Mapping[str, Any] | None = None,
    output_root: Path | None = Path("artifacts"),
) -> dict[str, Any]:
    """Build the receipt, write it locally when ``output_root`` is set, and return it."""
    receipt = build_receipt(run, identity=identity, code_sha=code_sha, inputs=inputs)
    if output_root is not None:
        receipt["_path"] = str(write_receipt_local(receipt, output_root))
    return receipt


def raise_if_blocked(run: QualityRun, phase: str) -> None:
    if run.blocked:
        failures = [
            f"{r.check_id}: {r.detail or r.observed}"
            for r in run.failures
            if r.severity == BLOCK
        ]
        raise PublishQualityError(
            f"publish {phase} checks failed; nothing committed: " + "; ".join(failures)
        )
