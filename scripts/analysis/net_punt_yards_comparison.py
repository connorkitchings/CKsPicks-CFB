#!/usr/bin/env python3
"""Net punt yards, v1 against provider-keyed v2, on pinned parents (read-only, no writes).

Contract 2026-10-09/01, Task 4.7. v2 must equal v1 for every game without a play-sequence
collision; only the collision games may differ (known issue 16).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

SCHEMA = "net_punt_yards_comparison_v1"
COLLISION_GAMES = frozenset({401310699, 401756916, 401761632, 401762831})
VALUE = "off_avg_net_punt_yards"


def compare_net_punt(
    v1: pd.DataFrame, v2: pd.DataFrame, collision_games: frozenset[int]
) -> dict[str, Any]:
    """Per ``(game_id, team)`` comparison of two ``calculate_st_analytics_agg`` outputs."""
    a = (
        v1.set_index(["game_id", "team"])[VALUE]
        if not v1.empty
        else pd.Series(dtype=float)
    )
    b = (
        v2.set_index(["game_id", "team"])[VALUE]
        if not v2.empty
        else pd.Series(dtype=float)
    )
    keys = a.index.union(b.index)
    left, right = a.reindex(keys), b.reindex(keys)
    same = (left == right) | (left.isna() & right.isna())
    differing = [k for k in keys[~same.to_numpy()]]
    outside = [k for k in differing if int(k[0]) not in collision_games]
    return {
        "team_games_compared": int(len(keys)),
        "team_games_differing": len(differing),
        "differing_games": sorted({int(k[0]) for k in differing}),
        "differing_outside_collision_games": len(outside),
        "differing_detail": [
            {
                "game_id": int(g),
                "team": t,
                "v1": None if pd.isna(left[(g, t)]) else float(left[(g, t)]),
                "v2": None if pd.isna(right[(g, t)]) else float(right[(g, t)]),
            }
            for g, t in differing
        ],
    }


def main() -> None:  # pragma: no cover - requires pinned R2 parents
    from dotenv import load_dotenv

    from cks_picks_cfb.data.lake import DatasetRef, read_dataset
    from cks_picks_cfb.data.storage import get_storage
    from cks_picks_cfb.features.aggregations.team_game import calculate_st_analytics_agg
    from cks_picks_cfb.features.pipeline import build_preaggregation_pipeline
    from scripts.analysis.play_identity_impact import legacy_dedup

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historical-parents", type=Path, required=True)
    parser.add_argument("--seasons", nargs="+", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load_dotenv(".env")
    if os.getenv("CFB_STORAGE_BACKEND") != "r2":
        raise SystemExit("The comparison requires explicit R2 storage")
    blocks = json.loads(args.historical_parents.read_text())["seasons"]
    storage = get_storage(environment="preview")

    def ref(entry: dict) -> DatasetRef:
        return DatasetRef(
            **{
                k: entry[k]
                for k in (
                    "dataset",
                    "version_id",
                    "schema_version",
                    "content_sha",
                    "uri",
                )
            }
        )

    seasons: dict[str, Any] = {}
    for season in sorted(args.seasons):
        frames = {
            p["dataset"]: read_dataset(storage, ref(p))
            for p in blocks[str(season)]["parents"]
        }
        options = dict(
            games_df=frames["fbs_involved_games"].rename(
                columns={"kickoff_utc": "start_date"}
            ),
            teams_df=frames["teams"],
            venues_df=None,
            weather_df=None,
            corrections_df=frames["data_corrections"],
            nullable_ppa=True,
        )
        by1, dr1, *_ = build_preaggregation_pipeline(
            legacy_dedup(frames["plays"]), **options
        )
        by2, dr2, *_ = build_preaggregation_pipeline(
            frames["plays"], play_identity="byplay_v2", **options
        )
        sequence = ["game_id", "drive_number", "play_number"]
        collided = sorted(
            int(g)
            for g in by2.loc[by2.duplicated(sequence, keep=False), "game_id"].unique()
        )
        reuse = by2.groupby(["game_id", "drive_number"])["drive_id"].nunique()
        reused_games = sorted(
            int(g)
            for g in reuse[reuse > 1].index.get_level_values(0).unique()
            if int(g) not in collided
        )
        result = compare_net_punt(
            calculate_st_analytics_agg(by1, dr1),
            calculate_st_analytics_agg(by2, dr2),
            COLLISION_GAMES,
        )
        result["collision_games_in_season"] = collided
        result["games_with_reused_drive_numbers"] = len(reused_games)
        result["reused_drive_number_games_that_differ"] = len(
            set(reused_games) & set(result["differing_games"])
        )
        seasons[str(season)] = result
    report = {
        "schema_version": SCHEMA,
        "contract": "docs/plans/2026-10-09/01-byplay-v2-play-identity.md#task-4",
        "inputs": {
            "historical_parents_sha256": hashlib.sha256(
                args.historical_parents.read_bytes()
            ).hexdigest()
        },
        "seasons": seasons,
        "totals": {
            "team_games_compared": sum(
                s["team_games_compared"] for s in seasons.values()
            ),
            "team_games_differing": sum(
                s["team_games_differing"] for s in seasons.values()
            ),
            "differing_outside_collision_games": sum(
                s["differing_outside_collision_games"] for s in seasons.values()
            ),
            "games_with_reused_drive_numbers": sum(
                s["games_with_reused_drive_numbers"] for s in seasons.values()
            ),
            "reused_drive_number_games_that_differ": sum(
                s["reused_drive_number_games_that_differ"] for s in seasons.values()
            ),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report["totals"], indent=2))


if __name__ == "__main__":
    main()
