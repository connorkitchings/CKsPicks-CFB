"""Executable, pre-kick quote selection and settlement helpers."""

from __future__ import annotations

import pandas as pd


def american_profit_per_unit(price: float | int | None) -> float:
    """Return the profit on a one-unit stake for American odds."""
    if price is None or pd.isna(price):
        return 1.0 / 1.1
    value = float(price)
    if value == 0:
        raise ValueError("American odds cannot be zero")
    return value / 100.0 if value > 0 else 100.0 / abs(value)


def pick_direction(prediction: float, consensus_line: float, *, target: str) -> str:
    """Choose a market side using the consensus line, before line shopping."""
    if target == "spread":
        return "home" if prediction + consensus_line >= 0 else "away"
    if target == "total":
        return "over" if prediction >= consensus_line else "under"
    raise ValueError("target must be spread or total")


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
