import glob
import os

import pandas as pd


def main():
    year = 2025
    pattern = f"artifacts/reports/{year}/scored/CFB_week*_bets_scored.csv"
    files = glob.glob(pattern)

    if not files:
        print(f"No scored files found for {year}")
        return

    print(f"Found {len(files)} scored files for {year}")

    all_bets = []
    for f in files:
        df = pd.read_csv(f)
        df["week"] = int(os.path.basename(f).split("week")[1].split("_")[0])
        all_bets.append(df)

    df = pd.concat(all_bets, ignore_index=True)

    # Spread Performance
    print("\n--- Spread Performance (Stacked Model) ---")
    spread_bets = df[df["Spread Bet Result"].isin(["Win", "Loss", "Push"])]
    wins = len(spread_bets[spread_bets["Spread Bet Result"] == "Win"])
    losses = len(spread_bets[spread_bets["Spread Bet Result"] == "Loss"])
    pushes = len(spread_bets[spread_bets["Spread Bet Result"] == "Push"])
    total = wins + losses
    win_rate = wins / total if total > 0 else 0.0

    print(f"Overall: {wins}-{losses}-{pushes} ({win_rate:.1%})")

    # By Week
    print("\nBy Week:")
    for week in sorted(spread_bets["week"].unique()):
        week_bets = spread_bets[spread_bets["week"] == week]
        w = len(week_bets[week_bets["Spread Bet Result"] == "Win"])
        losses_count = len(week_bets[week_bets["Spread Bet Result"] == "Loss"])
        p = len(week_bets[week_bets["Spread Bet Result"] == "Push"])
        t = w + losses_count
        wr = w / t if t > 0 else 0.0
        print(f"Week {week}: {w}-{losses_count}-{p} ({wr:.1%})")

    # Total Performance
    print("\n--- Total Performance (CatBoost Model) ---")
    total_bets = df[df["Total Bet Result"].isin(["Win", "Loss", "Push"])]
    wins = len(total_bets[total_bets["Total Bet Result"] == "Win"])
    losses = len(total_bets[total_bets["Total Bet Result"] == "Loss"])
    pushes = len(total_bets[total_bets["Total Bet Result"] == "Push"])
    total = wins + losses
    win_rate = wins / total if total > 0 else 0.0

    print(f"Overall: {wins}-{losses}-{pushes} ({win_rate:.1%})")


if __name__ == "__main__":
    main()
