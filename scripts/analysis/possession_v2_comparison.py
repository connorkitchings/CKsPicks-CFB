#!/usr/bin/env python3
"""Provider-keyed possession ledger against v1, on pinned parents (read-only, no writes).

Contract 2026-10-09/01, Task 4 stop gate. For each season it builds the v1 ledger (from the
historical ``keep="first"`` by-play, because v1 refuses a collision) and the v2 ledger (from
every distinct provider play), runs the independent verifier on v2, and reports:

* whether the producer and the verifier agree frame for frame;
* possession, event and observation differences between v1 and v2, by game;
* the one-sided events, with the games they belong to.

The population is the games whose *baseline* ledger already reconciles to the certified finals
plus the four collision games, so the builder's season-level reconciliation guard (which the
unadmitted baseline would otherwise trip on a fraction of real games) does not mask the
comparison. v1, v2 and the verifier all receive the identical population.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

SCHEMA = "possession_v2_comparison_v1"
COLLISION_GAMES = frozenset({401310699, 401756916, 401761632, 401762831})
EVENT_FIELDS = [
    "score_increment",
    "scoring_category",
    "unit_category",
    "quality_reason",
]


def compare_events(
    v1_events: pd.DataFrame, v2_events: pd.DataFrame, id_map: dict[str, str]
) -> dict[str, Any]:
    """Compare v1 and v2 scoring events by ``(provider event id, team)``.

    ``id_map`` maps a v1 ``season:game:drive:play`` id to the v2 id of the play it names; v1
    events at an unmappable (colliding) sequence are left out of the shared comparison and are
    reported by the caller through ``unmapped``. Missing values compare equal.
    """
    mapped = v1_events.assign(_id=v1_events["source_event_id"].map(id_map))
    unmapped = int(mapped["_id"].isna().sum())
    left = mapped.dropna(subset=["_id"]).set_index(["_id", "team"])[EVENT_FIELDS]
    right = v2_events.set_index(["source_event_id", "team"])[EVENT_FIELDS]
    shared = left.index.intersection(right.index)
    a, b = left.loc[shared].astype(object), right.loc[shared].astype(object)
    a, b = a.mask(a.isna(), "<NA>"), b.mask(b.isna(), "<NA>")
    differing = (a != b).any(axis=1)

    def game_of(index: tuple[str, str]) -> int:
        return int(index[0].split(":")[1])

    only_v1 = left.index.difference(right.index)
    only_v2 = right.index.difference(left.index)
    return {
        "unmapped_v1_events": unmapped,
        "shared_events": int(len(shared)),
        "shared_events_differing": int(differing.sum()),
        "shared_differing_games": sorted(
            {game_of(i) for i in differing[differing].index}
        ),
        "only_v1": sorted(f"{i[0]}|{i[1]}" for i in only_v1),
        "only_v2": sorted(f"{i[0]}|{i[1]}" for i in only_v2),
        "one_sided_games": sorted(
            {game_of(i) for i in only_v1} | {game_of(i) for i in only_v2}
        ),
        "one_sided_points": int(
            pd.to_numeric(left.loc[only_v1, "score_increment"], errors="coerce")
            .fillna(0)
            .sum()
            + pd.to_numeric(right.loc[only_v2, "score_increment"], errors="coerce")
            .fillna(0)
            .sum()
        ),
    }


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:  # pragma: no cover - requires pinned R2 parents
    from dotenv import load_dotenv

    from cks_picks_cfb.data.lake import DatasetRef, read_dataset
    from cks_picks_cfb.data.storage import get_storage
    from cks_picks_cfb.features.pipeline import build_preaggregation_pipeline
    from cks_picks_cfb.ratings import possession_measurements as pm
    from cks_picks_cfb.ratings.possession_verification import reconstruct_measurements
    from scripts.analysis.play_identity_impact import diff_frames, legacy_dedup

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
        games = frames["fbs_involved_games"]
        options = dict(
            games_df=games.rename(columns={"kickoff_utc": "start_date"}),
            teams_df=frames["teams"],
            venues_df=None,
            weather_df=None,
            corrections_df=frames["data_corrections"],
            nullable_ppa=True,
        )
        by2, *_ = build_preaggregation_pipeline(
            frames["plays"], play_identity="byplay_v2", **options
        )
        by1, *_ = build_preaggregation_pipeline(
            legacy_dedup(frames["plays"]), **options
        )
        with_plays = set(by2["game_id"].astype(int))
        population = games[
            ["season", "week", "game_id", "home_team", "away_team", "kickoff_utc"]
        ].assign(
            forecast_eligible=True,
            outcome_valid=games["home_points"].notna() & games["away_points"].notna(),
        )
        population = population[
            population["game_id"].isin(with_plays) & population["outcome_valid"]
        ].reset_index(drop=True)
        finals = {}
        for g in games.itertuples():
            finals[(int(g.game_id), str(g.home_team))] = g.home_points
            finals[(int(g.game_id), str(g.away_team))] = g.away_points

        def reconciled(byplay: pd.DataFrame, identity: str | None) -> set[int]:
            options2 = {"play_identity": identity} if identity else {}
            _, events = pm.build_possession_ledger(
                byplay=byplay, population=population, outcomes=None, **options2
            )
            totals = events.groupby(["game_id", "team"])["score_increment"].sum()
            ok: dict[int, list[bool]] = {}
            for (game, team), value in totals.items():
                ok.setdefault(int(game), []).append(
                    finals.get((int(game), team)) == value
                )
            return {g for g, flags in ok.items() if len(flags) == 2 and all(flags)}

        keep = (
            reconciled(by1, None)
            | reconciled(by2, "byplay_v2")
            | (COLLISION_GAMES & with_plays)
        )
        used = population[population["game_id"].isin(keep)].reset_index(drop=True)
        by1, by2 = by1[by1["game_id"].isin(keep)], by2[by2["game_id"].isin(keep)]
        outcomes = games[["season", "game_id", "home_points", "away_points"]].copy()
        built = pm.build_measurements(
            byplay=by2, population=used, outcomes=outcomes, play_identity="byplay_v2"
        )
        checked = reconstruct_measurements(
            byplay=by2, outcomes=outcomes, population=used, play_identity="byplay_v2"
        )
        agreement = {}
        for name in ("possessions", "scoring_events", "observations", "coverage"):
            try:
                pd.testing.assert_frame_equal(
                    getattr(built, name), getattr(checked, name), check_dtype=False
                )
                agreement[name] = True
            except AssertionError:
                agreement[name] = False
        v1 = pm.build_measurements(byplay=by1, population=used, outcomes=outcomes)
        observations = diff_frames(
            v1.observations,
            built.observations,
            ["game_id", "team", "measurement_id", "unit_role"],
        )
        unique = by2.drop_duplicates(
            ["season", "game_id", "drive_number", "play_number"], keep=False
        )
        id_map = {
            f"{r.season}:{r.game_id}:{r.drive_number}:{r.play_number}": (
                f"{r.season}:{r.game_id}:{r.source_play_id}"
            )
            for r in unique[
                ["season", "game_id", "drive_number", "play_number", "source_play_id"]
            ].itertuples()
        }
        flagged = built.scoring_events[
            built.scoring_events["quality_reason"] == "unresolved_play_order"
        ]
        seasons[str(season)] = {
            "population_games": int(len(population)),
            "population_games_used": int(len(used)),
            "producer_equals_verifier": agreement,
            "possessions": {
                "v1": int(len(v1.possessions)),
                "v2": int(len(built.possessions)),
            },
            "unresolved_play_order_events": int(len(flagged)),
            "observation_cells_changed": int(observations["changed_cell_count"]),
            "observation_cells_changed_by_game": dict(
                sorted(
                    Counter(
                        int(c["key"][0]) for c in observations["changed_cells"]
                    ).items()
                )
            ),
            "observation_rows_one_sided": [
                len(observations["only_historical"]),
                len(observations["only_retained"]),
            ],
            "events": compare_events(v1.scoring_events, built.scoring_events, id_map)
            | {"v1": int(len(v1.scoring_events)), "v2": int(len(built.scoring_events))},
        }
    report = {
        "schema_version": SCHEMA,
        "contract": "docs/plans/2026-10-09/01-byplay-v2-play-identity.md#task-4",
        "population": "games with plays whose baseline ledger reconciles, plus the collision games",
        "inputs": {"historical_parents_sha256": sha256_file(args.historical_parents)},
        "seasons": seasons,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {s: r["producer_equals_verifier"] for s, r in seasons.items()}, indent=2
        )
    )


if __name__ == "__main__":
    main()
