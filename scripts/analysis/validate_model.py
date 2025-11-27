import argparse
import logging
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

# Add source root to path
sys.path.append(str(Path(__file__).resolve().parents[2]))
# noqa: E402
from src.config import MODELS_DIR, get_data_root
from src.models.betting import apply_betting_policy
from src.scripts.generate_weekly_bets_clean import (
    load_hybrid_ensemble_models,
    load_points_for_models,
    load_points_for_stats,
    load_week_dataset,
    predict_with_legacy,
    predict_with_points_for,
)

load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
log = logging.getLogger(__name__)


def validate_season(
    year: int,
    model_year: str,
    data_root: str,
    model_dir: str,
    spread_threshold: float,
    total_threshold: float,
    mode: str = "points_for",
    bankroll: float = 10000,
) -> pd.DataFrame:
    """Run validation for an entire season."""
    all_bets = []

    # Load models once
    log.info(
        f"Loading models for model year {model_year} from {model_dir} (Mode: {mode})..."
    )

    home_model = None
    away_model = None
    stats = None
    direct_models = None

    try:
        if mode == "points_for":
            home_model, away_model = load_points_for_models(model_year, model_dir)
            stats = load_points_for_stats(model_year, model_dir)
        elif mode == "direct":
            # For direct mode, we assume model_year points to a dir with spread_*.joblib and total_*.joblib
            # We pass the parent dir as spread/total model dir, and model_year as the subdir
            # load_hybrid_ensemble_models expects (model_year, spread_dir, total_dir)
            # and looks in spread_dir/model_year.
            # So we pass model_dir as the root.
            direct_models = load_hybrid_ensemble_models(
                model_year, model_dir, model_dir
            )
        else:
            raise ValueError(f"Unknown mode: {mode}")

    except FileNotFoundError as e:
        log.error(f"Model not found: {e}")
        sys.exit(1)

    # Iterate through weeks
    # Week 1 is often skipped in adjustment caches due to lack of prior data, start at 2
    # Go up to week 16 (conference championships)
    start_week = 2
    end_week = 16

    log.info(f"Validating {year} season (Weeks {start_week}-{end_week})...")

    for week in range(start_week, end_week + 1):
        try:
            # Load data
            df = load_week_dataset(
                year,
                week,
                data_root,
                adjustment_iteration=4,  # Default for production
            )

            if df.empty:
                log.warning(f"Week {week}: No data found.")
                continue

            preds = pd.DataFrame()

            if mode == "points_for":
                # Use standard deviations from stats file or defaults
                spread_std = 18.0
                total_std = 17.0

                preds = predict_with_points_for(
                    df,
                    home_model,
                    away_model,
                    spread_std=spread_std,
                    total_std=total_std,
                    stats=stats,
                )
            elif mode == "direct":
                preds = predict_with_legacy(direct_models, df)

            if preds.empty:
                log.warning(f"Week {week}: No predictions generated.")
                continue

            # Apply Betting Policy
            # For direct models (ensembles), we might have std dev from the ensemble.
            # predict_with_legacy returns 'predicted_spread_std_dev' and 'predicted_total_std_dev'.
            # We can use those if available.

            spread_std_threshold = None
            total_std_threshold = None

            if mode == "direct":
                # Example thresholds for ensemble std dev (tight agreement)
                # These might need tuning. For now, let's be loose or None.
                # spread_std_threshold = 3.0
                pass

            bets = apply_betting_policy(
                preds,
                spread_edge_threshold=spread_threshold,
                total_edge_threshold=total_threshold,
                spread_std_dev_threshold=spread_std_threshold,
                total_std_dev_threshold=total_std_threshold,
                min_games_played=4,
                bankroll=bankroll,
            )

            # Filter to placed bets
            placed_bets = bets[
                (bets["spread_bet_reason"] == "Bet Placed")
                | (bets["total_bet_reason"] == "Bet Placed")
            ].copy()

            if not placed_bets.empty:
                placed_bets["week"] = week
                all_bets.append(placed_bets)
                log.info(f"Week {week}: {len(placed_bets)} bets placed.")
            else:
                log.info(f"Week {week}: No bets placed.")

        except Exception as e:
            log.error(f"Error processing Week {week}: {e}")
            continue

    if not all_bets:
        return pd.DataFrame()

    return pd.concat(all_bets, ignore_index=True)


