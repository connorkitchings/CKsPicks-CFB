#!/usr/bin/env python3
"""Summarize feature coverage for cached team_week_adj partitions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from src.config import get_data_root
from src.utils.local_storage import LocalStorage


def _load_week_df(
    year: int, week: int, iteration: int | None, data_root: str | None
) -> pd.DataFrame:
    storage = LocalStorage(
        data_root=data_root, file_format="csv", data_type="processed"
    )
    filters: dict[str, int] = {"year": year, "week": week}
    if iteration is not None:
        filters = {"iteration": iteration, "year": year, "week": week}
    records = storage.read_index("team_week_adj", filters)
    if not records:
        return pd.DataFrame()
    return pd.DataFrame.from_records(records)


def _summarize(df: pd.DataFrame) -> dict:
    if df.empty:
        return {}
    coverage = (df.notna().sum() / len(df)).sort_values(ascending=False)
    zero_share = ((df == 0).sum() / len(df)).sort_values(ascending=False)
    prefix_summary: dict[str, dict[str, float]] = {}
    for column in df.columns:
        prefix = column.split("_")[0]
        prefix_summary.setdefault(prefix, {"columns": 0, "coverage_sum": 0.0})
        prefix_summary[prefix]["columns"] += 1
        prefix_summary[prefix]["coverage_sum"] += float(coverage.get(column, 0.0))
    for prefix, stats in prefix_summary.items():
        stats["avg_coverage"] = stats["coverage_sum"] / max(stats["columns"], 1)
        stats.pop("coverage_sum")
    return {
        "row_count": len(df),
        "column_count": df.shape[1],
        "coverage": coverage.to_dict(),
        "zero_share": zero_share.to_dict(),
        "prefix_summary": prefix_summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Profile cached team_week_adj features."
    )
    parser.add_argument(
        "--year", type=int, required=True, help="Season year to inspect."
    )
    parser.add_argument(
        "--week", type=int, required=True, help="Week number to inspect."
    )
    parser.add_argument(
        "--iteration",
        type=int,
        default=4,
        help="Opponent-adjustment iteration depth (default: 4). Use -1 for legacy layout.",
    )
    parser.add_argument(
        "--data-root",
        type=str,
        default=str(get_data_root()),
        help="Absolute data root path (defaults to env or ./data).",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Number of highest-coverage columns to print (default: 20).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write the full summary as JSON.",
    )
    args = parser.parse_args()

    iteration = None if args.iteration < 0 else args.iteration
    df = _load_week_df(args.year, args.week, iteration, args.data_root)
    if df.empty:
        print(
            "No records found; confirm the cache exists for the requested parameters."
        )
        return

    summary = _summarize(df)
    coverage = summary["coverage"]
    print(f"Rows: {summary['row_count']} | Columns: {summary['column_count']}")
    print("Top coverage columns:")
    for column, value in list(coverage.items())[: args.top]:
        print(f"  {column}: {value:.2%}")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(
                {
                    "year": args.year,
                    "week": args.week,
                    "iteration": iteration,
                    **summary,
                },
                indent=2,
            )
        )
        print(f"Wrote detailed summary to {args.output}")


if __name__ == "__main__":
    main()
