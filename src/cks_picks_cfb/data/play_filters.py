"""Shared play-eligibility rules for team stats and the ratings that consume them.

Team stats owns the definition of which Silver ``byplay`` rows count as plays;
the ratings import it from here rather than keeping a copy.

Two filters, deliberately different:

* ``eligible_possession_play`` is the **V5 legacy filter**: regulation only, no
  special teams (``st``), penalty, two-point try, garbage time or dead play. The
  signed V5 measurement artifacts were built with it, so it must not change
  while that lineage is in service.
* ``scrimmage_play_mask`` is the legacy filter plus a play-type rule that drops
  kicking plays. It exists because CFBD labels a returned punt "Punt Return"
  and Silver enrichment (before the 2026-10-02 fix) did not list that type in
  its special-teams set, so those rows carry ``st == 0`` and look like 4th-down
  scrimmage plays by the punting team (``ppa`` 0.0, ``turnover`` 0, yards =
  return yards). The legacy filter still passes them, which dilutes per-play
  means and inflates conversion and explosive-play denominators. Anything that
  counts plays (team stats, and ratings built on team stats) uses
  ``scrimmage_play_mask``.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

_DEAD_MARKERS = ("timeout", "end of", "period end", "game end", "delay of game")

#: Play types that are kicking plays however Silver flagged ``st``.
KICKING_PLAY_TYPES = ("Punt Return",)
_KICKING_PLAY_PREFIXES = ("Punt", "Kickoff", "Field Goal", "Extra Point")


def finite_number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if np.isfinite(result) else None


def play_period(value: Any) -> str:
    numeric = finite_number(value)
    if numeric is None or numeric != int(numeric) or numeric < 1:
        return "unknown"
    return "overtime" if numeric >= 5 else "regulation"


def is_dead_play(value: Any) -> bool:
    text = str(value or "").casefold()
    return any(marker in text for marker in _DEAD_MARKERS)


def eligible_play(row: Any) -> bool:
    """V5 legacy play filter for one row (see module docstring)."""
    return (
        play_period(row.quarter) == "regulation"
        and finite_number(row.st) == 0
        and finite_number(row.penalty) == 0
        and finite_number(row.twopoint) == 0
        and finite_number(row.garbage) == 0
        and not is_dead_play(row.play_type)
    )


def eligible_possession_play_mask(byplay: pd.DataFrame) -> pd.Series:
    """Vector form of the V5 legacy filter. Still passes "Punt Return" rows."""
    return pd.Series(
        [eligible_play(row) for row in byplay.itertuples(index=False)],
        index=byplay.index,
        dtype=bool,
    )


def kicking_play_mask(play_type: pd.Series) -> pd.Series:
    text = play_type.astype(str)
    return text.isin(KICKING_PLAY_TYPES) | text.str.startswith(_KICKING_PLAY_PREFIXES)


def scrimmage_play_mask(byplay: pd.DataFrame) -> pd.Series:
    """Legacy filter minus kicking plays: the plays team stats counts."""
    return eligible_possession_play_mask(byplay) & ~kicking_play_mask(
        byplay["play_type"]
    )
