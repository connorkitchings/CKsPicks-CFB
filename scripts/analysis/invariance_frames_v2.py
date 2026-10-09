#!/usr/bin/env python3
"""Build the v1 and v2 frames for one season from pinned parents (read-only; local files only).

Contract 2026-10-09/01, Task 5. v1 is the current code run on the historical ``keep="first"``
by-play (so the only difference between the two sides is the play identity); v2 is the same
code on every distinct provider play. Both sides go through the same chain: Silver by-play,
drives, team-game, source reconciliation, possession ledger, admitted scoring ledger, Gold
converters and evidence, observations (measurements) and the team-game metrics. The pinned
decisions anchor v1; the re-keyed decisions (``admission_decisions_v2.csv``) drive v2.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

REKEYED_DECISIONS = Path(
    "docs/plans/2026-10-08/repair-track-evidence/admission-v2/admission_decisions_v2.csv"
)
COLLISION_GAMES = frozenset({401310699, 401756916, 401761632, 401762831})


def build_side(
    *,
    identity: str,
    plays: pd.DataFrame,
    options: dict[str, Any],
    games: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
    population: pd.DataFrame,
    outcomes: pd.DataFrame,
    finals: dict,
    decisions_for: Any,
    index: dict,
    games_gold: pd.DataFrame,
    storage_bundle: Any,
) -> dict[str, Any]:  # pragma: no cover - requires pinned R2 parents
    from cks_picks_cfb.data.reconciliation import (
        reconcile_completed_games,
        stream_points_by_team_game,
    )
    from cks_picks_cfb.features.pipeline import build_preaggregation_pipeline
    from cks_picks_cfb.metrics import evidence as ev
    from cks_picks_cfb.metrics import ledger as ml
    from cks_picks_cfb.metrics.builders import build_team_game_metrics
    from cks_picks_cfb.metrics.season_features import season_features
    from cks_picks_cfb.ratings import admission as adm
    from cks_picks_cfb.ratings import possession_measurements as pm
    from cks_picks_cfb.ratings import score_envelope_r1 as r1
    from cks_picks_cfb.rebuild.gold import coverage_frame
    from scripts.analysis.play_identity_impact import legacy_dedup

    v2 = identity == "byplay_v2"
    extra = {"play_identity": identity} if v2 else {}
    source = plays if v2 else legacy_dedup(plays)
    byplay, drives, team_game, _ = build_preaggregation_pipeline(
        source, **options, **extra
    )
    reconciliation = reconcile_completed_games(
        games,
        team_game.merge(
            stream_points_by_team_game(byplay), on=["game_id", "team"], how="left"
        ),
        frames.get("team_game_stats"),
        declared_incomplete_game_ids=(),
    )

    def ledgers(frame: pd.DataFrame):
        possessions, baseline = pm.build_possession_ledger(
            byplay=frame,
            population=population,
            outcomes=outcomes,
            scope="historical",
            **extra,
        )
        canonical = pm._canonicalize_byplay_teams(frame)
        candidate_plays, _ = r1.apply_r1(canonical, finals)
        _, candidate = pm.build_possession_ledger(
            byplay=candidate_plays,
            population=population,
            outcomes=outcomes,
            scope="historical",
            **extra,
        )
        members: dict[str, list[str]] = {}
        r1.changed_groups(
            baseline,
            candidate,
            restoration_team_games=r1.restoration_jumps(canonical),
            members_out=members,
        )
        return possessions, baseline, candidate, members, canonical

    possessions, baseline, candidate, members, canonical = ledgers(byplay)
    decisions = decisions_for(members)
    admitted = adm.build_admitted_events(baseline, candidate, decisions, members)
    # One label on both sides, so version columns never show up as differences.
    versions = {
        name: "invariance-proof"
        for name in ("byplay", "drives", "coverage", "decisions")
    }
    admitted_groups = decisions[decisions["decision"] == adm.ADMITTED]
    evidence_ids = {
        r.group_id: (ev.evidence_id(r.group_id, index[int(r.game_id)]["sha256"]),)
        for r in admitted_groups.itertuples(index=False)
    }
    groups_by_event = {
        (int(r.game_id), str(r.team), str(r.source_event_id)): r.allocation_group_id
        for r in admitted.dropna(subset=["allocation_group_id"]).itertuples()
    }
    to_possessions = ml.possessions_to_v2 if v2 else ml.possessions_to_v1
    to_events = ml.scoring_events_to_v2 if v2 else ml.scoring_events_to_v1
    drives_gold = drives
    if "season" not in drives_gold.columns:
        drives_gold = drives.merge(
            byplay[["game_id", "season", "week"]].drop_duplicates("game_id"),
            on="game_id",
            how="left",
            suffixes=("", "_play"),
        )
    possessions_gold = to_possessions(
        possessions, drives_gold, source_versions=versions
    )
    ledger_gold = to_events(
        admitted,
        canonical,
        finals=finals,
        source_versions=versions,
        rule_version="baseline_v1",
        groups=groups_by_event,
        admitted_evidence=evidence_ids,
        admitted_rule_version=adm.RULE_VERSION,
        populate_envelopes=True,
    )
    evidence = ev.build_evidence(decisions, ledger_gold, index)
    coverage = coverage_frame(games_gold, reconciliation)
    metrics = build_team_game_metrics(
        plays=byplay,
        possessions=possessions_gold,
        ledger=ledger_gold,
        games=games_gold[
            [
                c
                for c in games_gold.columns
                if c not in ("forecast_eligible", "measurement_usable")
            ]
        ],
        source_versions=versions,
        timing_class="historically_reconstructed",
        coverage=coverage,
    )
    features = season_features(metrics, games_gold)
    observations = pm.build_measurements(
        byplay=byplay,
        population=population,
        outcomes=outcomes,
        scope="historical",
        possessions=possessions,
        scoring_events=admitted,
        **extra,
    )
    return {
        "byplay": byplay,
        "drives": drives,
        "team_game": team_game,
        "source_reconciliation": reconciliation,
        "possessions": possessions_gold,
        "scoring_ledger": ledger_gold,
        "evidence": evidence,
        "team_game_metrics": metrics,
        "season_features": features,
        "observations": observations.observations,
        "decisions": decisions,
        "members": members,
        "admitted": admitted,
    }


def build_season(season: int) -> dict[str, Any]:  # pragma: no cover
    from dotenv import load_dotenv

    from cks_picks_cfb.data.data_first_possession_v1 import build_population
    from cks_picks_cfb.data.lake import DatasetRef, read_dataset
    from cks_picks_cfb.data.storage import get_storage
    from cks_picks_cfb.metrics import evidence as ev
    from cks_picks_cfb.ratings import admission as adm
    from cks_picks_cfb.ratings.admission_rekey import legacy_event_map, rekey_decisions
    from cks_picks_cfb.rebuild.gold import games_frame
    from cks_picks_cfb.rebuild.legacy import _finals, _repair
    from scripts.analysis.play_identity_impact import legacy_dedup
    from scripts.analysis.rekey_admission_v2 import (
        CFBD_MANIFEST,
        PHASE2C_PARENTS,
        PINNED_DECISIONS,
        REPAIR_MANIFEST,
    )

    load_dotenv(".env")
    if os.getenv("CFB_STORAGE_BACKEND") != "r2":
        raise SystemExit("The invariance proof requires explicit R2 storage")
    storage = get_storage(environment="preview")

    def ref(entry: dict) -> DatasetRef:
        keys = ("dataset", "version_id", "schema_version", "content_sha", "uri")
        return DatasetRef(**{k: entry[k] for k in keys})

    pins = json.loads(PHASE2C_PARENTS.read_text())["seasons"][str(season)]
    frames = {p["dataset"]: read_dataset(storage, ref(p)) for p in pins["parents"]}
    outcomes = read_dataset(storage, ref(pins["game_outcomes"]))
    repair, _ = _repair(storage, REPAIR_MANIFEST, scope="historical")
    population = build_population(
        read_dataset(storage, ref(repair["output_refs"]["population"])),
        scope="historical",
    )
    population = population[population["season"] == season].reset_index(drop=True)
    games = frames["fbs_involved_games"].rename(columns={"kickoff_utc": "start_date"})
    options = dict(
        games_df=games,
        teams_df=frames["teams"],
        venues_df=None,
        weather_df=None,
        corrections_df=frames["data_corrections"],
        nullable_ppa=True,
    )
    finals = _finals(population, outcomes)
    points = outcomes[["season", "game_id", "home_points", "away_points"]]
    games_gold = games_frame(
        population.merge(
            points, on=["season", "game_id"], how="left", validate="one_to_one"
        ),
        frames["fbs_involved_games"],
    )
    records = [
        json.loads(r) for r in CFBD_MANIFEST.read_text().splitlines() if r.strip()
    ]
    cache: dict[str, bytes] = {}

    def read_bundle(name: str) -> bytes:
        if name not in cache:
            cache[name] = storage.read_bytes(ev.BUNDLE_PREFIX + name)
        return cache[name]

    index = ev.bundle_index(records, read_bundle)
    pinned = pd.read_csv(PINNED_DECISIONS)
    pinned = pinned[pinned["season"] == season].reset_index(drop=True)
    rekeyed = pd.read_csv(REKEYED_DECISIONS)
    rekeyed = rekeyed[rekeyed["season"] == season].reset_index(drop=True)

    def decisions_v1(members: dict) -> pd.DataFrame:
        return pinned.drop(columns=["group_id_v1"], errors="ignore")

    def decisions_v2(members: dict) -> pd.DataFrame:
        return rekeyed

    common = dict(
        plays=frames["plays"],
        options=options,
        games=games,
        frames=frames,
        population=population,
        outcomes=outcomes,
        finals=finals,
        index=index,
        games_gold=games_gold,
        storage_bundle=None,
    )
    side1 = build_side(identity="byplay_v1", decisions_for=decisions_v1, **common)
    side2 = build_side(identity="byplay_v2", decisions_for=decisions_v2, **common)
    kept = legacy_dedup(frames["plays"])
    removed = frames["plays"].loc[~frames["plays"].index.isin(kept.index)]
    restored = (
        removed["play_id"]
        .astype("int64")
        .astype(str)
        .isin(set(side2["byplay"]["source_play_id"].astype(str)))
    )
    accounting = {
        "removed_by_historical_dedup": int(len(removed)),
        "restored_in_v2_byplay": int(restored.sum()),
        "removed_by_unchanged_play_type_filter": {
            str(k): int(v)
            for k, v in removed.loc[~restored.to_numpy(), "play_type"]
            .value_counts()
            .items()
        },
    }
    event_map = legacy_event_map(frames["plays"], season)
    mapped = rekey_decisions(pinned, event_map)
    return {
        "season": season,
        "v1": side1,
        "v2": side2,
        "dedup_accounting": accounting,
        "event_map": event_map,
        "group_map": dict(zip(mapped["group_id_v1"], mapped["group_id"], strict=True)),
        "plays": frames["plays"],
        "population": population,
        "adm": adm.ADMITTED,
    }


def build_2026(pin_file: Path) -> dict[str, Any]:  # pragma: no cover
    """The 2026 Silver tables and baseline measurements, v1 against v2, from a pinned parent set.

    2026 has no admission decisions (they cover 2015-2025), so the measurement side is the
    baseline possession ledger and its observations, the same inputs the 2026 states stage uses.
    """
    from dotenv import load_dotenv

    from cks_picks_cfb.data.data_first_possession_v1 import build_population
    from cks_picks_cfb.data.data_first_repair_v2 import reconcile_population
    from cks_picks_cfb.data.lake import DatasetRef, read_dataset
    from cks_picks_cfb.data.reconciliation import (
        reconcile_completed_games,
        stream_points_by_team_game,
    )
    from cks_picks_cfb.data.storage import get_storage
    from cks_picks_cfb.features.pipeline import build_preaggregation_pipeline
    from cks_picks_cfb.ratings import possession_measurements as pm
    from cks_picks_cfb.ratings.admission_rekey import legacy_event_map
    from scripts.analysis.play_identity_impact import legacy_dedup

    load_dotenv(".env")
    if os.getenv("CFB_STORAGE_BACKEND") != "r2":
        raise SystemExit("The invariance proof requires explicit R2 storage")
    storage = get_storage(environment="preview")

    def ref(entry: dict) -> DatasetRef:
        keys = ("dataset", "version_id", "schema_version", "content_sha", "uri")
        return DatasetRef(**{k: entry[k] for k in keys})

    pins = json.loads(pin_file.read_text())
    frames = {p["dataset"]: read_dataset(storage, ref(p)) for p in pins["parents"]}
    outcomes = read_dataset(storage, ref(pins["game_outcomes"]))
    games = frames["games"].rename(columns={"kickoff_utc": "start_date"})
    options = dict(
        games_df=games,
        teams_df=frames["teams"],
        venues_df=None,
        weather_df=None,
        corrections_df=None,
        nullable_ppa=True,
    )
    plays = frames["plays"]
    sides: dict[str, dict[str, Any]] = {}
    for identity in ("byplay_v1", "byplay_v2"):
        v2 = identity == "byplay_v2"
        extra = {"play_identity": identity} if v2 else {}
        byplay, drives, team_game, _ = build_preaggregation_pipeline(
            plays if v2 else legacy_dedup(plays), **options, **extra
        )
        reconciliation = reconcile_completed_games(
            games,
            team_game.merge(
                stream_points_by_team_game(byplay), on=["game_id", "team"], how="left"
            ),
            frames.get("team_game_stats"),
            declared_incomplete_game_ids=(),
        )
        sides[identity] = {
            "byplay": byplay,
            "drives": drives,
            "team_game": team_game,
            "source_reconciliation": reconciliation,
        }
    completed = frames["games"][frames["games"]["completed"].astype(bool)]
    raw, _ = reconcile_population(
        schedule=completed[
            [
                "season",
                "week",
                "game_id",
                "kickoff_utc",
                "home_team",
                "away_team",
                "completed",
            ]
        ],
        outcomes=outcomes[
            ["season", "game_id", "completed", "home_points", "away_points"]
        ],
        observed_games=completed[["season", "game_id"]],
        reconciliation=sides["byplay_v1"]["source_reconciliation"],
        omissions={},
        scope="season_2026",
    )
    population = build_population(
        raw,
        scope="season_2026",
        expected_rows=len(raw),
        expected_eligible=int(raw["forecast_eligible"].sum()),
    )
    for identity, side in sides.items():
        extra = {"play_identity": identity} if identity == "byplay_v2" else {}
        result = pm.build_measurements(
            byplay=side["byplay"],
            population=population,
            outcomes=outcomes,
            scope="season_2026",
            **extra,
        )
        side["observations"] = result.observations
        side["possessions"] = result.possessions
        side["scoring_events"] = result.scoring_events
    return {
        "season": 2026,
        "v1": sides["byplay_v1"],
        "v2": sides["byplay_v2"],
        "event_map": legacy_event_map(plays, 2026),
        "plays": plays,
        "population": population,
    }
