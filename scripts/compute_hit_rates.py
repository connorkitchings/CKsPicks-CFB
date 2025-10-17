"""
Build per-week and season-level betting results summaries from scored reports.

Writes CSV files to artifacts/reports/<year>/metrics/<year>_results.csv with columns:
- week (individual weeks plus a "season" aggregate row)
- games_available, spread_bets, total_bets, spread_wins, total_wins
- spread_hit_rate, total_hit_rate, overall_hit_rate
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Optional

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src.config import REPORTS_DIR, SCORED_SUBDIR, METRICS_SUBDIR


def _get_scored_dir(report_dir: Path, year: int) -> Path:
    preferred = report_dir / str(year) / SCORED_SUBDIR
    legacy = report_dir / str(year)
    if preferred.exists():
        return preferred
    if legacy.exists():
        return legacy
    raise FileNotFoundError(
        f"No scored reports found for {year} under {preferred} or {legacy}"
    )


def _extract_week(path: Path) -> Optional[int]:
    match = re.search(r"week(\d+)", path.stem)
    return int(match.group(1)) if match else None


def _count_spread_bets(df: pd.DataFrame) -> tuple[int, int]:
    if "Spread Bet" in df.columns and "Spread Bet Result" in df.columns:
        mask = df["Spread Bet"].astype(str).str.lower().isin(["home", "away"])
        wins = (df["Spread Bet Result"] == "Win") & mask
        return int(mask.sum()), int(wins.sum())
    if {"bet_spread", "pick_win"}.issubset(df.columns):
        mask = df["bet_spread"].astype(str).str.lower().isin(["home", "away"])
        wins = df["pick_win"].fillna(0).astype(int)
        return int(mask.sum()), int((wins == 1).astype(int)[mask].sum())
    return 0, 0


def _count_total_bets(df: pd.DataFrame) -> tuple[int, int]:
    if "Total Bet" in df.columns and "Total Bet Result" in df.columns:
        mask = df["Total Bet"].astype(str).str.lower().isin(["over", "under"])
        wins = (df["Total Bet Result"] == "Win") & mask
        return int(mask.sum()), int(wins.sum())
    if {"bet_total", "total_pick_win"}.issubset(df.columns):
        mask = df["bet_total"].astype(str).str.lower().isin(["over", "under"])
        wins = df["total_pick_win"].fillna(0).astype(int)
        return int(mask.sum()), int((wins == 1).astype(int)[mask].sum())
    return 0, 0


def _games_available(df: pd.DataFrame) -> int:
    if "Game" in df.columns:
        return df["Game"].nunique()
    if "game_id" in df.columns:
        return df["game_id"].nunique()
    return len(df)


def build_results_summary(year: int, report_dir: Path) -> pd.DataFrame:
    scored_dir = _get_scored_dir(report_dir, year)
    weekly_paths = sorted(
        (p for p in scored_dir.glob("CFB_week*_bets_scored.csv") if p.is_file()),
        key=lambda p: _extract_week(p) or 0,
    )
    if not weekly_paths:
        raise FileNotFoundError(f"No weekly scored reports found in {scored_dir}")

    rows: list[dict[str, object]] = []

    for path in weekly_paths:
        week = _extract_week(path)
        if week is None:
            continue
        df = pd.read_csv(path)
        games = _games_available(df)
        spread_bets, spread_wins = _count_spread_bets(df)
        total_bets, total_wins = _count_total_bets(df)

        overall_bets = spread_bets + total_bets
        overall_wins = spread_wins + total_wins

        row = {
            "week": week,
            "games_available": games,
            "spread_bets": spread_bets,
            "spread_wins": spread_wins,
            "spread_hit_rate": (
                spread_wins / spread_bets if spread_bets > 0 else None
            ),
            "total_bets": total_bets,
            "total_wins": total_wins,
            "total_hit_rate": total_wins / total_bets if total_bets > 0 else None,
            "overall_bets": overall_bets,
            "overall_wins": overall_wins,
            "overall_hit_rate": (
                overall_wins / overall_bets if overall_bets > 0 else None
            ),
        }
        rows.append(row)

    summary = pd.DataFrame(rows).sort_values("week").reset_index(drop=True)

    season_row = {
        "week": "season",
        "games_available": summary["games_available"].sum(),
        "spread_bets": summary["spread_bets"].sum(),
        "spread_wins": summary["spread_wins"].sum(),
        "spread_hit_rate": (
            summary["spread_wins"].sum() / summary["spread_bets"].sum()
            if summary["spread_bets"].sum() > 0
            else None
        ),
        "total_bets": summary["total_bets"].sum(),
        "total_wins": summary["total_wins"].sum(),
        "total_hit_rate": (
            summary["total_wins"].sum() / summary["total_bets"].sum()
            if summary["total_bets"].sum() > 0
            else None
        ),
        "overall_bets": summary["overall_bets"].sum(),
        "overall_wins": summary["overall_wins"].sum(),
        "overall_hit_rate": (
            summary["overall_wins"].sum() / summary["overall_bets"].sum()
            if summary["overall_bets"].sum() > 0
            else None
        ),
    }
    summary = pd.concat([summary, pd.DataFrame([season_row])], ignore_index=True)
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Summarize weekly and season betting performance."
    )
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--report-dir", type=str, default=str(REPORTS_DIR))
    args = ap.parse_args()

    report_dir = Path(args.report_dir)
    summary = build_results_summary(args.year, report_dir)

    metrics_dir = report_dir / str(args.year) / METRICS_SUBDIR
    metrics_dir.mkdir(parents=True, exist_ok=True)
    out_path = metrics_dir / f"{args.year}_results.csv"
    summary.to_csv(out_path, index=False)

    print(summary.to_string(index=False))
    print(f"\nSaved results summary to {out_path}")


if __name__ == "__main__":
    main()
