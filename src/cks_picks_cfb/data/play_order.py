"""Shared play order and the unresolved-play rule for ``byplay_v2`` consumers.

Plays are ordered by ``(season, game_id, period, drive_number, play_number)``, where the period
is the ``quarter`` column. The game clock is diagnostic only: several plays legitimately share
a second and the clock can run backwards, so it is never an ordering key and never a reason to
exclude a play. Overtime has no usable clock, so its order is the sequence alone. Provider play
IDs are not monotonic (negative synthetic IDs sit beside 18-digit IDs) and never order plays.

A play is *unresolved* in exactly two cases:

* ``missing_period``: the period is null or below 1 (``byplay`` fills a missing quarter with 0);
* ``tied_sequence``: distinct provider play IDs share ``(period, drive_number, play_number)``.

An unresolved play stays in the stream, because dropping it would move its score change onto
the next play. The flag lets consumers exclude it from order-sensitive measurements instead.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from cks_picks_cfb.data.play_identity import SOURCE_PLAY_ID

PLAY_ORDER_KEYS = ("season", "game_id", "quarter", "drive_number", "play_number")
REASON_MISSING_PERIOD = "missing_period"
REASON_TIED_SEQUENCE = "tied_sequence"
UNRESOLVED_REASONS = (REASON_MISSING_PERIOD, REASON_TIED_SEQUENCE)
FLAG_COLUMN = "play_order_unresolved"
REASON_COLUMN = "play_order_reason"
_REQUIRED = ("game_id", "quarter", "drive_number", "play_number")


class PlayOrderError(ValueError):
    """Raised when plays cannot be ordered under the rule without guessing."""


def order_keys(frame: pd.DataFrame) -> list[str]:
    """The ordering keys present in ``frame`` (``season`` is optional)."""
    missing = [name for name in _REQUIRED if name not in frame.columns]
    if missing:
        raise PlayOrderError(f"plays lack ordering columns: {missing}")
    return [name for name in PLAY_ORDER_KEYS if name in frame.columns]


def order_plays(frame: pd.DataFrame) -> pd.DataFrame:
    """Plays in stable ``PLAY_ORDER_KEYS`` order; never converts values or uses the clock."""
    return frame.sort_values(order_keys(frame), kind="mergesort")


def missing_period(frame: pd.DataFrame) -> pd.Series:
    quarter = pd.to_numeric(frame["quarter"], errors="coerce")
    return quarter.isna() | (quarter < 1)


def flag_unresolved_plays(frame: pd.DataFrame) -> pd.DataFrame:
    """Index-aligned ``play_order_unresolved`` / ``play_order_reason`` for every play.

    A frame without ``source_play_id`` (``byplay_v1``) is unique on its sequence, so only a
    missing period can be unresolved; a duplicated sequence there is an error, because the
    helper must not decide which duplicate wins.
    """
    keys = order_keys(frame)
    absent = missing_period(frame)
    tied = pd.Series(False, index=frame.index)
    if SOURCE_PLAY_ID in frame.columns:
        valid = frame.loc[~absent]
        size = valid.groupby(keys, sort=False)[SOURCE_PLAY_ID].transform("nunique")
        tied.loc[valid.index] = size > 1
    elif frame.loc[~absent].duplicated(keys).any():
        raise PlayOrderError(
            "a frame without source_play_id must be unique on its sequence"
        )
    reason = pd.Series(
        [
            REASON_MISSING_PERIOD if gone else REASON_TIED_SEQUENCE if tie else None
            for gone, tie in zip(absent, tied)
        ],
        index=frame.index,
        dtype=object,
    )
    return pd.DataFrame({FLAG_COLUMN: absent | tied, REASON_COLUMN: reason})


def tie_groups(frame: pd.DataFrame) -> list[pd.Index]:
    """Index labels of each tied-sequence group, in play order."""
    if SOURCE_PLAY_ID not in frame.columns:
        return []
    keys = order_keys(frame)
    ordered = order_plays(frame)
    ordered = ordered.loc[~missing_period(ordered)]
    size = ordered.groupby(keys, sort=False)[SOURCE_PLAY_ID].transform("nunique")
    tied = ordered.loc[size > 1]
    return [group.index for _, group in tied.groupby(keys, sort=False)]


def unresolved_play_keys(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Every unresolved play by key, with its reason and tie-group size, for disclosure."""
    flags = flag_unresolved_plays(frame)
    keys = order_keys(frame)
    unresolved = frame.loc[flags[FLAG_COLUMN]].assign(
        **{REASON_COLUMN: flags.loc[flags[FLAG_COLUMN], REASON_COLUMN]}
    )
    if unresolved.empty:
        return []
    if SOURCE_PLAY_ID in unresolved.columns:
        size = unresolved.groupby(keys, sort=False)[SOURCE_PLAY_ID].transform("size")
    else:
        size = pd.Series(1, index=unresolved.index)
    unresolved = unresolved.assign(group_size=size)
    tail = [SOURCE_PLAY_ID] if SOURCE_PLAY_ID in unresolved.columns else []
    unresolved = unresolved.sort_values([*keys, *tail], kind="mergesort")
    out = []
    for row in unresolved.to_dict("records"):
        item = {name: _plain(row[name]) for name in keys}
        if tail:
            item[SOURCE_PLAY_ID] = str(row[SOURCE_PLAY_ID])
        item["reason"] = row[REASON_COLUMN]
        item["group_size"] = int(row["group_size"])
        out.append(item)
    return out


def _plain(value: Any) -> Any:
    return value.item() if hasattr(value, "item") else value
