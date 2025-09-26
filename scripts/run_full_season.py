#!/usr/bin/env python3
"""Run model predictions and scoring for full 2024 season."""

import os
import subprocess
import pandas as pd
from pathlib import Path


def main():
    DATA_ROOT = "/Volumes/CK SSD/Coding Projects/cfb_model"
    MODEL_DIR = "./models/ridge_baseline"
    REPORT_DIR = "./reports"
    YEAR = 2024
    weeks_to_run = list(range(5, 17))  # Weeks 5-16

    print(f"Running model for {len(weeks_to_run)} weeks: {weeks_to_run}")

    all_results = []
    bet_summary = []

    for week in weeks_to_run:
        print(f"\n=== Processing Week {week} ===")

        # Generate predictions
        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = "./src"

            result = subprocess.run(
                [
                    "python3",
                    "src/cfb_model/scripts/generate_weekly_bets_clean.py",
                    "--year",
                    str(YEAR),
                    "--week",
                    str(week),
                    "--data-root",
                    DATA_ROOT,
                    "--model-dir",
                    MODEL_DIR,
                    "--output-dir",
                    REPORT_DIR,
                ],
                capture_output=True,
                text=True,
                env=env,
            )

            if result.returncode != 0:
                print(f"ERROR generating week {week}: {result.stderr}")
                continue

            print(f"Generated predictions for week {week}")

        except Exception as e:
            print(f"ERROR running predictions for week {week}: {e}")
            continue

        # Score predictions
        try:
            result = subprocess.run(
                [
                    "python3",
                    "scripts/score_weekly_picks.py",
                    "--year",
                    str(YEAR),
                    "--week",
                    str(week),
                    "--data-root",
                    DATA_ROOT,
                    "--report-dir",
                    REPORT_DIR,
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                print(f"ERROR scoring week {week}: {result.stderr}")
                continue

            print(f"Scored predictions for week {week}")

        except Exception as e:
            print(f"ERROR scoring week {week}: {e}")
            continue

        # Load and analyze results
        scored_path = f"{REPORT_DIR}/{YEAR}/CFB_week{week}_bets_scored.csv"
        if os.path.exists(scored_path):
            try:
                scored_df = pd.read_csv(scored_path)
                spread_bets = scored_df[scored_df["bet_spread"].isin(["home", "away"])]

                if len(spread_bets) > 0:
                    wins = spread_bets["pick_win"].sum()
                    total = len(spread_bets)
                    hit_rate = wins / total

                    print(f"Week {week}: {wins}/{total} = {hit_rate:.3f}")

                    bet_summary.append(
                        {
                            "week": week,
                            "wins": int(wins),
                            "total_bets": total,
                            "hit_rate": hit_rate,
                        }
                    )

                    all_results.append(scored_df)
                else:
                    print(f"Week {week}: No bets generated")
                    bet_summary.append(
                        {"week": week, "wins": 0, "total_bets": 0, "hit_rate": None}
                    )
            except Exception as e:
                print(f"ERROR analyzing week {week}: {e}")
        else:
            print(f"ERROR: Scored file not found for week {week}")

    # Print summary
    print("\n" + "=" * 60)
    print("SEASON SUMMARY")
    print("=" * 60)

    total_wins = sum(s["wins"] for s in bet_summary)
    total_bets = sum(s["total_bets"] for s in bet_summary)

    print(f"\nWeekly Results:")
    for summary in bet_summary:
        if summary["hit_rate"] is not None:
            print(
                f"Week {summary['week']:2d}: {summary['wins']:2d}/{summary['total_bets']:2d} = {summary['hit_rate']:5.3f}"
            )
        else:
            print(f"Week {summary['week']:2d}: No bets")

    if total_bets > 0:
        overall_hit_rate = total_wins / total_bets
        print(f"\nOVERALL: {total_wins}/{total_bets} = {overall_hit_rate:.3f}")
        print(f"Breakeven needed: 0.524 (52.4%)")
        print(f"Performance vs breakeven: {overall_hit_rate - 0.524:+.3f}")

        # Calculate additional stats
        weeks_with_bets = [s for s in bet_summary if s["hit_rate"] is not None]
        if weeks_with_bets:
            hit_rates = [s["hit_rate"] for s in weeks_with_bets]
            avg_weekly_hit_rate = sum(hit_rates) / len(hit_rates)
            print(f"Average weekly hit rate: {avg_weekly_hit_rate:.3f}")
            print(f"Weeks with bets: {len(weeks_with_bets)}/{len(bet_summary)}")
    else:
        print("\nNo bets generated across all weeks")

    # Save combined results
    if all_results:
        combined_df = pd.concat(all_results, ignore_index=True)
        combined_path = f"{REPORT_DIR}/{YEAR}/CFB_season_2024_all_bets_scored.csv"
        combined_df.to_csv(combined_path, index=False)
        print(f"\nCombined results saved to: {combined_path}")

        # Additional analysis
        print(f"\nDetailed Analysis:")
        print(f"Total games analyzed: {len(combined_df)}")
        spread_bets = combined_df[combined_df["bet_spread"].isin(["home", "away"])]
        print(f"Total spread bets: {len(spread_bets)}")

        if len(spread_bets) > 0:
            home_bets = spread_bets[spread_bets["bet_spread"] == "home"]
            away_bets = spread_bets[spread_bets["bet_spread"] == "away"]

            print(
                f"Home bets: {len(home_bets)}, Win rate: {home_bets['pick_win'].mean():.3f}"
            )
            print(
                f"Away bets: {len(away_bets)}, Win rate: {away_bets['pick_win'].mean():.3f}"
            )

            # Edge analysis
            print(f"\nEdge Analysis:")
            print(f"Average edge: {spread_bets['edge_spread'].mean():.2f}")
            print(f"Minimum edge: {spread_bets['edge_spread'].min():.2f}")
            print(f"Maximum edge: {spread_bets['edge_spread'].max():.2f}")


if __name__ == "__main__":
    main()
