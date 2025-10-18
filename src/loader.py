"""
Utilities for loading and preparing analysis datasets.
"""

from __future__ import annotations

import os

import pandas as pd

from src.config import SCORED_SUBDIR


def load_scored_season_data(year: int, report_dir: str) -> pd.DataFrame | None:
    """
    Loads and combines all weekly scored bet files for a given season.

    Args:
        year: The season year to load.
        report_dir: The root directory where reports are stored.

    Returns:
        A single DataFrame containing all scored bets for the season, or None
        if no files are found.
    """
    preferred_dir = os.path.join(report_dir, str(year), SCORED_SUBDIR)
    legacy_dir = os.path.join(report_dir, str(year))
    if os.path.isdir(preferred_dir):
        season_dir = preferred_dir
    elif os.path.isdir(legacy_dir):
        season_dir = legacy_dir
    else:
        print(f"Warning: Report directory not found for year {year} at {preferred_dir}")
        return None

    scored_files = [
        os.path.join(season_dir, f)
        for f in os.listdir(season_dir)
        if f.startswith("CFB_week") and f.endswith("_scored.csv")
    ]

    if not scored_files:
        print(f"Warning: No scored report files found for year {year} in {season_dir}")
        return None

    df_list = [pd.read_csv(f) for f in scored_files]
    combined_df = pd.concat(df_list, ignore_index=True)

    # Basic data cleaning and type conversion
    if "edge_spread" in combined_df.columns:
        combined_df["edge_spread"] = pd.to_numeric(
            combined_df["edge_spread"], errors="coerce"
        )
    if "edge_total" in combined_df.columns:
        combined_df["edge_total"] = pd.to_numeric(
            combined_df["edge_total"], errors="coerce"
        )

    return combined_df
