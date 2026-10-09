"""Stage 5: build the Gold datasets from the verified, zero-drift comparison outputs.

Datasets (all season-partitioned, written to a throwaway local lake and streamed out):
``football_possessions_v1``, ``football_scoring_ledger_v1`` (admitted ledger with R1
envelopes, retained baseline allocations keeping baseline provenance),
``scoring_attribution_evidence_v1``, ``team_game_metrics_v1`` and
``season_level_features_v1``. Nothing here is read from the legacy chain except through the
already-verified ``step5_comparison`` outputs.
"""

from __future__ import annotations

import hashlib
import io
import json
import tempfile
from collections.abc import Iterator, Mapping
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from cks_picks_cfb.rebuild import common, comparison, eligibility
from cks_picks_cfb.rebuild.errors import GateError
from cks_picks_cfb.rebuild.orchestrator import StageContext, StageOutput
from cks_picks_cfb.rebuild.silver import identity_of

SUMMARY = "rebuild/6a/{run_id}/gold/summary.json"
DATASETS = (
    "football_possessions",
    "football_scoring_ledger",
    "scoring_attribution_evidence",
    "team_game_metrics",
    "season_level_features",
)
SCHEMA_VERSIONS = {name: f"{name}_v1" for name in DATASETS}
TIMING = "historically_reconstructed"
GOLD_CONFIG = {
    "datasets": SCHEMA_VERSIONS,
    "coverage_rule": "exact_match_reconciliation_and_measurement_usable",
    "ledger": {"rule_version": "baseline_v1", "populate_envelopes": True},
    "populations": ["website", "v5"],
}


#: Provider-keyed (v2) play identity changes the possession ledger, the scoring ledger and the
#: attribution evidence; team-game metrics and season features carry no play identity.
SCHEMA_VERSIONS_V2 = {
    **SCHEMA_VERSIONS,
    "football_possessions": "football_possessions_v2",
    "football_scoring_ledger": "football_scoring_ledger_v2",
    "scoring_attribution_evidence": "scoring_attribution_evidence_v2",
}
GOLD_CONFIG_V2 = {
    **GOLD_CONFIG,
    "datasets": SCHEMA_VERSIONS_V2,
    "play_identity": "byplay_v2",
}


def settings_for(identity: str) -> tuple[dict[str, Any], dict[str, str]]:
    """The Gold config and schema versions for a plan's play identity; v1 stays all ``_v1``."""
    if identity == "byplay_v2":
        return GOLD_CONFIG_V2, SCHEMA_VERSIONS_V2
    if identity == "byplay_v1":
        if not all(version.endswith("_v1") for version in SCHEMA_VERSIONS.values()):
            raise GateError("the byplay_v1 gold datasets must all be _v1 schemas")
        return GOLD_CONFIG, SCHEMA_VERSIONS
    raise GateError(f"unknown play identity: {identity}")


def _as_stored(frame: pd.DataFrame) -> pd.DataFrame:
    """The frame exactly as a reader will see it after the lake's parquet round trip.

    The writer digests the frame it is given; a reader digests what it reads back, so the
    two must start from the same representation (nullable ints, None versus NaN).
    """
    from cks_picks_cfb.data.lake import parquet_bytes

    return pd.read_parquet(io.BytesIO(parquet_bytes(frame.to_dict("records"))))


