"""Ingestion (Bronze) checks. All register at ``warn`` until receipts are reviewed.

Each registered check reads named inputs from the run context and returns
``skipped`` when its input is absent, so a check never passes by having nothing
to look at. Inputs (all optional):

- ``catalog_versions``: DataFrame ``dataset, version_id, as_of[, seasons]`` of validated versions
- ``pins``: mapping ``dataset -> version_id`` chosen for the run
- ``expected_requests`` / ``completed_requests``: sets of request identities
- ``schedule``: DataFrame ``season, week, game_id`` (the pinned schedule)
- ``games``: DataFrame ``season, week, game_id, completed, home_points, away_points``
- ``plays``: DataFrame with ``game_id`` and optionally ``ppa``; ``drives``: ``game_id``
- ``min_plays``: per-completed-game play floor (default 60)
- ``odds_capture``: mapping with ``unmatched_events``; ``market_quotes``: DataFrame
- ``schemas``: mapping ``name -> (DataFrame, DatasetSchema)`` for contract evidence

Hard write-time rejection stays in ``validate_frame``; these checks add evidence the
hard gate does not cover (completeness, coverage, pinning) and record it in the
receipt.
"""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from cks_picks_cfb.quality.checks import WARN, Outcome, register_check, skipped

DEFAULT_MIN_PLAYS = 60
PRICE_COLUMNS = ("home_spread_price", "away_spread_price", "over_price", "under_price")


def _ambiguous_by_season(group: pd.DataFrame) -> bool:
    """True when the versions cannot be told apart by a season filter.

    Versions are distinguishable only if each declares a non-empty season set and the
    sets are pairwise disjoint. A missing ``seasons`` column counts as empty.
    """
    if "seasons" not in group.columns:
        return True
    sets = [set(s or ()) for s in group["seasons"]]
    if any(not s for s in sets):
        return True
    return any(
        sets[a] & sets[b] for a in range(len(sets)) for b in range(a + 1, len(sets))
    )


def unpinned_multi_version_datasets(
    versions: pd.DataFrame, pins: Mapping[str, str]
) -> dict[str, list[str]]:
    """Datasets whose newest ``as_of`` has several versions a season filter cannot split.

    Silver can hold many validated versions for one ``as_of``. ``venues`` holds one
    per capture year with no season partition, so "the newest" is arbitrary and the
    dataset needs an explicit pin naming one of its versions. Season-partitioned
    datasets (disjoint ``seasons``) are selected by season and do not need a pin.
    ``versions`` has ``dataset, version_id, as_of`` and optionally ``seasons``.
    """
    problems: dict[str, list[str]] = {}
    for dataset, group in versions.groupby("dataset"):
        newest = group[group["as_of"] == group["as_of"].max()]
        ids = sorted(newest["version_id"].astype(str))
        if len(ids) < 2 or not _ambiguous_by_season(newest):
            continue
        pin = pins.get(str(dataset))
        if pin is None or pin not in set(group["version_id"].astype(str)):
            problems[str(dataset)] = ids
    return problems


def request_gaps(expected: set[str], completed: set[str]) -> dict[str, list[str]]:
    return {
        "missing": sorted(expected - completed),
        "unexpected": sorted(completed - expected),
    }


def games_vs_schedule(games: pd.DataFrame, schedule: pd.DataFrame) -> dict[str, Any]:
    expected = set(schedule["game_id"].astype(int))
    present = set(games["game_id"].astype(int))
    duplicates = int(games["game_id"].duplicated().sum())
    missing = sorted(expected - present)
    extra = sorted(present - expected)
    weeks = (
        sorted(set(schedule.loc[schedule["game_id"].astype(int).isin(missing), "week"]))
        if missing
        else []
    )
    return {
        "missing": missing,
        "extra": extra,
        "duplicates": duplicates,
        "weeks_with_missing": [int(w) for w in weeks],
    }


def completed_score_nulls(games: pd.DataFrame) -> dict[str, Any]:
    done = games[games["completed"].fillna(False).astype(bool)]
    bad = done[done["home_points"].isna() | done["away_points"].isna()]
    return {
        "completed": len(done),
        "null_scores": sorted(bad["game_id"].astype(int)),
    }


