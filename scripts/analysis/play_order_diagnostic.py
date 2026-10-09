#!/usr/bin/env python3
"""Period-label diagnostic for contract 2026-10-09/01 (read-only, no writes to any store).

Questions answered from the pinned normalized Silver play parents:

* Which plays land on a fresh 15:00 clock under an older period label ("period resets"), and
  do they sit at drive boundaries or in games that also carry the next period label?
* Is ``(period, drive_number, play_number)`` or ``(drive_number, play_number)`` the more
  coherent order? Coherence is measured against the period label and the game clock: a pair
  is a violation when the period goes backwards or the clock goes up inside one period.
* How many games have a drive number that goes backwards in the period-first order?

Nothing here excludes a play. The game clock is diagnostic only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCHEMA = "period_label_diagnostic_v1"
REGULATION_PERIODS = (1, 2, 3, 4)
PERIOD_SECONDS = 15 * 60
COLUMNS = [
    "game_id",
    "period",
    "drive_number",
    "play_number",
    "play_id",
    "clock_minutes",
    "clock_seconds",
    "play_type",
]
KEY = ["game_id", "period", "drive_number", "play_number"]


def prepare(plays: pd.DataFrame) -> pd.DataFrame:
    """Plays with a row number, seconds remaining, and a flag for same-sequence ties."""
    frame = plays[COLUMNS].copy()
    frame["row"] = np.arange(len(frame))
    frame["rem"] = pd.to_numeric(frame["clock_minutes"], errors="coerce") * 60 + (
        pd.to_numeric(frame["clock_seconds"], errors="coerce")
    )
    frame["tied"] = frame.groupby(KEY)["play_id"].transform("nunique") > 1
    return frame


def regulation(frame: pd.DataFrame) -> pd.DataFrame:
    """Untied regulation plays with a usable clock."""
    keep = (
        frame["period"].isin(REGULATION_PERIODS) & ~frame["tied"] & frame["rem"].notna()
    )
    return frame.loc[keep]


def period_reset_events(frame: pd.DataFrame) -> pd.DataFrame:
    """Plays on a fresh 15:00 clock that follow a play with less time left in the same period."""
    ordered = regulation(frame).sort_values([*KEY, "row"], kind="mergesort")
    grouped = ordered.groupby(["game_id", "period"], sort=False)
    ordered = ordered.assign(
        delta=grouped["rem"].diff(),
        prev_type=grouped["play_type"].shift(),
        prev_drive=grouped["drive_number"].shift(),
        prev_rem=grouped["rem"].shift(),
    )
    events = ordered[
        (ordered["delta"] > 0)
        & (ordered["rem"] == PERIOD_SECONDS)
        & (ordered["prev_rem"] <= PERIOD_SECONDS)
    ].copy()
    periods = frame.groupby("game_id")["period"].agg(
        lambda s: frozenset(int(x) for x in s.dropna())
    )
    events["new_drive"] = events["drive_number"] != events["prev_drive"]
    events["next_period_present"] = [
        (int(p) + 1) in periods[g] for g, p in zip(events["game_id"], events["period"])
    ]
    events["game_lacks_a_regulation_period"] = [
        not set(REGULATION_PERIODS) <= periods[g] for g in events["game_id"]
    ]
    return events


def violations_by_game(ordered: pd.DataFrame) -> pd.Series:
    """Pairs that cannot be in true order: the period goes back, or the clock goes up."""
    grouped = ordered.groupby("game_id", sort=False)
    previous_period = grouped["period"].shift()
    previous_rem = grouped["rem"].shift()
    bad_period = ordered["period"] < previous_period
    bad_clock = (
        (ordered["period"] == previous_period)
        & (ordered["rem"] > previous_rem)
        & (ordered["rem"] <= PERIOD_SECONDS)
        & (previous_rem <= PERIOD_SECONDS)
    )
    return (
        bad_period.groupby(ordered["game_id"])
        .sum()
        .add(bad_clock.groupby(ordered["game_id"]).sum(), fill_value=0)
    )


def ordering_comparison(frame: pd.DataFrame) -> dict[str, Any]:
    """Period-first against drive-first order, measured by violations per game."""
    plays = regulation(frame)
    period_first = plays.sort_values([*KEY, "row"], kind="mergesort")
    drive_first = plays.sort_values(
        ["game_id", "drive_number", "play_number", "row"], kind="mergesort"
    )
    a, b = violations_by_game(period_first), violations_by_game(drive_first)
    decreasing = period_first.groupby("game_id")["drive_number"].apply(
        lambda s: bool((s.diff() < 0).any())
    )
    inversion = decreasing[decreasing].index
    in_a, in_b = a.reindex(inversion), b.reindex(inversion)
    return {
        "games": int(plays["game_id"].nunique()),
        "violations_period_first": int(a.sum()),
        "violations_drive_first": int(b.sum()),
        "inversion_games": int(len(inversion)),
        "inversion_games_period_first_better": int((in_a < in_b).sum()),
        "inversion_games_drive_first_better": int((in_b < in_a).sum()),
        "inversion_games_equal": int((in_a == in_b).sum()),
        "inversion_game_ids": sorted(int(g) for g in inversion),
    }


def summarize_season(plays: pd.DataFrame) -> dict[str, Any]:
    frame = prepare(plays)
    events = period_reset_events(frame)
    comparison = ordering_comparison(frame)
    reset_games = {int(g) for g in events["game_id"].unique()}
    inversion = set(comparison.pop("inversion_game_ids"))
    return {
        "reset_events": int(len(events)),
        "reset_games": len(reset_games),
        "reset_at_new_drive": int(events["new_drive"].sum()),
        "reset_with_next_period_present": int(events["next_period_present"].sum()),
        "reset_in_game_missing_a_regulation_period": int(
            events["game_lacks_a_regulation_period"].sum()
        ),
        "previous_play_types": dict(
            sorted(Counter(events["prev_type"].fillna("NA")).items())
        ),
        "reset_play_types": dict(
            sorted(Counter(events["play_type"].fillna("NA")).items())
        ),
        "inversion_games_with_reset": len(inversion & reset_games),
        **comparison,
    }


def add_totals(seasons: dict[str, dict[str, Any]]) -> dict[str, int]:
    totals: Counter[str] = Counter()
    for report in seasons.values():
        for key, value in report.items():
            if isinstance(value, int) and not isinstance(value, bool):
                totals[key] += value
    return dict(sorted(totals.items()))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:  # pragma: no cover - requires pinned R2 parents
    from dotenv import load_dotenv

    from cks_picks_cfb.data.lake import DatasetRef, read_dataset
    from cks_picks_cfb.data.storage import get_storage

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historical-parents", type=Path, required=True)
    parser.add_argument("--season-2026-parents", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load_dotenv(".env")
    if os.getenv("CFB_STORAGE_BACKEND") != "r2":
        raise SystemExit("The diagnostic requires explicit R2 storage")
    blocks = {
        int(year): block
        for year, block in json.loads(args.historical_parents.read_text())[
            "seasons"
        ].items()
    }
    blocks[2026] = json.loads(args.season_2026_parents.read_text())
    storage = get_storage(environment="preview")
    seasons: dict[str, dict[str, Any]] = {}
    for season in sorted(blocks):
        entry = next(p for p in blocks[season]["parents"] if p["dataset"] == "plays")
        ref = DatasetRef(
            **{
                k: entry[k]
                for k in (
                    "dataset",
                    "version_id",
                    "schema_version",
                    "content_sha",
                    "uri",
                )
            }
        )
        report = summarize_season(read_dataset(storage, ref))
        report["plays_version_id"] = entry["version_id"]
        report["plays_content_sha"] = entry["content_sha"]
        seasons[str(season)] = report
    report = {
        "schema_version": SCHEMA,
        "contract": "docs/plans/2026-10-09/01-byplay-v2-play-identity.md#amendment-3",
        "method": (
            "period resets = untied regulation plays at 15:00 following a play with less "
            "time left in the same period; violations = period decreases or clock increases "
            "between consecutive plays; the clock excludes nothing"
        ),
        "inputs": {
            "historical_parents_sha256": sha256_file(args.historical_parents),
            "season_2026_parents_sha256": sha256_file(args.season_2026_parents),
        },
        "seasons": seasons,
        "totals": add_totals(
            {
                s: {k: v for k, v in r.items() if not k.startswith("plays_")}
                for s, r in seasons.items()
            }
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report["totals"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
