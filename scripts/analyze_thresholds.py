import glob
from pathlib import Path

import numpy as np
import pandas as pd


def analyze_thresholds():
    # Define data directory
    # Using the path found in the previous step
    data_dir = Path("artifacts/reports/2024/scored")

    # Load all scored bet files
    files = glob.glob(str(data_dir / "CFB_week*_bets_scored.csv"))
    if not files:
        print(f"No files found in {data_dir}")
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
    print(f"Total bets loaded: {len(all_bets)}")

    # Normalize Result columns
    # Assuming 'Spread Bet Result' and 'Total Bet Result' contain 'Win', 'Loss', 'Push'
    # Or 1.0, 0.0, 0.5

    results = []

    thresholds = np.arange(0.0, 10.5, 0.5)

    for threshold in thresholds:
        # --- Spread Bets ---
        # Filter for valid spread bets
        spread_bets = all_bets[all_bets["Spread Bet"].isin(["home", "away"])].copy()

        # Ensure edge_spread exists
        if "edge_spread" not in spread_bets.columns:
            # Try to calculate if missing (optional, but better to rely on existing data)
            pass

        # Filter by threshold
        spread_subset = spread_bets[spread_bets["edge_spread"] >= threshold]

        s_wins = 0
        s_losses = 0
        s_pushes = 0

        # Calculate results
        # Check for different result formats
        if "Spread Bet Result" in spread_subset.columns:
            s_wins = len(
                spread_subset[spread_subset["Spread Bet Result"].isin(["Win", 1, 1.0])]
            )
            s_losses = len(
                spread_subset[spread_subset["Spread Bet Result"].isin(["Loss", 0, 0.0])]
            )
            s_pushes = len(
                spread_subset[spread_subset["Spread Bet Result"].isin(["Push", 0.5])]
            )

        s_count = s_wins + s_losses + s_pushes
        s_win_rate = s_wins / (s_wins + s_losses) if (s_wins + s_losses) > 0 else 0.0
        s_net_units = (s_wins * 1.0) - (s_losses * 1.1)
        s_roi = (
            s_net_units / ((s_wins + s_losses) * 1.1)
            if (s_wins + s_losses) > 0
            else 0.0
        )

        # --- Total Bets ---
        total_bets = all_bets[all_bets["Total Bet"].isin(["over", "under"])].copy()
        total_subset = total_bets[total_bets["edge_total"] >= threshold]

        t_wins = 0
        t_losses = 0
        t_pushes = 0

        if "Total Bet Result" in total_subset.columns:
            t_wins = len(
                total_subset[total_subset["Total Bet Result"].isin(["Win", 1, 1.0])]
            )
            t_losses = len(
                total_subset[total_subset["Total Bet Result"].isin(["Loss", 0, 0.0])]
            )
            t_pushes = len(
                total_subset[total_subset["Total Bet Result"].isin(["Push", 0.5])]
            )

        t_count = t_wins + t_losses + t_pushes
        t_win_rate = t_wins / (t_wins + t_losses) if (t_wins + t_losses) > 0 else 0.0
        t_net_units = (t_wins * 1.0) - (t_losses * 1.1)
        t_roi = (
            t_net_units / ((t_wins + t_losses) * 1.1)
            if (t_wins + t_losses) > 0
            else 0.0
        )

        # --- Combined ---
        c_wins = s_wins + t_wins
        c_losses = s_losses + t_losses
        c_pushes = s_pushes + t_pushes
        c_count = c_wins + c_losses + c_pushes
        c_win_rate = c_wins / (c_wins + c_losses) if (c_wins + c_losses) > 0 else 0.0
        c_net_units = s_net_units + t_net_units
        c_roi = (
            c_net_units / ((c_wins + c_losses) * 1.1)
            if (c_wins + c_losses) > 0
            else 0.0
        )

        results.append(
            {
                "Threshold": threshold,
                "Spread Count": s_count,
                "Spread Win%": s_win_rate,
                "Spread Units": s_net_units,
                "Spread ROI": s_roi,
                "Total Count": t_count,
                "Total Win%": t_win_rate,
                "Total Units": t_net_units,
                "Total ROI": t_roi,
                "Combined Count": c_count,
                "Combined Win%": c_win_rate,
                "Combined Units": c_net_units,
                "Combined ROI": c_roi,
            }
        )

    results_df = pd.DataFrame(results)

    # Formatting for display
    display_df = results_df.copy()
    for col in [
        "Spread Win%",
        "Spread ROI",
        "Total Win%",
        "Total ROI",
        "Combined Win%",
        "Combined ROI",
    ]:
        display_df[col] = display_df[col].map("{:.1%}".format)
    for col in ["Spread Units", "Total Units", "Combined Units"]:
        display_df[col] = display_df[col].map("{:+.1f}".format)

    print("\nThreshold Analysis (2024 Season)")
    print("================================")
    print(display_df.to_string(index=False))

    # Save raw results
    output_path = data_dir.parent / "threshold_analysis_2024.csv"
    results_df.to_csv(output_path, index=False)
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    analyze_thresholds()
