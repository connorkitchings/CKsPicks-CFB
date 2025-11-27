"""
Calculate 2024 win rate for the optimized XGBoost model.

This script:
1. Loads the optimized XGBoost model
2. Generates predictions for all 2024 weeks
3. Calculates hit rates for spread and total predictions
"""

import sys
from pathlib import Path

import joblib
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.config import get_data_root
from src.models.features import load_point_in_time_data


def calculate_win_rate():
    """Calculate 2024 win rate for optimized XGBoost."""
    # Load the most recent XGBoost model from artifacts
    # Assuming it was saved in the last training run
    model_dir = Path("artifacts/models/2024")

    # Look for the most recent model
    model_files = list(model_dir.glob("*_xgboost.joblib"))
    if not model_files:
        print("ERROR: No XGBoost models found in artifacts/models/2024/")
        return

    # Use the most recent one (by modification time)
    latest_model = max(model_files, key=lambda p: p.stat().st_mtime)
    print(f"Loading model: {latest_model}")

    home_model = joblib.load(
        model_dir / "home_catboost.joblib"
    )  # Should be XGBoost from latest run
    away_model = joblib.load(model_dir / "away_catboost.joblib")

    print(f"Home model type: {type(home_model)}")
    print(f"Away model type: {type(away_model)}")

    data_root = get_data_root()

    all_predictions = []

    # Generate predictions for all 2024 weeks
    for week in range(1, 16):
        print(f"Processing Week {week}...")
        df = load_point_in_time_data(2024, week, data_root, include_betting_lines=True)

        if df is None or df.empty:
            print(f"  No data for week {week}")
            continue

        # Get features that the model expects
        if hasattr(home_model, "feature_names_in_"):
            expected_features = list(home_model.feature_names_in_)
        elif hasattr(home_model, "get_booster"):
            expected_features = home_model.get_booster().feature_names
        else:
            # Fallback to build_feature_list
            from src.models.features import build_feature_list

            expected_features = build_feature_list(df)

        # Only use features that exist in both the model and the data
        available_features = [f for f in expected_features if f in df.columns]

        # Filter to games with complete data
        required_cols = available_features + [
            "home_points",
            "away_points",
            "spread_line",
            "total_line",
        ]
        df_complete = df.dropna(subset=required_cols).copy()

        if df_complete.empty:
            print(f"  No complete data for week {week}")
            continue

        x_features = df_complete[available_features]

        # Predict scores
        home_pred = home_model.predict(x_features)
        away_pred = away_model.predict(x_features)

        # Calculate derived predictions
        df_complete["pred_home_score"] = home_pred
        df_complete["pred_away_score"] = away_pred
        df_complete["pred_spread"] = (
            away_pred - home_pred
        )  # Away - Home (negative favors home)
        df_complete["pred_total"] = home_pred + away_pred

        # Calculate actual values
        df_complete["actual_spread"] = (
            df_complete["away_points"] - df_complete["home_points"]
        )
        df_complete["actual_total"] = (
            df_complete["home_points"] + df_complete["away_points"]
        )

        # Calculate edges
        df_complete["spread_edge"] = (
            df_complete["pred_spread"] - df_complete["spread_line"]
        )
        df_complete["total_edge"] = (
            df_complete["pred_total"] - df_complete["total_line"]
        )

        all_predictions.append(df_complete)

    # Combine all weeks
    results = pd.concat(all_predictions, ignore_index=True)

    print(f"\nTotal games analyzed: {len(results)}")

    # Calculate win rates for spread (using 3.5 threshold)
    spread_threshold = 3.5
    spread_bets = results[abs(results["spread_edge"]) >= spread_threshold].copy()

    if len(spread_bets) > 0:
        # Determine bet side and outcome
        spread_bets["bet_side"] = spread_bets["spread_edge"].apply(
            lambda x: "home" if x < 0 else "away"
        )

        def spread_win(row):
            if row["bet_side"] == "home":
                # Bet on home to cover (actual spread needs to be MORE NEGATIVE than line)
                return row["actual_spread"] < row["spread_line"]
            else:
                # Bet on away to cover
                return row["actual_spread"] > row["spread_line"]

        spread_bets["win"] = spread_bets.apply(spread_win, axis=1)
        spread_bets["push"] = spread_bets["actual_spread"] == spread_bets["spread_line"]

        spread_wins = spread_bets["win"].sum()
        spread_pushes = spread_bets["push"].sum()
        spread_losses = len(spread_bets) - spread_wins - spread_pushes
        spread_hit_rate = (
            spread_wins / (spread_wins + spread_losses) * 100
            if (spread_wins + spread_losses) > 0
            else 0
        )

        print(f"\n=== SPREAD BETS (Edge >= {spread_threshold}) ===")
        print(f"Total Bets: {len(spread_bets)}")
        print(f"Wins: {spread_wins}")
        print(f"Losses: {spread_losses}")
        print(f"Pushes: {spread_pushes}")
        print(f"Hit Rate: {spread_hit_rate:.1f}%")
    else:
        print(f"\n=== SPREAD BETS (Edge >= {spread_threshold}) ===")
        print("No bets met threshold")

    # Calculate win rates for total (using 3.5 threshold)
    total_threshold = 3.5
    total_bets = results[abs(results["total_edge"]) >= total_threshold].copy()

    if len(total_bets) > 0:
        # Determine bet side and outcome
        total_bets["bet_side"] = total_bets["total_edge"].apply(
            lambda x: "under" if x < 0 else "over"
        )

        def total_win(row):
            if row["bet_side"] == "over":
                return row["actual_total"] > row["total_line"]
            else:
                return row["actual_total"] < row["total_line"]

        total_bets["win"] = total_bets.apply(total_win, axis=1)
        total_bets["push"] = total_bets["actual_total"] == total_bets["total_line"]

        total_wins = total_bets["win"].sum()
        total_pushes = total_bets["push"].sum()
        total_losses = len(total_bets) - total_wins - total_pushes
        total_hit_rate = (
            total_wins / (total_wins + total_losses) * 100
            if (total_wins + total_losses) > 0
            else 0
        )

        print(f"\n=== TOTAL BETS (Edge >= {total_threshold}) ===")
        print(f"Total Bets: {len(total_bets)}")
        print(f"Wins: {total_wins}")
        print(f"Losses: {total_losses}")
        print(f"Pushes: {total_pushes}")
        print(f"Hit Rate: {total_hit_rate:.1f}%")
    else:
        print(f"\n=== TOTAL BETS (Edge >= {total_threshold}) ===")
        print("No bets met threshold")


if __name__ == "__main__":
    calculate_win_rate()
