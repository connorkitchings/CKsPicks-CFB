"""Generate betting reports from raw predictions."""

import argparse
from pathlib import Path
from typing import Optional

import pandas as pd

from src.config import REPORTS_DIR
from src.models.betting import apply_betting_policy


def generate_report(
    predictions_path: str,
    year: int,
    week: int,
    bankroll: float = 10000.0,
    spread_threshold: float = 3.5,
    total_threshold: float = 3.5,
    output_dir: Optional[str] = None,
):
    """
    Generate betting report from predictions.

    Args:
        predictions_path: Path to predictions CSV.
        year: Season year.
        week: Week number.
        bankroll: Current bankroll.
        spread_threshold: Minimum edge for spread bets.
        total_threshold: Minimum edge for total bets.
        output_dir: Directory to save reports.
    """
    df = pd.read_csv(predictions_path)

    # Apply Betting Policy
    # Note: apply_betting_policy expects specific column names.
    # We might need to adapt the dataframe or update the policy function.
    # For now, let's assume standard columns or map them.

    # Mapping 'prediction' to 'predicted_spread' if needed
    if "predicted_spread" not in df.columns and "prediction" in df.columns:
        df["predicted_spread"] = df["prediction"]

    # Map spread_line to home_team_spread_line
    if "spread_line" in df.columns and "home_team_spread_line" not in df.columns:
        df["home_team_spread_line"] = df["spread_line"]

    # Ensure predicted_total exists if we want to bet totals (placeholder for now)
    if "predicted_total" not in df.columns:
        df["predicted_total"] = df["total_line"] if "total_line" in df.columns else 0.0

    # Ensure std devs exist
    if "predicted_spread_std_dev" not in df.columns:
        df["predicted_spread_std_dev"] = 14.0  # Default fallback
    if "predicted_total_std_dev" not in df.columns:
        df["predicted_total_std_dev"] = 14.0  # Default fallback

    bets_df = apply_betting_policy(
        df,
        bankroll=bankroll,
        spread_edge_threshold=spread_threshold,
        total_edge_threshold=total_threshold,
        # Add other thresholds as needed
    )

    # Save Results
    out_dir = Path(output_dir) if output_dir else REPORTS_DIR / str(year)
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / f"week_{week}_bets.csv"
    bets_df.to_csv(csv_path, index=False)
    print(f"Betting CSV saved to {csv_path}")

    # Generate HTML Report (Simplified for now)
    html_path = out_dir / f"week_{week}_report.html"
    _write_html_report(bets_df, html_path, year, week)
    print(f"HTML Report saved to {html_path}")


def _write_html_report(df: pd.DataFrame, path: Path, year: int, week: int):
    """Write a simple HTML report."""
    # Filter for actual bets
    active_bets = df[
        (df["spread_bet_reason"] == "Bet Placed")
        | (df["total_bet_reason"] == "Bet Placed")
    ].copy()

    html = f"""
    <html>
    <head>
        <title>CFB Model Bets - {year} Week {week}</title>
        <style>
            body {{ font-family: sans-serif; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
        </style>
    </head>
    <body>
        <h1>Recommended Bets - {year} Week {week}</h1>
        {active_bets.to_html(index=False)}
    </body>
    </html>
    """
    with open(path, "w") as f:
        f.write(html)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", type=str, required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--bankroll", type=float, default=10000.0)
    parser.add_argument("--spread-threshold", type=float, default=3.5)
    parser.add_argument("--total-threshold", type=float, default=3.5)
    parser.add_argument("--output-dir", type=str)
    args = parser.parse_args()

    generate_report(
        args.predictions,
        args.year,
        args.week,
        args.bankroll,
        args.spread_threshold,
        args.total_threshold,
        args.output_dir,
    )
