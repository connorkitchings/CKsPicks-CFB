import pandas as pd

try:
    file_path = "/Users/connorkitchings/Desktop/Repositories/cfb_model/reports/2024/CFB_season_2024_all_bets_scored.csv"
    combined_df = pd.read_csv(file_path)

    # --- Total Analysis ---
    total_bets = combined_df[combined_df["Total Bet"].isin(["over", "under"])].copy()
    total_wins = (total_bets["Total Bet Result"] == "Win").sum()
    total_losses = (total_bets["Total Bet Result"] == "Loss").sum()
    total_pushes = (total_bets["Total Bet Result"] == "Push").sum()
    total_total_decided = total_wins + total_losses
    total_hit_rate = (
        total_wins / total_total_decided if total_total_decided > 0 else 0.0
    )

    print("--- Totals Performance Breakdown (2024 Season) ---")
    print(f"Total 'Over/Under' Bets Placed: {len(total_bets)}")
    print(f"Wins: {total_wins}")
    print(f"Losses: {total_losses}")
    print(f"Pushes: {total_pushes}")
    print(f"Decided Bets (Wins + Losses): {total_total_decided}")
    print(f"Hit Rate (Wins / Decided Bets): {total_hit_rate:.2%}")
    print("-------------------------------------------------")

except Exception as e:
    print(f"An error occurred during analysis: {e}")