def play_coverage(
    games: pd.DataFrame,
    plays: pd.DataFrame,
    drives: pd.DataFrame | None,
    *,
    min_plays: int,
) -> dict[str, Any]:
    done = set(
        games.loc[games["completed"].fillna(False).astype(bool), "game_id"].astype(int)
    )
    counts = plays.groupby(plays["game_id"].astype(int)).size()
    no_plays = sorted(done - set(counts.index))
    short = sorted(int(g) for g, n in counts.items() if g in done and n < min_plays)
    out: dict[str, Any] = {
        "completed": len(done),
        "no_plays": no_plays,
        "below_floor": short,
    }
    if drives is not None:
        out["no_drives"] = sorted(done - set(drives["game_id"].astype(int)))
    return out


def price_presence(quotes: pd.DataFrame) -> dict[str, Any]:
    present = [c for c in PRICE_COLUMNS if c in quotes.columns]
    if not present or quotes.empty:
        return {
            "rows": len(quotes),
            "with_any_price": 0,
            "rate": 0.0,
            "columns": present,
        }
    with_any = int(quotes[present].notna().any(axis=1).sum())
    return {
        "rows": len(quotes),
        "with_any_price": with_any,
        "rate": with_any / len(quotes),
        "columns": present,
    }


@register_check(
    "ingest.versions_pinned",
    stage="ingest",
    severity=WARN,
    description="Datasets with several validated versions at the newest as_of are pinned",
)
def _versions_pinned(ctx: Mapping[str, Any]) -> Outcome:
    if ctx.get("catalog_versions") is None:
        return skipped("catalog_versions not provided")
    problems = unpinned_multi_version_datasets(
        ctx["catalog_versions"], ctx.get("pins") or {}
    )
    return Outcome(
        not problems,
        observed=problems,
        expected="every multi-version dataset has a pin naming one of its versions",
        detail="" if not problems else f"unpinned: {sorted(problems)}",
    )


@register_check(
    "ingest.capture_completeness",
    stage="ingest",
    severity=WARN,
    description="Every requested entity/season/week request has a completed attempt",
)
def _capture_completeness(ctx: Mapping[str, Any]) -> Outcome:
    if ctx.get("expected_requests") is None or ctx.get("completed_requests") is None:
        return skipped("expected_requests/completed_requests not provided")
    gaps = request_gaps(set(ctx["expected_requests"]), set(ctx["completed_requests"]))
    return Outcome(
        not gaps["missing"],
        observed={
            "missing": len(gaps["missing"]),
            "unexpected": len(gaps["unexpected"]),
        },
        expected={"missing": 0},
        detail=f"missing: {gaps['missing'][:10]}" if gaps["missing"] else "",
    )


@register_check(
    "ingest.games_vs_schedule",
    stage="ingest",
    severity=WARN,
    description="Every scheduled game was ingested once (extra games are reported, not failed)",
)
def _games_vs_schedule(ctx: Mapping[str, Any]) -> Outcome:
    if ctx.get("games") is None or ctx.get("schedule") is None:
        return skipped("games/schedule not provided")
    gap = games_vs_schedule(ctx["games"], ctx["schedule"])
    # Extra games are expected: Silver holds every FBS-involved game while the
    # published schedule is narrower. They are reported, not failed.
    ok = not (gap["missing"] or gap["duplicates"])
    return Outcome(
        ok,
        observed={k: (len(v) if isinstance(v, list) else v) for k, v in gap.items()},
        expected={"missing": 0, "duplicates": 0},
        detail=""
        if ok
        else f"missing {gap['missing'][:10]}, duplicates {gap['duplicates']}",
    )


