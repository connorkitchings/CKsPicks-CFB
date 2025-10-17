"""
Generates a detailed performance summary report for a given season.
"""

import argparse
import json
import os

import numpy as np
import pandas as pd

from src.config import REPORTS_DIR, SCORED_SUBDIR, METRICS_SUBDIR


def calculate_roi(hit_rate, odds=-110):
    """Calculates ROI given a hit rate and American odds."""
    if hit_rate == 0:
        return 0.0
    if odds < 0:
        payout = 100 / abs(odds)
    else:
        payout = odds / 100
    return (hit_rate * payout) - (1 - hit_rate)


def main():
    parser = argparse.ArgumentParser(
        description="Generate a detailed performance report for a season."
    )
    parser.add_argument(
        "--year", type=int, required=True, help="The season year to analyze."
    )
    parser.add_argument(
        "--report-dir",
        type=str,
        default=str(REPORTS_DIR),
        help="Directory where scored reports are located.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(REPORTS_DIR / METRICS_SUBDIR),
        help="Directory to save the summary report.",
    )
    args = parser.parse_args()

    season_report_dir = os.path.join(
        args.report_dir, str(args.year), SCORED_SUBDIR
    )
    if not os.path.exists(season_report_dir):
        print(f"Report directory not found: {season_report_dir}")
        return

    all_scored_files = [
        f for f in os.listdir(season_report_dir) if f.endswith("_scored.csv")
    ]
    if not all_scored_files:
        print(f"No scored report files found in {season_report_dir}")
        return

    df_list = [
        pd.read_csv(os.path.join(season_report_dir, f)) for f in all_scored_files
    ]
    combined_df = pd.concat(df_list, ignore_index=True)

    summary = {"year": args.year, "total_bets": len(combined_df)}

    # Spread Analysis
    spread_bets = combined_df[combined_df["bet_spread"].isin(["home", "away"])].copy()
    if not spread_bets.empty:
        spread_wins = spread_bets["pick_win"].sum()
        spread_total = len(spread_bets)
        spread_hit_rate = spread_wins / spread_total if spread_total > 0 else 0.0
        spread_roi = calculate_roi(spread_hit_rate)

        summary["spreads"] = {
            "total_bets": spread_total,
            "wins": int(spread_wins),
            "hit_rate": spread_hit_rate,
            "roi": spread_roi,
            "by_edge_bucket": {},
            "by_bet_side": {},
        }

        # By edge bucket
        edge_bins = [0, 3.5, 5, 7, 10, np.inf]
        labels = ["0-3.5", "3.5-5", "5-7", "7-10", "10+"]
        spread_bets["edge_bucket"] = pd.cut(
            spread_bets["edge_spread"], bins=edge_bins, labels=labels, right=False
        )
        bucket_groups = spread_bets.groupby("edge_bucket")
        for name, group in bucket_groups:
            wins = group["pick_win"].sum()
            total = len(group)
            hit_rate = wins / total if total > 0 else 0.0
            summary["spreads"]["by_edge_bucket"][name] = {
                "bets": total,
                "wins": int(wins),
                "hit_rate": hit_rate,
            }

        # By bet side (home/away)
        side_groups = spread_bets.groupby("bet_spread")
        for name, group in side_groups:
            wins = group["pick_win"].sum()
            total = len(group)
            hit_rate = wins / total if total > 0 else 0.0
            summary["spreads"]["by_bet_side"][name] = {
                "bets": total,
                "wins": int(wins),
                "hit_rate": hit_rate,
            }

    # Total Analysis
    total_bets_df = combined_df[combined_df["bet_total"].isin(["over", "under"])].copy()
    if not total_bets_df.empty:
        total_wins = total_bets_df["total_pick_win"].sum()
        total_total = len(total_bets_df)
        total_hit_rate = total_wins / total_total if total_total > 0 else 0.0
        total_roi = calculate_roi(total_hit_rate)

        summary["totals"] = {
            "total_bets": total_total,
            "wins": int(total_wins),
            "hit_rate": total_hit_rate,
            "roi": total_roi,
        }

    # Save summary report
    os.makedirs(args.output_dir, exist_ok=True)
    output_path = os.path.join(args.output_dir, f"performance_summary_{args.year}.json")
    with open(output_path, "w") as f:
        json.dump(summary, f, indent=4)

    print(f"Performance summary saved to {output_path}")
    print(json.dumps(summary, indent=4))


if __name__ == "__main__":
    main()
