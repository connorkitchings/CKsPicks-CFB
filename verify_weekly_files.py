import os

import pandas as pd

try:
    report_dir = "/Users/connorkitchings/Desktop/Repositories/cfb_model/reports/2024"
    scored_files = [
        os.path.join(report_dir, f)
        for f in os.listdir(report_dir)
        if f.startswith("CFB_week") and f.endswith("_scored.csv")
    ]

    if not scored_files:
        print("No weekly scored files found.")
    else:
        df_list = [pd.read_csv(f) for f in scored_files]
        combined_df = pd.concat(df_list, ignore_index=True)

        # --- Total Analysis ---
        total_bets = combined_df[
            combined_df["Total Bet"].isin(["over", "under"])
        ].copy()
        total_wins = (total_bets["Total Bet Result"] == "Win").sum()
        total_losses = (total_bets["Total Bet Result"] == "Loss").sum()
        total_total_decided = total_wins + total_losses
        total_hit_rate = (
            total_wins / total_total_decided if total_total_decided > 0 else 0.0
        )

        print("--- Totals Performance from WEEKLY files ---")
        print(
            f"Wins: {total_wins}, Losses: {total_losses}, Decided: {total_total_decided}"
        )
        print(f"Hit Rate: {total_hit_rate:.2%}")
        print("------------------------------------------")

except Exception as e:
    print(f"An error occurred: {e}")