def score_bets(bets_df: pd.DataFrame) -> pd.DataFrame:
    """Score the bets against actual results."""
    scored = bets_df.copy()

    # Calculate results
    # Spread: Home - Away. If Home is -7 and wins by 10, result is -10.
    # Bet is "Home" or "Away".
    # If Bet Home (-7), we need Home Score - Away Score > 7
    # Actually, let's use the standard logic:
    # Spread Result = Away Score - Home Score (Standard convention? No, let's check)
    # In this repo: Spread is Home Team Spread. e.g. -7.0.
    # Margin = Away - Home.
    # If Margin < Spread, Home Cover.
    # Wait, let's stick to the simple logic:
    # If Home Score - Away Score > -1 * Spread, Home Covers.

    # Let's use the columns available: home_points_actual, away_points_actual
    # Note: load_week_dataset doesn't guarantee actuals are present if running for future.
    # But for validation (past years), they should be in the raw games data if 'completed' is true.

    # Check if actuals exist
    if "home_points" not in scored.columns or "away_points" not in scored.columns:
        # Try to find them from the raw load if they were kept?
        # load_week_dataset keeps all columns from raw games.
        pass

    # Calculate outcomes
    scored["home_margin"] = scored["home_points"] - scored["away_points"]
    scored["total_points"] = scored["home_points"] + scored["away_points"]

    # Score Spread Bets
    # Bet is on 'bet_spread' column: 'Home' or 'Away'
    # Line is 'home_team_spread_line'
    # If Bet Home: Win if Home Margin > -1 * Line
    # If Bet Away: Win if Home Margin < -1 * Line

    def score_spread(row):
        if row["spread_bet_reason"] != "Bet Placed":
            return None

        line = row["home_team_spread_line"]
        margin = row["home_margin"]
        pick = row["bet_spread"]

        if pd.isna(margin) or pd.isna(line):
            return None

        # Push
        if margin == -1 * line:
            return "Push"

        if pick == "Home":
            return "Win" if margin > -1 * line else "Loss"
        elif pick == "Away":
            return "Win" if margin < -1 * line else "Loss"
        return None

    # Score Total Bets
    def score_total(row):
        if row["total_bet_reason"] != "Bet Placed":
            return None

        line = row["total_line"]
        points = row["total_points"]
        pick = row["bet_total"]

        if pd.isna(points) or pd.isna(line):
            return None

        if points == line:
            return "Push"

        if pick == "Over":
            return "Win" if points > line else "Loss"
        elif pick == "Under":
            return "Win" if points < line else "Loss"
        return None

    scored["spread_result"] = scored.apply(score_spread, axis=1)
    scored["total_result"] = scored.apply(score_total, axis=1)

    return scored


def calculate_metrics(df: pd.DataFrame) -> dict:
    """Calculate Win Rate, ROI, and Volume."""
    metrics = {}

    for bet_type in ["spread", "total"]:
        result_col = f"{bet_type}_result"
        if result_col not in df.columns:
            continue

        # Filter to graded bets
        graded = df[df[result_col].isin(["Win", "Loss", "Push"])]

        if graded.empty:
            metrics[bet_type] = {
                "bets": 0,
                "wins": 0,
                "losses": 0,
                "pushes": 0,
                "win_rate": 0.0,
                "roi": 0.0,
            }
            continue

        wins = len(graded[graded[result_col] == "Win"])
        losses = len(graded[graded[result_col] == "Loss"])
        pushes = len(graded[graded[result_col] == "Push"])
        total = wins + losses  # Exclude pushes from denominator for win rate?
        # Standard convention: Win Rate = Wins / (Wins + Losses)

        win_rate = (wins / total) * 100 if total > 0 else 0.0

        # ROI Calculation (assuming -110 odds -> 0.909 win, 1.0 loss)
        # Profit = (Wins * 0.909) - (Losses * 1.0)
        # ROI = Profit / (Wins + Losses)
        profit_units = (wins * 0.90909) - losses
        roi = (profit_units / total) * 100 if total > 0 else 0.0

        metrics[bet_type] = {
            "bets": len(graded),  # Include pushes in volume
            "wins": wins,
            "losses": losses,
            "pushes": pushes,
            "win_rate": win_rate,
            "roi": roi,
        }

    return metrics


def main():
    parser = argparse.ArgumentParser(
        description="Validate a saved model against a full season."
    )
    parser.add_argument(
        "--year", type=int, required=True, help="Validation year (e.g., 2024)"
    )
    parser.add_argument(
        "--model-year",
        type=str,
        required=True,
        help="Year/Name of the model artifact (e.g., 2024 or 2024_baseline)",
    )
    parser.add_argument("--data-root", type=str, default=None, help="Path to data root")
    parser.add_argument(
        "--model-dir", type=str, default=str(MODELS_DIR), help="Path to models dir"
    )
    parser.add_argument(
        "--spread-threshold", type=float, default=8.0, help="Spread edge threshold"
    )
    parser.add_argument(
        "--total-threshold", type=float, default=8.0, help="Total edge threshold"
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["points_for", "direct"],
        default="points_for",
        help="Prediction mode: 'points_for' or 'direct'",
    )

    args = parser.parse_args()

    data_root = args.data_root or str(get_data_root())

    log.info(
        f"Starting validation for Year {args.year} using Model Year {args.model_year} (Mode: {args.mode})"
    )

    bets_df = validate_season(
        args.year,
        args.model_year,
        data_root,
        args.model_dir,
        args.spread_threshold,
        args.total_threshold,
        mode=args.mode,
    )

    if bets_df.empty:
        log.warning("No bets generated for the entire season.")
        return

    log.info("Scoring bets...")
    scored_df = score_bets(bets_df)

    metrics = calculate_metrics(scored_df)

    print("\n" + "=" * 40)
    print(f"VALIDATION RESULTS: {args.year}")
    print(
        f"Model: {args.model_year} | Thresholds: {args.spread_threshold}/{args.total_threshold} | Mode: {args.mode}"
    )
    print("=" * 40)

    for bet_type, stats in metrics.items():
        print(f"\n{bet_type.upper()}:")
        print(f"  Bets:     {stats['bets']}")
        print(f"  Record:   {stats['wins']}-{stats['losses']}-{stats['pushes']}")
        print(f"  Win Rate: {stats['win_rate']:.2f}%")
        print(f"  ROI:      {stats['roi']:.2f}%")

    print("\n" + "=" * 40)

    # Save results
    output_path = Path(
        f"artifacts/validation/static/{args.year}_validation_{args.mode}.csv"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    scored_df.to_csv(output_path, index=False)
    log.info(f"Detailed results saved to {output_path}")


if __name__ == "__main__":
    main()
