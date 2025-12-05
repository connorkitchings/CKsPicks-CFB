"""Script to evaluate betting performance using integrated historical lines."""

import logging
import sys
from pathlib import Path
from typing import List

import pandas as pd

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))
# noqa: E402
from src.config import ARTIFACTS_DIR, DATA_ROOT  # noqa: E402
from src.utils.local_storage import LocalStorage  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def load_betting_lines(years: List[int]) -> pd.DataFrame:
    """Load betting lines for the specified years from local storage."""
    storage = LocalStorage(data_root=DATA_ROOT, data_type="raw", file_format="csv")
    all_lines = []

    for year in years:
        logging.info(f"Loading betting lines for {year}...")
        # Read all partitions for the year
        # Since we partitioned by year and week, we can filter by year
        lines = storage.read_index("betting_lines", filters={"year": year})
        if lines:
            df = pd.DataFrame(lines)
            all_lines.append(df)
        else:
            logging.warning(f"No betting lines found for {year}.")

    if not all_lines:
        return pd.DataFrame()

    combined_lines = pd.concat(all_lines, ignore_index=True)

    # Deduplicate: Take the first available line per game (or prioritize specific providers if needed)
    # For now, we'll just take the first one per game_id as a simple consensus proxy
    # Ideally, we'd aggregate or select 'consensus' provider
    # Let's prioritize 'Bovada' or 'DraftKings' if available, else first

    # Sort to prioritize providers (arbitrary preference for major books)
    provider_priority = {
        "consensus": 0,
        "Bovada": 1,
        "DraftKings": 2,
        "FanDuel": 3,
        "BetMGM": 4,
        "Caesars": 5,
    }

    combined_lines["provider_rank"] = (
        combined_lines["provider"].map(provider_priority).fillna(99)
    )
    combined_lines = combined_lines.sort_values("provider_rank")

    # Drop duplicates, keeping the highest priority provider
    unique_lines = combined_lines.drop_duplicates(subset=["game_id"], keep="first")

    return unique_lines


def load_predictions(years: List[int]) -> pd.DataFrame:
    """Load predictions for the specified years."""
    all_preds = []
    for year in years:
        pred_path = (
            ARTIFACTS_DIR / "validation" / "walk_forward" / f"{year}_predictions.csv"
        )
        if pred_path.exists():
            logging.info(f"Loading predictions for {year} from {pred_path}...")
            df = pd.read_csv(pred_path)
            # Ensure id is int
            if "id" in df.columns:
                df["id"] = df["id"].astype(int)
            all_preds.append(df)
        else:
            logging.warning(f"Predictions file not found for {year}: {pred_path}")

    if not all_preds:
        return pd.DataFrame()

    return pd.concat(all_preds, ignore_index=True)


