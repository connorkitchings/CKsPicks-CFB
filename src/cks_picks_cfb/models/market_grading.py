"""Executable, pre-kick quote selection and settlement helpers.

Policy version: model_side_best_quote_v1
-----------------------------------------
1. Derive the model's side from the consensus/canonical snapshot line.  Line
   shopping never changes the already-fixed direction.
2. Admit only quote rows that are linked to the canonical snapshot, share the
   same game_id and target, carry a non-null point and side price, and whose
   capture timestamp is strictly before the game's kickoff.
3. Among eligible candidates for the fixed side:
   - Spread  → highest signed point (least-negative or most-positive favours
               the model team; e.g. -3.0 is better than -3.5 for "home").
   - Total   → lowest point for over, highest point for under.
   - Break equal points by better American price (higher profit_per_unit),
     then quote_id ascending for determinism.
4. Return a NormalizedQuote dict.  A zero canonical edge, no eligible quotes,
   or a missing price yields None (no lean, no grade).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import pandas as pd

# ---------------------------------------------------------------------------
# Policy version identifier
# ---------------------------------------------------------------------------

SELECTION_POLICY_VERSION = "model_side_best_quote_v1"


# ---------------------------------------------------------------------------
# Odds helpers
# ---------------------------------------------------------------------------


def american_profit_per_unit(price: float | int | None) -> float:
    """Return the profit on a one-unit stake for American odds."""
    if price is None or pd.isna(price):
        return 1.0 / 1.1
    value = float(price)
    if value == 0:
        raise ValueError("American odds cannot be zero")
    return value / 100.0 if value > 0 else 100.0 / abs(value)


# ---------------------------------------------------------------------------
# Direction derivation (consensus-first; prevents line shopping from flipping)
# ---------------------------------------------------------------------------


def pick_direction(prediction: float, consensus_line: float, *, target: str) -> str:
    """Choose a market side using the consensus line, before line shopping."""
    if target == "spread":
        return "home" if prediction + consensus_line >= 0 else "away"
    if target == "total":
        return "over" if prediction >= consensus_line else "under"
    raise ValueError("target must be spread or total")


# ---------------------------------------------------------------------------
# Normalized quote shape
# ---------------------------------------------------------------------------


@dataclass
class NormalizedQuote:
    """One executable, pre-kickoff quote selected for a run/game/target.

    All fields are required for a valid selection; the caller must store this
    alongside the prediction artifact before freezing.
    """

    quote_id: str
    snapshot_id: str
    game_id: int | str
    target: str  # 'spread' or 'total'
    side: str  # 'home'/'away' or 'over'/'under'
    point: float
    price: float
    edge: float  # |model_value - point|, positive
    policy_version: str  # always SELECTION_POLICY_VERSION
    captured_at: datetime  # immutable capture time of the raw quote


# ---------------------------------------------------------------------------
# Core selection service
# ---------------------------------------------------------------------------


def select_best_quote(
    *,
    target: str,
    prediction: float,
    canonical_snapshot_id: str,
    canonical_line: float | None,
    game_id: int | str,
    kickoff_utc: datetime,
    quote_candidates: list[dict[str, Any]],
) -> NormalizedQuote | None:
    """Select the best executable pre-kickoff quote for a single target.

    Parameters
    ----------
    target:
        ``'spread'`` or ``'total'``.
    prediction:
        Model forecast value (predicted home margin for spread; predicted total
        for total).
    canonical_snapshot_id:
        The frozen snapshot ID bound to this prediction.  Only quotes linked to
        this snapshot are eligible.
    canonical_line:
        The consensus/canonical line used to establish the model's side.  None
        or missing → no selection (unlined target).
    game_id:
        The game this prediction covers.  Quotes for other games are rejected.
    kickoff_utc:
        Game kickoff time in UTC.  Quotes captured at or after this time are
        rejected.
    quote_candidates:
        List of dicts.  Each dict must contain at a minimum:
          - ``quote_id``:      str
          - ``snapshot_id``:   str   (must match canonical_snapshot_id)
          - ``game_id``:       int or str (must match game_id)
          - ``target``:        str   (must match target)
          - ``captured_at``:   datetime (timezone-aware)
          - ``point``:         float
          - ``home_spread_price`` / ``away_spread_price`` /
            ``over_price`` / ``under_price``: float (side-specific price)

    Returns
    -------
    NormalizedQuote or None
        None when the canonical line is missing, the edge is zero, or no
        eligible quote exists.
    """
    if canonical_line is None or pd.isna(canonical_line):
        return None

    direction = pick_direction(prediction, canonical_line, target=target)

    # Ensure kickoff is tz-aware
    if kickoff_utc.tzinfo is None:
        kickoff_utc = kickoff_utc.replace(tzinfo=timezone.utc)

    eligible: list[dict[str, Any]] = []
    for q in quote_candidates:
        # Snapshot linkage
        if q.get("snapshot_id") != canonical_snapshot_id:
            continue
        # Game match
        if str(q.get("game_id")) != str(game_id):
            continue
        # Target match
        if q.get("target") != target:
            continue
        # Required fields present
        qt_id = q.get("quote_id")
        point = q.get("point")
        if qt_id is None or point is None or pd.isna(point):
            continue
        # Side-specific price
        price = _side_price(q, direction, target)
        if price is None or pd.isna(price):
            continue
        # Pre-kickoff capture
        cap = q.get("captured_at")
        if cap is None:
            continue
        if isinstance(cap, str):
            cap = datetime.fromisoformat(cap)
        if cap.tzinfo is None:
            cap = cap.replace(tzinfo=timezone.utc)
        if cap >= kickoff_utc:
            continue
        eligible.append(
            {
                "quote_id": qt_id,
                "point": float(point),
                "price": float(price),
                "captured_at": cap,
            }
        )

    if not eligible:
        return None

    # Sort: best point first, then best price, then quote_id ascending
    eligible.sort(key=lambda r: _sort_key(r, target=target, direction=direction))
    best = eligible[0]

    # Edge: how far the model forecast is from the selected point (always ≥ 0)
    if target == "spread":
        # home-signed: prediction + point (where point is the home-team line)
        edge = abs(prediction + best["point"])
    else:
        edge = abs(prediction - best["point"])

    return NormalizedQuote(
        quote_id=best["quote_id"],
        snapshot_id=canonical_snapshot_id,
        game_id=game_id,
        target=target,
        side=direction,
        point=best["point"],
        price=best["price"],
        edge=edge,
        policy_version=SELECTION_POLICY_VERSION,
        captured_at=best["captured_at"],
    )


def _side_price(
    q: dict[str, Any],
    direction: str,
    target: str,
) -> float | None:
    """Return the side-specific American price for a quote dict."""
    if target == "spread":
        if direction == "home":
            return q.get("home_spread_price")
        return q.get("away_spread_price")
    # total
    if direction == "over":
        return q.get("over_price")
    return q.get("under_price")


def _sort_key(
    row: dict[str, Any],
    *,
    target: str,
    direction: str,
) -> tuple:
    """Return a sort tuple so that the best quote sorts first (ascending)."""
    point = row["point"]
    price = row["price"]
    qt_id = row["quote_id"]

    if target == "spread":
        # Highest (least negative) point is best for the model's team side
        point_key = -point  # negate so ascending sort picks highest
    elif direction == "over":
        point_key = point  # lowest point is best for over
    else:
        point_key = -point  # highest point is best for under

    # Better price = higher profit per unit; negate so ascending picks best
    price_key = -american_profit_per_unit(price)
    return (point_key, price_key, qt_id)


# ---------------------------------------------------------------------------
# Legacy helper (retained for backward compatibility; production paths use
# select_best_quote which enforces snapshot/game/target/kickoff eligibility)
# ---------------------------------------------------------------------------


def select_best_available_quote(
    quotes: pd.DataFrame,
    *,
    target: str,
    direction: str,
) -> pd.Series:
    """Select best executable line, then price, then bookmaker key.

    Quotes must carry ``market`` (``spreads`` or ``totals``), ``side``,
    ``point``, ``price``, and ``bookmaker``.  Direction is intentionally
    determined before this function so line shopping cannot flip a wager.

    .. deprecated::
        Use :func:`select_best_quote` for production paths.  This helper does
        not enforce snapshot/game/kickoff eligibility.
    """
    market = "spreads" if target == "spread" else "totals"
    rows = quotes[(quotes["market"] == market) & (quotes["side"] == direction)].copy()
    required = {"point", "price", "bookmaker"}
    missing = sorted(required - set(rows.columns))
    if missing:
        raise ValueError(f"Quote rows are missing columns: {missing}")
    rows = rows.dropna(subset=["point", "price", "bookmaker"])
    if rows.empty:
        raise ValueError(f"No executable {target}/{direction} quote")
    rows["point"] = pd.to_numeric(rows["point"], errors="raise")
    rows["price"] = pd.to_numeric(rows["price"], errors="raise")
    ascending_line = target == "total" and direction == "over"
    return rows.sort_values(
        ["point", "price", "bookmaker"],
        ascending=[ascending_line, False, True],
        kind="stable",
    ).iloc[0]


# ---------------------------------------------------------------------------
# Settlement
# ---------------------------------------------------------------------------


def settle_quote(
    *,
    target: str,
    direction: str,
    actual_spread: float | None = None,
    actual_total: float | None = None,
    point: float,
    price: float | int | None,
) -> float:
    """Settle a one-unit spread or total wager; a push returns zero."""
    if target == "spread":
        if actual_spread is None or direction not in {"home", "away"}:
            raise ValueError("Spread settlement requires home/away and actual_spread")
        signed_actual = (
            float(actual_spread) if direction == "home" else -float(actual_spread)
        )
        margin = signed_actual + float(point)
    elif target == "total":
        if actual_total is None or direction not in {"over", "under"}:
            raise ValueError("Total settlement requires over/under and actual_total")
        margin = float(actual_total) - float(point)
        if direction == "under":
            margin = -margin
    else:
        raise ValueError("target must be spread or total")
    if margin == 0:
        return 0.0
    return american_profit_per_unit(price) if margin > 0 else -1.0


# ---------------------------------------------------------------------------
# Coverage audit helpers (read-only; never mutates R2 or Neon)
# ---------------------------------------------------------------------------


def audit_quote_coverage(
    *,
    run_id: str,
    game_id: int | str,
    target: str,
    prediction: float,
    canonical_snapshot_id: str,
    canonical_line: float | None,
    kickoff_utc: datetime,
    quote_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return a read-only audit record for one prediction target.

    Does not mutate any data. Used by the coverage-audit script to account for
    every prediction target without guesses.

    Returns a dict with:
      - ``eligible``: bool
      - ``selected_quote_id``: str or None
      - ``selected_point``: float or None
      - ``no_line_reason``: str or None (only when not eligible)
      - ``candidate_count``: int (total candidates before filtering)
      - ``eligible_count``: int (candidates passing all filters)
    """
    if canonical_line is None or pd.isna(canonical_line):
        return {
            "run_id": run_id,
            "game_id": game_id,
            "target": target,
            "eligible": False,
            "selected_quote_id": None,
            "selected_point": None,
            "no_line_reason": "missing_canonical_line",
            "candidate_count": len(quote_candidates),
            "eligible_count": 0,
        }

    direction = pick_direction(prediction, canonical_line, target=target)

    # Count snapshot-scoped, game-matched, target-matched, priced, pre-kickoff
    if kickoff_utc.tzinfo is None:
        kickoff_utc = kickoff_utc.replace(tzinfo=timezone.utc)

    reasons: list[str] = []
    eligible_rows: list[dict] = []
    for q in quote_candidates:
        if q.get("snapshot_id") != canonical_snapshot_id:
            reasons.append("snapshot_mismatch")
            continue
        if str(q.get("game_id")) != str(game_id):
            reasons.append("game_mismatch")
            continue
        if q.get("target") != target:
            reasons.append("target_mismatch")
            continue
        qt_id = q.get("quote_id")
        point = q.get("point")
        if qt_id is None or point is None or pd.isna(point):
            reasons.append("missing_point_or_id")
            continue
        price = _side_price(q, direction, target)
        if price is None or pd.isna(price):
            reasons.append("missing_side_price")
            continue
        cap = q.get("captured_at")
        if cap is None:
            reasons.append("missing_captured_at")
            continue
        if isinstance(cap, str):
            cap = datetime.fromisoformat(cap)
        if cap.tzinfo is None:
            cap = cap.replace(tzinfo=timezone.utc)
        if cap >= kickoff_utc:
            reasons.append("post_kickoff")
            continue
        eligible_rows.append(
            {
                "quote_id": qt_id,
                "point": float(point),
                "price": float(price),
                "captured_at": cap,
            }
        )

    if not eligible_rows:
        no_line_reason = reasons[0] if reasons else "no_quotes"
        return {
            "run_id": run_id,
            "game_id": game_id,
            "target": target,
            "eligible": False,
            "selected_quote_id": None,
            "selected_point": None,
            "no_line_reason": no_line_reason,
            "candidate_count": len(quote_candidates),
            "eligible_count": 0,
        }

    eligible_rows.sort(key=lambda r: _sort_key(r, target=target, direction=direction))
    best = eligible_rows[0]

    return {
        "run_id": run_id,
        "game_id": game_id,
        "target": target,
        "eligible": True,
        "selected_quote_id": best["quote_id"],
        "selected_point": best["point"],
        "no_line_reason": None,
        "candidate_count": len(quote_candidates),
        "eligible_count": len(eligible_rows),
    }
