#!/usr/bin/env python3
"""Window 2 Step 5A: separate 2026 sizing of full R1 against the baseline ledger. Read-only.

Uses the latest validated 2026 Silver byplay, games and game outcomes in the Preview
catalog (not the pinned served bundle) and reports the catalog versions it used. 2026 is
reported separately and is excluded from the 25% gate. Writes only under ``--output-dir``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd
import psycopg
from dotenv import load_dotenv

from cks_picks_cfb.data.lake import DatasetRef, read_dataset
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.preseason_features import canonical_team
from cks_picks_cfb.quality.loaders import _ref_row
from cks_picks_cfb.ratings import possession_measurements as pm
from cks_picks_cfb.ratings import score_envelope_r1 as r1


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    storage = get_storage(environment="preview")
    versions: dict[str, dict] = {}
    frames: dict[str, pd.DataFrame] = {}
    with (
        psycopg.connect(os.environ["PREVIEW_DATABASE_URL"]) as conn,
        conn.cursor() as cur,
    ):
        for name in ("byplay", "games", "game_outcomes"):
            row = _ref_row(cur, name, 2026, None)
            versions[name] = {"version_id": row[1], "content_sha": row[3]}
            frames[name] = read_dataset(storage, DatasetRef(*[str(x) for x in row]))
    byplay = frames["byplay"][frames["byplay"].season == 2026].copy()
    games = frames["games"][
        (frames["games"].season == 2026)
        & frames["games"].completed.fillna(False).astype(bool)
    ]
    outcomes = frames["game_outcomes"][frames["game_outcomes"].season == 2026]
    population = games[
        ["season", "game_id", "week", "home_team", "away_team", "kickoff_utc"]
    ].merge(outcomes[["game_id", "home_points", "away_points"]], on="game_id")
    population["home_team"] = population["home_team"].map(canonical_team)
    population["away_team"] = population["away_team"].map(canonical_team)
    population["outcome_valid"] = True
    population["forecast_eligible"] = True
    byplay["offense"] = byplay["offense"].map(canonical_team)
    byplay["defense"] = byplay["defense"].map(canonical_team)
    byplay = byplay[byplay["game_id"].isin(population["game_id"])]
    finals: dict[tuple[int, str], float] = {}
    for row in population.itertuples():
        finals[(int(row.game_id), row.home_team)] = float(row.home_points)
        finals[(int(row.game_id), row.away_team)] = float(row.away_points)

    _, base = pm.build_possession_ledger(
        byplay=byplay, population=population, outcomes=None, scope="season_2026"
    )
    cand_plays, unresolved = r1.apply_r1(byplay, finals)
    _, cand = pm.build_possession_ledger(
        byplay=cand_plays, population=population, outcomes=None, scope="season_2026"
    )
    groups = r1.changed_groups(
        base, cand, restoration_team_games=r1.restoration_jumps(byplay)
    )
    groups.to_csv(args.output_dir / "groups_2026.csv", index=False)
    summary = {
        "inputs": versions,
        "completed_games": int(population["game_id"].nunique()),
        "weeks": sorted(int(w) for w in population["week"].unique()),
        "baseline_scoring_events": len(base),
        "candidate_scoring_events": len(cand),
        "baseline_reasons": {
            str(k): int(v)
            for k, v in base["quality_reason"].fillna("none").value_counts().items()
        },
        "r1_unresolved_team_games": len(unresolved),
        "groups": r1.summarize_groups(groups),
        "changed_games": int(groups["game_id"].nunique()),
        "week_bundles_of_changed_games": int(
            groups[["game_id"]]
            .drop_duplicates()
            .merge(population[["game_id", "week"]], on="game_id")["week"]
            .nunique()
        ),
    }
    (args.output_dir / "summary_2026.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, default=str)
    )
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
