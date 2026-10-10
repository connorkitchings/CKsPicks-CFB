"""Market-source lock for a week that has no original served run (pure, I/O-free).

The corrected replay of an *unserved* week (Week 6, which only ever had the display-only
run) has no original market snapshot set to pin, unlike Weeks 0-5. This module pins the
Silver market datasets that exist for that week and classifies, for every game and target,
whether an eligible quote exists under the same rule the replay uses
(``models.market_grading.select_best_quote``: linked to the canonical snapshot, captured
before kickoff and no later than the forecast cutoff).

A game/target without an eligible quote is a **verified gap**: no selection and no grade,
never a fabricated or post-kickoff quote (repair-track contract, decision of 2026-10-08).
"""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any

import pandas as pd

from cks_picks_cfb.models.late_quotes import validate_late_evidence
from cks_picks_cfb.models.market_grading import select_best_quote

TARGETS = ("spread", "total")
LINE_COLUMN = {"spread": "spread_line", "total": "total_line"}
SCHEMA = "week_market_sources_lock_v1"

#: Why a game/target has no eligible quote.
STATUS_ELIGIBLE = "eligible"
STATUS_NO_SNAPSHOT = "no_snapshot"
STATUS_NO_CANONICAL_LINE = "no_canonical_line"
STATUS_NO_QUOTE = "no_quote"
STATUS_POST_KICKOFF_ONLY = "post_kickoff_only"
STATUS_AFTER_AS_OF_ONLY = "after_as_of_only"


class MarketLockError(ValueError):
    """The market sources cannot be locked without inventing or hiding evidence."""


def _utc(value: Any) -> datetime:
    stamp = pd.Timestamp(value)
    stamp = (
        stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")
    )
    return stamp.to_pydatetime()


def _linked_ids(snapshot: Mapping[str, Any]) -> set[str]:
    linked = snapshot.get("source_quote_ids", "[]")
    if isinstance(linked, str):
        linked = json.loads(linked)
    return {str(item) for item in (linked if linked is not None else [])}


