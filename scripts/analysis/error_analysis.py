import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from src.config import ARTIFACTS_DIR  # noqa: E402

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def analyze_errors(year: int = 2024):
    pred_path = ARTIFACTS_DIR / "models" / str(year) / "predictions.csv"
    if not pred_path.exists():
        logging.error(f"Predictions not found at {pred_path}")
        return

    df = pd.read_csv(pred_path)

    # Ensure required columns exist
    required = ["spread_predicted", "spread_line", "home_points", "away_points", "week"]
    if not all(col in df.columns for col in required):
        logging.error(f"Missing columns. Found: {df.columns}")
        return

    # Calculate Actual Margin (Home - Away)
    df["actual_margin"] = df["home_points"] - df["away_points"]

    # Calculate Error
    # Error = Predicted - Actual
    # If Model says Home by 10 (-10), and Actual is Home by 7 (7).
    # Wait, spread_predicted is usually negative for Home Favorite.
    # Let's stick to "Home Advantage" units to avoid sign confusion.
    # Model Home Adv = -1 * spread_predicted
    # Market Home Adv = -1 * spread_line
    # Actual Home Adv = actual_margin

    df["model_home_adv"] = df["spread_predicted"]
    df["market_home_adv"] = -1 * df["spread_line"]

    # Error: How far off was the model?
    # Error = Model_Home_Adv - Actual_Home_Adv
    df["error"] = df["model_home_adv"] - df["actual_margin"]
    df["abs_error"] = df["error"].abs()

    # Market Error
    df["market_error"] = df["market_home_adv"] - df["actual_margin"]
    df["market_abs_error"] = df["market_error"].abs()

    # Edge
    df["edge"] = df["model_home_adv"] - df["market_home_adv"]
    df["abs_edge"] = df["edge"].abs()

    report = f"# Error Analysis {year}\n\n"
    report += f"**Total Games**: {len(df)}\n"
    report += f"**Model MAE**: {df['abs_error'].mean():.2f}\n"
    report += f"**Market MAE**: {df['market_abs_error'].mean():.2f}\n"
    report += f"**Model RMSE**: {np.sqrt((df['error'] ** 2).mean()):.2f}\n\n"

    # --- Segment: Spread Magnitude ---
    # Favorites: Market Home Adv > 7 (Home Fav) or < -7 (Away Fav)
    # Close: -7 to 7
    def categorize_spread(row):
        line = row["market_home_adv"]
        if line > 14:
            return "Heavy Home Fav (>14)"
        elif line > 7:
            return "Home Fav (7-14)"
        elif line < -14:
            return "Heavy Away Fav (<-14)"
        elif line < -7:
            return "Away Fav (-7 to -14)"
        else:
            return "Close Game (+/- 7)"

    df["spread_category"] = df.apply(categorize_spread, axis=1)

    report += "## Error by Spread Magnitude\n"
    seg_stats = df.groupby("spread_category")[
        ["abs_error", "market_abs_error", "error"]
    ].agg(["mean", "count"])
    report += seg_stats.to_markdown() + "\n\n"

    # --- Segment: Week ---
    def categorize_week(w):
        if w <= 4:
            return "Early (1-4)"
        elif w <= 9:
            return "Mid (5-9)"
        else:
            return "Late (10+)"

    df["week_category"] = df["week"].apply(categorize_week)

    report += "## Error by Season Phase\n"
    week_stats = df.groupby("week_category")[["abs_error", "market_abs_error"]].mean()
    report += week_stats.to_markdown() + "\n\n"

    # --- Segment: Disagreement (Edge) ---
    # High Disagreement: Abs Edge > 5
    df["disagreement"] = pd.cut(
        df["abs_edge"],
        bins=[-1, 2.5, 5, 100],
        labels=["Low (<2.5)", "Med (2.5-5)", "High (>5)"],
    )

    report += "## Error by Model-Market Disagreement\n"
    edge_stats = df.groupby("disagreement")[
        ["abs_error", "market_abs_error", "edge"]
    ].agg(["mean", "count"])
    report += edge_stats.to_markdown() + "\n\n"

    # --- Top 10 Worst Predictions ---
    report += "## Top 10 Worst Predictions (Model Misses)\n"
    worst = df.sort_values("abs_error", ascending=False).head(10)
    cols = [
        "week",
        "home_team",
        "away_team",
        "model_home_adv",
        "market_home_adv",
        "actual_margin",
        "error",
        "abs_error",
    ]
    report += worst[cols].to_markdown(index=False) + "\n\n"

    # Save Report
    out_path = ARTIFACTS_DIR / "reports" / f"error_analysis_{year}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        f.write(report)

    logging.info(f"Report saved to {out_path}")
    print(report)


if __name__ == "__main__":
    analyze_errors()
