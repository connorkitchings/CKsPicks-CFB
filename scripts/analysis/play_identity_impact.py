#!/usr/bin/env python3
"""Task 1 of contract 2026-10-09/01: read-only play-identity impact diff and census.

Reads the pinned normalized Silver parents (Preview R2, read only) and reports, without
any write:

* each known sequence collision, classified by key;
* the plays that the period-first ordering rule would mark unresolved;
* a census of game-clock reversals (diagnostic only; nothing is excluded);
* drive-number reuse across provider drive IDs (drive-identity exposure);
* a shadow diff for the collision games: the historical ``keep="first"`` build against
  a build that retains every distinct provider play.

The shadow build gives the retained plays unique sequence numbers that follow
``(period, drive_number, play_number)`` so the unchanged v1 pipeline can run on them.
It is evidence for sizing the change, not the v2 implementation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCHEMA = "play_identity_impact_v1"
SEQ = ["game_id", "drive_number", "play_number"]
REGULATION_PERIODS = (1, 2, 3, 4)
PERIOD_SECONDS = 15 * 60
BUCKETS = (("le_10s", 1, 10), ("s11_to_60", 11, 60), ("gt_60s", 61, None))
SOURCE_TOKEN = re.compile(r"\d{4}:\d+:-?\d+:-?\d+")
ORDERING_RULE = (
    "order by (period, drive_number, play_number); the game clock is diagnostic only; "
    "a play is unresolved only when its period is missing or distinct provider play IDs "
    "remain tied on (period, drive_number, play_number); provider IDs never order plays"
)


def source_play_ids(values: pd.Series) -> pd.Series:
    """Provider play IDs as exact strings; float input is rejected, never converted."""
    if pd.api.types.is_float_dtype(values):
        raise ValueError("float provider play IDs lose precision; refusing to convert")
    if values.isna().any():
        raise ValueError("provider play ID is missing")
    converted = []
    for value in values:
        if isinstance(value, (bool, np.bool_, float, np.floating)):
            raise ValueError("float or boolean provider play ID")
        text = str(value).strip() if isinstance(value, str) else str(int(value))
        converted.append(str(int(text)))
    return pd.Series(converted, index=values.index, dtype="string")


def _seconds_remaining(frame: pd.DataFrame) -> pd.Series:
    return pd.to_numeric(frame["clock_minutes"], errors="coerce") * 60 + pd.to_numeric(
        frame["clock_seconds"], errors="coerce"
    )


def legacy_dedup(plays: pd.DataFrame) -> pd.DataFrame:
    """The historical by-play dedup: first row wins at each displayed sequence."""
    return plays.drop_duplicates(subset=SEQ, keep="first")


def order_diagnostics(plays: pd.DataFrame) -> dict[str, Any]:
    """Unresolved plays under the ordering rule plus the clock-reversal census."""
    frame = plays[
        [
            "game_id",
            "period",
            "drive_number",
            "play_number",
            "play_id",
            "clock_minutes",
            "clock_seconds",
        ]
    ].copy()
    frame["source_play_id"] = source_play_ids(frame["play_id"])
    frame["row"] = np.arange(len(frame))
    missing_period = frame["period"].isna()
    tie_size = (
        frame.loc[~missing_period]
        .groupby(["game_id", "period", "drive_number", "play_number"], sort=False)[
            "source_play_id"
        ]
        .transform("nunique")
    )
    tied = pd.Series(False, index=frame.index)
    tied.loc[tie_size.index] = tie_size > 1
    unresolved_mask = missing_period | tied
    unresolved = frame.loc[unresolved_mask].copy()
    unresolved["reason"] = np.where(
        missing_period.loc[unresolved.index], "missing_period", "tied_sequence"
    )

    resolved = frame.loc[
        ~unresolved_mask
        & frame["period"].isin(REGULATION_PERIODS)
        & _seconds_remaining(frame).notna()
    ].copy()
    resolved["remaining"] = _seconds_remaining(resolved)
    resolved = resolved.sort_values(
        ["game_id", "period", "drive_number", "play_number", "row"], kind="mergesort"
    )
    resolved["delta"] = resolved.groupby(["game_id", "period"], sort=False)[
        "remaining"
    ].diff()
    resolved["previous_id"] = resolved.groupby(["game_id", "period"], sort=False)[
        "source_play_id"
    ].shift()
    resolved["previous_remaining"] = resolved.groupby(
        ["game_id", "period"], sort=False
    )["remaining"].shift()
    # A period lasts 15 minutes; a larger remaining time is a corrupt clock value, not a
    # reversal in play order.
    resolved["impossible"] = (resolved["remaining"] > PERIOD_SECONDS) | (
        resolved["previous_remaining"] > PERIOD_SECONDS
    )
    compared = resolved["delta"].notna()
    reversals = resolved.loc[compared & (resolved["delta"] > 0)]
    valid = reversals.loc[~reversals["impossible"]]

    def bucketed(frame: pd.DataFrame) -> dict[str, int]:
        out = {}
        for name, low, high in BUCKETS:
            mask = frame["delta"] >= low
            if high is not None:
                mask &= frame["delta"] <= high
            out[name] = int(mask.sum())
        return out

    buckets = bucketed(reversals)
    negative = reversals["source_play_id"].str.startswith("-") | reversals[
        "previous_id"
    ].str.startswith("-")
    largest = reversals.sort_values(
        ["delta", "game_id", "row"], ascending=[False, True, True]
    ).head(10)
    return {
        "rows": int(len(frame)),
        "missing_period_rows": int(missing_period.sum()),
        "missing_sequence_rows": int(
            frame[["drive_number", "play_number"]].isna().any(axis=1).sum()
        ),
        "unresolved": [
            {
                "game_id": int(row.game_id),
                "period": None if pd.isna(row.period) else int(row.period),
                "drive_number": None
                if pd.isna(row.drive_number)
                else int(row.drive_number),
                "play_number": None
                if pd.isna(row.play_number)
                else int(row.play_number),
                "source_play_id": str(row.source_play_id),
                "reason": row.reason,
            }
            for row in unresolved.sort_values(
                ["game_id", "period", "drive_number", "play_number", "row"]
            ).itertuples()
        ],
        "clock": {
            "pairs_compared": int(compared.sum()),
            "same_second_pairs": int((resolved["delta"] == 0).sum()),
            "reversals": int(len(reversals)),
            "reversals_by_size": buckets,
            "impossible_clock_rows": int(
                (
                    _seconds_remaining(frame).loc[
                        frame["period"].isin(REGULATION_PERIODS)
                    ]
                    > PERIOD_SECONDS
                ).sum()
            ),
            "reversals_with_impossible_clock": int(reversals["impossible"].sum()),
            "valid_clock_reversals": int(len(valid)),
            "valid_clock_reversals_by_size": bucketed(valid),
            # a play at 15:00 after earlier plays in the same labelled period: the period
            # label looks wrong (the next period's plays carry this period's number)
            "valid_reversals_to_full_period_clock": int(
                (valid["remaining"] == PERIOD_SECONDS).sum()
            ),
            "valid_reversals_over_60s_not_to_full_period_clock": int(
                ((valid["delta"] > 60) & (valid["remaining"] != PERIOD_SECONDS)).sum()
            ),
            "reversals_involving_negative_id": int(negative.sum()),
            "reversals_over_60s_involving_negative_id": int(
                (negative & (reversals["delta"] > 60)).sum()
            ),
            "games_with_reversal": int(reversals["game_id"].nunique()),
            "largest_reversals": [
                {
                    "game_id": int(row.game_id),
                    "period": int(row.period),
                    "previous_play_id": str(row.previous_id),
                    "source_play_id": str(row.source_play_id),
                    "seconds_back": int(row.delta),
                }
                for row in largest.itertuples()
            ],
        },
    }


def drive_identity_reuse(plays: pd.DataFrame, collision_games: set[int]) -> dict:
    """Drive numbers shared by several provider drive IDs within one game."""
    if "drive_id" not in plays:
        return {"available": False}
    frame = plays[["game_id", "drive_number", "drive_id", "period"]].dropna(
        subset=["drive_number", "drive_id"]
    )
    per_drive = frame.groupby(["game_id", "drive_number"], sort=True).agg(
        drive_ids=("drive_id", "nunique"), periods=("period", "nunique")
    )
    reused = per_drive[per_drive["drive_ids"] > 1]
    games = sorted({int(game) for game, _ in reused.index})
    return {
        "available": True,
        "reused_drive_numbers": int(len(reused)),
        "games": len(games),
        "games_without_known_collision": [g for g in games if g not in collision_games],
    }


def classify_collision(rows: pd.DataFrame, key: dict[str, Any]) -> dict[str, Any]:
    """Class, identities and clock diagnostics for one sequence collision."""
    periods = sorted({int(p) for p in rows["period"].dropna()})
    ids = [str(v) for v in source_play_ids(rows["play_id"])]
    remaining = _seconds_remaining(rows)
    clock_known = bool(remaining.notna().all()) and remaining.nunique() == len(rows)
    clock_order = None
    if clock_known:
        clock_order = [ids[i] for i in np.argsort(-remaining.to_numpy(), kind="stable")]
    same_period = len(periods) == 1
    return {
        "season": int(key["season"]),
        "game_id": int(key["game_id"]),
        "drive_number": int(key["drive_number"]),
        "play_number": int(key["play_number"]),
        "class": "same_period" if same_period else "cross_period",
        "periods": periods,
        "source_play_ids": ids,
        "drive_ids": sorted({str(v) for v in rows.get("drive_id", [])}),
        "offenses": sorted({str(v) for v in rows["offense"]}),
        "unresolved_under_rule": bool(same_period or not periods),
        "distinct_provider_drives": rows["drive_id"].nunique() > 1
        if "drive_id" in rows
        else None,
        "clock_distinguishes": clock_known,
        "clock_order_matches_row_order": None
        if clock_order is None
        else clock_order == ids,
    }


def shadow_retained(plays: pd.DataFrame) -> pd.DataFrame:
    """Keep every distinct play; give drives and plays unique shadow sequence numbers.

    Drive numbers shared by several provider drive IDs keep their number for the earliest
    (period, first row) drive; later drives take new numbers above the game's maximum.
    A drive whose displayed play numbers still repeat is renumbered 1..n by
    ``(period, play_number, row order)``. Order inside a tie is the file row order and is
    not evidence of true order; such plays are reported as unresolved separately.
    """
    frame = plays.copy()
    frame["__row"] = np.arange(len(frame))
    frame["__drive_key"] = (
        frame["drive_id"].astype("string")
        if "drive_id" in frame
        else frame["drive_number"].astype("string")
    )
    frame["__period"] = frame["period"].fillna(-1)
    for game_id, game in frame.groupby("game_id", sort=True):
        highest = int(game["drive_number"].max())
        for number, drive in game.groupby("drive_number", sort=True):
            keys = (
                drive.groupby("__drive_key", sort=False)
                .agg(first_period=("__period", "min"), first_row=("__row", "min"))
                .sort_values(["first_period", "first_row"], kind="mergesort")
            )
            for rank, key in enumerate(keys.index):
                if rank == 0:
                    continue
                highest += 1
                mask = (frame["game_id"] == game_id) & (frame["drive_number"] == number)
                mask &= frame["__drive_key"] == key
                frame.loc[mask, "drive_number"] = highest
    repeated = frame.loc[frame.duplicated(SEQ, keep=False), ["game_id", "drive_number"]]
    for game_id, number in sorted(set(repeated.itertuples(index=False, name=None))):
        drive = frame[(frame["game_id"] == game_id) & (frame["drive_number"] == number)]
        order = drive.sort_values(
            ["__period", "play_number", "__row"], kind="mergesort"
        )
        frame.loc[order.index, "play_number"] = np.arange(1, len(order) + 1)
    if frame.duplicated(SEQ).any():
        raise ValueError("shadow sequence is not unique")
    return frame.drop(columns=["__row", "__drive_key", "__period"])


def _py(value: Any) -> Any:
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if math.isnan(value) else float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def _same(left: Any, right: Any) -> bool:
    left, right = _py(left), _py(right)
    if left is None or right is None:
        return left is None and right is None
    if isinstance(left, float) or isinstance(right, float):
        try:
            return math.isclose(float(left), float(right), rel_tol=1e-9, abs_tol=1e-12)
        except (TypeError, ValueError):
            return False
    return left == right


def diff_frames(
    left: pd.DataFrame,
    right: pd.DataFrame,
    key: list[str],
    ignore: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Cell-level difference of two frames joined on a unique key."""
    for name, frame in (("left", left), ("right", right)):
        if frame.duplicated(key).any():
            raise ValueError(f"{name} frame has duplicate keys for {key}")
    a, b = left.set_index(key), right.set_index(key)
    columns = [c for c in a.columns if c in b.columns and c not in ignore]
    common = a.index.intersection(b.index)
    changed = []
    for index in sorted(common, key=str):
        for column in columns:
            if not _same(a.at[index, column], b.at[index, column]):
                changed.append(
                    {
                        "key": [
                            _py(v) for v in np.atleast_1d(np.array(index, dtype=object))
                        ],
                        "column": column,
                        "historical": _py(a.at[index, column]),
                        "retained": _py(b.at[index, column]),
                    }
                )

    def describe(frame: pd.DataFrame, index) -> list[Any]:
        return [_py(v) for v in np.atleast_1d(np.array(index, dtype=object))]

    return {
        "key": key,
        "rows_historical": int(len(a)),
        "rows_retained": int(len(b)),
        "only_historical": [
            describe(a, i) for i in sorted(a.index.difference(b.index), key=str)
        ],
        "only_retained": [
            describe(b, i) for i in sorted(b.index.difference(a.index), key=str)
        ],
        "changed_cells": changed,
        "changed_cell_count": len(changed),
        "columns_compared": len(columns),
    }


