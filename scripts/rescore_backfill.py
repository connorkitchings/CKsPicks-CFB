import logging
import subprocess

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_command(cmd):
    logger.info(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def main():
    years = [2019, 2021, 2022, 2023, 2024]
    for year in years:
        for week in range(4, 16):
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
                logger.warning(f"Failed to score {year} Week {week}")


if __name__ == "__main__":
    main()
