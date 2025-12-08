import numpy as np
import pandas as pd

from src.features.v2_recency import load_v2_recency_data
from src.models.v1_baseline import V1BaselineModel


def check_distribution():
    year = 2024
    alpha = 0.3
    features = [
        "home_adj_off_epa_pp",
        "home_adj_def_epa_pp",
        "home_adj_off_sr",
        "home_adj_def_sr",
        "away_adj_off_epa_pp",
        "away_adj_def_epa_pp",
        "away_adj_off_sr",
        "away_adj_def_sr",
        "home_adj_off_rush_ypp",
        "home_adj_def_rush_ypp",
        "home_adj_off_pass_ypp",
        "home_adj_def_pass_ypp",
        "away_adj_off_rush_ypp",
        "away_adj_def_rush_ypp",
        "away_adj_off_pass_ypp",
        "away_adj_def_pass_ypp",
    ]

    # Load Training Data (Pre-2024)
    print("Loading training data...")
    train_dfs = [load_v2_recency_data(y, alpha=alpha) for y in [2019, 2021, 2022, 2023]]
    train_df = pd.concat([df for df in train_dfs if df is not None], ignore_index=True)

    # Train Models
    print("Training models...")
    spread_model = V1BaselineModel(alpha=1.0, features=features, target="spread_target")
    total_model = V1BaselineModel(alpha=1.0, features=features, target="total_target")
    spread_model.fit(train_df)
    total_model.fit(train_df)

    # Load Test Data (2024)
    print("Loading 2024 data...")
    df = load_v2_recency_data(year, alpha=alpha)

    # Predict
    spread_preds = spread_model.predict(df)
    total_preds = total_model.predict(df)

    # Calculate Edges
    spread_lines = df["spread_line"]
    total_lines = df["total_line"]

    spread_edge = np.abs(spread_preds - (-spread_lines))
    total_edge = np.abs(total_preds - total_lines)

    # Analysis
    print(f"\n--- Analysis for {year} ({len(df)} games) ---")
    print(f"Spread Edge Mean: {spread_edge.mean():.2f} (Std: {spread_edge.std():.2f})")
    print(f"Total Edge Mean:  {total_edge.mean():.2f}  (Std: {total_edge.std():.2f})")

    print("\n--- Spread Counts by Threshold ---")
    for t in [0.0, 2.5, 5.0, 7.0, 10.0]:
        count = (spread_edge >= t).sum()
        pct = count / len(df)
        print(f"Threshold >= {t:>4.1f}: {count:>3} bets ({pct:.1%})")

    print("\n--- Total Counts by Threshold ---")
    for t in [0.0, 0.5, 2.0, 5.0, 7.0]:
        count = (total_edge >= t).sum()
        pct = count / len(df)
        print(f"Threshold >= {t:>4.1f}: {count:>3} bets ({pct:.1%})")


if __name__ == "__main__":
    check_distribution()
