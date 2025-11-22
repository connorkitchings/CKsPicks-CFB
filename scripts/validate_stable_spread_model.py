#!/usr/bin/env python3
"""Walk-forward validation for the stable spread model."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import hydra
import pandas as pd
from omegaconf import DictConfig

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from src.models.features import load_point_in_time_data
from src.models.train_model import _concat_years


@hydra.main(config_path="../conf", config_name="config", version_base=None)
def main(cfg: DictConfig) -> None:
    """Main entrypoint for the stable model validation."""
    load_dotenv()

    start_week = 6
    end_week = 15
    years_to_process = [2023]  # Start with one year to test

    print(f"--- Starting stable model validation for years: {years_to_process} ---")

    for year in years_to_process:
        for week in range(start_week, end_week + 1):
            print(f"\n--- Processing Year {year}, Week {week} ---")

            # 1. Load data
            all_training_games = []
            for train_year in range(2019, year + 1):  # Use a wider history
                limit = week if train_year == year else 16
                for train_week in range(1, limit):
                    weekly_data = load_point_in_time_data(
                        train_year, train_week, cfg.data.data_root
                    )
                    if weekly_data is not None:
                        all_training_games.append(weekly_data)

            if not all_training_games:
                print(f"    Skipping week {week}: No training data.")
                continue

            train_df = _concat_years(all_training_games)

            valid_df = load_point_in_time_data(year, week, cfg.data.data_root)
            if valid_df is None:
                print(f"    Skipping week {week}: No validation data.")
                continue

            # 2. Create temp slice
            combined_df = pd.concat([train_df, valid_df], ignore_index=True)
            with tempfile.NamedTemporaryFile(
                mode="w+", delete=False, suffix=".csv"
            ) as tmp:
                slice_path = tmp.name
                combined_df.to_csv(slice_path, index=False)

            # 3. Call training script
            script_path = Path(__file__).parent / "train_stable_spread_model.py"
            train_weeks_str = f"[{','.join(map(str, train_df['week'].unique()))}]"

            command = [
                "python",
                str(script_path),
                "--slice-path",
                slice_path,
                "--model-year",
                str(year),
                "--train-weeks",
                train_weeks_str,
                "--valid-weeks",
                f"[{week}]",
            ]

            print(f"    Executing: {' '.join(command)}")
            subprocess.run(command, check=True)

            Path(slice_path).unlink()

    print("\n--- Stable model validation complete. ---")


if __name__ == "__main__":
    main()
