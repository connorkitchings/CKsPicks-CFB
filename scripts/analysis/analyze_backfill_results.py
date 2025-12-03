import glob

import pandas as pd


def analyze_backfill():
    # Path to scored bets
    # artifacts/reports/{year}/scored/CFB_week*_bets_scored.csv
    files = glob.glob("artifacts/reports/*/scored/CFB_week*_bets_scored.csv")

    if not files:
        print("No scored bet files found.")
        return

    print(f"Found {len(files)} scored files.")

    dfs = []
    for f in files:
        try:
            df = pd.read_csv(f)
            dfs.append(df)
        except Exception as e:
            print(f"Error reading {f}: {e}")

    if not dfs:
        print("No data loaded.")
        return

    all_bets = pd.concat(dfs, ignore_index=True)
    print(f"Total rows: {len(all_bets)}")

    # Analyze Spreads
    # Filter for "Spread Bet" != "No Bet"
    spread_bets = all_bets[all_bets["Spread Bet"] != "No Bet"].copy()

    print("\n=== Spread Performance ===")
    total_spread = len(spread_bets)
    if total_spread > 0:
        wins = len(spread_bets[spread_bets["Spread Bet Result"] == "Win"])
        losses = len(spread_bets[spread_bets["Spread Bet Result"] == "Loss"])
        pushes = len(spread_bets[spread_bets["Spread Bet Result"] == "Push"])

        decisive = wins + losses
        bet_win_rate = wins / decisive if decisive > 0 else 0.0

        # ROI (assuming -110 odds -> win=0.909, loss=-1)
        units = (wins * 0.909) - (losses * 1.0)
        roi = units / decisive if decisive > 0 else 0.0

        print(f"Record: {wins}-{losses}-{pushes}")
        print(f"Win Rate: {bet_win_rate:.1%}")
        print(f"Units: {units:.2f}")
        print(f"ROI: {roi:.1%}")
    else:
        print("No spread bets found.")

    # Analyze Totals
    total_bets = all_bets[all_bets["Total Bet"] != "No Bet"].copy()

    print("\n=== Total Performance ===")
    total_total = len(total_bets)
    if total_total > 0:
        wins = len(total_bets[total_bets["Total Bet Result"] == "Win"])
        losses = len(total_bets[total_bets["Total Bet Result"] == "Loss"])
        pushes = len(total_bets[total_bets["Total Bet Result"] == "Push"])

        decisive = wins + losses
        bet_win_rate = wins / decisive if decisive > 0 else 0.0

        units = (wins * 0.909) - (losses * 1.0)
        roi = units / decisive if decisive > 0 else 0.0

        print(f"Record: {wins}-{losses}-{pushes}")
        print(f"Win Rate: {bet_win_rate:.1%}")
        print(f"Units: {units:.2f}")
        print(f"ROI: {roi:.1%}")
    else:
        print("No total bets found.")

    # Breakdown by Year
    if "Date" in all_bets.columns:
        all_bets["Year"] = pd.to_datetime(all_bets["Date"], errors="coerce").dt.year

        print("\n=== Performance by Year ===")
        for year in sorted(all_bets["Year"].dropna().unique()):
            year_bets = all_bets[all_bets["Year"] == year]

            # Spread
            sb = year_bets[year_bets["Spread Bet"] != "No Bet"]
            sw = len(sb[sb["Spread Bet Result"] == "Win"])
            sl = len(sb[sb["Spread Bet Result"] == "Loss"])
            sd = sw + sl
            swr = sw / sd if sd > 0 else 0.0

            # Total
            tb = year_bets[year_bets["Total Bet"] != "No Bet"]
            tw = len(tb[tb["Total Bet Result"] == "Win"])
            tl = len(tb[tb["Total Bet Result"] == "Loss"])
            td = tw + tl
            twr = tw / td if td > 0 else 0.0

            print(
                f"{int(year)}: Spread {sw}-{sl} ({swr:.1%}) | Total {tw}-{tl} ({twr:.1%})"
            )


if __name__ == "__main__":
    analyze_backfill()
