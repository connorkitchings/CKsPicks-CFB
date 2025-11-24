"""
Backfill 2025 predictions using the new Mixed Ensemble models (trained on 2019-2023).
Orchestrates existing CLI scripts via subprocess.
"""

import subprocess
import sys

# Configuration
YEAR = 2025
MODEL_YEAR = 2024
START_WEEK = 2
END_WEEK = 13
DATA_ROOT = "/Volumes/CK SSD/Coding Projects/cfb_model"


def run_command(cmd):
    """Run a shell command and print output."""
    print(f"Running: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e}")
        # We don't exit on error for scoring, as games might not be final
        if "score_weekly_picks" not in cmd[2]:
            sys.exit(1)


def main():
    print(f"Starting backfill for {YEAR} (Weeks {START_WEEK}-{END_WEEK})...")

    # 1. Cache Weekly Stats
    print(f"\n--- Caching Weekly Stats for {YEAR} ---")
    run_command(
        [
            "uv",
            "run",
            "python",
            "scripts/cache_weekly_stats.py",
            "--year",
            str(YEAR),
            "--stage",
            "both",
            "--data-root",
            DATA_ROOT,
            "--adjustment-iterations",
            "0,1,2,3,4",
        ]
    )

    # 2. Generate and Score for each week
    for week in range(START_WEEK, END_WEEK + 1):
        print(f"\n--- Processing Week {week} ---")

        # Generate Bets
        run_command(
            [
                "uv",
                "run",
                "python",
                "-m",
                "src.scripts.generate_weekly_bets_clean",
                "--year",
                str(YEAR),
                "--week",
                str(week),
                "--model-year",
                str(MODEL_YEAR),
                "--prediction-mode",
                "points_for",
                "--data-root",
                DATA_ROOT,
                "--model-dir",
                "artifacts/models",
                "--output-dir",
                "artifacts/reports",
                "--bankroll",
                "10000",
                "--spread-threshold",
                "8.0",
                "--total-threshold",
                "8.0",
                "--max-weekly-exposure-fraction",
                "0.15",
                "--max-single-bet-fraction",
                "0.05",
            ]
        )

        # Score Picks
        print(f"Scoring Week {week}...")
        run_command(
            [
                "uv",
                "run",
                "python",
                "scripts/score_weekly_picks.py",
                "--year",
                str(YEAR),
                "--week",
                str(week),
                "--data-root",
                DATA_ROOT,
                "--report-dir",
                "artifacts/reports",
            ]
        )

    print("\n--------------------------------------------------")
    print("Backfill complete!")


if __name__ == "__main__":
    main()
