#!/usr/bin/env python3
"""Materialize bounded, immutable Preview-only Phase 3 v2 evidence."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import pandas as pd
import yaml
from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_phase2 import DEVELOPMENT_SEASONS
from cks_picks_cfb.data.data_first_phase3 import verify_core_eligibility
from cks_picks_cfb.data.data_first_phase3_v2 import (
    EXPECTED_ADJUSTED_HISTORY_ROWS,
    PHASE3_V2_DATASETS,
    PHASE3_V2_OUTPUT_ROOT,
    REQUIRED_REPAIR_CANONICAL_SHA256,
    REQUIRED_REPAIR_RAW_SHA256,
    Phase3V2Error,
    build_population,
    complete_observation_grid,
    phase3_v2_identity,
    select_retained_core,
    sha256,
    validate_phase3_v2_config,
    verify_repair_manifest,
)
from cks_picks_cfb.data.lake import (
    BuildRequest,
    DatasetRef,
    PartitionedDatasetPart,
    PartitionedDatasetWriter,
    canonical_frame_digest,
    partition_key,
    partition_order_key,
    partitioned_records_sha,
    read_dataset,
    require_dataset,
)
from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ratings.contracts import (
    OBSERVATION_COLUMNS,
    load_measurement_config,
    validate_observation_frame,
)
from cks_picks_cfb.ratings.observations import build_measurement_observations
from cks_picks_cfb.ratings.phase3 import (
    build_pass_rush_observations,
    run_candidate_feature_tournament,
)
from cks_picks_cfb.ratings.phase3_v2 import (
    CompactTournamentFeatureBuilder,
    iter_replayable_measurements,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = (
    REPO_ROOT / "conf/research/data_first_football_v1/phase3_measurement_core_v2.yaml"
)
V1_CONFIG = (
    REPO_ROOT / "conf/research/data_first_football_v1/phase3_measurement_core_v1.yaml"
)
RELEVANT_PATHS = (
    "conf/research/data_first_football_v1/phase3_measurement_core_v2.yaml",
    "scripts/research/run_data_first_phase3_v2.py",
    "scripts/research/verify_data_first_phase3_v2.py",
    "src/cks_picks_cfb/data/lake.py",
    "src/cks_picks_cfb/data/data_first_phase3_v2.py",
    "src/cks_picks_cfb/ratings/phase3_v2.py",
    "src/cks_picks_cfb/data/schema_contracts.py",
    "tests/test_data_lake.py",
    "tests/test_data_first_phase3_v2.py",
)
MAX_PARTITION_ROWS = 100_000
MAX_COMPACT_ROWS = 250_000
EXPECTED_RAW_COMPONENT_ROWS = 428_880
EXPECTED_COMPACT_FEATURE_ROWS = 142_960
EXPECTED_ROWS = {
    "population": 8936,
    "observations": 303790,
    "pregame_snapshots": 1215160,
    "adjusted_history": EXPECTED_ADJUSTED_HISTORY_ROWS,
    "predictions": 202176,
}
PARTITIONS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "population": (("season",), ("season",)),
    "observations": (("season",), ("season",)),
    "pregame_snapshots": (("season", "week"), ("season", "week")),
    "adjusted_history": (("season", "week"), ("season", "week")),
    "terminal": (("season",), ("season",)),
    "predictions": (("season",), ("season",)),
    "attribution": (("scope",), ()),
}


def _git_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _tracked_clean() -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and not result.stdout.strip()


def _require_committed_paths() -> None:
    for path in RELEVANT_PATHS:
        if subprocess.run(
            ["git", "ls-files", "--error-unmatch", path],
            cwd=REPO_ROOT,
            capture_output=True,
            check=False,
        ).returncode:
            raise Phase3V2Error(f"Phase 3 v2 path is not committed: {path}")
    if subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", *RELEVANT_PATHS],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
    ).returncode:
        raise Phase3V2Error("Phase 3 v2 code paths differ from committed HEAD")


def _utc(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise Phase3V2Error("--as-of must be timezone-aware")
    return result.astimezone(timezone.utc)


def _ref(value: Mapping[str, Any]) -> DatasetRef:
    return DatasetRef(
        **{
            key: str(value[key])
            for key in ("dataset", "version_id", "schema_version", "content_sha", "uri")
        }
    )


def _immutable_json(storage: Any, uri: str, payload: Mapping[str, Any]) -> None:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=str
    ).encode()
    if storage.exists(uri):
        if storage.read_bytes(uri) != encoded:
            raise Phase3V2Error(f"immutable artifact collision: {uri}")
        return
    storage.write_bytes(encoded, uri)


def _load_config(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text())
    if not isinstance(payload, dict):
        raise Phase3V2Error("Phase 3 v2 configuration must be a mapping")
    validate_phase3_v2_config(payload)
    return payload


def _read_repair_parent(storage: Any, uri: str) -> tuple[dict[str, Any], str]:
    raw = storage.read_bytes(uri)
    raw_sha = hashlib.sha256(raw).hexdigest()
    if raw_sha != REQUIRED_REPAIR_RAW_SHA256:
        raise Phase3V2Error("--repair-manifest-uri is not the sealed Repair v2 parent")
    payload = verify_repair_manifest(json.loads(raw))
    if payload.get("manifest_sha256") != REQUIRED_REPAIR_CANONICAL_SHA256:
        raise Phase3V2Error("Repair parent canonical checksum changed")
    return payload, raw_sha


def _source_refs(
    storage: Any, repair: Mapping[str, Any]
) -> dict[int, dict[str, DatasetRef]]:
    uri = ((repair.get("parents") or {}).get("core_eligibility") or {}).get("uri")
    if not uri:
        raise Phase3V2Error("Repair manifest does not bind a core eligibility parent")
    grouped: dict[int, dict[str, DatasetRef]] = {
        season: {} for season in DEVELOPMENT_SEASONS
    }
    for value in verify_core_eligibility(json.loads(storage.read_bytes(str(uri)))):
        ref = _ref(value)
        require_dataset(ref, str(value["dataset"]))
        grouped[int(value["season"])][ref.dataset] = ref
    if any(len(refs) != 7 for refs in grouped.values()):
        raise Phase3V2Error("certified sources do not resolve seven parents per season")
    return grouped


def _observations_for_season(
    storage: Any,
    refs: Mapping[str, DatasetRef],
    identity: Mapping[str, Any],
    as_of: datetime,
) -> pd.DataFrame:
    config = load_measurement_config(V1_CONFIG)
    source = {
        dataset: read_dataset(storage, ref) for dataset, ref in sorted(refs.items())
    }
    try:
        base = build_measurement_observations(
            byplay=source["byplay"],
            drives=source["drives"],
            games=source["fbs_involved_games"],
            outcomes=source["game_outcomes"],
            reconciled_team_game=source["reconciled_team_game"],
            config=config,
            as_of=as_of,
            code_sha=str(identity["code_sha"]),
            config_sha=str(identity["config_sha"]),
            parent_ref_shas=";".join(
                ref.content_sha for _, ref in sorted(refs.items())
            ),
        )
        validate_observation_frame(base.frame, config)
        pass_rush, _ = build_pass_rush_observations(
            byplay=source["byplay"], base_observations=base.frame
        )
        return (
            pd.concat((base.frame, pass_rush), ignore_index=True)[
                list(OBSERVATION_COLUMNS)
            ]
            .sort_values(
                ["season", "week", "game_id", "team", "measurement_id", "unit_role"],
                kind="mergesort",
            )
            .reset_index(drop=True)
        )
    finally:
        source.clear()
        gc.collect()


@dataclass
class DatasetPlan:
    name: str
    partition_keys: tuple[str, ...]
    row_partition_keys: tuple[str, ...]
    parts: list[dict[str, Any]] = field(default_factory=list)

    def add(self, partition: Mapping[str, Any], frame: pd.DataFrame) -> None:
        dataset, version = PHASE3_V2_DATASETS[self.name]
        schema = schema_for(dataset, version)
        validate_frame(frame, schema)
        partition = dict(partition)
        if tuple(partition) != self.partition_keys or len(frame) > MAX_PARTITION_ROWS:
            raise Phase3V2Error(f"invalid bounded {self.name} partition: {partition}")
        for column in self.row_partition_keys:
            if (
                not frame.empty
                and not frame[column]
                .map(lambda value: value == partition[column])
                .all()
            ):
                raise Phase3V2Error(f"{self.name} rows escape partition {partition}")
        item = {
            "partition": partition,
            "row_count": int(len(frame)),
            "records_sha": canonical_frame_digest(frame, columns=schema.required),
        }
        if self.parts and partition_order_key(partition) <= partition_order_key(
            self.parts[-1]["partition"]
        ):
            raise Phase3V2Error(f"{self.name} partitions are not strictly ordered")
        self.parts.append(item)

    @property
    def row_count(self) -> int:
        return int(sum(part["row_count"] for part in self.parts))

    @property
    def records_sha(self) -> str:
        return partitioned_records_sha(self.parts, self.partition_keys)

    def expected(self) -> dict[str, Mapping[str, Any]]:
        return {partition_key(part["partition"]): part for part in self.parts}

    def json(self) -> dict[str, Any]:
        return {
            "partition_keys": list(self.partition_keys),
            "row_partition_keys": list(self.row_partition_keys),
            "row_count": self.row_count,
            "records_sha": self.records_sha,
            "parts": self.parts,
        }


@dataclass
class Phase3Preflight:
    population: pd.DataFrame
    compact_tournament_features: pd.DataFrame
    compact_evidence: dict[str, Any]
    predictions: pd.DataFrame
    attribution: pd.DataFrame
    retained: dict[str, Any]
    certification: dict[str, Any]
    plans: dict[str, DatasetPlan]


def _plans() -> dict[str, DatasetPlan]:
    return {
        name: DatasetPlan(name, keys, row_keys)
        for name, (keys, row_keys) in PARTITIONS.items()
    }


def _add(
    plans: Mapping[str, DatasetPlan],
    name: str,
    partition: Mapping[str, Any],
    frame: pd.DataFrame,
    writers: Mapping[str, PartitionedDatasetWriter] | None = None,
) -> None:
    plans[name].add(partition, frame)
    if writers is not None:
        writers[name].add(PartitionedDatasetPart(partition, frame))


def _certification(
    population: pd.DataFrame,
    plans: Mapping[str, DatasetPlan],
    compact_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    checks = {
        "population_complete": len(population) == 8936
        and int(population["forecast_eligible"].sum()) == 8935,
        "measurement_population_preserved": int(population["measurement_usable"].sum())
        == 8903,
        "expected_replay_counts": all(
            plans[name].row_count == rows for name, rows in EXPECTED_ROWS.items()
        ),
        "forbidden_2020_absent": not population["season"].astype(int).eq(2020).any(),
        "reconstructed_timing_only": population["timing_class"]
        .eq("historically_reconstructed")
        .all(),
        "compact_tournament_state_bounded": (
            int(compact_evidence["raw_iteration_four_component_rows"])
            == EXPECTED_RAW_COMPONENT_ROWS
            and int(compact_evidence["compact_tournament_feature_rows"])
            == EXPECTED_COMPACT_FEATURE_ROWS
            and int(compact_evidence["compact_tournament_feature_rows"])
            <= MAX_COMPACT_ROWS
            and int(compact_evidence["max_snapshot_partition_rows"])
            <= MAX_PARTITION_ROWS
            and int(compact_evidence["max_history_partition_rows"])
            <= MAX_PARTITION_ROWS
            and int(compact_evidence["max_component_partition_rows"])
            <= MAX_PARTITION_ROWS
            and int(compact_evidence["max_feature_partition_rows"])
            <= MAX_PARTITION_ROWS
            and int(compact_evidence["max_prediction_rows"]) <= MAX_COMPACT_ROWS
            and bool(compact_evidence["raw_component_accumulator_absent"])
        ),
    }
    from cks_picks_cfb.data.data_first_phase2d import signed_payload

    return signed_payload(
        {
            "schema_version": "data_first_phase3_certification_v2",
            "checks": checks,
            "all_checks_passed": all(checks.values()),
            "row_counts": {name: plan.row_count for name, plan in plans.items()},
            "output_records_sha256": {
                name: plan.records_sha for name, plan in plans.items()
            },
            "compact_tournament_evidence": dict(compact_evidence),
            "population_sha256": canonical_frame_digest(
                population,
                columns=schema_for(*PHASE3_V2_DATASETS["population"]).required,
            ),
            "timing_class": "historically_reconstructed",
            "production_activation_authorized": False,
        }
    )


def preflight_phase3_v2(
    *,
    storage: Any,
    repair: Mapping[str, Any],
    identity: Mapping[str, Any],
    as_of: datetime,
    writers: Mapping[str, PartitionedDatasetWriter] | None = None,
) -> Phase3Preflight:
    """Run all Phase 3 math in bounded partitions; optionally write children."""
    repair_ref = _ref(repair["output_refs"]["population"])
    repair_population = read_dataset(storage, repair_ref)
    validate_frame(
        repair_population, schema_for(repair_ref.dataset, repair_ref.schema_version)
    )
    population, plans, refs = (
        build_population(repair_population),
        _plans(),
        _source_refs(storage, repair),
    )
    compact_builder = CompactTournamentFeatureBuilder()
    for season in DEVELOPMENT_SEASONS:
        season_population = population[
            population["season"].astype(int) == season
        ].copy()
        _add(plans, "population", {"season": season}, season_population, writers)
        observed = _observations_for_season(storage, refs[season], identity, as_of)
        observations = complete_observation_grid(
            population=season_population, observed=observed
        )
        _add(plans, "observations", {"season": season}, observations, writers)
        for replay in iter_replayable_measurements(
            population=season_population, observations=observations
        ):
            if replay.week is None:
                _add(plans, "terminal", {"season": season}, replay.terminal, writers)
                compact_builder.add_terminal(replay.terminal)
                continue
            partition = {"season": season, "week": replay.week}
            _add(plans, "pregame_snapshots", partition, replay.snapshots, writers)
            _add(plans, "adjusted_history", partition, replay.history, writers)
            week_games = season_population[
                (season_population["forecast_eligible"])
                & (season_population["week"].astype(int) == int(replay.week))
            ].copy()
            compact_builder.add_week(
                snapshots=replay.snapshots,
                games=week_games,
            )
        del observed, observations
        gc.collect()
    compact = compact_builder.finish()
    if len(compact) > MAX_COMPACT_ROWS:
        raise Phase3V2Error("compact tournament state exceeds sealed bound")
    compact_evidence = {
        "raw_iteration_four_component_rows": compact_builder.raw_component_rows,
        "compact_tournament_feature_rows": len(compact),
        "compact_tournament_feature_sha256": canonical_frame_digest(
            compact, columns=list(compact.columns)
        ),
        "max_snapshot_partition_rows": max(
            (part["row_count"] for part in plans["pregame_snapshots"].parts),
            default=0,
        ),
        "max_history_partition_rows": max(
            (part["row_count"] for part in plans["adjusted_history"].parts),
            default=0,
        ),
        "max_component_partition_rows": compact_builder.max_component_partition_rows,
        "max_feature_partition_rows": compact_builder.max_feature_partition_rows,
        "raw_component_accumulator_absent": True,
    }
    if (
        compact_evidence["raw_iteration_four_component_rows"]
        != EXPECTED_RAW_COMPONENT_ROWS
    ):
        raise Phase3V2Error("raw compact component count differs from sealed invariant")
    if (
        compact_evidence["compact_tournament_feature_rows"]
        != EXPECTED_COMPACT_FEATURE_ROWS
    ):
        raise Phase3V2Error(
            "compact tournament feature count differs from sealed invariant"
        )
    predictions = run_candidate_feature_tournament(
        features=compact,
        outcomes=population,
        ridge_alpha=10.0,
    )
    if len(predictions) > MAX_COMPACT_ROWS:
        raise Phase3V2Error("tournament predictions exceed sealed bound")
    for season, frame in predictions.groupby("season", sort=True):
        _add(
            plans,
            "predictions",
            {"season": int(season)},
            frame.reset_index(drop=True),
            writers,
        )
    attribution, retained = select_retained_core(predictions)
    _add(plans, "attribution", {"scope": "all"}, attribution, writers)
    compact_evidence["max_prediction_rows"] = len(predictions)
    certification = _certification(population, plans, compact_evidence)
    if not certification["all_checks_passed"]:
        raise Phase3V2Error(
            f"Phase 3 v2 certification failed: {[name for name, value in certification['checks'].items() if not value]}"
        )
    return Phase3Preflight(
        population,
        compact,
        compact_evidence,
        predictions,
        attribution,
        retained,
        certification,
        plans,
    )


def _writers(
    storage: Any,
    identity: Mapping[str, Any],
    as_of: datetime,
    repair: Mapping[str, Any],
    plans: Mapping[str, DatasetPlan],
) -> dict[str, PartitionedDatasetWriter]:
    parent = _ref(repair["output_refs"]["population"])
    result = {}
    for name, plan in plans.items():
        dataset, schema = PHASE3_V2_DATASETS[name]
        result[name] = PartitionedDatasetWriter(
            storage,
            build=BuildRequest(
                dataset=dataset,
                parent_refs=(parent,),
                code_sha=str(identity["code_sha"]),
                config_sha=str(identity["config_sha"]),
                as_of=as_of,
                schema_version=schema,
                tier="gold",
            ),
            partition_keys=plan.partition_keys,
            row_partition_keys=plan.row_partition_keys,
            expected_parts=plan.expected(),
        )
    return result


def _apply(
    storage: Any,
    run_id: str,
    preflight: Phase3Preflight,
    repair: Mapping[str, Any],
    identity: Mapping[str, Any],
    as_of: datetime,
) -> dict[str, Any]:
    prefix = f"{PHASE3_V2_OUTPUT_ROOT}/{run_id}"
    retained_uri = f"{prefix}/retained-core-manifest.json"
    if storage.exists(retained_uri):
        existing = json.loads(storage.read_bytes(retained_uri))
        if (existing.get("identity") or {}).get("identity_sha256") == identity[
            "identity_sha256"
        ]:
            return {
                "manifest_uri": retained_uri,
                "manifest": existing,
                "already_applied": True,
            }
        raise Phase3V2Error(f"Phase 3 v2 run identity already exists: {run_id}")
    publication = {
        "schema_version": "data_first_phase3_publication_plan_v1",
        "identity": dict(identity),
        "plans": {name: plan.json() for name, plan in preflight.plans.items()},
        "certification_sha256": preflight.certification["manifest_sha256"],
        "retained_core_sha256": preflight.retained["manifest_sha256"],
        "compact_tournament_evidence": preflight.compact_evidence,
        "production_activation_authorized": False,
    }
    _immutable_json(storage, f"{prefix}/publication-plan.json", publication)
    writers = _writers(storage, identity, as_of, repair, preflight.plans)
    repeated = preflight_phase3_v2(
        storage=storage, repair=repair, identity=identity, as_of=as_of, writers=writers
    )
    if (
        repeated.certification["manifest_sha256"],
        repeated.retained["manifest_sha256"],
        repeated.compact_evidence,
    ) != (
        preflight.certification["manifest_sha256"],
        preflight.retained["manifest_sha256"],
        preflight.compact_evidence,
    ):
        raise Phase3V2Error("apply recomputation differs from preflight")
    refs = {name: asdict(writer.finish()) for name, writer in writers.items()}
    from cks_picks_cfb.data.data_first_phase2d import signed_payload

    retained = signed_payload(
        {
            **{
                key: value
                for key, value in repeated.retained.items()
                if key != "manifest_sha256"
            },
            "identity": dict(identity),
            "repair_manifest_uri": identity["repair_manifest_uri"],
            "repair_manifest_raw_sha256": identity["repair_manifest_raw_sha256"],
            "repair_manifest_canonical_sha256": identity[
                "repair_manifest_canonical_sha256"
            ],
            "output_refs": refs,
            "output_rows": {
                name: plan.row_count for name, plan in repeated.plans.items()
            },
            "output_records_sha256": {
                name: plan.records_sha for name, plan in repeated.plans.items()
            },
            "certification_sha256": repeated.certification["manifest_sha256"],
            "compact_tournament_evidence": repeated.compact_evidence,
            "production_activation_authorized": False,
        }
    )
    _immutable_json(storage, f"{prefix}/identity.json", identity)
    _immutable_json(storage, f"{prefix}/certification.json", repeated.certification)
    for name, ref in refs.items():
        _immutable_json(storage, f"{prefix}/{name}-ref.json", ref)
    _immutable_json(storage, retained_uri, retained)
    return {
        "manifest_uri": retained_uri,
        "manifest": retained,
        "already_applied": False,
    }


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repair-manifest-uri", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--environment", choices=["preview"], required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    path, as_of = Path(args.config).resolve(), _utc(args.as_of)
    if path != DEFAULT_CONFIG.resolve():
        raise Phase3V2Error("Phase 3 v2 requires the sealed default configuration")
    _load_config(path)
    if _git_sha() != args.expected_code_sha:
        raise Phase3V2Error("--expected-code-sha must equal committed HEAD")
    if args.apply:
        if not _tracked_clean():
            raise Phase3V2Error("apply requires a clean tracked worktree")
        _require_committed_paths()
    storage = get_storage(environment="preview")
    repair, raw_sha = _read_repair_parent(storage, args.repair_manifest_uri)
    identity = phase3_v2_identity(
        run_id=args.run_id,
        environment="preview",
        as_of=as_of.isoformat().replace("+00:00", "Z"),
        code_sha=args.expected_code_sha,
        config_sha=sha256(path.read_bytes()),
        repair_manifest_uri=args.repair_manifest_uri,
        repair_manifest_raw_sha256=raw_sha,
        repair_manifest_canonical_sha256=repair["manifest_sha256"],
    )
    preflight = preflight_phase3_v2(
        storage=storage, repair=repair, identity=identity, as_of=as_of
    )
    summary: dict[str, Any] = {
        "state": "dry_run",
        "identity": identity,
        "row_counts": {name: plan.row_count for name, plan in preflight.plans.items()},
        "partition_inventory": {
            name: len(plan.parts) for name, plan in preflight.plans.items()
        },
        "output_records_sha256": {
            name: plan.records_sha for name, plan in preflight.plans.items()
        },
        "selected_candidate": preflight.retained["selected_candidate"],
        "certification_sha256": preflight.certification["manifest_sha256"],
        "retained_core_sha256": preflight.retained["manifest_sha256"],
        "compact_tournament_evidence": preflight.compact_evidence,
    }
    if args.apply:
        applied = _apply(storage, args.run_id, preflight, repair, identity, as_of)
        summary |= {
            "state": "already_applied" if applied["already_applied"] else "applied",
            "manifest_uri": applied["manifest_uri"],
            "retained_core_sha256": applied["manifest"]["manifest_sha256"],
        }
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
