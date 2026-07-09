"""Operational artifact paths and storage sync helpers.

R2/S3 storage is the durable home for weekly prediction and scored CSVs.
Local files under data/production are working copies used by the Python
pipeline and legacy email/review scripts.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from cks_picks_cfb.data.storage import StorageBackend, get_storage


def local_prediction_path(year: int, week: int) -> Path:
    return Path("data/production/predictions") / str(year) / f"CFB_week{week}_bets.csv"


def local_scored_path(year: int, week: int) -> Path:
    return (
        Path("data/production/scored") / str(year) / f"CFB_week{week}_bets_scored.csv"
    )


def prediction_artifact_path(year: int, week: int) -> str:
    return f"artifacts/production/predictions/year={year}/CFB_week{week}_bets.csv"


def scored_artifact_path(year: int, week: int) -> str:
    return f"artifacts/production/scored/year={year}/CFB_week{week}_bets_scored.csv"


def scored_artifact_prefix(year: int) -> str:
    return f"artifacts/production/scored/year={year}/"


def read_csv_artifact(path: str, storage: StorageBackend | None = None) -> pd.DataFrame:
    store = storage or get_storage()
    return store.read_csv(path)


def write_csv_artifact(
    df: pd.DataFrame,
    path: str,
    storage: StorageBackend | None = None,
) -> None:
    store = storage or get_storage()
    store.write_csv(df, path, index=False)
