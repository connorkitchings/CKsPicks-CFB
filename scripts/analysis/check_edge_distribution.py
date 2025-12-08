import numpy as np
import pandas as pd

from src.features.v2_recency import load_v2_recency_data
from src.models.v1_baseline import V1BaselineModel


def calculate_metrics(
    edge_series, preds_series, line_series, actual_series, target_type
):
    """
    Calculates ROI and Hit Rate for a given set of bets.
    """
    if len(edge_series) == 0:
        return 0, 0.0, 0.0

    wins = 0
    losses = 0

    if target_type == "total":
        # Totals logic
        # Bet Over if Pred > Line
        # Bet Under if Pred < Line
        bet_over = preds_series > line_series
        bet_under = preds_series < line_series

        outcome_over = actual_series > line_series
        outcome_under = actual_series < line_series

        # Win: Bet Over & Outcome Over OR Bet Under & Outcome Under
        wins_vector = (bet_over & outcome_over) | (bet_under & outcome_under)
        # Loss: Bet Over & Outcome Under OR Bet Under & Outcome Over
        losses_vector = (bet_over & outcome_under) | (bet_under & outcome_over)

        wins = wins_vector.sum()
        losses = losses_vector.sum()

    elif target_type == "spread":
        # Spread logic
        # Pred is Home Margin (Home - Away)
        # Line is Home Spread (e.g., -7.0)
        # Bet Home if Pred > -Line (e.g., Pred > 7.0)
        # Bet Away if Pred < -Line

        vegas_margin = -1 * line_series
        bet_home = preds_series > vegas_margin
        bet_away = preds_series < vegas_margin

        home_cover = actual_series > vegas_margin
        away_cover = actual_series < vegas_margin

        wins_vector = (bet_home & home_cover) | (bet_away & away_cover)
        losses_vector = (bet_home & away_cover) | (bet_away & home_cover)

        wins = wins_vector.sum()
        losses = losses_vector.sum()

    n_bets = wins + losses  # Excludes pushes

    if n_bets == 0:
        return 0, 0.0, 0.0

    hit_rate = wins / n_bets
    profit = (wins * 0.9090909) - losses
    roi = profit / n_bets

    return n_bets, hit_rate, roi


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

    # Filter out games without lines
    df = df.dropna(
        subset=["spread_line", "total_line", "spread_target", "total_target"]
    )

    # Predict
    spread_preds = spread_model.predict(df)
    total_preds = total_model.predict(df)

    # Calculate Edges
    spread_lines = df["spread_line"]
    total_lines = df["total_line"]

    # Actuals
    spread_actuals = df["spread_target"]
    total_actuals = df["total_target"]

    spread_edge = np.abs(spread_preds - (-spread_lines))
    total_edge = np.abs(total_preds - total_lines)

    # Analysis
    print(f"\n--- Analysis for {year} ({len(df)} games) ---")
    print(f"Spread Edge Mean: {spread_edge.mean():.2f} (Std: {spread_edge.std():.2f})")
    print(f"Total Edge Mean:  {total_edge.mean():.2f}  (Std: {total_edge.std():.2f})")

    print("\n--- Spread ROI by Threshold ---")
    print(f"{'Thresh':<6} {'Bets':<5} {'%Vol':<6} {'Hit%':<6} {'ROI':<7}")
    for t in [0.0, 2.5, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]:
        mask = spread_edge >= t
        n_bets, hr, roi = calculate_metrics(
            spread_edge[mask],
            spread_preds[mask],
            spread_lines[mask],
            spread_actuals[mask],
            "spread",
        )
        pct_vol = n_bets / len(df)
        print(f"{t:<6.1f} {n_bets:<5} {pct_vol:<6.1%} {hr:<6.1%} {roi:+.2%}")

    print("\n--- Total ROI by Threshold ---")
    print(f"{'Thresh':<6} {'Bets':<5} {'%Vol':<6} {'Hit%':<6} {'ROI':<7}")
    # Finer grained steps for totals since we suspect 0.5 is too low
    for t in [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 7.0, 8.0]:
        mask = total_edge >= t
        n_bets, hr, roi = calculate_metrics(
            total_edge[mask],
            total_preds[mask],
            total_lines[mask],
            total_actuals[mask],
            "total",
        )
        pct_vol = n_bets / len(df)
        print(f"{t:<6.1f} {n_bets:<5} {pct_vol:<6.1%} {hr:<6.1%} {roi:+.2%}")


if __name__ == "__main__":
    check_distribution()
