import argparse
import logging
import subprocess
from typing import List

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def run_command(cmd: List[str]):
    logger.info(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"Command failed: {result.stderr}")
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")
    return result.stdout


def process_week(year: int, week: int):
    logger.info(f"=== Processing {year} Week {week} ===")

    # 1. Predict
    run_command(
        [
            "uv",
            "run",
            "python",
            "scripts/predict_ratings.py",
            "--year",
            str(year),
            "--week",
            str(week),
            "--draws",
            "500",  # Faster for backfill
            "--tune",
            "500",
        ]
    )

    # 2. Generate Bets
    # Note: This requires betting lines to be present.
    # If they are missing, this step will fail or produce empty bets.
    try:
        run_command(
            [
                "uv",
                "run",
                "python",
                "scripts/generate_bets_from_ratings.py",
                "--year",
                str(year),
                "--week",
                str(week),
            ]
        )
    except RuntimeError:
        logger.warning(
            f"Bet generation failed for {year} Week {week} (likely missing lines). Skipping scoring."
        )
        return

    # 3. Score Bets
    # Only score if the week is in the past (completed)
    # For 2025 Week 14, we skip scoring.
    if year == 2025 and week == 14:
        logger.info("Skipping scoring for current week.")
        return

    try:
        run_command(
            [
                "uv",
                "run",
                "python",
                "scripts/score_weekly_picks.py",
                "--year",
                str(year),
                "--week",
                str(week),
            ]
        )
    except RuntimeError:
        logger.warning(
            f"Scoring failed for {year} Week {week}. Maybe games not played yet?"
        )


def main():
    parser = argparse.ArgumentParser(description="Backfill ratings and bets.")
    parser.add_argument(
        "--years",
        type=str,
        default="2024",
        help="Comma-separated years (e.g. 2024,2025)",
    )
    parser.add_argument(
        "--start-week", type=int, default=4, help="Start week (inclusive)"
    )
    parser.add_argument("--end-week", type=int, default=16, help="End week (exclusive)")
    args = parser.parse_args()

    years = [int(y) for y in args.years.split(",")]

    for year in years:
        for week in range(args.start_week, args.end_week):
            process_week(year, week)


if __name__ == "__main__":
    main()