def evaluate_performance(merged_df: pd.DataFrame) -> str:
    """Calculate performance metrics and return a markdown report."""

    # Ensure we have necessary columns
    required_cols = [
        "spread_pred_points_for_ensemble",
        "spread",  # Closing spread from betting lines
        "spread_open",  # Opening spread
        "home_points_actual",
        "away_points_actual",
    ]

    for col in required_cols:
        if col not in merged_df.columns:
            return f"Error: Missing column {col} in merged data."

    # Calculate actual spread result (Home - Away)
    # Note: Betting lines usually express spread as "Home Team -7.5" meaning Home needs to win by > 7.5
    # So if spread is -7.5, and result is 10 (Home 20, Away 10), Home covers.
    # Result > -1 * spread  => Cover (e.g. 10 > 7.5)
    # Let's align signs.
    # CFBD spread convention: negative value favors home team (e.g. -7.0).
    # Actual margin: Home - Away.
    # Cover condition: Margin > -1 * Spread (e.g. 10 > 7.0)

    merged_df["actual_margin"] = (
        merged_df["home_points_actual"] - merged_df["away_points_actual"]
    )

    # Calculate Edge against Closing Line
    # Edge = Pred_Spread - Market_Spread
    # Wait, signs matter.
    # If Model says -10 (Home by 10) and Market says -7 (Home by 7).
    # Model thinks Home is stronger. Edge is 3 points.
    # Formula: (Market_Spread - Model_Spread) ? No.
    # Let's stick to "Home Advantage" terms.
    # Model Home Adv = -1 * spread_pred
    # Market Home Adv = -1 * spread
    # Edge = Model_Home_Adv - Market_Home_Adv
    # Example: Model -10 -> Adv +10. Market -7 -> Adv +7. Edge = +3.

    merged_df["model_home_adv"] = -1 * merged_df["spread_pred_points_for_ensemble"]
    merged_df["market_home_adv"] = -1 * merged_df["spread"]
    merged_df["market_open_home_adv"] = -1 * merged_df["spread_open"]

    merged_df["edge_closing"] = (
        merged_df["model_home_adv"] - merged_df["market_home_adv"]
    )
    merged_df["edge_opening"] = (
        merged_df["model_home_adv"] - merged_df["market_open_home_adv"]
    )

    # Bet Selection Logic (Standard Policy)
    # Bet Home if Edge > 3.5
    # Bet Away if Edge < -3.5 (Model thinks Home Adv is much lower than Market)

    threshold = 5.0

    def determine_bet(row, edge_col):
        edge = row[edge_col]
        if edge > threshold:
            return "HOME"
        elif edge < -threshold:
            return "AWAY"
        return "NO_BET"

    merged_df["bet_closing"] = merged_df.apply(
        lambda r: determine_bet(r, "edge_closing"), axis=1
    )
    merged_df["bet_opening"] = merged_df.apply(
        lambda r: determine_bet(r, "edge_opening"), axis=1
    )

    # Outcome Logic
    # Bet Home: Win if Margin > Market Home Adv
    # Bet Away: Win if Margin < Market Home Adv

    def determine_outcome(row, bet_col, line_col):
        bet = row[bet_col]
        margin = row["actual_margin"]
        line_adv = row[line_col]  # Market Home Adv

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
            # Betting Away means we think Home won't cover.
            # So we win if Margin < Line Adv
            if margin < line_adv:
                return "WIN"
            elif margin > line_adv:
                return "LOSS"
            else:
                return "PUSH"

    merged_df["outcome_closing"] = merged_df.apply(
        lambda r: determine_outcome(r, "bet_closing", "market_home_adv"), axis=1
    )
    merged_df["outcome_opening"] = merged_df.apply(
        lambda r: determine_outcome(r, "bet_opening", "market_open_home_adv"), axis=1
    )

    # Metrics Calculation
    report = "# Betting Performance Report (Integrated Lines)\n\n"

    for line_type, outcome_col in [
        ("Closing Line", "outcome_closing"),
        ("Opening Line", "outcome_opening"),
    ]:
        df_bets = merged_df[merged_df[outcome_col].notna()]
        n_bets = len(df_bets)
        wins = len(df_bets[df_bets[outcome_col] == "WIN"])
        losses = len(df_bets[df_bets[outcome_col] == "LOSS"])
        pushes = len(df_bets[df_bets[outcome_col] == "PUSH"])

        bet_win_rate = (wins / (wins + losses)) * 100 if (wins + losses) > 0 else 0.0
        roi = (
            ((wins - 1.1 * losses) / (wins + losses + pushes)) * 100
            if n_bets > 0
            else 0.0
        )  # Simple flat unit ROI approx

        report += f"## Performance vs {line_type}\n"
        report += f"- **Total Bets**: {n_bets}\n"
        report += f"- **Record**: {wins}-{losses}-{pushes}\n"
        report += f"- **Win Rate**: {bet_win_rate:.2f}%\n"
        report += f"- **Est. ROI (Flat)**: {roi:.2f}%\n\n"

        # Breakdown by Year
        report += "### By Year\n"
        year_stats = (
            df_bets.groupby("season")[
                "outcome_closing" if "closing" in outcome_col else "outcome_opening"
            ]
            .value_counts()
            .unstack(fill_value=0)
        )
        if "WIN" not in year_stats.columns:
            year_stats["WIN"] = 0
        if "LOSS" not in year_stats.columns:
            year_stats["LOSS"] = 0

        for year in year_stats.index:
            y_wins = year_stats.loc[year, "WIN"]
            y_losses = year_stats.loc[year, "LOSS"]
            y_rate = (
                (y_wins / (y_wins + y_losses)) * 100 if (y_wins + y_losses) > 0 else 0.0
            )
            report += f"- **{year}**: {y_wins}-{y_losses} ({y_rate:.1f}%)\n"
        report += "\n"

    return report


def main() -> None:
    """Main execution."""
    years = [2019, 2021, 2022, 2023, 2024, 2025]

    # 1. Load Data
    lines_df = load_betting_lines(years)
    preds_df = load_predictions(years)

    if lines_df.empty or preds_df.empty:
        logging.error("Failed to load necessary data. Exiting.")
        return

    # 2. Join
    # Ensure keys match
    # lines_df: game_id, year
    # preds_df: id, season

    # Rename for merge consistency
    lines_df = lines_df.rename(columns={"year": "season"})

    logging.info(f"Lines shape: {lines_df.shape}")
    logging.info(f"Preds shape: {preds_df.shape}")

    merged_df = pd.merge(
        preds_df,
        lines_df,
        left_on=["id", "season"],
        right_on=["game_id", "season"],
        how="inner",
    )

    logging.info(f"Merged shape: {merged_df.shape}")

    if merged_df.empty:
        logging.error("Merge resulted in empty DataFrame. Check IDs.")
        return

    # 3. Evaluate
    report_content = evaluate_performance(merged_df)

    # 4. Save Report
    report_path = (
        ARTIFACTS_DIR / "reports" / "betting_analysis" / "betting_performance_report.md"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with open(report_path, "w") as f:
        f.write(report_content)

    logging.info(f"Report saved to {report_path}")
    print(report_content)


if __name__ == "__main__":
    main()
