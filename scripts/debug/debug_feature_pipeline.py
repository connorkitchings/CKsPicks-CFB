#!/usr/bin/env python3
"""Inspect cached team_week_adj features for NaN/inf values and extreme magnitudes."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import get_data_root
from src.utils.local_storage import LocalStorage


def _parse_weeks(raw: str | None) -> list[int] | None:
    if not raw:
        return None
    weeks: list[int] = []
    for chunk in (piece.strip() for piece in raw.split(",") if piece.strip()):
        try:
            weeks.append(int(chunk))
        except ValueError:
            continue
    return weeks or None


def _infer_weeks(root: Path, iteration: int | None, year: int) -> list[int]:
    base = root / "team_week_adj"
    if iteration is not None:
        base = base / f"iteration={iteration}"
    base = base / f"year={year}"
    if not base.exists():
        return []
    weeks: list[int] = []
    for p in sorted(base.glob("week=*")):
        try:
            weeks.append(int(p.name.split("=")[1]))
        except ValueError:
            continue
    return weeks


def _load_weekly_df(
    year: int, iteration: int | None, weeks: list[int] | None, data_root: str
) -> pd.DataFrame:
    storage = LocalStorage(
        data_root=data_root, data_type="processed", file_format="csv"
    )
    target_weeks = weeks or _infer_weeks(storage.root(), iteration, year)
    frames: list[pd.DataFrame] = []
    for week in target_weeks:
        filters = {"year": year, "week": week}
        if iteration is not None:
            filters = {"iteration": iteration, **filters}
        records = storage.read_index("team_week_adj", filters)
        if records:
            frames.append(pd.DataFrame.from_records(records))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True, sort=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Debug cached weekly features for non-finite values."
    )
    parser.add_argument(
        "--year", type=int, required=True, help="Season year to inspect."
    )
    parser.add_argument(
        "--iteration",
        type=int,
        default=4,
        help="Opponent-adjustment iteration depth (use -1 for legacy layout).",
    )
    parser.add_argument(
        "--weeks",
        type=str,
        help="Comma-separated list of weeks to check (defaults to all weeks found).",
    )
    parser.add_argument(
        "--data-root",
        type=str,
        default=str(get_data_root()),
        help="Absolute data root (defaults to env or ./data).",
    )
    parser.add_argument(
        "--top-abs",
        type=int,
        default=10,
        help="Number of columns to show when listing largest absolute values.",
    )
    args = parser.parse_args()

    iteration = None if args.iteration < 0 else args.iteration
    weeks = _parse_weeks(args.weeks)
    week_label = ",".join(map(str, weeks)) if weeks else "all"

    df = _load_weekly_df(args.year, iteration, weeks, args.data_root)
    if df.empty:
        print("No rows found for the requested parameters.")
        return

    numeric = df.select_dtypes(include=["number"])
    nonfinite = (~np.isfinite(numeric)).sum()
    nonfinite = nonfinite[nonfinite > 0].sort_values(ascending=False)
    abs_max = numeric.abs().max().sort_values(ascending=False)

    print(
        f"Loaded {len(df)} rows / {numeric.shape[1]} numeric cols | "
        f"year={args.year}, weeks={week_label}, iteration={iteration if iteration is not None else 'legacy'}"
    )
    if nonfinite.empty:
        print("No NaN/inf detected in numeric columns.")
    else:
        print("Non-finite counts by column (descending):")
        for col, count in nonfinite.items():
            print(f"  {col}: {count}")

    print(f"Top {args.top_abs} absolute values by column:")
    for col, val in abs_max.head(args.top_abs).items():
        print(f"  {col}: {val}")


if __name__ == "__main__":
    main()
