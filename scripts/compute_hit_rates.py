"""
Compute season hit rates and counts from scored weekly reports.

Writes a CSV to reports/metrics/hit_rates_<year>.csv with columns:
- year, up_to_week, spread_hit_rate, total_hit_rate, spread_count, total_count

Usage:
  uv run python scripts/compute_hit_rates.py --year 2024 --report-dir ./reports
  uv run python scripts/compute_hit_rates.py --year 2025 --report-dir ./reports --up-to-week 5
"""

from __future__ import annotations

import argparse
import glob
from pathlib import Path

import pandas as pd


def compute(
    year: int, report_dir: Path, up_to_week: int | None
) -> tuple[float | None, float | None, int, int]:
    paths: list[Path] = []
    season_combined = report_dir / str(year) / f"CFB_season_{year}_all_bets_scored.csv"
    if season_combined.exists():
        paths = [season_combined]
    else:
        paths = [
            Path(p)
            for p in glob.glob(
                str(report_dir / str(year) / "CFB_week*_bets_scored.csv")
            )
        ]
    if not paths:
        return None, None, 0, 0

    frames: list[pd.DataFrame] = []
    for p in paths:
        try:
            df = pd.read_csv(p)
            frames.append(df)
        except Exception:
            continue
    if not frames:
        return None, None, 0, 0

    scored = pd.concat(frames, ignore_index=True)
    if up_to_week is not None and "Week" in scored.columns:
        scored = scored[scored["Week"] <= up_to_week]

    # Spread
    spr = None
    spr_n = 0
    if {"Spread Bet", "Spread Bet Result"}.issubset(scored.columns):
        placed = scored[scored["Spread Bet"].str.lower().isin(["home", "away"])]
        decided = placed[placed["Spread Bet Result"].isin(["Win", "Loss"])]
        spr_n = int(len(decided))
        if spr_n > 0:
            spr = float((decided["Spread Bet Result"] == "Win").mean())
    elif "bet_spread" in scored.columns and "pick_win" in scored.columns:
        placed = scored[scored["bet_spread"].str.lower().isin(["home", "away"])]
        # pick_win assumed 1=win, 0=loss; exclude NaNs
        decided = placed[placed["pick_win"].isin([0, 1])]
        spr_n = int(len(decided))
        if spr_n > 0:
            spr = float(decided["pick_win"].mean())

    # Total
    tot = None
    tot_n = 0
    if {"Total Bet", "Total Bet Result"}.issubset(scored.columns):
        placed_t = scored[scored["Total Bet"].str.lower().isin(["over", "under"])]
        decided_t = placed_t[placed_t["Total Bet Result"].isin(["Win", "Loss"])]
        tot_n = int(len(decided_t))
        if tot_n > 0:
            tot = float((decided_t["Total Bet Result"] == "Win").mean())
    elif "bet_total" in scored.columns and "total_pick_win" in scored.columns:
        placed_t = scored[scored["bet_total"].str.lower().isin(["over", "under"])]
        decided_t = placed_t[placed_t["total_pick_win"].isin([0, 1])]
        tot_n = int(len(decided_t))
        if tot_n > 0:
            tot = float(decided_t["total_pick_win"].mean())

    return spr, tot, spr_n, tot_n


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Compute hit rates and counts from scored reports."
    )
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--report-dir", type=str, default="./reports")
    ap.add_argument("--up-to-week", type=int, default=None)
    args = ap.parse_args()

    report_dir = Path(args.report_dir)
    spr, tot, spr_n, tot_n = compute(args.year, report_dir, args.up_to_week)

    out_dir = report_dir / "metrics"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"hit_rates_{args.year}.csv"

    row = {
        "year": args.year,
        "up_to_week": args.up_to_week,
        "spread_hit_rate": spr,
        "total_hit_rate": tot,
        "spread_count": spr_n,
        "total_count": tot_n,
    }
    pd.DataFrame([row]).to_csv(out_path, index=False)
    print(f"Saved hit rates to {out_path}")
    print(row)


if __name__ == "__main__":
    main()
