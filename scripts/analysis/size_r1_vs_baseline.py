#!/usr/bin/env python3
"""Window 2 Step 5A: size full R1 against the baseline scoring ledger. Read-only.

Rebuilds the served historical baseline scoring ledger from the pinned Silver inputs the
repair manifest names, applies the non-serving R1 candidate to the same inputs, and counts
allocation groups under the frozen definitions
(docs/plans/2026-10-03/window2/5a-frozen-definitions.md). Writes only local files under
``--output-dir``; makes no CFBD request and no R2 or database write.

    PYTHONPATH=src:. uv run python scripts/analysis/size_r1_vs_baseline.py \\
        --repair-manifest-uri <uri> --output-dir <dir> [--expected-scoring-events 86937]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_possession_v1 import build_population
from cks_picks_cfb.data.lake import read_dataset
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ratings import possession_measurements as pm
from cks_picks_cfb.ratings import score_envelope_r1 as r1
from scripts.research.run_data_first_possession_measurements import (
    _concat_source_frames,
    _ref,
    _repair,
    _sources,
)


def _log(message: str, start: float) -> None:
    print(f"[{time.time() - start:7.1f}s] {message}", file=sys.stderr, flush=True)


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repair-manifest-uri", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-scoring-events", type=int, default=None)
    parser.add_argument(
        "--reuse-baseline",
        action="store_true",
        help="Reuse baseline_events.parquet from --output-dir if present",
    )
    args = parser.parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    start = time.time()

    storage = get_storage(environment="preview")
    repair, _raw_sha = _repair(storage, args.repair_manifest_uri, scope="historical")
    repair_population = read_dataset(storage, _ref(repair["output_refs"]["population"]))
    population = build_population(repair_population, scope="historical")
    refs = _sources(storage, repair, scope="historical")
    byplay = _concat_source_frames(
        [read_dataset(storage, refs[s]["byplay"]) for s in sorted(refs)]
    )
    outcomes = _concat_source_frames(
        [read_dataset(storage, refs[s]["game_outcomes"]) for s in sorted(refs)]
    )
    _log(
        f"inputs: {len(byplay)} plays, {len(population)} population rows, seasons {sorted(refs)}",
        start,
    )

    baseline_cache = args.output_dir / "baseline_events.parquet"
    if args.reuse_baseline and baseline_cache.exists():
        base_events = pd.read_parquet(baseline_cache)
        _log(f"baseline ledger reused from {baseline_cache.name}", start)
    else:
        _, base_events = pm.build_possession_ledger(
            byplay=byplay, population=population, outcomes=outcomes, scope="historical"
        )
        base_events.to_parquet(baseline_cache)
    _log(f"baseline ledger: {len(base_events)} scoring events", start)
    if (
        args.expected_scoring_events is not None
        and len(base_events) != args.expected_scoring_events
    ):
        print(
            f"baseline scoring events {len(base_events)} != expected {args.expected_scoring_events}",
            file=sys.stderr,
        )
        return 2

    canonical = pm._canonicalize_byplay_teams(byplay)
    # Same certified finals the ledger uses: population joined to the game outcomes.
    pop_scores = population
    if "home_points" not in population.columns:
        pop_scores = population.merge(
            outcomes[
                ["season", "game_id", "home_points", "away_points"]
            ].drop_duplicates(["season", "game_id"]),
            on=["season", "game_id"],
            how="left",
        )
    finals: dict[tuple[int, str], float] = {}
    for row in pop_scores.itertuples(index=False):
        if getattr(row, "outcome_valid", False):
            if pd.notna(row.home_points):
                finals[(int(row.game_id), str(row.home_team))] = float(row.home_points)
            if pd.notna(row.away_points):
                finals[(int(row.game_id), str(row.away_team))] = float(row.away_points)
    candidate_plays, unresolved = r1.apply_r1(canonical, finals)
    _log(
        f"R1 applied: {len(unresolved)} unresolved team-games, {len(finals)} finals",
        start,
    )
    _, cand_events = pm.build_possession_ledger(
        byplay=candidate_plays,
        population=population,
        outcomes=outcomes,
        scope="historical",
    )
    cand_events.to_parquet(args.output_dir / "candidate_events.parquet")
    _log(f"candidate ledger: {len(cand_events)} scoring events", start)

    restoration = r1.restoration_jumps(canonical)
    groups = r1.changed_groups(
        base_events, cand_events, restoration_team_games=restoration
    )
    groups.to_csv(args.output_dir / "groups.csv", index=False)

    games = population[["season", "game_id", "week"]].drop_duplicates("game_id")
    if "season_type" in population.columns:
        games = games.merge(
            population[["game_id", "season_type"]].drop_duplicates("game_id"),
            on="game_id",
        )
    changed_games = (
        groups[["season", "game_id"]]
        .drop_duplicates()
        .merge(games.drop(columns="season"), on="game_id", how="left")
    )
    changed_games.to_csv(args.output_dir / "changed_games.csv", index=False)

    scored = pd.concat(
        [base_events.assign(side="baseline"), cand_events.assign(side="candidate")]
    )
    summary = {
        "inputs": {
            "plays": len(byplay),
            "population_rows": len(population),
            "seasons": sorted(int(s) for s in refs),
        },
        "baseline_scoring_events": len(base_events),
        "candidate_scoring_events": len(cand_events),
        "r1_unresolved_team_games": len(unresolved),
        "team_games_with_finals": len(finals),
        "restoration_gt8_team_games": len(restoration),
        "all_seasons": r1.summarize_groups(groups),
        "gate_scope": r1.summarize_groups(groups[groups["season"] != 2026]),
        "changed_games": int(len(changed_games)),
        "changed_games_by_season": {
            int(k): int(v) for k, v in changed_games.groupby("season").size().items()
        },
        "changed_week_bundles_by_season_type": (
            int(
                changed_games[
                    ["season", "week"]
                    + (["season_type"] if "season_type" in changed_games else [])
                ]
                .drop_duplicates()
                .shape[0]
            )
        ),
        "all_week_bundles_in_scope": int(
            population[
                ["season", "week"]
                + (["season_type"] if "season_type" in population else [])
            ]
            .drop_duplicates()
            .shape[0]
        ),
        "games_in_scope": int(population["game_id"].nunique()),
        "groups_by_season_and_cause": {
            f"{int(s)}|{c}": int(n)
            for (s, c), n in groups.groupby(["season", "primary_cause"]).size().items()
        },
        "points_recovered_by_season": {
            int(s): float(v)
            for s, v in groups[groups["net_points"] > 0]
            .groupby("season")["net_points"]
            .sum()
            .items()
        },
        "points_reduced_by_season": {
            int(s): float(v)
            for s, v in groups[groups["net_points"] < 0]
            .groupby("season")["net_points"]
            .sum()
            .items()
        },
        "events_scored_rows": len(scored),
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, default=str)
    )
    _log("done", start)
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
