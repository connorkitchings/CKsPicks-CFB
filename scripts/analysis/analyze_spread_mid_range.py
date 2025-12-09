import glob
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

# Set plot style
sns.set_theme(style="whitegrid")

def get_repo_root():
    """Get the root directory of the repo."""
    return Path(__file__).parent.parent.parent

def analyze_mid_range_spreads():
    """
    Analyzes the performance of spread bets in the 2.5 to 7.0 edge range.
    """
    repo_root = get_repo_root()
    scored_data_path = repo_root / "data" / "production" / "scored" / "2024"
    output_path = repo_root / "artifacts" / "analysis"
    output_path.mkdir(parents=True, exist_ok=True)

    # 1. Load and concatenate all 2024 scored data
    all_files = glob.glob(str(scored_data_path / "CFB_week*_bets_scored.csv"))
    if not all_files:
        print(f"No scored files found in {scored_data_path}. Exiting.")
        return

    df = pd.concat((pd.read_csv(f) for f in all_files), ignore_index=True)

    # Ensure required columns are numeric
    for col in ['edge_spread', 'Spread Prediction', 'home_team_spread_line']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # Convert 'Win'/'Loss' to 1/0
    df['Spread Bet Result'] = df['Spread Bet Result'].apply(lambda x: 1 if x == 'Win' else 0)

    df.dropna(subset=['edge_spread', 'Spread Bet Result', 'Spread Prediction', 'home_team_spread_line'], inplace=True)


    # 2. Filter for the mid-range bets
    mid_range_df = df[(df['edge_spread'] >= 2.5) & (df['edge_spread'] <= 7.0)].copy()

    if mid_range_df.empty:
        print("No bets found in the 2.5 to 7.0 edge range.")
        return

    # 3. Calculate performance
    n_bets = len(mid_range_df)
    n_wins = mid_range_df['Spread Bet Result'].sum()
    hit_rate = n_wins / n_bets if n_bets > 0 else 0
    roi = ((n_wins * 0.91) - (n_bets - n_wins)) / n_bets if n_bets > 0 else 0

    print("--- Mid-Range Spread Performance (Edge: 2.5 to 7.0) ---")
    print(f"Total Bets: {n_bets}")
    print(f"Hit Rate: {hit_rate:.2%}")
    print(f"ROI: {roi:.2%}")
    print("--------------------------------------------------------")


    # 4. Analyze Prediction Error
    mid_range_df['actual_spread_line'] = mid_range_df['home_points'] - mid_range_df['away_points']
    mid_range_df['prediction_error'] = mid_range_df['Spread Prediction'] - mid_range_df['actual_spread_line']

    mean_error = mid_range_df['prediction_error'].mean()
    std_error = mid_range_df['prediction_error'].std()

    print(f"Prediction Error Mean: {mean_error:.2f}")
    print(f"Prediction Error Std Dev: {std_error:.2f}")
    print("\n")


    # 5. Generate and save plots

    # Plot 1: Prediction Error Distribution
    plt.figure(figsize=(12, 6))
    sns.histplot(mid_range_df['prediction_error'], kde=True, bins=30)
    plt.axvline(mean_error, color='r', linestyle='--', label=f'Mean Error: {mean_error:.2f}')
    plt.title('Prediction Error Distribution for Mid-Range Spreads (Edge: 2.5-7.0)')
    plt.xlabel('Prediction Error (Predicted Spread - Actual Spread)')
    plt.ylabel('Frequency')
    plt.legend()
    error_dist_path = output_path / 'mid_range_spread_error_distribution.png'
    plt.savefig(error_dist_path)
    print(f"Saved error distribution plot to: {error_dist_path}")

    # Plot 2: Predicted vs. Actual Spread
    plt.figure(figsize=(10, 10))
    sns.regplot(x='actual_spread_line', y='Spread Prediction', data=mid_range_df,
                scatter_kws={'alpha':0.3}, line_kws={'color':'red'})
    plt.plot([-60, 60], [-60, 60], 'k--', label='Perfect Prediction')
    plt.title('Predicted vs. Actual Spread for Mid-Range Bets')
    plt.xlabel('Actual Spread (Home Score - Away Score)')
    plt.ylabel('Predicted Spread')
    plt.axis('equal')
    plt.grid(True)
    plt.legend()
    pred_vs_actual_path = output_path / 'mid_range_spread_predicted_vs_actual.png'
    plt.savefig(pred_vs_actual_path)
    print(f"Saved predicted vs. actual plot to: {pred_vs_actual_path}")


if __name__ == "__main__":
    analyze_mid_range_spreads()
