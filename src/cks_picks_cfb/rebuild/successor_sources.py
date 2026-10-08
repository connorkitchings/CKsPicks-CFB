"""Corrected-lineage inputs for the successor (intended-update) release builders.

The successor builders were written against the first repaired lineage and its pinned R2
parents. A corrected rebuild publishes the same kinds of frames under a hash-pinned 6A run,
so the builders can run on it unchanged once their inputs come from there. Reads go through
``PublishedRun``, which refuses any object that is not in the signed root manifest.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from cks_picks_cfb.rebuild.published import PublishedRun

#: Frames the historical bridge builder and verifier read (``--historical-cache`` layout).
HISTORICAL_FRAMES = (
    "population",
    "observations",
    "terminal",
    "outcomes",
    "v5_predictions",
    "v5_features",
    "snapshots",
    "priors",
    "rating_states",
)
OUTCOME_COLUMNS = ["season", "game_id", "completed", "home_points", "away_points"]


def historical_frames(run: PublishedRun) -> dict[str, pd.DataFrame]:
    """The nine historical frames of a published 6A run, keyed by cache file name.

    ``v5_predictions`` is empty: the bridge builder and verifier never read it (only the
    research evaluation does), and the corrected lineage has no served historical
    predictions to put there.
    """
    from cks_picks_cfb.data.data_first_possession_v1 import build_population

    raw = run.frame("eligibility/population_raw.parquet")
    outcomes = raw.rename(columns={"schedule_completed": "completed"})[OUTCOME_COLUMNS]
    return {
        "population": build_population(raw, scope="historical"),
        "observations": run.frame("ratings/observations.parquet"),
        "terminal": run.frame("ratings/terminal.parquet"),
        "outcomes": outcomes,
        "v5_predictions": pd.DataFrame(),
        "v5_features": run.frame("forecast/feature_frame.parquet"),
        "snapshots": run.frame("ratings/snapshots.parquet"),
        "priors": run.frame("ratings/priors.parquet"),
        "rating_states": run.frame("ratings/rating_states.parquet"),
    }


def write_historical_cache(run: PublishedRun, out_dir: Path) -> dict[str, int]:
    """Write ``historical_frames`` as the cache directory the builders accept locally."""
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = {}
    for name, frame in historical_frames(run).items():
        frame.to_parquet(out_dir / f"{name}.parquet")
        rows[name] = len(frame)
    return rows
