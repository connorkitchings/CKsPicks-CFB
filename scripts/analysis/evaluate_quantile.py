import logging
import sys
from pathlib import Path

import pandas as pd

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from src.config import ARTIFACTS_DIR  # noqa: E402

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def evaluate_quantile(year: int = 2024):
    pred_path = ARTIFACTS_DIR / "models" / str(year) / "predictions.csv"
    if not pred_path.exists():
        logging.error(f"Predictions not found at {pred_path}")
        return

    df = pd.read_csv(pred_path)

    required = [
        "spread_p10",
        "spread_p50",
        "spread_p90",
        "spread_line",
        "home_points",
        "away_points",
    ]
    if not all(col in df.columns for col in required):
        logging.error(f"Missing quantile columns. Found: {df.columns}")
        return

    # Calculate Actuals
    # Target = Home - Away
    df["actual_margin"] = df["home_points"] - df["away_points"]

    # Reconstruct Absolute Intervals
    # Residual = Target + Line => Target = Residual - Line
    df["pred_p10"] = df["spread_p10"] - df["spread_line"]
    df["pred_p50"] = df["spread_p50"] - df["spread_line"]
    df["pred_p90"] = df["spread_p90"] - df["spread_line"]

    # Market Implied Margin
    df["market_margin"] = -1 * df["spread_line"]

    # 1. Coverage Analysis
    # Is Actual within [p10, p90]?
    df["covered"] = (df["actual_margin"] >= df["pred_p10"]) & (
        df["actual_margin"] <= df["pred_p90"]
    )
    coverage = df["covered"].mean()

    print(f"--- Coverage Analysis {year} ---")
    print("Target Coverage: 80% (10th to 90th percentile)")
    print(f"Actual Coverage: {coverage:.2%}")

    # 2. Betting Strategy: High Confidence
    # If Market < p10: We are 90% confident result > Market -> Bet Home
    # If Market > p90: We are 90% confident result < Market -> Bet Away

    bets = []
    for _, row in df.iterrows():
        market = row["market_margin"]
        p10 = row["pred_p10"]
        p90 = row["pred_p90"]
        actual = row["actual_margin"]

        bet = None
        if market < p10:
            bet = "Home"
            # Bet Home: Win if Actual > Market
            win = actual > market
        elif market > p90:
            bet = "Away"
            # Bet Away: Win if Actual < Market
            win = actual < market

        if bet:
            bets.append(
                {
                    "week": row["week"],
                    "home": row["home_team"],
                    "away": row["away_team"],
                    "bet": bet,
                    "market": market,
                    "p10": p10,
                    "p90": p90,
                    "actual": actual,
                    "win": win,
                    "push": actual == market,
                }
            )

    if not bets:
        print("No bets placed with High Confidence strategy.")
        return

    bets_df = pd.DataFrame(bets)
    # Filter pushes
    bets_df = bets_df[~bets_df["push"]]

    wins = bets_df["win"].sum()
    total = len(bets_df)
    win_rate = wins / total if total > 0 else 0
    roi = (wins * 0.909 - (total - wins)) / total if total > 0 else 0

    print("\n--- High Confidence Betting (Outside 80% Interval) ---")
    print(f"Total Bets: {total}")
    print(f"Record: {wins}-{total - wins}")
    print(f"Win Rate: {win_rate:.2%}")
    print(f"ROI: {roi:.2%}")

    # Save results
    out_path = ARTIFACTS_DIR / "reports" / f"quantile_eval_{year}.md"
    with open(out_path, "w") as f:
        f.write(f"# Quantile Evaluation {year}\n\n")
        f.write(f"**Coverage**: {coverage:.2%}\n\n")
        f.write("## High Confidence Betting\n")
        f.write(f"- **Bets**: {total}\n")
        f.write(f"- **Win Rate**: {win_rate:.2%}\n")
        f.write(f"- **ROI**: {roi:.2%}\n")

    # --- 3. Calibrated Interval (Historical RMSE) ---
    # Assume RMSE ~ 16.5 (from Error Analysis)
    # 80% Interval = +/- 1.28 * RMSE = +/- 21.12
    rmse = 16.5
    width = 1.28 * rmse

    df["calib_p10"] = df["pred_p50"] - width
    df["calib_p90"] = df["pred_p50"] + width

    calib_coverage = (
        (df["actual_margin"] >= df["calib_p10"])
        & (df["actual_margin"] <= df["calib_p90"])
    ).mean()

    print(f"\n--- Calibrated Interval (Median +/- {width:.2f}) ---")
    print(f"Coverage: {calib_coverage:.2%}")

    # Betting with Calibrated Interval
    calib_bets = []
    for _, row in df.iterrows():
        market = row["market_margin"]
        p10 = row["calib_p10"]
        p90 = row["calib_p90"]
        actual = row["actual_margin"]

        bet = None
        if market < p10:
            bet = "Home"
            win = actual > market
        elif market > p90:
            bet = "Away"
            win = actual < market

        if bet:
            calib_bets.append({"win": win, "push": actual == market})

    if calib_bets:
        calib_df = pd.DataFrame(calib_bets)
        calib_df = calib_df[~calib_df["push"]]
        c_wins = calib_df["win"].sum()
        c_total = len(calib_df)
        c_wr = c_wins / c_total
        c_roi = (c_wins * 0.909 - (c_total - c_wins)) / c_total

        print(f"Total Bets: {c_total}")
        print(f"Record: {c_wins}-{c_total - c_wins}")
        print(f"Win Rate: {c_wr:.2%}")
        print(f"ROI: {c_roi:.2%}")

        with open(out_path, "a") as f:
            f.write(f"\n## Calibrated Interval (Fixed +/- {width:.2f})\n")
            f.write(f"**Coverage**: {calib_coverage:.2%}\n")
            f.write(f"- **Bets**: {c_total}\n")
            f.write(f"- **Win Rate**: {c_wr:.2%}\n")
            f.write(f"- **ROI**: {c_roi:.2%}\n")


if __name__ == "__main__":
    evaluate_quantile()