def config_sha(config: Mapping[str, Any] = GOLD_CONFIG) -> str:
    return hashlib.sha256(
        json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def games_frame(population: pd.DataFrame, fbs_games: pd.DataFrame) -> pd.DataFrame:
    """Games with the builder's required columns plus the population flags."""
    keys = ["season", "game_id"]
    extra = fbs_games[
        [*keys, "season_type", "home_classification", "away_classification"]
    ].drop_duplicates(keys)
    games = population.merge(extra, on=keys, how="left", validate="one_to_one")
    if games["season_type"].isna().any():
        raise GateError(
            "population games missing from the pinned FBS-involved schedule"
        )
    games["home_fbs"] = (
        games["home_classification"].astype(str).str.casefold().eq("fbs")
    )
    games["away_fbs"] = (
        games["away_classification"].astype(str).str.casefold().eq("fbs")
    )
    games["season_type"] = games["season_type"].astype(str).str.casefold()
    return games[
        [
            "season",
            "week",
            "game_id",
            "season_type",
            "home_team",
            "away_team",
            "kickoff_utc",
            "home_points",
            "away_points",
            "home_fbs",
            "away_fbs",
            "forecast_eligible",
            "measurement_usable",
        ]
    ].reset_index(drop=True)


def coverage_frame(games: pd.DataFrame, reconciliation: pd.DataFrame) -> pd.DataFrame:
    """Explicit per-team coverage from verified parents, never from absent rows.

    A game is complete only if its source reconciliation is an exact match and its
    measurements are usable; anything else is explicitly incomplete.
    """
    classes = reconciliation.drop_duplicates("game_id").set_index("game_id")[
        "classification"
    ]
    rows = []
    for game in games.itertuples(index=False):
        complete = bool(
            classes.get(game.game_id) == "exact_match" and bool(game.measurement_usable)
        )
        for team in (game.home_team, game.away_team):
            rows.append(
                {
                    "season": int(game.season),
                    "game_id": int(game.game_id),
                    "team": team,
                    "plays_complete": complete,
                    "possessions_complete": complete,
                    "scoring_complete": complete,
                }
            )
    return pd.DataFrame(rows)


def _digest(values: list[str]) -> str:
    return hashlib.sha256(json.dumps(sorted(values)).encode()).hexdigest()


def _read(context: StageContext, stage: str, key: str) -> bytes:
    return context.read_artifact(stage, key)


def load_comparison(context: StageContext) -> dict[str, Any]:
    prefix = comparison.PREFIX.format(run_id=context.plan.run_id)
    read = lambda name: _read(context, "step5_comparison", prefix + name)  # noqa: E731
    receipt = json.loads(read(comparison.RECEIPT))
    if not receipt.get("passed"):
        raise GateError("gold requires a passing step5_comparison")
    return {
        "possessions": pd.read_parquet(
            io.BytesIO(read(comparison.FILES["possessions"]))
        ),
        "admitted": pd.read_parquet(
            io.BytesIO(read(comparison.FILES["admitted_events"]))
        ),
        "decisions": pd.read_csv(io.BytesIO(read(comparison.FILES["decisions"]))),
    }


def build(context: StageContext) -> StageOutput:
    from cks_picks_cfb.data.lake import (
        BuildRequest,
        PartitionedDatasetPart,
        PartitionedDatasetWriter,
        read_dataset,
    )
    from cks_picks_cfb.data.storage.local import LocalStorage
    from cks_picks_cfb.metrics import contracts as gold
    from cks_picks_cfb.metrics import evidence as ev
    from cks_picks_cfb.metrics.builders import build_team_game_metrics
    from cks_picks_cfb.metrics.ledger import (
        possessions_to_v1,
        possessions_to_v2,
        scoring_events_to_v1,
        scoring_events_to_v2,
    )
    from cks_picks_cfb.metrics.season_features import season_features
    from cks_picks_cfb.ratings import admission as adm
    from cks_picks_cfb.ratings import possession_measurements as pm
    from cks_picks_cfb.rebuild import legacy as legacy5c

    storage = common.preview_storage(context)
    pin_file = json.loads(context.read_input("phase2c_silver_parents"))
    seasons = sorted(context.plan.seasons)
    silver = common.silver_summary(context)
    identity = identity_of(context)
    v2 = identity == "byplay_v2"
    config, schema_versions = settings_for(identity)
    as_of = datetime.fromisoformat(
        context.plan.policies["silver_as_of"].replace("Z", "+00:00")
    )
    parents = tuple(
        common.dataset_ref(item["datasets"][name]["ref"])
        for item in sorted(silver["seasons"], key=lambda i: i["season"])
        for name in ("byplay", "drives", "source_reconciliation")
    )
    byplay = common.staged_silver(context, "byplay")
    drives = common.staged_silver(context, "drives")
    reconciliation = common.staged_silver(context, "source_reconciliation")
    population = pd.read_parquet(
        io.BytesIO(
            _read(
                context,
                "eligibility",
                eligibility.PREFIX.format(run_id=context.plan.run_id)
                + eligibility.POPULATION,
            )
        )
    )
    inputs = load_comparison(context)
    fbs_games = pd.concat(
        [
            read_dataset(
                storage, common.pinned_parent(pin_file, s, "fbs_involved_games")
            )
            for s in seasons
        ],
        ignore_index=True,
    )
    games = games_frame(population, fbs_games)
    versions = {
        "byplay": _digest(
            [i["datasets"]["byplay"]["ref"]["version_id"] for i in silver["seasons"]]
        ),
        "drives": _digest(
            [i["datasets"]["drives"]["ref"]["version_id"] for i in silver["seasons"]]
        ),
        "coverage": _digest(
            [
                i["datasets"]["source_reconciliation"]["ref"]["version_id"]
                for i in silver["seasons"]
            ]
        ),
        "decisions": context.plan.decisions[
            "admission_decisions_v2_csv" if v2 else "admission_decisions_csv"
        ],
    }

    # Evidence bytes come from the pinned CFBD bundles on Preview R2, hash-verified.
    manifest_bytes = context.read_input("cfbd_drives_manifest")
    records = [
        json.loads(row) for row in manifest_bytes.decode().splitlines() if row.strip()
    ]
    index = ev.bundle_index(
        records, lambda name: storage.read_bytes(ev.BUNDLE_PREFIX + name)
    )
    decisions = inputs["decisions"]
    admitted_groups = decisions[decisions["decision"] == "admitted"]
    evidence_ids = {
        row.group_id: (ev.evidence_id(row.group_id, index[int(row.game_id)]["sha256"]),)
        for row in admitted_groups.itertuples(index=False)
    }
    canonical = pm._canonicalize_byplay_teams(byplay)
    finals = legacy5c._finals(population, pd.DataFrame())
    group_map = {
        (int(r.game_id), str(r.team), str(r.source_event_id)): r.allocation_group_id
        for r in inputs["admitted"].dropna(subset=["allocation_group_id"]).itertuples()
    }
    possessions = (possessions_to_v2 if v2 else possessions_to_v1)(
        inputs["possessions"], drives, source_versions=versions
    )
    ledger = (scoring_events_to_v2 if v2 else scoring_events_to_v1)(
        inputs["admitted"],
        canonical,
        finals=finals,
        source_versions=versions,
        rule_version="baseline_v1",
        groups=group_map,
        admitted_evidence=evidence_ids,
        admitted_rule_version=adm.RULE_VERSION,
        populate_envelopes=True,
    )
    evidence = ev.build_evidence(decisions, ledger, index)
    coverage = coverage_frame(games, reconciliation)
    metrics = build_team_game_metrics(
        plays=byplay,
        possessions=possessions,
        ledger=ledger,
        games=games[
            [
                c
                for c in games.columns
                if c not in ("forecast_eligible", "measurement_usable")
            ]
        ],
        source_versions=versions,
        timing_class=TIMING,
        coverage=coverage,
    )
    features = season_features(metrics, games)

    frames = {
        "football_possessions": possessions,
        "football_scoring_ledger": ledger,
        "scoring_attribution_evidence": evidence,
        "team_game_metrics": metrics,
        "season_level_features": features,
    }
    problems = (
        (gold.possessions_v2_problems if v2 else gold.possessions_problems)(possessions)
        + (gold.scoring_ledger_v2_problems if v2 else gold.scoring_ledger_problems)(
            ledger, possessions
        )
        + gold.evidence_problems(evidence)
        + gold.team_game_metrics_problems(metrics)
        + gold.defense_mirror_problems(metrics)
    )
    summary: dict[str, Any] = {
        "config": config,
        "config_sha": config_sha(config),
        "contract_problem_count": len(problems),
        "contract_problems": problems[:20],
        "datasets": {},
    }
    prefix = SUMMARY.format(run_id=context.plan.run_id)

    def artifacts() -> Iterator[tuple[str, bytes]]:
        with tempfile.TemporaryDirectory(prefix="6a-gold-") as tmp:
            local = LocalStorage(tmp)
            for name in DATASETS:
                frame = frames[name]
                writer = PartitionedDatasetWriter(
                    local,
                    build=BuildRequest(
                        dataset=name,
                        parent_refs=parents,
                        code_sha=context.code_sha,
                        config_sha=config_sha(config),
                        as_of=as_of,
                        schema_version=schema_versions[name],
                        tier="gold",
                    ),
                    partition_keys=("season",),
                )
                for season in seasons:
                    writer.add(
                        PartitionedDatasetPart(
                            partition={"season": season},
                            frame=_as_stored(frame[frame["season"] == season]),
                        )
                    )
                ref = writer.finish()
                summary["datasets"][name] = {
                    "ref": asdict(ref),
                    "rows": int(len(frame)),
                    "parts": [dict(part) for part in writer.parts],
                }
            files = sorted(
                (p for p in Path(tmp).rglob("*") if p.is_file()),
                key=lambda p: (p.name == "partitioned-manifest.json", str(p)),
            )
            for path in files:
                yield str(path.relative_to(tmp)), path.read_bytes()
        yield (
            prefix,
            json.dumps(summary, indent=2, sort_keys=True, default=str).encode(),
        )

    return StageOutput(artifacts=artifacts(), metrics={"datasets": len(DATASETS)})


class _StagedStorage:
    """Serve staged bytes to the lake's own readers, so verification uses its checks."""

    def __init__(self, context: StageContext):
        self._context = context

    def read_bytes(self, uri: str) -> bytes:
        return self._context.read_artifact(self._context.stage.name, uri)

    def exists(self, uri: str) -> bool:
        try:
            self.read_bytes(uri)
            return True
        except (FileNotFoundError, KeyError, OSError):
            return False


def _load(context: StageContext, name: str, info: Mapping[str, Any]) -> pd.DataFrame:
    from cks_picks_cfb.data.lake import PartitionedDatasetRef, iter_partitioned_dataset

    ref = dict(info["ref"])
    ref["partition_keys"] = tuple(ref["partition_keys"])
    frames = list(
        iter_partitioned_dataset(_StagedStorage(context), PartitionedDatasetRef(**ref))
    )
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def verify(context: StageContext) -> list[str]:
    """Independent verification: lake-level part checks, contracts, references, totals."""
    from cks_picks_cfb.metrics import contracts as gold
    from cks_picks_cfb.metrics import evidence as ev
    from cks_picks_cfb.rebuild.plan import HISTORICAL_SEASONS

    stage = context.stage.name
    summary = json.loads(
        context.read_artifact(stage, SUMMARY.format(run_id=context.plan.run_id))
    )
    problems: list[str] = []
    identity = identity_of(context)
    v2 = identity == "byplay_v2"
    config, _ = settings_for(identity)
    if summary["config_sha"] != config_sha(config):
        problems.append("gold config identity changed")
    if summary["contract_problem_count"]:
        problems.append(
            f"build recorded {summary['contract_problem_count']} contract problems"
        )
    if set(summary["datasets"]) != set(DATASETS):
        return problems + ["gold datasets differ from the plan"]
    frames: dict[str, pd.DataFrame] = {}
    for name in DATASETS:
        info = summary["datasets"][name]
        try:
            frames[name] = _load(context, name, info)  # hash, schema, digest, row count
        except Exception as exc:  # the lake reader raises StorageError on any mismatch
            problems.append(f"{name}: lake-level verification failed: {exc}")
            continue
        seasons = sorted(p["partition"]["season"] for p in info["parts"])
        if seasons != sorted(HISTORICAL_SEASONS):
            problems.append(f"{name}: seasons {seasons}")
        if len(frames[name]) != info["rows"]:
            problems.append(f"{name}: row count differs from the summary")
    if problems:
        return problems
    possessions, ledger = (
        frames["football_possessions"],
        frames["football_scoring_ledger"],
    )
    evidence, metrics = (
        frames["scoring_attribution_evidence"],
        frames["team_game_metrics"],
    )
    problems += (gold.possessions_v2_problems if v2 else gold.possessions_problems)(
        possessions
    )
    problems += (
        gold.scoring_ledger_v2_problems if v2 else gold.scoring_ledger_problems
    )(ledger, possessions)
    problems += gold.evidence_problems(evidence)
    problems += gold.team_game_metrics_problems(metrics)
    problems += gold.defense_mirror_problems(metrics)

    # The ledger must be exactly the verified admitted events, not a re-derivation.
    admitted = load_comparison(context)["admitted"]
    key = ["season", "game_id", "team", "source_event_id"]
    if len(ledger) != len(admitted) or set(map(tuple, ledger[key].values)) != set(
        map(tuple, admitted[key].values)
    ):
        problems.append("ledger events differ from the verified admitted events")
    resolved = ledger[ledger["scoring_category"] != "unresolved"]
    if int(resolved["score_increment"].sum()) != int(
        admitted[admitted["scoring_category"] != "unresolved"]["score_increment"].sum()
    ):
        problems.append("ledger points differ from the admitted events")

    # Evidence references and retained bytes, verified against the pinned CFBD manifest.
    storage = common.preview_storage(context)
    records = [
        json.loads(row)
        for row in context.read_input("cfbd_drives_manifest").decode().splitlines()
        if row.strip()
    ]
    read_bundle = lambda name: storage.read_bytes(ev.BUNDLE_PREFIX + name)  # noqa: E731
    index = ev.bundle_index(records, read_bundle)
    problems += ev.evidence_reference_problems(evidence, ledger, index, read_bundle)

    # Offensive possession points recomputed from the ledger, independent of the builder.
    expected = (
        ledger[ledger["scoring_category"] == "eligible_regulation_offense"]
        .groupby(["season", "game_id", "team"])["score_increment"]
        .sum()
    )
    observed = metrics[
        (metrics["metric"] == "offensive_possession_points")
        & (metrics["role"] == "offense")
        & (metrics["coverage_status"] == "observed")
    ].set_index(["season", "game_id", "team"])["numerator"]
    aligned = expected.reindex(observed.index).fillna(0)
    if not (aligned.astype(float) == observed.astype(float)).all():
        problems.append("offensive possession points differ from the ledger")
    return problems
