"""Corrected-lineage inputs for the successor (intended-update) release builders.

The successor builders were written against the first repaired lineage and its pinned R2
parents. A corrected rebuild publishes the same kinds of frames under a hash-pinned 6A run,
so the builders can run on it unchanged once their inputs come from there. Reads go through
``PublishedRun``, which refuses any object that is not in the signed root manifest.
"""

from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import Any

import pandas as pd

from cks_picks_cfb.rebuild.errors import GateError
from cks_picks_cfb.rebuild.published import PublishedRun, open_pinned_run

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


# ---------------------------------------------------------------------------
# Inputs read through a corrected successor lock (release tooling, no local caches)
# ---------------------------------------------------------------------------


def lineage(lock: dict[str, Any]) -> dict[str, Any]:
    """The corrected-lineage block of a successor lock, or an error naming what is missing."""
    block = lock.get("corrected_lineage")
    if not block or block.get("kind") != "corrected_rebuild":
        raise GateError("the source lock is not a corrected successor lock")
    return block


def is_corrected(lock: dict[str, Any]) -> bool:
    return bool(lock.get("corrected_lineage"))


def rebuild_run(storage: Any, lock: dict[str, Any]) -> PublishedRun:
    block = lineage(lock)
    return open_pinned_run(
        storage, block["rebuild_run_id"], block["rebuild_root_raw_sha256"]
    )


def replay_run(storage: Any, lock: dict[str, Any]) -> PublishedRun:
    block = lineage(lock)
    if not block.get("replay_run_id"):
        raise GateError("the corrected lock names no replay run for application frames")
    return open_pinned_run(
        storage,
        block["replay_run_id"],
        block["replay_root_raw_sha256"],
        namespace="rebuild/6b/",
    )


def lock_schedule(storage: Any, lock: dict[str, Any]) -> pd.DataFrame:
    """The locked 2026 schedule (canonical team names) from the pinned Silver games."""
    from cks_picks_cfb.rebuild import states_2026

    parent = lock["research_source_import"]["replay_parents"]
    raw = storage.read_bytes(parent["schedule_uri"])
    if hashlib.sha256(raw).hexdigest() != parent["schedule_content_sha256"]:
        raise GateError("pinned schedule dataset changed")
    return states_2026.locked_schedule(pd.read_parquet(io.BytesIO(raw)), lock)


def rating_inputs(
    storage: Any, lock: dict[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(schedule, observations, priors, terminal) for the 2026 rating builder."""
    run = rebuild_run(storage, lock)
    return (
        lock_schedule(storage, lock),
        run.frame("states_2026/observations.parquet"),
        run.frame("states_2026/priors.parquet"),
        run.frame("ratings/terminal.parquet"),
    )


def forecast_inputs(
    storage: Any,
    lock: dict[str, Any],
    *,
    current_teams: pd.DataFrame | None = None,
    live_as_of: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(schedule, replay features, live features) for the forecast builder.

    Weeks before the lock's active week are replay weeks: the 6B application frames are
    their 2026 feature rows (the four rating means are replaced from the pregame states by
    the builder). A lock with a live week also needs the post-week team states and a real
    ``live_as_of``; its feature rows cover only games that have not kicked off, and the
    omitted game ids travel on ``features.attrs``.
    """
    active = int(lock["active_week"]["week"])
    frames = replay_run(storage, lock).frame("application_frames/frames.parquet")
    replay = frames[frames["week"].astype(int).lt(active)].reset_index(drop=True)
    schedule = lock_schedule(storage, lock)
    if not lineage(lock).get("live_week"):
        return schedule, replay, frames.iloc[0:0].copy()
    if current_teams is None or not live_as_of:
        raise GateError("a live week needs the current team states and a live as_of")
    from cks_picks_cfb.rebuild.live_week import live_week_features

    live = live_week_features(
        storage, lock, as_of=live_as_of, current_teams=current_teams
    )
    features = live.features.reset_index(drop=True)
    features.attrs["omitted_kicked_off_game_ids"] = live.omitted_kicked_off_game_ids
    features.attrs["as_of"] = live.as_of
    return schedule, replay, features


def corrected_parents(
    lock: dict[str, Any], lock_raw: bytes
) -> dict[str, dict[str, str]]:
    """The parent pins a corrected bridge manifest records (instead of the old research pins)."""
    block = lineage(lock)
    return {
        "corrected_rebuild": {
            "uri": f"rebuild/6a/{block['rebuild_run_id']}/root-manifest.json",
            "raw_sha256": block["rebuild_root_raw_sha256"],
        },
        "task4_receipt": {
            "uri": f"rebuild/6a/{block['task4_run_id']}/receipt/receipt.json",
            "raw_sha256": block["task4_receipt_raw_sha256"],
        },
        "source_lock": {
            "uri": "successor-source-lock",
            "raw_sha256": hashlib.sha256(lock_raw).hexdigest(),
        },
    }
