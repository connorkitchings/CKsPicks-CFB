#!/usr/bin/env python3
"""Create intersection wagers where legacy ensemble and points-for agree.

For each requested week, this script loads the legacy predictions and the
points-for predictions, retains bets only when both models choose the same
side, and writes the filtered report to a target directory. The resulting CSV
matches the standard weekly report schema so it can be scored with
``scripts/score_weekly_picks.py``.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def parse_weeks(raw: str) -> list[int]:
    """Parse week string such as '5-13' or '5,6,7'."""
    raw = raw.strip()
    if "-" in raw:
        start, end = raw.split("-", maxsplit=1)
        return list(range(int(start), int(end) + 1))
    return [int(part.strip()) for part in raw.split(",") if part.strip()]


def _safe_min(series_a: pd.Series, series_b: pd.Series) -> pd.Series:
    combined = pd.concat([series_a.abs(), series_b.abs()], axis=1)
    return combined.min(axis=1)


def combine_week(
    season: int,
    week: int,
    *,
    legacy_dir: Path,
    points_dir: Path,
    output_dir: Path,
) -> tuple[int, int]:
    legacy_path = legacy_dir / str(season) / "predictions" / f"CFB_week{week}_bets.csv"
    points_path = points_dir / str(season) / "predictions" / f"CFB_week{week}_bets.csv"
    if not legacy_path.is_file() or not points_path.is_file():
        print(
            f"[warn] Missing predictions for week {week}: {legacy_path}, {points_path}"
        )
        return 0, 0

    legacy = pd.read_csv(legacy_path)
    points = pd.read_csv(points_path)

    if "game_id" not in legacy.columns or "game_id" not in points.columns:
        raise ValueError("Both reports must contain a 'game_id' column.")

    legacy = legacy.set_index("game_id", drop=False)
    points = points.set_index("game_id", drop=False)

    merged = legacy.join(points, lsuffix="_legacy", rsuffix="_pf", how="inner")
    if merged.empty:
        print(f"[warn] No overlapping games for week {week}")
        return 0, 0

    final = legacy.loc[merged.index].copy()

    spread_agree = (
        (merged["Spread Bet_legacy"] != "none")
        & (merged["Spread Bet_pf"] != "none")
        & (merged["Spread Bet_legacy"] == merged["Spread Bet_pf"])
    )
    total_agree = (
        (merged["Total Bet_legacy"] != "none")
        & (merged["Total Bet_pf"] != "none")
        & (merged["Total Bet_legacy"] == merged["Total Bet_pf"])
    )

    # Spread fields
    final["Spread Bet"] = np.where(spread_agree, merged["Spread Bet_legacy"], "none")
    final["bet_units_spread"] = np.where(
        spread_agree,
        np.minimum(
            merged["bet_units_spread_legacy"],
            merged["bet_units_spread_pf"],
        ),
        0.0,
    )
    final["spread_bet_reason"] = np.where(
        spread_agree,
        "Consensus between models",
        "Filtered out (no consensus)",
    )
    final["Spread Prediction"] = (
        merged["Spread Prediction_legacy"] + merged["Spread Prediction_pf"]
    ) / 2
    final["predicted_spread_std_dev"] = np.where(
        spread_agree,
        np.minimum(
            merged["predicted_spread_std_dev_legacy"],
            merged["predicted_spread_std_dev_pf"],
        ),
        0.0,
    )
    final["edge_spread"] = np.where(
        spread_agree,
        _safe_min(merged["edge_spread_legacy"], merged["edge_spread_pf"]),
        0.0,
    )

    # Totals fields
    final["Total Bet"] = np.where(total_agree, merged["Total Bet_legacy"], "none")
    final["bet_units_total"] = np.where(
        total_agree,
        np.minimum(
            merged["bet_units_total_legacy"],
            merged["bet_units_total_pf"],
        ),
        0.0,
    )
    final["total_bet_reason"] = np.where(
        total_agree,
        "Consensus between models",
        "Filtered out (no consensus)",
    )
    final["Total Prediction"] = (
        merged["Total Prediction_legacy"] + merged["Total Prediction_pf"]
    ) / 2
    final["predicted_total_std_dev"] = np.where(
        total_agree,
        np.minimum(
            merged["predicted_total_std_dev_legacy"],
            merged["predicted_total_std_dev_pf"],
        ),
        0.0,
    )
    final["edge_total"] = np.where(
        total_agree,
        _safe_min(merged["edge_total_legacy"], merged["edge_total_pf"]),
        0.0,
    )

    final["Spread Prediction"] = final["Spread Prediction"].round(6)
    final["Total Prediction"] = final["Total Prediction"].round(6)

    predictions_dir = output_dir / str(season) / "predictions"
    predictions_dir.mkdir(parents=True, exist_ok=True)
    output_path = predictions_dir / f"CFB_week{week}_bets.csv"
    final.to_csv(output_path, index=False)
    print(
        f"[info] Week {week}: "
        f"{spread_agree.sum()} spread bets, {total_agree.sum()} total bets -> {output_path}"
    )
    return int(spread_agree.sum()), int(total_agree.sum())


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Combine legacy and points-for predictions, keeping only consensus bets."
    )
    parser.add_argument("--season", type=int, required=True, help="Season year.")
    parser.add_argument(
        "--weeks",
        type=str,
        required=True,
        help="Weeks to process (e.g., '5-13' or '5,6,7').",
    )
    parser.add_argument(
        "--legacy-reports",
        type=str,
        default="artifacts/reports",
        help="Base directory for legacy ensemble reports.",
    )
    parser.add_argument(
        "--points-for-reports",
        type=str,
        default="artifacts/reports/points_for",
        help="Base directory for points-for reports.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="artifacts/reports/hybrid",
        help="Directory to write consensus reports.",
    )
    args = parser.parse_args()

    weeks = parse_weeks(args.weeks)
    legacy_dir = Path(args.legacy_reports)
    points_dir = Path(args.points_for_reports)
    output_dir = Path(args.output_dir)

    total_spread = 0
    total_total = 0
    for week in weeks:
        spread_count, total_count = combine_week(
            args.season,
            week,
            legacy_dir=legacy_dir,
            points_dir=points_dir,
            output_dir=output_dir,
        )
        total_spread += spread_count
        total_total += total_count

    print(
        f"\n[summary] {args.season} weeks {weeks}: "
        f"{total_spread} spread bets, {total_total} total bets retained."
    )


if __name__ == "__main__":
    main()
