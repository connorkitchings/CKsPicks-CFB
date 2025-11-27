#!/usr/bin/env python3
"""Compare scored betting results across multiple model modes."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, Iterable

import pandas as pd


def _parse_mode_arg(raw: str) -> tuple[str, Path]:
    if "=" not in raw:
        raise argparse.ArgumentTypeError(
            "--mode expects NAME=PATH (e.g., legacy=artifacts/reports/2024/scored)"
        )
    name, path = raw.split("=", 1)
    return name.strip(), Path(path.strip())


def _discover_csvs(base: Path) -> list[Path]:
    if base.is_file() and base.suffix.lower() == ".csv":
        return [base]
    if base.is_dir():
        matches = sorted(base.rglob("*_bets_scored.csv"))
        if not matches:
            matches = sorted(base.rglob("*.csv"))
        if matches:
            return matches
    raise FileNotFoundError(f"No scored CSV files found under {base}")


def load_scored(paths: Iterable[Path]) -> pd.DataFrame:
    frames = [pd.read_csv(path) for path in paths]
    return pd.concat(frames, ignore_index=True)


def _result_to_win(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .map({"win": 1, "loss": 0})
        .fillna(0)
        .astype(int)
    )


def compute_metrics(
    df: pd.DataFrame, bet_col: str, result_col: str
) -> Dict[str, float]:
    placed = df[df[bet_col].str.lower().isin(["home", "away", "over", "under"])]
    if placed.empty:
        return {"win_rate": float("nan"), "wins": 0, "bets": 0}
    wins = _result_to_win(placed[result_col]).sum()
    bets = len(placed)
    units_col = "bet_units_spread" if bet_col == "Spread Bet" else "bet_units_total"
    units_won = (placed[result_col].str.lower() == "win").astype(int) * placed[
        units_col
    ]
    units_lost = (placed[result_col].str.lower() == "loss").astype(int) * placed[
        units_col
    ]
    net_units = units_won.sum() - units_lost.sum()
    return {
        "win_rate": wins / bets if bets else float("nan"),
        "wins": int(wins),
        "bets": int(bets),
        "net_units": float(net_units),
    }


def weekly_summary(df: pd.DataFrame, bet_col: str, result_col: str) -> pd.DataFrame:
    if "Week" not in df.columns:
        return pd.DataFrame()
    placed = df[df[bet_col].str.lower().isin(["home", "away", "over", "under"])]
    if placed.empty:
        return pd.DataFrame()
    placed = placed.assign(win=_result_to_win(placed[result_col]))
    weekly = (
        placed.groupby("Week")["win"]
        .agg(wins="sum", bets="count")
        .assign(hit_rate=lambda x: x["wins"] / x["bets"])
        .reset_index()
    )
    return weekly


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare scored bets between models.")
    parser.add_argument(
        "--season", type=str, required=True, help="Season label (e.g., 2024)"
    )
    parser.add_argument(
        "--mode",
        action="append",
        required=True,
        help="Mode mapping NAME=PATH_TO_SCORED_CSVS. Repeat for each mode.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/reports/metrics"),
        help="Directory to write summary CSVs",
    )
    parser.add_argument(
        "--print",
        action="store_true",
        help="Print summaries to stdout in addition to writing files.",
    )
    args = parser.parse_args()

    mode_paths = dict(_parse_mode_arg(m) for m in args.mode)
    overall_rows = []
    weekly_frames = []

    for mode, path in mode_paths.items():
        csvs = _discover_csvs(path)
        df = load_scored(csvs)
        spread = compute_metrics(df, "Spread Bet", "Spread Bet Result")
        totals = compute_metrics(df, "Total Bet", "Total Bet Result")
        overall_rows.append(
            {
                "season": args.season,
                "mode": mode,
                "spread_win_rate": spread["win_rate"],
                "spread_bets": spread["bets"],
                "spread_wins": spread["wins"],
                "spread_net_units": spread["net_units"],
                "total_win_rate": totals["win_rate"],
                "total_bets": totals["bets"],
                "total_wins": totals["wins"],
                "total_net_units": totals["net_units"],
            }
        )

        spread_weekly = weekly_summary(df, "Spread Bet", "Spread Bet Result")
        totals_weekly = weekly_summary(df, "Total Bet", "Total Bet Result")
        weekly = spread_weekly.merge(
            totals_weekly,
            on="Week",
            how="outer",
            suffixes=("_spread", "_total"),
        ).assign(mode=mode)
        weekly_frames.append(weekly)

    overall_df = pd.DataFrame(overall_rows)
    weekly_df = (
        pd.concat(weekly_frames, ignore_index=True) if weekly_frames else pd.DataFrame()
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    overall_path = args.output_dir / f"model_comparison_overall_{args.season}.csv"
    weekly_path = args.output_dir / f"model_comparison_weekly_{args.season}.csv"
    overall_df.to_csv(overall_path, index=False)
    weekly_df.to_csv(weekly_path, index=False)

    if args.print:
        print("Overall summary:\n", overall_df.to_string(index=False))
        print("\nWeekly summary head:\n", weekly_df.head().to_string(index=False))
    else:
        print(f"Wrote overall summary to {overall_path}")
        print(f"Wrote weekly summary to {weekly_path}")


if __name__ == "__main__":
    main()
