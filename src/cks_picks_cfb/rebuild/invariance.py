"""Cell-level v1 against v2 comparison for the invariance proof (contract 2026-10-09/01, Task 5).

Pure functions over frames. A difference outside the collision games is a finding; a
difference inside them becomes a discrepancy-ledger row naming the original value, the
corrected value, the source evidence, the disposition and the descendants it reaches. Equality
semantics (tolerance, null handling, datetimes) are those of ``published_diff``.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import pandas as pd

from cks_picks_cfb.rebuild.published_diff import _plain, _same


@dataclass(frozen=True)
class CellDiff:
    keys: tuple[str, ...]
    rows_compared: int
    cells_compared: int
    only_left: pd.DataFrame
    only_right: pd.DataFrame
    cells: pd.DataFrame  # keys..., column, left, right


def add_ordinal(
    frame: pd.DataFrame, keys: Sequence[str], order: Sequence[str]
) -> pd.DataFrame:
    """Number the rows that share ``keys`` (in ``order``) so repeated keys stay distinct."""
    ordered = frame.sort_values([*keys, *order], kind="mergesort")
    return ordered.assign(_ordinal=ordered.groupby(list(keys), dropna=False).cumcount())


def cell_diff(
    left: pd.DataFrame,
    right: pd.DataFrame,
    *,
    keys: Sequence[str],
    columns: Sequence[str] | None = None,
    tolerance: float = 1e-9,
) -> CellDiff:
    """Compare two frames on ``keys``; every differing cell and every one-sided row."""
    keys = tuple(keys)
    for side, frame in (("left", left), ("right", right)):
        if frame.duplicated(list(keys)).any():
            raise ValueError(f"{side} frame is not unique on {list(keys)}")
    shared = [c for c in left.columns if c in right.columns and c not in keys]
    use = list(shared if columns is None else [c for c in columns if c in shared])
    merged = left[[*keys, *use]].merge(
        right[[*keys, *use]],
        on=list(keys),
        how="outer",
        suffixes=("_l", "_r"),
        indicator=True,
    )
    both = merged[merged["_merge"] == "both"].reset_index(drop=True)
    only_left = (
        merged[merged["_merge"] == "left_only"][list(keys)]
        .sort_values(list(keys))
        .reset_index(drop=True)
    )
    only_right = (
        merged[merged["_merge"] == "right_only"][list(keys)]
        .sort_values(list(keys))
        .reset_index(drop=True)
    )
    pieces = []
    for column in use:
        same = _same(
            both[f"{column}_l"],
            both[f"{column}_r"],
            json_column=False,
            tolerance=tolerance,
        )
        bad = both.loc[~same.to_numpy(), list(keys)].copy()
        if bad.empty:
            continue
        bad["column"] = column
        bad["left"] = both.loc[~same.to_numpy(), f"{column}_l"].to_numpy()
        bad["right"] = both.loc[~same.to_numpy(), f"{column}_r"].to_numpy()
        pieces.append(bad)
    cells = (
        pd.concat(pieces, ignore_index=True)
        if pieces
        else pd.DataFrame(columns=[*keys, "column", "left", "right"])
    )
    if not cells.empty:
        cells = cells.sort_values([*keys, "column"], kind="mergesort").reset_index(
            drop=True
        )
    return CellDiff(
        keys=keys,
        rows_compared=int(len(both)),
        cells_compared=int(len(both) * len(use)),
        only_left=only_left,
        only_right=only_right,
        cells=cells,
    )


def games_touched(diff: CellDiff, game_column: str = "game_id") -> set[int]:
    games: set[int] = set()
    for frame in (diff.cells, diff.only_left, diff.only_right):
        if not frame.empty:
            games |= {int(g) for g in frame[game_column].unique()}
    return games


def summarize(
    diff: CellDiff,
    collision_games: Collection[int],
    *,
    left_rows: int,
    right_rows: int,
    game_column: str = "game_id",
) -> dict[str, Any]:
    """Counts for the report; ``outside`` must be zero or the proof fails."""
    collision = {int(g) for g in collision_games}
    games = games_touched(diff, game_column)
    outside = sorted(games - collision)

    def n_outside(frame: pd.DataFrame) -> int:
        return (
            0
            if frame.empty
            else int((~frame[game_column].astype(int).isin(collision)).sum())
        )

    return {
        "rows_v1": left_rows,
        "rows_v2": right_rows,
        "rows_compared": diff.rows_compared,
        "cells_compared": diff.cells_compared,
        "cells_changed": int(len(diff.cells)),
        "rows_only_v1": int(len(diff.only_left)),
        "rows_only_v2": int(len(diff.only_right)),
        "games_touched": sorted(games),
        "outside_collision": {
            "games": outside,
            "cells": n_outside(diff.cells),
            "rows_only_v1": n_outside(diff.only_left),
            "rows_only_v2": n_outside(diff.only_right),
        },
    }


def _text(value: Any) -> Any:
    plain = _plain(value)
    if isinstance(plain, (list, dict)):
        return json.dumps(plain, sort_keys=True, default=str)
    return plain


def ledger_rows(
    diff: CellDiff,
    *,
    table: str,
    season: int,
    collision_games: Collection[int],
    evidence_of: Callable[[int], str],
    disposition_of: Callable[[str, str, str, Any, Any], str],
    descendants: str,
    explanation: Mapping[str, str],
    game_column: str = "game_id",
) -> list[dict[str, Any]]:
    """One discrepancy-ledger row per changed cell and per one-sided row.

    Rows outside the collision games are still written (with disposition ``UNEXPLAINED``)
    so a failing proof carries its own evidence.
    """
    collision = {int(g) for g in collision_games}
    rows: list[dict[str, Any]] = []

    def base(
        record: Mapping[str, Any],
        change: str,
        column: str,
        left: Any = None,
        right: Any = None,
    ) -> dict[str, Any]:
        game = int(record[game_column])
        explained = game in collision
        return {
            "season": season,
            "game_id": game,
            "table": table,
            "key": json.dumps(
                {k: _text(record[k]) for k in diff.keys}, sort_keys=True, default=str
            ),
            "change": change,
            "column": column,
            "source_evidence": evidence_of(game) if explained else "",
            "disposition": disposition_of(change, table, column, left, right)
            if explained
            else "UNEXPLAINED",
            "affected_descendants": descendants if explained else "",
            "explanation": explanation[change]
            if explained
            else "difference outside the collision games",
        }

    for record in diff.cells.to_dict("records"):
        rows.append(
            {
                **base(
                    record,
                    "cell_changed",
                    record["column"],
                    record["left"],
                    record["right"],
                ),
                "v1_value": _text(record["left"]),
                "v2_value": _text(record["right"]),
            }
        )
    for record in diff.only_left.to_dict("records"):
        rows.append(
            {
                **base(record, "row_only_in_v1", ""),
                "v1_value": "present",
                "v2_value": "",
            }
        )
    for record in diff.only_right.to_dict("records"):
        rows.append(
            {
                **base(record, "row_only_in_v2", ""),
                "v1_value": "",
                "v2_value": "present",
            }
        )
    return rows
