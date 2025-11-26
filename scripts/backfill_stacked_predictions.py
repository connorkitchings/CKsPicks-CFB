import subprocess
from pathlib import Path


def run_command(cmd):
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def main():
    year = 2025
    start_week = 4
    end_week = 14  # exclusive, so up to 13

    for week in range(start_week, end_week):
        print(f"\n--- Generating Stacked Bets for Week {week} ---")
        try:
            run_command(
                [
                    "uv",
                    "run",
                    "python",
                    "scripts/generate_stacked_bets.py",
                    "--year",
                    str(year),
                    "--week",
                    str(week),
                ]
            )
        except subprocess.CalledProcessError:
            print(f"Failed to generate bets for Week {week}. Skipping.")
            continue

        # Rename stacked bets to standard bets file for scoring
        predictions_dir = Path(f"artifacts/reports/{year}/predictions")
        stacked_file = predictions_dir / f"CFB_week{week}_stacked_bets.csv"
        target_file = predictions_dir / f"CFB_week{week}_bets.csv"
        bad_file = predictions_dir / f"CFB_week{week}_bets_with_ids.csv"

        # Remove empty/bad files that might confuse scorer
        if bad_file.exists():
            bad_file.unlink()

        if stacked_file.exists():
            # Rename (overwrite if exists)
            stacked_file.replace(target_file)
            print(f"Renamed {stacked_file.name} to {target_file.name}")
        else:
            print(f"Error: {stacked_file} not found.")
            # If target exists, maybe we can proceed?
            if not target_file.exists():
                continue

        print(f"--- Scoring Week {week} ---")
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
        except subprocess.CalledProcessError:
            print(f"Failed to score bets for Week {week}. Skipping.")


if __name__ == "__main__":
    main()
