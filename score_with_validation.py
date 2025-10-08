#!/usr/bin/env python3

import sys

sys.path.insert(0, "src")
import pandas as pd


def main():
    print("=== SCORING VALIDATION ===")

    # Load original betting report
    bets_df = pd.read_csv("reports/2025/CFB_week6_bets.csv")
    expected_spread_bets = len(bets_df[bets_df["Spread Bet"].isin(["home", "away"])])
    expected_total_bets = len(bets_df[bets_df["Total Bet"].isin(["over", "under"])])

    print(f"Expected spread bets: {expected_spread_bets}")
    print(f"Expected total bets: {expected_total_bets}")

    # Check scored file if it exists
    try:
        scored_df = pd.read_csv("reports/2025/CFB_week6_bets_scored.csv")
        actual_spread_bets = len(
            scored_df[scored_df["Spread Bet"].isin(["home", "away"])]
        )
        actual_total_bets = len(
            scored_df[scored_df["Total Bet"].isin(["over", "under"])]
        )

        print(f"Actual spread bets in scored file: {actual_spread_bets}")
        print(f"Actual total bets in scored file: {actual_total_bets}")

        if actual_spread_bets != expected_spread_bets:
            print("❌ VALIDATION FAILED: Spread bet count mismatch")
        if actual_total_bets != expected_total_bets:
            print("❌ VALIDATION FAILED: Total bet count mismatch")

        if (
            actual_spread_bets == expected_spread_bets
            and actual_total_bets == expected_total_bets
        ):
            print("✅ VALIDATION PASSED: Bet counts match")

        # Show results breakdown
        print("\nSpread bet results:")
        print(
            scored_df[scored_df["Spread Bet"].isin(["home", "away"])][
                "Spread Bet Result"
            ].value_counts()
        )

        print("\nTotal bet results:")
        print(
            scored_df[scored_df["Total Bet"].isin(["over", "under"])][
                "Total Bet Result"
            ].value_counts()
        )

        # Show games with vs without scores
        spread_bets = scored_df[scored_df["Spread Bet"].isin(["home", "away"])]
        games_with_scores = spread_bets[spread_bets["Spread Bet Result"] != "Pending"]
        games_without_scores = spread_bets[
            spread_bets["Spread Bet Result"] == "Pending"
        ]

        print(f"\nGames with final results: {len(games_with_scores)}")
        print(f"Games still pending: {len(games_without_scores)}")

        if len(games_without_scores) > 0:
            print("\nPending games:")
            for _, row in games_without_scores.iterrows():
                print(f"  {row['Game']}")

    except FileNotFoundError:
        print("❌ No scored file found")


if __name__ == "__main__":
    main()
