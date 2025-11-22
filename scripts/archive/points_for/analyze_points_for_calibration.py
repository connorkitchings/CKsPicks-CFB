#!/usr/bin/env python3
"""Analyze points-for model calibration and threshold sensitivity.

This script summarizes residual statistics from points-for training,
loads scored weekly outputs, and evaluates how different edge/standard
deviation thresholds would have affected bet volume and performance.

Example:
    python scripts/analyze_points_for_calibration.py \
        --season 2024 \
        --model-dir artifacts/models \
        --reports-dir artifacts/reports/points_for \
        --metric-path artifacts/reports/metrics/points_for_vs_legacy_weeks5_13.csv
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import pandas as pd

DEFAULT_EDGE_THRESHOLDS = [6.0, 7.0, 8.0, 9.0, 10.0]
DEFAULT_STD_THRESHOLDS = [12.0, 14.0, 16.0, 18.0, 20.0]


def load_points_for_stats(model_dir: Path, model_year: int) -> dict | None:
    stats_path = model_dir / str(model_year) / "points_for_stats.json"
    if not stats_path.is_file():
        print(f"[warn] No stats file found at {stats_path}")
        return None
    try:
        return json.loads(stats_path.read_text())
    except json.JSONDecodeError as exc:
        print(f"[warn] Failed to parse {stats_path}: {exc}")
        return None


def load_scored_reports(
    reports_dir: Path, season: int, weeks: Iterable[int]
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for week in weeks:
        path = reports_dir / str(season) / "scored" / f"CFB_week{week}_bets_scored.csv"
        if not path.is_file():
            print(f"[warn] Skipping missing scored report {path}")
            continue
        df = pd.read_csv(path)
        df["Week"] = week
        frames.append(df)
    if not frames:
        raise FileNotFoundError("No scored reports found for requested weeks.")
    return pd.concat(frames, ignore_index=True)


def evaluate_thresholds(
    df: pd.DataFrame,
    *,
    target: str,
    edge_thresholds: Iterable[float],
    std_thresholds: Iterable[float],
) -> pd.DataFrame:
    result_col = f"{target} Bet Result"
    edge_col = "edge_spread" if target.lower() == "spread" else "edge_total"
    std_col = (
        "predicted_spread_std_dev"
        if target.lower() == "spread"
        else "predicted_total_std_dev"
    )
    bet_units_col = (
        "bet_units_spread" if target.lower() == "spread" else "bet_units_total"
    )

    working = df.copy()
    working = working[working[result_col].isin(["Win", "Loss", "Push"])].copy()
    working = working.dropna(subset=[edge_col, std_col, bet_units_col])

    records: list[dict] = []
    for edge_th in edge_thresholds:
        for std_th in std_thresholds:
            subset = working[
                (working[edge_col].abs() >= edge_th) & (working[std_col] <= std_th)
            ]
            if subset.empty:
                records.append(
                    {
                        "edge_threshold": edge_th,
                        "std_threshold": std_th,
                        "bets": 0,
                        "wins": 0,
                        "losses": 0,
                        "pushes": 0,
                        "win_pct": 0.0,
                        "units": 0.0,
                    }
                )
                continue

            wins = (subset[result_col] == "Win").sum()
            losses = (subset[result_col] == "Loss").sum()
            pushes = (subset[result_col] == "Push").sum()
            units = 0.0
            for _, row in subset.iterrows():
                stake = float(row.get(bet_units_col, 0) or 0.0)
                outcome = row[result_col]
                if outcome == "Win":
                    units += stake
                elif outcome == "Loss":
                    units -= stake
            win_pct = wins / (wins + losses) if (wins + losses) else 0.0
            records.append(
                {
                    "edge_threshold": edge_th,
                    "std_threshold": std_th,
                    "bets": len(subset),
                    "wins": wins,
                    "losses": losses,
                    "pushes": pushes,
                    "win_pct": round(win_pct, 3),
                    "units": round(units, 3),
                }
            )
    return pd.DataFrame(records)


def summarize_distribution(df: pd.DataFrame, column: str) -> pd.Series:
    series = df[column].dropna()
    return pd.Series(
        {
            "count": len(series),
            "mean": round(series.mean(), 3),
            "std": round(series.std(ddof=1), 3),
            "min": round(series.min(), 3),
            "50%": round(series.quantile(0.5), 3),
            "75%": round(series.quantile(0.75), 3),
            "90%": round(series.quantile(0.9), 3),
            "95%": round(series.quantile(0.95), 3),
            "max": round(series.max(), 3),
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze calibrated points-for residuals and threshold sensitivity."
    )
    parser.add_argument(
        "--season", type=int, default=2024, help="Season year to analyze."
    )
    parser.add_argument(
        "--model-dir",
        type=str,
        default="artifacts/models",
        help="Directory containing points-for model artifacts.",
    )
    parser.add_argument(
        "--reports-dir",
        type=str,
        default="artifacts/reports/points_for",
        help="Root directory containing points-for weekly reports.",
    )
    parser.add_argument(
        "--weeks",
        type=str,
        default="5-13",
        help="Week range or comma-separated list (e.g., '5-13' or '5,6,7').",
    )
    parser.add_argument(
        "--edge-thresholds",
        type=str,
        default="6,7,8,9,10",
        help="Comma-separated edge thresholds to evaluate.",
    )
    parser.add_argument(
        "--std-thresholds",
        type=str,
        default="12,14,16,18,20",
        help="Comma-separated std-dev thresholds to evaluate.",
    )
    parser.add_argument(
        "--metric-path",
        type=str,
        default="artifacts/reports/metrics/points_for_vs_legacy_weeks5_13.csv",
        help="Existing comparison CSV to reference (optional).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="artifacts/reports/metrics",
        help="Directory to write analysis summaries.",
    )
    args = parser.parse_args()

    model_dir = Path(args.model_dir)
    reports_dir = Path(args.reports_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Parse weeks
    if "-" in args.weeks:
        start, end = args.weeks.split("-", maxsplit=1)
        weeks = list(range(int(start), int(end) + 1))
    else:
        weeks = [int(w.strip()) for w in args.weeks.split(",") if w.strip()]

    edge_thresholds = [float(x) for x in args.edge_thresholds.split(",")]
    std_thresholds = [float(x) for x in args.std_thresholds.split(",")]

    stats = load_points_for_stats(model_dir, args.season)
    if stats:
        print("=== Points-for residual statistics ===")
        print(json.dumps(stats, indent=2))

    print("\n=== Loading scored reports ===")
    scored_df = load_scored_reports(reports_dir, args.season, weeks)
    print(f"Loaded {len(scored_df)} scored rows across weeks {weeks}")

    # Distribution summaries
    dist_spread = summarize_distribution(scored_df, "predicted_spread_std_dev")
    dist_total = summarize_distribution(scored_df, "predicted_total_std_dev")
    edges_spread = summarize_distribution(scored_df, "edge_spread")
    edges_total = summarize_distribution(scored_df, "edge_total")

    summary_table = pd.DataFrame(
        {
            "spread_std_dev": dist_spread,
            "total_std_dev": dist_total,
            "edge_spread": edges_spread,
            "edge_total": edges_total,
        }
    )
    print("\n=== Distribution summary ===")
    print(summary_table)

    # Threshold evaluation
    spread_eval = evaluate_thresholds(
        scored_df,
        target="Spread",
        edge_thresholds=edge_thresholds,
        std_thresholds=std_thresholds,
    )
    total_eval = evaluate_thresholds(
        scored_df,
        target="Total",
        edge_thresholds=edge_thresholds,
        std_thresholds=std_thresholds,
    )

    spread_path = output_dir / f"points_for_spread_thresholds_{args.season}.csv"
    total_path = output_dir / f"points_for_total_thresholds_{args.season}.csv"
    summary_csv = output_dir / f"points_for_distribution_summary_{args.season}.csv"

    spread_eval.to_csv(spread_path, index=False)
    total_eval.to_csv(total_path, index=False)
    summary_table.to_csv(summary_csv)

    print(f"\nWrote spread threshold grid to {spread_path}")
    print(spread_eval.to_markdown(index=False))
    print(f"\nWrote total threshold grid to {total_path}")
    print(total_eval.to_markdown(index=False))

    if args.metric_path:
        metric_path = Path(args.metric_path)
        if metric_path.is_file():
            print(f"\nExisting comparison metrics: {metric_path}")
            metric_df = pd.read_csv(metric_path)
            print(metric_df.to_markdown(index=False))


if __name__ == "__main__":
    main()