@register_check(
    "ingest.completed_games_have_scores",
    stage="ingest",
    severity=WARN,
    description="Completed games carry both final scores",
)
def _completed_scores(ctx: Mapping[str, Any]) -> Outcome:
    if ctx.get("games") is None:
        return skipped("games not provided")
    res = completed_score_nulls(ctx["games"])
    return Outcome(
        not res["null_scores"],
        observed={
            "completed": res["completed"],
            "null_scores": len(res["null_scores"]),
        },
        expected={"null_scores": 0},
        detail=f"game ids: {res['null_scores'][:10]}" if res["null_scores"] else "",
    )


@register_check(
    "ingest.plays_and_drives_per_completed_game",
    stage="ingest",
    severity=WARN,
    description="Every completed game has plays at or above the floor, and drives",
)
def _play_coverage(ctx: Mapping[str, Any]) -> Outcome:
    if ctx.get("games") is None or ctx.get("plays") is None:
        return skipped("games/plays not provided")
    res = play_coverage(
        ctx["games"],
        ctx["plays"],
        ctx.get("drives"),
        min_plays=int(ctx.get("min_plays", DEFAULT_MIN_PLAYS)),
    )
    bad = res["no_plays"] or res["below_floor"] or res.get("no_drives")
    return Outcome(
        not bad,
        observed={k: (len(v) if isinstance(v, list) else v) for k, v in res.items()},
        expected={"no_plays": 0, "below_floor": 0, "no_drives": 0},
        detail=""
        if not bad
        else f"no plays {res['no_plays'][:10]}, short {res['below_floor'][:10]}",
    )


@register_check(
    "ingest.ppa_coverage",
    stage="ingest",
    severity=WARN,
    description="Provider PPA column is present and its missing count is recorded before any fill",
)
def _ppa_coverage(ctx: Mapping[str, Any]) -> Outcome:
    if ctx.get("plays") is None:
        return skipped("plays not provided")
    plays = ctx["plays"]
    if "ppa" not in plays.columns:
        return Outcome(False, expected="ppa column present", detail="ppa column absent")
    missing = int(plays["ppa"].isna().sum())
    return Outcome(
        True,
        observed={"plays": len(plays), "ppa_missing": missing},
        expected="count recorded; a numeric zero is not treated as missing",
    )


@register_check(
    "ingest.odds_unmatched_events",
    stage="ingest",
    severity=WARN,
    description="Odds API events that matched no scheduled game are counted and zero",
)
def _odds_unmatched(ctx: Mapping[str, Any]) -> Outcome:
    if ctx.get("odds_capture") is None:
        return skipped("odds_capture not provided")
    count = int(ctx["odds_capture"].get("unmatched_events", 0))
    return Outcome(
        count == 0,
        observed={"unmatched_events": count},
        expected={"unmatched_events": 0},
    )


@register_check(
    "ingest.quote_price_presence",
    stage="ingest",
    severity=WARN,
    description="Captured market quotes carry at least some actual prices (price provenance)",
)
def _price_presence(ctx: Mapping[str, Any]) -> Outcome:
    if ctx.get("market_quotes") is None:
        return skipped("market_quotes not provided")
    res = price_presence(ctx["market_quotes"])
    if not res["columns"]:
        return skipped("market_quotes source carries no price columns")
    return Outcome(
        res["with_any_price"] > 0,
        observed=res,
        expected="rate above 0; a rate of 0 means every price is a default",
        detail="" if res["with_any_price"] else "no quote carries an actual price",
    )


@register_check(
    "ingest.schema_contract",
    stage="ingest",
    severity=WARN,
    description="Frames satisfy their dataset contract (the hard write gate, recorded in the receipt)",
)
def _schema_contract(ctx: Mapping[str, Any]) -> list[Outcome] | Outcome:
    if not ctx.get("schemas"):
        return skipped("schemas not provided")
    from cks_picks_cfb.data.schema_contracts import DatasetSchemaError, validate_frame

    outcomes = []
    for name, (frame, schema) in sorted(ctx["schemas"].items()):
        try:
            validate_frame(frame, schema)
            outcomes.append(Outcome(True, scope={"dataset": name}))
        except DatasetSchemaError as exc:
            outcomes.append(Outcome(False, detail=str(exc), scope={"dataset": name}))
    return outcomes