def classify_week_markets(
    snapshots: pd.DataFrame,
    quotes: pd.DataFrame,
    schedule: pd.DataFrame,
    *,
    as_of: str,
    accepted_late_quotes: list[dict[str, Any]] | None = None,
    cfbd_comparison_receipt: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """One row per scheduled game and target with its quote-eligibility status.

    ``schedule`` has ``game_id`` and ``kickoff_utc`` for exactly the week's games;
    ``snapshots`` one canonical row per game (``market_snapshot_id``, ``spread_line``,
    ``total_line``, ``market_captured_at``, ``source_quote_ids``); ``quotes`` the quote
    rows (``quote_id``, ``game_id``, ``captured_at``, and ``spread`` / ``total`` points).
    """
    validate_late_evidence(accepted_late_quotes or [], cfbd_comparison_receipt)
    for name, frame, needed in (
        ("snapshots", snapshots, {"game_id", "market_snapshot_id"}),
        ("quotes", quotes, {"game_id", "quote_id", "captured_at"}),
        ("schedule", schedule, {"game_id", "kickoff_utc"}),
    ):
        if missing := needed - set(frame.columns):
            raise MarketLockError(f"{name} lacks columns: {sorted(missing)}")
    if schedule["game_id"].duplicated().any():
        raise MarketLockError("schedule has duplicate game ids")
    if snapshots["game_id"].duplicated().any():
        raise MarketLockError("market snapshots have duplicate canonical games")
    cutoff = _utc(as_of)
    if "market_captured_at" in snapshots.columns:
        captured = pd.to_datetime(snapshots["market_captured_at"], utc=True)
        if captured.isna().any() or (captured > pd.Timestamp(cutoff)).any():
            raise MarketLockError("a market snapshot was captured after as_of")
    by_game = snapshots.set_index("game_id")
    records = quotes.to_dict("records")
    rows: list[dict[str, Any]] = []
    for game in schedule.sort_values("game_id").itertuples(index=False):
        game_id = int(game.game_id)
        kickoff = _utc(game.kickoff_utc)
        snapshot = by_game.loc[game_id] if game_id in by_game.index else None
        for target in TARGETS:
            row = {
                "game_id": game_id,
                "target": target,
                "kickoff_utc": kickoff.isoformat().replace("+00:00", "Z"),
            }
            if snapshot is None:
                rows.append({**row, "status": STATUS_NO_SNAPSHOT})
                continue
            line = snapshot.get(LINE_COLUMN[target])
            if line is None or pd.isna(line):
                rows.append({**row, "status": STATUS_NO_CANONICAL_LINE})
                continue
            linked = _linked_ids(snapshot)
            snapshot_id = str(snapshot["market_snapshot_id"])
            candidates = [
                {
                    **quote,
                    "snapshot_id": snapshot_id,
                    "entity": "betting_lines"
                    if quote.get("__capture_provider") == "cfbd"
                    else quote.get("entity"),
                    "target": target,
                    "point": quote.get(target),
                }
                for quote in records
                if int(quote["game_id"]) == game_id
                and (not linked or str(quote["quote_id"]) in linked)
            ]
            # Existence of an eligible quote does not depend on the model side, so any
            # prediction works; the rule itself is the replay's own.
            selected = select_best_quote(
                target=target,
                prediction=0.0,
                canonical_snapshot_id=snapshot_id,
                canonical_line=float(line),
                game_id=game_id,
                kickoff_utc=kickoff,
                quote_candidates=candidates,
                forecast_cutoff=cutoff,
                accepted_late_quotes=accepted_late_quotes,
            )
            if selected is not None:
                rows.append({**row, "status": STATUS_ELIGIBLE})
                continue
            priced = [
                _utc(c["captured_at"])
                for c in candidates
                if c.get("point") is not None and not pd.isna(c["point"])
            ]
            if not priced:
                status = STATUS_NO_QUOTE
            elif all(stamp >= kickoff for stamp in priced):
                status = STATUS_POST_KICKOFF_ONLY
            else:
                status = STATUS_AFTER_AS_OF_ONLY
            rows.append({**row, "status": status})
    return rows


def verified_gaps(rows: list[Mapping[str, Any]], *, week: int) -> list[dict[str, Any]]:
    """The game/targets that get no selection and no grade, in the lock's gap format."""
    return [
        {
            "week": week,
            "game_id": row["game_id"],
            "target": row["target"],
            "status": f"{row['status']}; verified gap, no selection or grade",
        }
        for row in rows
        if row["status"] != STATUS_ELIGIBLE
    ]


def coverage_summary(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    games = {row["game_id"] for row in rows}
    summary: dict[str, Any] = {"games": len(games)}
    for target in TARGETS:
        target_rows = [row for row in rows if row["target"] == target]
        counts: dict[str, int] = {}
        for row in target_rows:
            counts[row["status"]] = counts.get(row["status"], 0) + 1
        summary[target] = {
            "eligible": counts.get(STATUS_ELIGIBLE, 0),
            "gaps": len(target_rows) - counts.get(STATUS_ELIGIBLE, 0),
            "by_status": dict(sorted(counts.items())),
        }
    return summary


def week_entry(
    *,
    as_of: str,
    cutoff_source: Mapping[str, Any],
    source_manifest: Mapping[str, Any],
    games: Mapping[str, Any],
    market_quotes: Mapping[str, Any],
    market_snapshots: Mapping[str, Any],
    rows: list[Mapping[str, Any]],
    week: int,
    accepted_late_quotes: list[dict[str, Any]] | None = None,
    cfbd_comparison_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """The ``weeks[str(week)]`` entry of the reconstruction source refs."""
    validate_late_evidence(accepted_late_quotes or [], cfbd_comparison_receipt)
    return {
        "accepted_late_quotes": list(accepted_late_quotes or []),
        "cfbd_comparison_receipt": dict(cfbd_comparison_receipt or {}),
        "as_of": as_of,
        "cutoff_source": dict(cutoff_source),
        "market_sources": {
            "games": dict(games),
            "market_quotes": dict(market_quotes),
            "market_snapshots": dict(market_snapshots),
        },
        "source_manifest": dict(source_manifest),
        "market_gaps": verified_gaps(rows, week=week),
        "market_coverage": coverage_summary(rows),
    }


def extend_source_refs(
    base: Mapping[str, Any], *, week: int, entry: Mapping[str, Any]
) -> dict[str, Any]:
    """Add one unserved week to the reconstruction source refs; earlier weeks never change."""
    if base.get("schema_version") != "reconstruction_source_refs_v1":
        raise MarketLockError("unknown reconstruction source refs schema")
    weeks = {int(key) for key in base["weeks"]}
    if week in weeks:
        raise MarketLockError(f"week {week} already has market sources")
    if week != max(weeks) + 1:
        raise MarketLockError(f"week {week} does not follow the last locked week")
    refs = copy.deepcopy(dict(base))
    refs["weeks"][str(week)] = dict(entry)
    return refs
