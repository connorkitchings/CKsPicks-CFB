import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd
from omegaconf import OmegaConf

from cks_picks_cfb.features.v2_recency import load_v2_recency_data
from cks_picks_cfb.models.v1_baseline import V1BaselineModel

# Setup Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def calculate_betting_stats(
    df: pd.DataFrame,
    spread_col: str,
    total_col: str,
    spread_threshold: float,
    total_threshold: float,
) -> Dict[str, Any]:
    """Calculate betting stats for a given DataFrame."""
    if df.empty:
        return {
            "spread": {"wins": 0, "losses": 0, "bets": 0, "win_pct": 0.0, "roi": 0.0},
            "total": {"wins": 0, "losses": 0, "bets": 0, "win_pct": 0.0, "roi": 0.0},
        }

    # Betting Lines
    # Handle column naming variations if necessary, but v2_recency standardizes to spread_line/total_line
    spread_lines = df["spread_line"]
    total_lines = df["total_line"]

    # Actual Outcomes
    home_points = df["home_points"]
    away_points = df["away_points"]

    margin = home_points - away_points
    total_score = home_points + away_points

    # --- Spread Stats ---
    spread_preds = df[spread_col]
    spread_edge = np.abs(spread_preds - (-spread_lines))

    # Bet Side: Pred > -Line (e.g. Pred -7 vs Line -3 -> Bet Home)
    bet_home = spread_preds > -spread_lines

    # Outcomes
    # If Margin + Line > 0, Home Covered. (e.g. Margin 7, Line +3 -> 10 > 0)
    cover_margin = margin + spread_lines

    win_home = (bet_home) & (cover_margin > 0)
    loss_home = (bet_home) & (cover_margin < 0)
    win_away = (~bet_home) & (
        cover_margin < 0
    )  # Bet Away means we expect home didn't cover
    loss_away = (~bet_home) & (cover_margin > 0)

    # Filter by Threshold
    spread_mask = spread_edge >= spread_threshold

    s_wins = int((win_home[spread_mask] | win_away[spread_mask]).sum())
    s_losses = int((loss_home[spread_mask] | loss_away[spread_mask]).sum())
    s_bets = s_wins + s_losses
    s_win_pct = s_wins / s_bets if s_bets > 0 else 0.0
    s_profit = (s_wins * 0.9091) - s_losses
    s_roi = s_profit / s_bets if s_bets > 0 else 0.0

    # --- Total Stats ---
    total_preds = df[total_col]
    total_edge = np.abs(total_preds - total_lines)
    bet_over = total_preds > total_lines

    win_over = (bet_over) & (total_score > total_lines)
    loss_over = (bet_over) & (total_score < total_lines)
    win_under = (~bet_over) & (total_score < total_lines)
    loss_under = (~bet_over) & (total_score > total_lines)

    total_mask = total_edge >= total_threshold

    t_wins = int((win_over[total_mask] | win_under[total_mask]).sum())
    t_losses = int((loss_over[total_mask] | loss_under[total_mask]).sum())
    t_bets = t_wins + t_losses
    t_win_pct = t_wins / t_bets if t_bets > 0 else 0.0
    t_profit = (t_wins * 0.9091) - t_losses
    t_roi = t_profit / t_bets if t_bets > 0 else 0.0

    return {
        "spread": {
            "wins": s_wins,
            "losses": s_losses,
            "bets": s_bets,
            "win_pct": s_win_pct,
            "roi": s_roi,
        },
        "total": {
            "wins": t_wins,
            "losses": t_losses,
            "bets": t_bets,
            "win_pct": t_win_pct,
            "roi": t_roi,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Generate System Betting Stats")
    parser.add_argument(
        "--config",
        type=str,
        default="conf/weekly_bets/v2_champion.yaml",
        help="Path to weekly bets config",
    )
    # Allow overriding week, otherwise default to config
    parser.add_argument(
        "--week", type=int, default=None, help="Current week number (overrides config)"
    )
    args = parser.parse_args()

    # Load Config
    cfg = OmegaConf.load(args.config)

    current_year = cfg.year
    current_week = args.week if args.week is not None else cfg.week

    logger.info(f"Generating System Stats for {current_year} Week {current_week}")

    # Extract Parameters from Config
    spread_threshold = cfg.spread_edge_threshold
    total_threshold = cfg.total_edge_threshold
    alpha = cfg.features.alpha

    # Load Feature Config to get feature list
    # The config has `models.spread.features`, pointing to proper config file
    feat_cfg_path = cfg.models.spread.features
    feat_cfg = OmegaConf.load(feat_cfg_path)

    # Feature Extraction Logic
    if "features" in feat_cfg:
        features = list(feat_cfg.features.keys())
    elif "groups" in feat_cfg:
        # Assuming groups is a list of feature names
        features = list(feat_cfg.groups)
    else:
        # Fallback for simple dict/list
        features = list(feat_cfg.keys())

    logger.info(f"Loaded {len(features)} features: {features}")

    logger.info(
        f"Configuration: Spread > {spread_threshold}, Total > {total_threshold}, Alpha={alpha}"
    )

    # Define Training Years (from Config or standardized logic)
    # Config has training.train_years
    train_years_base = list(cfg.training.train_years)
    test_year_historical = cfg.training.test_year  # 2024
    deploy_year = cfg.training.deploy_year  # 2025

    output_data = {}

    # === 1. Historical Validation (Last Year, e.g. 2024) ===
    logger.info(f"Processing Historical Year: {test_year_historical}")

    # Train on base years
    train_dfs_hist = []
    for y in train_years_base:
        df = load_v2_recency_data(y, alpha=alpha)
        if df is not None:
            train_dfs_hist.append(df)
    train_df_hist = pd.concat(train_dfs_hist, ignore_index=True)

    model_spread_hist = V1BaselineModel(
        alpha=1.0, features=features, target="spread_target"
    )
    model_total_hist = V1BaselineModel(
        alpha=1.0, features=features, target="total_target"
    )
    model_spread_hist.fit(train_df_hist)
    model_total_hist.fit(train_df_hist)

    # Predict Historical Year
    df_hist = load_v2_recency_data(test_year_historical, alpha=alpha)
    if df_hist is not None and not df_hist.empty:
        df_hist["spread_pred"] = model_spread_hist.predict(df_hist)
        df_hist["total_pred"] = model_total_hist.predict(df_hist)

        # A. Full Season Stats
        stats_hist_full = calculate_betting_stats(
            df_hist, "spread_pred", "total_pred", spread_threshold, total_threshold
        )
        output_data[f"{test_year_historical}_full"] = stats_hist_full

        # B. Specific Week Stats
        df_hist_wk = df_hist[df_hist["week"] == current_week]
        stats_hist_wk = calculate_betting_stats(
            df_hist_wk, "spread_pred", "total_pred", spread_threshold, total_threshold
        )
        output_data[f"{test_year_historical}_week_{current_week}"] = stats_hist_wk

    # === 2. Current Year System YTD (e.g. 2025) ===
    logger.info(f"Processing Current Year YTD: {deploy_year}")

    # Train on base + historical year (Walk Forward)
    train_years_curr = train_years_base + [test_year_historical]
    train_dfs_curr = []
    for y in train_years_curr:
        # Optimization: could reuse loaded dfs, but keeping simple for safely
        df = load_v2_recency_data(y, alpha=alpha)
        if df is not None:
            train_dfs_curr.append(df)
    train_df_curr = pd.concat(train_dfs_curr, ignore_index=True)

    model_spread_curr = V1BaselineModel(
        alpha=1.0, features=features, target="spread_target"
    )
    model_total_curr = V1BaselineModel(
        alpha=1.0, features=features, target="total_target"
    )
    model_spread_curr.fit(train_df_curr)
    model_total_curr.fit(train_df_curr)

    # Predict Current Year
    df_curr = load_v2_recency_data(deploy_year, alpha=alpha)
    if df_curr is not None and not df_curr.empty:
        df_curr["spread_pred"] = model_spread_curr.predict(df_curr)
        df_curr["total_pred"] = model_total_curr.predict(df_curr)

        # C. YTD Stats
        stats_curr_ytd = calculate_betting_stats(
            df_curr, "spread_pred", "total_pred", spread_threshold, total_threshold
        )
        output_data[f"{deploy_year}_ytd"] = stats_curr_ytd

    # Save Results
    output_path = Path("data/production/system_stats.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)

    logger.info(f"System stats saved to {output_path}")


if __name__ == "__main__":
    main()
