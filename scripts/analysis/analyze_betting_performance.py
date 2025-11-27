import glob

import numpy as np
import pandas as pd


def analyze_betting_performance():
    # Paths
    predictions_path = "artifacts/validation/walk_forward/2024_predictions.csv"
    games_path = "/Volumes/CK SSD/Coding Projects/cfb_model/raw/games/year=2024"
    betting_path = (
        "/Volumes/CK SSD/Coding Projects/cfb_model/raw/betting_lines/year=2024"
    )

    print(f"Loading predictions from {predictions_path}...")
    preds = pd.read_csv(predictions_path)

    print(f"Loading games from {games_path}...")
    games_files = glob.glob(f"{games_path}/**/data.csv", recursive=True)
    games_list = [pd.read_csv(f) for f in games_files]
    games = pd.concat(games_list, ignore_index=True)

    # Rename id to game_id for consistency if needed, or keep id
    # games has 'id', betting has 'game_id'

    print(f"Loading betting lines from {betting_path}...")
    betting_files = glob.glob(f"{betting_path}/**/data.csv", recursive=True)
    betting_list = [pd.read_csv(f) for f in betting_files]
    betting = pd.concat(betting_list, ignore_index=True)

    # Process betting lines: take consensus or average per game
    # If 'provider' column exists, maybe filter?
    # For now, group by game_id and take mean of spread/over_under
    betting_agg = (
        betting.groupby("game_id")[["spread", "over_under"]].mean().reset_index()
    )

    # Merge Games and Betting
    # games.id = betting.game_id
    games_betting = games.merge(
        betting_agg, left_on="id", right_on="game_id", how="left"
    )

    # Merge with Predictions
    # preds.id = games.id
    merged = preds.merge(
        games_betting, on="id", how="inner", suffixes=("", "_actual_data")
    )

    print(f"Merged shape: {merged.shape}")

    # Calculate outcomes
    # Spread: Home - Away
    # Note: 'home_points' from games data might be float or int
    merged["score_diff"] = merged["home_points"] - merged["away_points"]
    merged["total_score"] = merged["home_points"] + merged["away_points"]

    # Evaluate Points-For Model
    thresholds = [0.0, 2.5, 5.0]

    print("\n--- Betting Performance (Points-For Model) ---")

    for th in thresholds:
        # Spread
        # spread_line from betting data is usually: Negative = Favorite.
        # If Home is -7, spread = -7.
        # If Home wins by 10 (diff +10), 10 + (-7) = +3 > 0 => Home Cover.
        # Model Pred (Home - Away) = spread_pred_points_for_catboost.
        # Predicted Cover Margin = Pred + Spread.

        # Ensure spread is not NaN
        valid_spreads = merged.dropna(
            subset=["spread", "spread_pred_points_for_catboost", "score_diff"]
        )

        valid_spreads["pred_cover_margin"] = (
            valid_spreads["spread_pred_points_for_catboost"] + valid_spreads["spread"]
        )

        bets = valid_spreads[np.abs(valid_spreads["pred_cover_margin"]) > th].copy()

        if len(bets) == 0:
            print(f"Spread Threshold {th}: No bets")
            continue

        # Determine Bet Side
        bets["bet_side"] = np.where(bets["pred_cover_margin"] > 0, "Home", "Away")

        # Determine Result
        bets["actual_cover_margin"] = bets["score_diff"] + bets["spread"]

        conditions = [
            (bets["bet_side"] == "Home") & (bets["actual_cover_margin"] > 0),
            (bets["bet_side"] == "Away") & (bets["actual_cover_margin"] < 0),
            (bets["actual_cover_margin"] == 0),
        ]
        choices = [1, 1, 0]  # Win, Win, Push

        bets["result"] = np.select(conditions, choices, default=-1)  # -1 = Loss

        decisive_bets = bets[bets["result"] != 0]
        wins = len(decisive_bets[decisive_bets["result"] == 1])
        losses = len(decisive_bets[decisive_bets["result"] == -1])
        total = wins + losses

        if total > 0:
            win_rate = wins / total
            # Units: Win = +0.91 (at -110), Loss = -1.0
            units = (wins * 0.909) - (losses * 1.0)
            print(
                f"Spread Threshold {th}: {wins}-{losses} ({win_rate:.1%}) | Units: {units:.2f} | Vol: {len(bets)}"
            )
        else:
            print(f"Spread Threshold {th}: No decisive bets")

    print("\n--- Totals Performance ---")
    for th in thresholds:
        valid_totals = merged.dropna(
            subset=["over_under", "total_pred_points_for_catboost", "total_score"]
        )

        valid_totals["total_edge"] = (
            valid_totals["total_pred_points_for_catboost"] - valid_totals["over_under"]
        )

        bets = valid_totals[np.abs(valid_totals["total_edge"]) > th].copy()

        if len(bets) == 0:
            continue

        bets["bet_side"] = np.where(bets["total_edge"] > 0, "Over", "Under")

        # Result
        bets["total_diff"] = bets["total_score"] - bets["over_under"]

        conditions = [
            (bets["bet_side"] == "Over") & (bets["total_diff"] > 0),
            (bets["bet_side"] == "Under") & (bets["total_diff"] < 0),
            (bets["total_diff"] == 0),
        ]
        choices = [1, 1, 0]
        bets["result"] = np.select(conditions, choices, default=-1)

        decisive_bets = bets[bets["result"] != 0]
        wins = len(decisive_bets[decisive_bets["result"] == 1])
        losses = len(decisive_bets[decisive_bets["result"] == -1])
        total = wins + losses

        if total > 0:
            win_rate = wins / total
            units = (wins * 0.909) - (losses * 1.0)
            print(
                f"Total Threshold {th}: {wins}-{losses} ({win_rate:.1%}) | Units: {units:.2f} | Vol: {len(bets)}"
            )


if __name__ == "__main__":
    analyze_betting_performance()
