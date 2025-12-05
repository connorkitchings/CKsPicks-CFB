import os
import sys

import mlflow
import numpy as np
import pandas as pd
from omegaconf import OmegaConf

# Add project root to path
sys.path.append(os.getcwd())

from src.config import get_data_root
from src.features.selector import select_features
from src.models.features import load_point_in_time_data
from src.utils.mlflow_tracking import setup_mlflow


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

    # Win Rate (excluding pushes)
    decisions = wins + losses
    bet_win_rate = (wins / decisions) * 100 if decisions > 0 else 0.0

    # ROI (Assuming -110 odds: Win=+0.909, Loss=-1.0)
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


def optimize_thresholds():
    setup_mlflow()
    years = [2024, 2025]
    data_root = get_data_root()

    # Load Models
    print("Loading models...")
    spread_model_name = "spread_catboost_ppr_seed_5"
    total_model_name = "totals_xgboost_ppr_seed_5"

    spread_model = mlflow.pyfunc.load_model(f"models:/{spread_model_name}/Production")
    total_model = mlflow.pyfunc.load_model(f"models:/{total_model_name}/Production")

    # Load Configs
    spread_cfg = OmegaConf.load("conf/features/ppr_v1.yaml")
    total_cfg = OmegaConf.load("conf/features/standard_v1.yaml")
    spread_full_cfg = OmegaConf.create({"features": spread_cfg})
    total_full_cfg = OmegaConf.create({"features": total_cfg})

    all_bets = []

    for year in years:
        print(f"Processing {year}...")
        for week in range(1, 16):
            try:
                df = load_point_in_time_data(
                    year, week, data_root, include_betting_lines=True
                )
            except Exception:
                continue

            if df is None or df.empty:
                continue

            # Filter to completed games with lines
            if "spread_target" not in df.columns or "total_target" not in df.columns:
                continue

            # Ensure lines exist
            if "spread_line" not in df.columns or "total_line" not in df.columns:
                continue

            df = df.dropna(
                subset=["spread_target", "total_target", "spread_line", "total_line"]
            )
            if df.empty:
                continue

            # --- Spread Prediction ---
            x_spread = select_features(df, spread_full_cfg)
            spread_preds = spread_model.predict(x_spread)

            # --- Total Prediction ---
            x_total = select_features(df, total_full_cfg)
            total_preds = total_model.predict(x_total)

            # --- Calculate Edges and Results ---

            # Spread Logic
            # spread_line is usually negative for Home Fav (e.g. -7)
            # Home Cover: spread_target > -spread_line (e.g. 10 > 7)
            # Bet Home: spread_preds > -spread_line

            # Edge = abs(Pred - (-Line)) = abs(Pred + Line)
            spread_edges = np.abs(spread_preds + df["spread_line"])

            # Determine Bet Side
            bet_home = spread_preds > -df["spread_line"]

            # Determine Result
            home_cover = df["spread_target"] > -df["spread_line"]
            push = df["spread_target"] == -df["spread_line"]

            spread_results = []
            for i in range(len(df)):
                if push.iloc[i]:
                    res = "Push"
                elif bet_home.iloc[i] and home_cover.iloc[i]:
                    res = "Win"
                elif not bet_home.iloc[i] and not home_cover.iloc[i]:
                    res = "Win"
                else:
                    res = "Loss"
                spread_results.append(res)

            # Total Logic
            # Edge = abs(Pred - Line)
            total_edges = np.abs(total_preds - df["total_line"])

            # Determine Bet Side
            # Pred > Line => Over
            bet_over = total_preds > df["total_line"]

            # Determine Result
            over_hit = df["total_target"] > df["total_line"]
            total_push = df["total_target"] == df["total_line"]

            total_bet_results = []
            for i in range(len(df)):
                if total_push.iloc[i]:
                    res = "Push"
                elif bet_over.iloc[i] and over_hit.iloc[i]:
                    res = "Win"
                elif not bet_over.iloc[i] and not over_hit.iloc[i]:
                    res = "Win"
                else:
                    res = "Loss"
                total_bet_results.append(res)

            # Collect Data
            temp_df = pd.DataFrame(
                {
                    "edge_spread": spread_edges,
                    "Spread Bet Result": spread_results,
                    "edge_total": total_edges,
                    "Total Bet Result": total_bet_results,
                }
            )
            all_bets.append(temp_df)

    if not all_bets:
        print("No bets generated.")
        return

    full_df = pd.concat(all_bets, ignore_index=True)
    print(f"Total Bets Analyzed: {len(full_df)}")

    print("\n--- SPREAD OPTIMIZATION ---")
    spread_stats = []
    for th in [i / 2 for i in range(0, 21)]:  # 0.0 to 10.0
        s = calculate_stats(full_df, th, "edge_spread", "Spread Bet Result")
        if s:
            spread_stats.append(s)

    spread_res_df = pd.DataFrame(spread_stats)
    print(spread_res_df.to_string(index=False, float_format="%.2f"))

    print("\n--- TOTAL OPTIMIZATION ---")
    total_stats = []
    for th in range(0, 21):  # 0 to 20
        s = calculate_stats(full_df, th, "edge_total", "Total Bet Result")
        if s:
            total_stats.append(s)

    total_res_df = pd.DataFrame(total_stats)
    print(total_res_df.to_string(index=False, float_format="%.2f"))


if __name__ == "__main__":
    optimize_thresholds()
