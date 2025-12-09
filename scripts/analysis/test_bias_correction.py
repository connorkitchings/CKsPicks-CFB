import glob
from pathlib import Path

import pandas as pd


def get_repo_root():
    return Path(__file__).parent.parent.parent

def calculate_roi(df):
    if len(df) == 0:
        return 0.0, 0.0

    # 1 for Win, 0 for Loss, 0.5 for Push (assuming Push is refunded, so 0 profit/loss but counts to volume?
    # Usually Push is money back. ROI = Profit / Risk.
    # Profit: Win (+0.91), Loss (-1.0), Push (0.0).
    # Let's check how 'Spread Bet Result' is coded. In scored csv, it's 1 for Win, 0 for Loss.
    # What about push? The scorer likely handles it. Let's look at scoring script later if needed.
    # For now, assume standard:
    # Win: +0.9091 units
    # Loss: -1.0 units
    # Push: 0 units

    # Check if 'Spread Result' is available (margin).
    # If Spread Bet Result is 1/0, we can calculate.

    n_bets = len(df)
    n_wins = df['Spread Bet Result'].sum()
    n_losses = n_bets - n_wins # Approximation if no pushes coded

    # More precise using columns if available, but let's stick to the standard from previous analysis
    roi = ((n_wins * 0.9091) - n_losses) / n_bets
    hit_rate = n_wins / n_bets
    return roi, hit_rate

def test_bias_correction():
    repo_root = get_repo_root()
    scored_data_path = repo_root / "data" / "production" / "scored" / "2024"

    # 1. Load Data
    all_files = glob.glob(str(scored_data_path / "CFB_week*_bets_scored.csv"))
    df = pd.concat((pd.read_csv(f) for f in all_files), ignore_index=True)

    # Cleanup
    numeric_cols = ['edge_spread', 'Spread Prediction', 'home_team_spread_line', 'home_points', 'away_points']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # Convert 'Win'/'Loss' to 1/0
    # Note: Scored files have 'Spread Bet Result' as 'Win'/'Loss'
    if df['Spread Bet Result'].dtype == 'object':
        df['Spread Bet Result'] = df['Spread Bet Result'].apply(lambda x: 1 if x == 'Win' else 0)

    df.dropna(subset=numeric_cols + ['Spread Bet Result'], inplace=True)

    # 2. Baseline Performance (Original 2.5 - 7.0 bucket)
    baseline_df = df[(df['edge_spread'] >= 2.5) & (df['edge_spread'] <= 7.0)].copy()
    base_roi, base_hr = calculate_roi(baseline_df)

    print("--- Baseline (2.5 <= Edge <= 7.0) ---")
    print(f"Bets: {len(baseline_df)}")
    print(f"Hit Rate: {base_hr:.2%}")
    print(f"ROI: {base_roi:.2%}")
    print("-------------------------------------\
")

    # 3. Apply Correction
    # Bias was -1.14 (Prediction < Actual). So we ADD 1.14 to Prediction.
    correction = 1.14
    df['corrected_prediction'] = df['Spread Prediction'] + correction

    # 4. Recalculate Edges and Bet outcomes
    # Edge = |Pred - Line|
    # But wait, we need to know WHICH SIDE the model bets.
    # The 'edge_spread' is positive.
    # Logic:
    # If Pred > Line, Model likes Home (Edge = Pred - Line).
    # If Pred < Line, Model likes Away (Edge = Line - Pred).
    # Let's replicate this logic.

    def evaluate_bet(row):
        pred = row['corrected_prediction']
        line = row['home_team_spread_line']
        actual_margin = row['home_points'] - row['away_points'] # Home Margin

        # Determine Bet
        if pred > line:
            # Bet Home
            edge = pred - line
            bet_side = 'Home'
            # Result: Win if Actual > Line
            # (Tie logic: Actual == Line -> Push)
            if actual_margin > line:
                result = 1
            elif actual_margin == line:
                result = 0.5 # Treat push as no P/L, but let's count volume?
                             # For ROI calc, Push means 0 profit.
            else:
                result = 0
        else:
            # Bet Away
            edge = line - pred
            bet_side = 'Away'
            # Result: Win if Actual < Line
            if actual_margin < line:
                result = 1
            elif actual_margin == line:
                result = 0.5
            else:
                result = 0

        return pd.Series([edge, bet_side, result])

    df[['new_edge', 'new_bet_side', 'new_result']] = df.apply(evaluate_bet, axis=1)

    # 5. Evaluate Corrected Performance (New 2.5 - 7.0 bucket)
    corrected_df = df[(df['new_edge'] >= 2.5) & (df['new_edge'] <= 7.0)].copy()

    # Recalculate ROI for new results
    # Handle Pushes (0.5) correctly for ROI
    # Profit = (Wins * 0.9091) - Losses
    # Wins = count of 1s
    # Losses = count of 0s
    n_bets_new = len(corrected_df)
    n_wins_new = len(corrected_df[corrected_df['new_result'] == 1])
    n_losses_new = len(corrected_df[corrected_df['new_result'] == 0])
    n_pushes_new = len(corrected_df[corrected_df['new_result'] == 0.5])

    if n_bets_new > 0:
        profit_new = (n_wins_new * 0.9091) - n_losses_new
        roi_new = profit_new / n_bets_new # ROI is usually on total turnover. Pushes count as returned stake.
    else:
        roi_new = 0

    hit_rate_new = n_wins_new / (n_bets_new - n_pushes_new) if (n_bets_new - n_pushes_new) > 0 else 0

    print("--- Corrected (+1.14 pts) (2.5 <= Edge <= 7.0) ---")
    print(f"Bets: {n_bets_new}")
    print(f"Hit Rate: {hit_rate_new:.2%}")
    print(f"ROI: {roi_new:.2%}")
    print("--------------------------------------------------\n")

    # 6. Comparison
    print("Impact of Correction:")
    print(f"Volume: {len(baseline_df)} -> {n_bets_new} ({n_bets_new - len(baseline_df):+d})")
    print(f"ROI: {base_roi:.2%} -> {roi_new:.2%} ({roi_new - base_roi:+.2%})")

if __name__ == "__main__":
    test_bias_correction()
