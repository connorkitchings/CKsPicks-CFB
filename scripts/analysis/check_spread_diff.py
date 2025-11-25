"""Script to analyze the difference between dataset 'spread_actual' and real betting lines."""

import logging
import sys
from pathlib import Path

import pandas as pd

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from src.config import ARTIFACTS_DIR, DATA_ROOT  # noqa: E402
from src.utils.local_storage import LocalStorage  # noqa: E402

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")


def main():
    year = 2024

    # 1. Load Predictions (contains spread_actual from training data)
    pred_path = (
        ARTIFACTS_DIR / "validation" / "walk_forward" / f"{year}_predictions.csv"
    )
    if not pred_path.exists():
        logging.error(f"Predictions not found for {year}")
        return

    preds_df = pd.read_csv(pred_path)

    # 2. Load Real Betting Lines
    storage = LocalStorage(data_root=DATA_ROOT, data_type="raw", file_format="csv")
    lines = storage.read_index("betting_lines", filters={"year": year})
    if not lines:
        logging.error(f"No lines found for {year}")
        return

    lines_df = pd.DataFrame(lines)

    # Prioritize providers like in the eval script
    provider_priority = {
        "Bovada": 1,
        "DraftKings": 2,
        "FanDuel": 3,
        "BetMGM": 4,
        "Caesars": 5,
    }
    lines_df["provider_rank"] = lines_df["provider"].map(provider_priority).fillna(99)
    lines_df = lines_df.sort_values("provider_rank")
    unique_lines = lines_df.drop_duplicates(subset=["game_id"], keep="first")

    # 3. Merge
    # Ensure ID types match
    preds_df["id"] = preds_df["id"].astype(int)
    unique_lines["game_id"] = unique_lines["game_id"].astype(int)

    merged = pd.merge(
        preds_df,
        unique_lines,
        left_on="id",
        right_on="game_id",
        how="inner",
        suffixes=("_train", "_real"),
    )

    # 4. Analyze Difference
    # spread_actual in preds is typically: Home - Away (negative favors home? or positive?)
    # Let's check the convention.
    # In CFBD, spread is usually "Home Team -7".
    # In our dataset, we need to verify.

    # Let's look at a sample
    sample = merged[
        ["home_team", "away_team", "spread_actual", "spread", "provider"]
    ].head(5)
    print("--- Sample Data ---")
    print(sample)
    print("-" * 20)

    # Calculate difference
    # Assuming both use the same sign convention (negative = home favored)
    merged["diff"] = merged["spread_actual"] - merged["spread"]
    merged["abs_diff"] = merged["diff"].abs()

    mean_diff = merged["diff"].mean()
    mae = merged["abs_diff"].mean()
    std_diff = merged["diff"].std()

    # Count significant differences
    diff_gt_0_5 = (merged["abs_diff"] > 0.5).sum()
    diff_gt_1_0 = (merged["abs_diff"] > 1.0).sum()
    diff_gt_3_0 = (merged["abs_diff"] > 3.0).sum()
    total = len(merged)

    print(f"\n--- Analysis for {year} ({total} games) ---")
    print(f"Mean Difference (Train - Real): {mean_diff:.4f}")
    print(f"Mean Absolute Error: {mae:.4f}")
    print(f"Std Dev of Difference: {std_diff:.4f}")
    print(
        f"\nGames with Diff > 0.5 pts: {diff_gt_0_5} ({diff_gt_0_5 / total * 100:.1f}%)"
    )
    print(
        f"Games with Diff > 1.0 pts: {diff_gt_1_0} ({diff_gt_1_0 / total * 100:.1f}%)"
    )
    print(
        f"Games with Diff > 3.0 pts: {diff_gt_3_0} ({diff_gt_3_0 / total * 100:.1f}%)"
    )

    # Correlation
    corr = merged["spread_actual"].corr(merged["spread"])
    print(f"\nCorrelation: {corr:.4f}")


if __name__ == "__main__":
    main()
