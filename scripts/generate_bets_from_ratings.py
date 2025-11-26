import argparse
import logging
import os
import sys
from pathlib import Path

import pandas as pd

# Add project root to path
sys.path.append(os.getcwd())

from src.config import ARTIFACTS_DIR, DATA_ROOT, PREDICTIONS_SUBDIR, REPORTS_DIR

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Generate bets from ratings predictions."
    )
    parser.add_argument("--year", type=int, required=True, help="Season year")
    parser.add_argument("--week", type=int, required=True, help="Week number")
    parser.add_argument(
        "--spread-threshold",
        type=float,
        default=2.5,
        help="Minimum edge for spread bets",
    )
    parser.add_argument(
        "--total-threshold", type=float, default=3.0, help="Minimum edge for total bets"
    )
    args = parser.parse_args()

    # 1. Load Predictions
    pred_path = (
        ARTIFACTS_DIR
        / "predictions"
        / str(args.year)
        / f"week_{args.week}_ratings_preds.csv"
    )
    if not pred_path.exists():
        logger.error(f"Predictions not found at {pred_path}")
        return

    preds_df = pd.read_csv(pred_path)
    logger.info(f"Loaded {len(preds_df)} predictions from {pred_path}")

    # 2. Load Betting Lines
    # Try multiple paths for betting lines (raw vs processed)
    # The CLI ingest writes to raw/betting_lines/year=YYYY/week=WW/data.csv (or similar structure depending on LocalStorage)
    # Let's check the standard raw path first
    lines_dir = (
        Path(DATA_ROOT)
        / "raw"
        / "betting_lines"
        / f"year={args.year}"
        / f"week={args.week}"
    )
    lines_files = list(lines_dir.glob("*.csv")) if lines_dir.exists() else []

    if not lines_files:
        # Fallback: check if there's a consolidated file
        logger.warning(
            f"No betting lines found in {lines_dir}. Checking for consolidated file..."
        )
        # This part depends on how ingestion stores it. The CLI log said: "Wrote 201 records to betting_lines/year=2025/week=14"
        # So it should be there.
        logger.error(f"Could not find betting lines for {args.year} Week {args.week}")
        return

    # Load all line files for the week (usually just one)
    lines_dfs = []
    for f in lines_files:
        if f.name.startswith("._"):
            continue
        try:
            df = pd.read_csv(f)
        except UnicodeDecodeError:
            logger.warning(f"Unicode error reading {f}, trying latin-1")
            df = pd.read_csv(f, encoding="latin-1")
        lines_dfs.append(df)
    lines_df = pd.concat(lines_dfs, ignore_index=True)

    # Filter for a specific provider if needed (e.g. 'Bovada', 'Consensus')
    # For now, let's take the first available line per game, preferring 'Consensus' or 'Bovada'
    if "provider" in lines_df.columns:
        # Sort by provider preference
        provider_order = {"Consensus": 0, "Bovada": 1}
        lines_df["provider_rank"] = lines_df["provider"].map(provider_order).fillna(99)
        lines_df = lines_df.sort_values("provider_rank")

    # Deduplicate by game_id
    lines_df = lines_df.drop_duplicates(subset=["game_id"], keep="first")
    logger.info(f"Loaded {len(lines_df)} unique betting lines.")

    # 2b. Load Games Data for Date/Time
    games_path = Path(DATA_ROOT) / "raw" / "games" / f"year={args.year}" / "data.csv"
    games_df = pd.DataFrame()
    if games_path.exists():
        all_games = pd.read_csv(games_path)
        if "id" in all_games.columns:
            all_games["game_id"] = all_games["id"]
        # Filter for current week
        games_df = all_games[all_games["week"] == args.week][
            ["game_id", "start_date"]
        ].copy()
        games_df["game_id"] = games_df["game_id"].astype(str)
    else:
        logger.warning(f"Games data not found at {games_path}")

    # 3. Merge Predictions and Lines
    # Ensure game_id types match
    preds_df["game_id"] = preds_df["game_id"].astype(str)
    lines_df["game_id"] = lines_df["game_id"].astype(str)

    merged_df = pd.merge(
        preds_df, lines_df, on="game_id", how="inner", suffixes=("", "_line")
    )

    # Merge Date/Time if available
    if not games_df.empty:
        merged_df = pd.merge(merged_df, games_df, on="game_id", how="left")
        # Parse start_date to Date and Time
        # Format: 2025-11-29T17:00:00.000Z or similar
        dt = pd.to_datetime(merged_df["start_date"], errors="coerce")
        # Convert to Eastern Time (assuming input is UTC)
        dt = (
            dt.dt.tz_convert("US/Eastern")
            if dt.dt.tz is not None
            else dt.dt.tz_localize("UTC").dt.tz_convert("US/Eastern")
        )

        merged_df["Date"] = dt.dt.strftime("%m/%d/%Y")
        merged_df["Time"] = dt.dt.strftime("%I:%M %p")
    else:
        merged_df["Date"] = ""
        merged_df["Time"] = ""

    logger.info(f"Merged {len(merged_df)} games with lines.")

    # 4. Generate Bets
    bets = []

    for _, row in merged_df.iterrows():
        # Spread Logic
        # Model Spread is (Home - Away). Negative means Home is favored.
        # Book Spread is also (Home - Away). Negative means Home is favored.
        # Edge = Model Spread - Book Spread ??
        # Example: Model says Home -7. Book says Home -3.
        # We think Home wins by 7. Market thinks 3. We like Home.
        # Model (-7) < Book (-3).
        # So if Model < Book - Threshold -> Bet Home.
        # Example: Model says Home +3. Book says Home -3.
        # We think Home loses by 3 (or wins). Market thinks Home wins by 3.
        # We differ by 6 points. We like Away.
        # Model (+3) > Book (-3) + Threshold -> Bet Away.

        model_spread = row["pred_spread"]
        book_spread = row["spread"]

        if pd.notna(model_spread) and pd.notna(book_spread):
            # Bet Home (Model is more negative/favored than Book)
            if model_spread < (book_spread - args.spread_threshold):
                bets.append(
                    {
                        "game_id": row["game_id"],
                        "Date": row.get("Date", ""),
                        "Time": row.get("Time", ""),
                        "Game": f"{row['away_team']} @ {row['home_team']}",
                        "Home Team": row["home_team"],
                        "Away Team": row["away_team"],
                        "Spread Bet": "Home",
                        "Spread Line": book_spread,
                        "Model Spread": model_spread,
                        "Spread Edge": book_spread - model_spread,
                        "Spread Confidence": "High",  # Placeholder
                    }
                )
            # Bet Away (Model is more positive/underdog than Book)
            elif model_spread > (book_spread + args.spread_threshold):
                bets.append(
                    {
                        "game_id": row["game_id"],
                        "Date": row.get("Date", ""),
                        "Time": row.get("Time", ""),
                        "Game": f"{row['away_team']} @ {row['home_team']}",
                        "Home Team": row["home_team"],
                        "Away Team": row["away_team"],
                        "Spread Bet": "Away",
                        "Spread Line": book_spread,
                        "Model Spread": model_spread,
                        "Spread Edge": model_spread - book_spread,
                        "Spread Confidence": "High",
                    }
                )
            else:
                # No Bet
                bets.append(
                    {
                        "game_id": row["game_id"],
                        "Date": row.get("Date", ""),
                        "Time": row.get("Time", ""),
                        "Game": f"{row['away_team']} @ {row['home_team']}",
                        "Home Team": row["home_team"],
                        "Away Team": row["away_team"],
                        "Spread Bet": "No Bet",
                        "Spread Line": book_spread,
                        "Model Spread": model_spread,
                        "Spread Edge": 0,
                        "Spread Confidence": "None",
                    }
                )

        # Total Logic
        # Model Total vs Book Total
        model_total = row["pred_total"]
        book_total = row["over_under"]

        if pd.notna(model_total) and pd.notna(book_total):
            bets[-1]["Total Prediction"] = model_total
            bets[-1]["Spread Prediction"] = model_spread
            if model_total > (book_total + args.total_threshold):
                bets[-1]["Total Bet"] = "Over"
                bets[-1]["Total Line"] = book_total
                bets[-1]["Model Total"] = model_total
                bets[-1]["Total Edge"] = model_total - book_total
            elif model_total < (book_total - args.total_threshold):
                bets[-1]["Total Bet"] = "Under"
                bets[-1]["Total Line"] = book_total
                bets[-1]["Model Total"] = model_total
                bets[-1]["Total Edge"] = book_total - model_total
            else:
                bets[-1]["Total Bet"] = "No Bet"
                bets[-1]["Total Line"] = book_total
                bets[-1]["Model Total"] = model_total
                bets[-1]["Total Edge"] = 0

    # 5. Save Bets
    bets_df = pd.DataFrame(bets)

    # Ensure output directory exists
    report_dir = Path(REPORTS_DIR) / str(args.year) / PREDICTIONS_SUBDIR
    report_dir.mkdir(parents=True, exist_ok=True)

    out_path = report_dir / f"CFB_week{args.week}_bets.csv"
    bets_df.to_csv(out_path, index=False)

    # Also save with IDs for scoring script (it looks for _with_ids or just standard)
    # The standard file has game_id, so it should be fine.
    # But let's save _with_ids just in case
    out_path_ids = report_dir / f"CFB_week{args.week}_bets_with_ids.csv"
    bets_df.to_csv(out_path_ids, index=False)

    logger.info(f"Saved {len(bets_df)} bets to {out_path}")


if __name__ == "__main__":
    main()
