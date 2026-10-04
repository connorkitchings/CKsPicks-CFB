#!/usr/bin/env python3
"""Window 2 Step 5A: size original-provider null PPA among the V5 eligible scrimmage plays (the contract's population P: the V5 filter minus kicking plays). Read-only.

The pinned Silver ``plays`` keep the provider's missing PPA; the pinned Silver ``byplay``
zero-fills it. Joining the two on ``(game_id, drive_number, play_number)`` shows how many
eligible plays have no real PPA, by season, EPA metric population and team-game. Writes only
local files under ``--output-dir``; no CFBD request, no R2 or database write.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from cks_picks_cfb.data.lake import read_dataset
from cks_picks_cfb.data.play_filters import scrimmage_play_mask
from cks_picks_cfb.data.storage import get_storage
from scripts.research.run_data_first_possession_measurements import _repair, _sources

KEY = ["game_id", "drive_number", "play_number"]


def exposure_for_season(plays: pd.DataFrame, byplay: pd.DataFrame) -> pd.DataFrame:
    """One row per (game, offense) with eligible-play counts and original-null PPA counts."""
    original = (
        plays[[*KEY, "ppa"]]
        .drop_duplicates(KEY)
        .rename(columns={"ppa": "ppa_original"})
    )
    eligible = byplay[scrimmage_play_mask(byplay)].merge(original, on=KEY, how="left")
    eligible["null_ppa"] = eligible["ppa_original"].isna()
    eligible["unmatched"] = ~eligible.set_index(KEY).index.isin(
        original.set_index(KEY).index
    )
    dropback = (
        eligible["dropback"].fillna(False).astype(bool)
        if "dropback" in eligible
        else False
    )
    rush = (
        eligible["rush_attempt"].fillna(False).astype(bool)
        if "rush_attempt" in eligible
        else False
    )
    down = pd.to_numeric(eligible["down"], errors="coerce")
    populations = {
        "eligible_epa": pd.Series(True, index=eligible.index),
        "epa_pass": dropback,
        "epa_rush": rush & ~dropback,
        "early_down_epa": down.isin([1, 2]),
    }
    rows = []
    for (season, game_id, team), group in eligible.groupby(
        ["season", "game_id", "offense"]
    ):
        record = {
            "season": int(season),
            "game_id": int(game_id),
            "team": team,
            "eligible_plays": len(group),
        }
        for name, mask in populations.items():
            part = group[mask.loc[group.index]]
            record[f"{name}_plays"] = len(part)
            record[f"{name}_null"] = int(part["null_ppa"].sum())
        record["unmatched_plays"] = int(group["unmatched"].sum())
        rows.append(record)
    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repair-manifest-uri", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    storage = get_storage(environment="preview")
    repair, _ = _repair(storage, args.repair_manifest_uri, scope="historical")
    refs = _sources(storage, repair, scope="historical")
    frames = []
    for season in sorted(refs):
        plays = read_dataset(storage, refs[season]["plays"])
        byplay = read_dataset(storage, refs[season]["byplay"])
        part = exposure_for_season(plays, byplay)
        frames.append(part)
        print(f"{season}: {len(part)} team-games", file=sys.stderr, flush=True)
    table = pd.concat(frames, ignore_index=True)
    table.to_csv(args.output_dir / "null_ppa_exposure.csv", index=False)
    summary = {}
    for name in ("eligible_epa", "epa_pass", "epa_rush", "early_down_epa"):
        plays_col, null_col = f"{name}_plays", f"{name}_null"
        by_season = table.groupby("season").agg(
            team_games=("game_id", "size"),
            plays=(plays_col, "sum"),
            null_plays=(null_col, "sum"),
            withheld_team_games=(null_col, lambda s: int((s > 0).sum())),
        )
        by_season["null_play_rate"] = by_season["null_plays"] / by_season["plays"]
        by_season["withheld_rate"] = (
            by_season["withheld_team_games"] / by_season["team_games"]
        )
        summary[name] = json.loads(by_season.round(4).to_json(orient="index"))
    summary["unmatched_eligible_plays"] = int(table["unmatched_plays"].sum())
    (args.output_dir / "null_ppa_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True)
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
