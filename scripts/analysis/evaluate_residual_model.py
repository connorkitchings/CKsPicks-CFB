import logging
import sys
from pathlib import Path

import pandas as pd

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from src.config import ARTIFACTS_DIR, DATA_ROOT  # noqa: E402
from src.utils.local_storage import LocalStorage  # noqa: E402

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def load_betting_lines(year: int) -> pd.DataFrame:
    storage = LocalStorage(data_root=DATA_ROOT, data_type="raw", file_format="csv")
    lines = storage.read_index("betting_lines", filters={"year": year})
    if not lines:
        return pd.DataFrame()

    df = pd.DataFrame(lines)

    provider_priority = {
        "consensus": 0,
        "Consensus": 0,
        "Bovada": 1,
        "DraftKings": 2,
        "FanDuel": 3,
        "BetMGM": 4,
        "Caesars": 5,
    }

    if "provider" in df.columns:
        df["provider_rank"] = df["provider"].map(provider_priority).fillna(99)
        df = df.sort_values(["game_id", "provider_rank"])
        df = df.drop_duplicates(subset=["game_id"], keep="first")

    return df


def evaluate_performance(merged_df: pd.DataFrame) -> str:
    # Calculate actual margin (Home - Away)
    merged_df["actual_margin"] = merged_df["home_points"] - merged_df["away_points"]

    # Model Home Adv = -1 * spread_predicted (since spread is usually negative for home favorite)
    # Wait, spread_predicted is in the same units as the spread line?
    # In train_model.py, we reconstructed absolute spread.
    # If spread_predicted is -7.5, it means Home by 7.5.
    # So Model Home Adv = -1 * spread_predicted.

    merged_df["model_home_adv"] = -1 * merged_df["spread_predicted"]
    merged_df["market_home_adv"] = -1 * merged_df["spread"]

    merged_df["edge"] = merged_df["model_home_adv"] - merged_df["market_home_adv"]

    for threshold in [0.0, 2.5, 5.0]:
        print(f"\n--- Threshold: {threshold} ---")

        def determine_bet(row):
            if row["edge"] > threshold:
                return "HOME"
            elif row["edge"] < -threshold:
                return "AWAY"
            return "NO_BET"

        merged_df["bet"] = merged_df.apply(determine_bet, axis=1)

        def determine_outcome(row):
            bet = row["bet"]
            margin = row["actual_margin"]
            line_adv = row["market_home_adv"]

            if bet == "NO_BET":
                return None

            if bet == "HOME":
                if margin > line_adv:
                    return "WIN"
                elif margin < line_adv:
                    return "LOSS"
                else:
                    return "PUSH"
            elif bet == "AWAY":
                if margin < line_adv:
                    return "WIN"
                elif margin > line_adv:
                    return "LOSS"
                else:
                    return "PUSH"

        merged_df["outcome"] = merged_df.apply(determine_outcome, axis=1)

        # Metrics
        df_bets = merged_df[merged_df["outcome"].notna()]
        n_bets = len(df_bets)
        wins = len(df_bets[df_bets["outcome"] == "WIN"])
        losses = len(df_bets[df_bets["outcome"] == "LOSS"])
        pushes = len(df_bets[df_bets["outcome"] == "PUSH"])

        win_rate = (wins / (wins + losses)) * 100 if (wins + losses) > 0 else 0.0
        roi = (
            ((wins - 1.1 * losses) / (wins + losses + pushes)) * 100
            if n_bets > 0
            else 0.0
        )

        print(
            f"Total Bets: {n_bets}\nRecord: {wins}-{losses}-{pushes}\nWin Rate: {win_rate:.2f}%\nROI: {roi:.2f}%"
        )

    return "Evaluation Complete"


def main():
    year = 2024
    pred_path = ARTIFACTS_DIR / "models" / str(year) / "predictions.csv"

    if not pred_path.exists():
        print(f"Predictions not found at {pred_path}")
        return

    preds_df = pd.read_csv(pred_path)
    lines_df = load_betting_lines(year)

    if lines_df.empty:
        print("No betting lines found")
        return

    # Merge
    # preds_df has 'id', 'season'
    # lines_df has 'game_id', 'year'

    lines_df = lines_df.rename(columns={"year": "season", "game_id": "id"})

    merged_df = pd.merge(preds_df, lines_df, on=["id", "season"], how="inner")

    if merged_df.empty:
        print("Merge resulted in empty DataFrame. Check IDs.")
        return

    report = evaluate_performance(merged_df)
    print(report)


if __name__ == "__main__":
    main()
