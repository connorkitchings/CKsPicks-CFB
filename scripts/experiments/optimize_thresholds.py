from pathlib import Path

import pandas as pd


def load_scored_data(years=[2024, 2025]):
    frames = []
    for year in years:
        scored_dir = Path(f"artifacts/reports/{year}/scored")
        if not scored_dir.exists():
            continue

        for p in scored_dir.glob("CFB_week*_bets_scored.csv"):
            try:
                df = pd.read_csv(p)
                if df.empty:
                    continue

                # Normalize columns (Robust Logic)
                if "Spread Edge" in df.columns:
                    if "edge_spread" in df.columns:
                        df["edge_spread"] = df["edge_spread"].fillna(df["Spread Edge"])
                        df.drop(columns=["Spread Edge"], inplace=True)
                    else:
                        df.rename(columns={"Spread Edge": "edge_spread"}, inplace=True)

                if "Total Edge" in df.columns:
                    if "edge_total" in df.columns:
                        df["edge_total"] = df["edge_total"].fillna(df["Total Edge"])
                        df.drop(columns=["Total Edge"], inplace=True)
                    else:
                        df.rename(columns={"Total Edge": "edge_total"}, inplace=True)

                # Ensure numeric
                for col in ["edge_spread", "edge_total"]:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce")

                frames.append(df)
            except Exception as e:
                print(f"Error loading {p}: {e}")
                continue

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True)


def calculate_stats(df, threshold, edge_col, result_col):
    if edge_col not in df.columns or result_col not in df.columns:
        return None

    # Filter by threshold
    subset = df[df[edge_col] >= threshold].copy()

    count = len(subset)
    if count == 0:
        return {"Threshold": threshold, "Count": 0, "Win Rate": 0.0, "ROI": 0.0}

    wins = len(subset[subset[result_col] == "Win"])
    losses = len(subset[subset[result_col] == "Loss"])
    # pushes = len(subset[subset[result_col] == "Push"])

    # Win Rate (excluding pushes)
    decisions = wins + losses
    bet_win_rate = (wins / decisions) * 100 if decisions > 0 else 0.0

    # ROI (Assuming -110 odds: Win=+0.909, Loss=-1.0)
    # ROI = (Net Profit / Total Wagered) * 100
    # Net Profit = (Wins * 0.909) - (Losses * 1.0)
    # Total Wagered = Wins + Losses (assuming 1 unit per bet)
    net_profit = (wins * 0.90909) - losses
    total_wagered = wins + losses
    roi = (net_profit / total_wagered) * 100 if total_wagered > 0 else 0.0

    return {
        "Threshold": threshold,
        "Count": count,
        "Wins": wins,
        "Losses": losses,
        "Win Rate": bet_win_rate,
        "ROI": roi,
    }


def main():
    print("Loading data for 2024 and 2025...")
    df = load_scored_data()
    print(f"Loaded {len(df)} total bets.")

    print("\n--- SPREAD OPTIMIZATION ---")
    spread_results = []
    for th in [i / 2 for i in range(0, 21)]:  # 0.0 to 10.0 step 0.5
        stats = calculate_stats(df, th, "edge_spread", "Spread Bet Result")
        if stats:
            spread_results.append(stats)

    spread_df = pd.DataFrame(spread_results)
    if not spread_df.empty:
        print(spread_df.to_string(index=False, float_format="%.2f"))
    else:
        print("No spread data found.")

    print("\n--- TOTAL OPTIMIZATION ---")
    total_results = []
    for th in range(0, 21):  # 0 to 20 step 1
        stats = calculate_stats(df, th, "edge_total", "Total Bet Result")
        if stats:
            total_results.append(stats)

    total_df = pd.DataFrame(total_results)
    if not total_df.empty:
        print(total_df.to_string(index=False, float_format="%.2f"))
    else:
        print("No total data found.")


if __name__ == "__main__":
    main()