ID_COLUMN_MARKERS = ("source", "possession_id", "event_id")


def remap_source_tokens(frame: pd.DataFrame, lookup: dict[str, str]) -> pd.DataFrame:
    """Replace ``season:game:drive:play`` tokens by provider play IDs in ID columns."""
    out = frame.copy()
    for column in out.columns:
        if (
            not any(m in column for m in ID_COLUMN_MARKERS)
            or out[column].dtype != object
        ):
            continue
        out[column] = out[column].map(
            lambda text: SOURCE_TOKEN.sub(lambda m: lookup[m.group(0)], text)
            if isinstance(text, str)
            else text
        )
    return out


def members_digest(parts: list[str]) -> str:
    """Stable short identity for a set of provider play IDs plus context values."""
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:16]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:  # pragma: no cover - requires pinned R2 parents
    from dotenv import load_dotenv

    from cks_picks_cfb.data.lake import DatasetRef, read_dataset
    from cks_picks_cfb.data.storage import get_storage
    from scripts.analysis.play_identity_shadow import run_shadow

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historical-parents", type=Path, required=True)
    parser.add_argument("--season-2026-parents", type=Path, required=True)
    parser.add_argument("--census", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load_dotenv(".env")
    if os.getenv("CFB_STORAGE_BACKEND") != "r2":
        raise SystemExit("The impact diff requires explicit R2 storage")

    historical = json.loads(args.historical_parents.read_text())["seasons"]
    blocks = {int(year): block for year, block in historical.items()}
    blocks[2026] = json.loads(args.season_2026_parents.read_text())
    census = json.loads(args.census.read_text())
    storage = get_storage(environment="preview")

    def ref(entry: dict) -> DatasetRef:
        return DatasetRef(
            **{
                name: entry[name]
                for name in (
                    "dataset",
                    "version_id",
                    "schema_version",
                    "content_sha",
                    "uri",
                )
            }
        )

    def parent(season: int, name: str) -> dict:
        matches = [p for p in blocks[season]["parents"] if p["dataset"] == name]
        if len(matches) != 1:
            raise ValueError(f"{season}: one pinned {name} parent is required")
        return matches[0]

    collisions = {
        int(item["season"]): item["sequence_collisions"] for item in census["seasons"]
    }
    collision_games = {
        s: {int(c["game_id"]) for c in rows} for s, rows in collisions.items()
    }
    all_games = {g for games in collision_games.values() for g in games}
    classified: list[dict] = []
    seasons: dict[str, Any] = {}
    plays_cache: dict[int, pd.DataFrame] = {}
    for season in sorted(blocks):
        plays = read_dataset(storage, ref(parent(season, "plays")))
        report = order_diagnostics(plays)
        report["drive_identity"] = drive_identity_reuse(
            plays, collision_games.get(season, set())
        )
        report["plays_version_id"] = parent(season, "plays")["version_id"]
        report["plays_content_sha"] = parent(season, "plays")["content_sha"]
        for collision in collisions.get(season, []):
            rows = plays[
                (plays.game_id == collision["game_id"])
                & (plays.drive_number == collision["drive_number"])
                & (plays.play_number == collision["play_number"])
            ]
            classified.append(classify_collision(rows, {"season": season, **collision}))
        seasons[str(season)] = report
        if season in collision_games and collision_games[season]:
            plays_cache[season] = plays
    classified.sort(
        key=lambda c: (c["season"], c["game_id"], c["drive_number"], c["play_number"])
    )

    shadow = run_shadow(
        storage=storage,
        blocks=blocks,
        plays_cache=plays_cache,
        collision_games=collision_games,
        ref=ref,
    )
    unresolved_total = sum(len(s["unresolved"]) for s in seasons.values())
    report = {
        "schema_version": SCHEMA,
        "contract": "docs/plans/2026-10-09/01-byplay-v2-play-identity.md#task-1",
        "ordering_rule": ORDERING_RULE,
        "inputs": {
            "historical_parents_sha256": sha256_file(args.historical_parents),
            "season_2026_parents_sha256": sha256_file(args.season_2026_parents),
            "census_sha256": sha256_file(args.census),
        },
        "collisions": classified,
        "collision_summary": {
            "total": len(classified),
            "cross_period": sum(c["class"] == "cross_period" for c in classified),
            "same_period": sum(c["class"] == "same_period" for c in classified),
            "unresolved_under_rule": sum(
                c["unresolved_under_rule"] for c in classified
            ),
            "games": sorted(all_games),
        },
        "unresolved_plays_all_seasons": unresolved_total,
        "seasons": seasons,
        "shadow": shadow,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "collisions": report["collision_summary"],
                "unresolved_plays_all_seasons": unresolved_total,
                "output": str(args.output),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
