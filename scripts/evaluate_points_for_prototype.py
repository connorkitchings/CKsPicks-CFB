import sys
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.config import get_data_root  # noqa: E402
from src.utils.local_storage import LocalStorage  # noqa: E402


def main():
    # Find the latest predictions file
    pred_dir = Path("artifacts/predictions/points_for_prototype")
    pred_files = list(pred_dir.glob("*_predictions.csv"))
    if not pred_files:
        print("No prediction files found.")
        return

    latest_file = max(pred_files, key=lambda p: p.stat().st_mtime)
    print(f"Evaluating: {latest_file}")

    preds_df = pd.read_csv(latest_file)

    # Load betting lines for 2024
    storage = LocalStorage(
        data_root=get_data_root(), file_format="csv", data_type="raw"
    )
    lines_records = storage.read_index("betting_lines", {"year": 2024})
    lines_df = pd.DataFrame.from_records(lines_records)

    # Filter for consensus or fallback
    if "provider" in lines_df.columns:
        lines_df["provider_rank"] = np.where(
            lines_df["provider"].astype(str).str.lower() == "consensus", 0, 1
        )
    else:
        lines_df["provider_rank"] = 1

    lines_df = (
        lines_df.sort_values(["game_id", "provider_rank"])
        .groupby("game_id", as_index=False)
        .first()
    )

    # Merge
    merged = preds_df.merge(lines_df, left_on="id", right_on="game_id", how="inner")

    # Calculate Spread Hit Rate
    # Bet Home if Pred Spread > Line + Threshold
    # Bet Away if Pred Spread < Line - Threshold
    threshold = 5.0  # Same as current production

    merged["spread_line"] = merged["spread"]  # usually home_team_spread

    # Edge: (Pred Home - Pred Away) - (Line)
    # If Pred Spread is 10 (Home by 10) and Line is 3 (Home -3), Edge is 7 points towards Home.
    # Wait, spread convention: Negative is favorite.
    # If Line is -3 (Home favored by 3), and Pred Spread is 10 (Home by 10).
    # Edge = Pred Spread - (-Line)? No.
    # Let's stick to "Home Margin".
    # Line -3 means Home is expected to win by 3.
    # Pred Spread (Home - Away) = 10.
    # Edge = 10 - 3 = 7? No.
    # If Line is -3, it means Home Score - Away Score = 3.
    # So we compare Pred Margin vs Implied Margin (-1 * spread_line).

    merged["implied_margin"] = -1 * merged["spread_line"]
    merged["pred_margin"] = merged["pred_spread"]

    merged["edge"] = merged["pred_margin"] - merged["implied_margin"]

    # Bet Logic
    # If Edge > Threshold -> Bet Home
    # If Edge < -Threshold -> Bet Away

    bets = []
    for _, row in merged.iterrows():
        edge = row["edge"]
        actual_margin = row["actual_spread"]
        line_margin = row["implied_margin"]

        if abs(edge) < threshold:
            continue

        if edge > 0:
            # Bet Home
            # Win if Actual Margin > Line Margin
            win = actual_margin > line_margin
            push = actual_margin == line_margin
            bets.append({"type": "Home", "edge": edge, "win": win, "push": push})
        else:
            # Bet Away
            # Win if Actual Margin < Line Margin
            win = actual_margin < line_margin
            push = actual_margin == line_margin
            bets.append({"type": "Away", "edge": edge, "win": win, "push": push})

    bets_df = pd.DataFrame(bets)
    if bets_df.empty:
        print("No bets found with threshold", threshold)
        return

    # Filter pushes
    decisive_bets = bets_df[~bets_df["push"]]
    wins = decisive_bets["win"].sum()
    total = len(decisive_bets)
    hit_rate = wins / total if total > 0 else 0

    print(f"\n--- Results (Threshold {threshold}) ---")
    print(f"Total Bets: {len(bets_df)}")
    print(f"Decisive Bets: {total}")
    print(f"Wins: {wins}")
    print(f"Hit Rate: {hit_rate:.1%}")

    # Totals Analysis
    # Threshold 3.5
    total_threshold = 3.5
    merged["total_edge"] = merged["pred_total"] - merged["over_under"]

    total_bets = []
    for _, row in merged.iterrows():
        edge = row["total_edge"]
        actual_total = row["actual_total"]
        line_total = row["over_under"]

        if abs(edge) < total_threshold:
            continue

        if edge > 0:
            # Bet Over
            win = actual_total > line_total
            push = actual_total == line_total
            total_bets.append({"type": "Over", "edge": edge, "win": win, "push": push})
        else:
            # Bet Under
            win = actual_total < line_total
            push = actual_total == line_total
            total_bets.append({"type": "Under", "edge": edge, "win": win, "push": push})

    total_bets_df = pd.DataFrame(total_bets)
    if not total_bets_df.empty:
        decisive_totals = total_bets_df[~total_bets_df["push"]]
        t_wins = decisive_totals["win"].sum()
        t_total = len(decisive_totals)
        t_hit_rate = t_wins / t_total if t_total > 0 else 0

        print(f"\n--- Totals Results (Threshold {total_threshold}) ---")
        print(f"Total Bets: {len(total_bets_df)}")
        print(f"Decisive Bets: {t_total}")
        print(f"Wins: {t_wins}")
        print(f"Hit Rate: {t_hit_rate:.1%}")


if __name__ == "__main__":
    main()
