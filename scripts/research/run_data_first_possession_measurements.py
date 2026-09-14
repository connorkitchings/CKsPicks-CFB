#!/usr/bin/env python3
"""Materialize certified Preview-only V5 possession measurements."""

from __future__ import annotations

import argparse
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

from cks_picks_cfb.data.data_first_phase3 import verify_core_eligibility
from cks_picks_cfb.data.data_first_phase3_v2 import verify_repair_manifest
from cks_picks_cfb.data.data_first_possession_v1 import (
    POSSESSION_DATASETS,
    POSSESSION_MANIFEST_SCHEMA,
    POSSESSION_OUTPUT_ROOT,
    REQUIRED_REPAIR_CANONICAL_SHA256,
    REQUIRED_REPAIR_RAW_SHA256,
    build_population,
    certification,
    possession_identity,
    sha256,
    validate_config,
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
)
from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ratings.possession_measurements import (
    build_measurements,
    replay_partitions,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = (
    REPO_ROOT / "conf/research/data_first_football_v1/possession_measurement_v1.yaml"
)
RELEVANT_PATHS = (
    "conf/research/data_first_football_v1/possession_measurement_v1.yaml",
    "src/cks_picks_cfb/data/data_first_possession_v1.py",
    "src/cks_picks_cfb/ratings/possession_measurements.py",
    "src/cks_picks_cfb/data/schema_contracts.py",
    "scripts/research/run_data_first_possession_measurements.py",
    "scripts/research/verify_data_first_possession_measurements.py",
)


class PossessionRunError(ValueError):
    pass


def _git_sha() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
    ).strip()


def _tracked_clean() -> bool:
    return not subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=REPO_ROOT,
        text=True,
    ).strip()


def _require_committed_paths() -> None:
    changed = subprocess.check_output(
        ["git", "diff", "--name-only", "HEAD"], cwd=REPO_ROOT, text=True
    ).splitlines()
    if set(changed) & set(RELEVANT_PATHS):
        raise PossessionRunError(
            "apply requires possession implementation at committed HEAD"
        )


def _utc(value: str) -> datetime:
    parsed = pd.Timestamp(value)
    if parsed.tzinfo is None:
        raise PossessionRunError("--as-of must be timezone-aware")
    return parsed.to_pydatetime().astimezone(timezone.utc)


def _ref(value: Mapping[str, Any]) -> DatasetRef:
    return DatasetRef(
        **{
            key: value[key]
            for key in ("dataset", "version_id", "schema_version", "content_sha", "uri")
        }
    )


def _immutable_json(storage: Any, uri: str, payload: Mapping[str, Any]) -> None:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=str
    ).encode()
    if storage.exists(uri):
        if storage.read_bytes(uri) != encoded:
            raise PossessionRunError(f"immutable object collision at {uri}")
        return
    storage.write_bytes(encoded, uri)


def _load_config(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text())
    if not isinstance(payload, dict):
        raise PossessionRunError("possession config must be a mapping")
    validate_config(payload)
    return payload


def _repair(storage: Any, uri: str) -> tuple[dict[str, Any], str]:
    raw = storage.read_bytes(uri)
    raw_sha = hashlib.sha256(raw).hexdigest()
    if raw_sha != REQUIRED_REPAIR_RAW_SHA256:
        raise PossessionRunError(
            "Repair manifest raw checksum is not the approved parent"
        )
    payload = verify_repair_manifest(json.loads(raw))
    if payload.get("manifest_sha256") != REQUIRED_REPAIR_CANONICAL_SHA256:
        raise PossessionRunError(
            "Repair manifest canonical checksum is not the approved parent"
        )
    return payload, raw_sha


def _sources(
    storage: Any, repair: Mapping[str, Any]
) -> dict[int, dict[str, DatasetRef]]:
    uri = ((repair.get("parents") or {}).get("core_eligibility") or {}).get("uri")
    if not uri:
        raise PossessionRunError("Repair manifest does not bind core eligibility")
    result: dict[int, dict[str, DatasetRef]] = {}
    for value in verify_core_eligibility(json.loads(storage.read_bytes(str(uri)))):
        season = int(value["season"])
        result.setdefault(season, {})[str(value["dataset"])] = _ref(value)
    if any({"byplay", "game_outcomes"} - set(refs) for refs in result.values()):
        raise PossessionRunError("Repair core sources lack byplay or outcome evidence")
    return result


@dataclass
class DatasetPlan:
    name: str
    partition_keys: tuple[str, ...]
    row_partition_keys: tuple[str, ...]
    parts: list[dict[str, Any]] = field(default_factory=list)

    def add(self, partition: Mapping[str, Any], frame: pd.DataFrame) -> None:
        dataset, version = POSSESSION_DATASETS[self.name]
        schema = schema_for(dataset, version)
        validate_frame(frame, schema)
        value = dict(partition)
        if tuple(value) != self.partition_keys:
            raise PossessionRunError(f"invalid {self.name} partition keys")
        for key in self.row_partition_keys:
            if (
                not frame.empty
                and not frame[key].map(lambda item: item == value[key]).all()
            ):
                raise PossessionRunError(f"{self.name} rows escape partition {value}")
        entry = {
            "partition": value,
            "row_count": int(len(frame)),
            "records_sha": canonical_frame_digest(frame, columns=schema.required),
        }
        if self.parts and partition_order_key(value) <= partition_order_key(
            self.parts[-1]["partition"]
        ):
            raise PossessionRunError(f"{self.name} partitions are not strictly ordered")
        self.parts.append(entry)

    @property
    def records_sha(self) -> str:
        return partitioned_records_sha(self.parts, self.partition_keys)

    @property
    def row_count(self) -> int:
        return sum(int(part["row_count"]) for part in self.parts)

    def expected(self) -> dict[str, Mapping[str, Any]]:
        return {partition_key(part["partition"]): part for part in self.parts}


_PARTITIONS = {
    "population": (("season",), ("season",)),
    "possessions": (("season",), ("season",)),
    "scoring_events": (("season",), ("season",)),
    "observations": (("season",), ("season",)),
    "snapshots": (("season", "week"), ("season", "week")),
    "adjusted_history": (("season", "week"), ("season", "week")),
    "terminal": (("season",), ("season",)),
    "coverage": (("season",), ("season",)),
}


def _plans() -> dict[str, DatasetPlan]:
    return {
        name: DatasetPlan(name, keys, row_keys)
        for name, (keys, row_keys) in _PARTITIONS.items()
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


@dataclass
class Preflight:
    population: pd.DataFrame
    frames: dict[str, pd.DataFrame]
    plans: dict[str, DatasetPlan]
    scale_diagnostics: dict[str, Any]
    certification: dict[str, Any]


def preflight(
    *,
    storage: Any,
    repair: Mapping[str, Any],
    identity: Mapping[str, Any],
    writers: Mapping[str, PartitionedDatasetWriter] | None = None,
) -> Preflight:
    population_ref = _ref(repair["output_refs"]["population"])
    repair_population = read_dataset(storage, population_ref)
    population = build_population(repair_population)
    refs = _sources(storage, repair)
    byplay, outcomes = [], []
    for season in sorted(refs):
        byplay.append(read_dataset(storage, refs[season]["byplay"]))
        outcomes.append(read_dataset(storage, refs[season]["game_outcomes"]))
    measurements = build_measurements(
        byplay=pd.concat(byplay, ignore_index=True),
        outcomes=pd.concat(outcomes, ignore_index=True),
        population=population,
    )
    frames = {
        "population": population,
        "possessions": measurements.possessions,
        "scoring_events": measurements.scoring_events,
        "observations": measurements.observations,
        "coverage": measurements.coverage,
    }
    plans = _plans()
    for name, frame in frames.items():
        keys = _PARTITIONS[name][0]
        if frame.empty:
            continue
        for values, part in frame.groupby(list(keys), sort=True, dropna=False):
            values = values if isinstance(values, tuple) else (values,)
            _add(
                plans,
                name,
                dict(zip(keys, values)),
                part.reset_index(drop=True),
                writers,
            )
    replay_evidence = replay_partitions(
        population=population,
        observations=measurements.observations,
        emit=lambda name, partition, frame: _add(
            plans, name, partition, frame, writers
        ),
    )
    scale_diagnostics: dict[str, Any] = {
        "fixed_settings": {
            "ppp": {"floor": 0.30, "fallback": 1.0},
            "epa_per_possession": {"floor": 0.50, "fallback": 1.50},
        },
        "replay": replay_evidence,
    }
    output_rows = {name: plan.row_count for name, plan in plans.items()}
    output_digests = {name: plan.records_sha for name, plan in plans.items()}
    signed = certification(
        population=population,
        output_rows=output_rows,
        output_digests=output_digests,
        coverage=measurements.coverage,
        scale_diagnostics=scale_diagnostics,
    )
    if not signed["all_checks_passed"]:
        raise PossessionRunError("possession measurement certification failed")
    return Preflight(population, frames, plans, scale_diagnostics, signed)


def _writers(
    storage: Any,
    identity: Mapping[str, Any],
    repair: Mapping[str, Any],
    plans: Mapping[str, DatasetPlan],
) -> dict[str, PartitionedDatasetWriter]:
    parent = _ref(repair["output_refs"]["population"])
    as_of = _utc(str(identity["as_of"]))
    return {
        name: PartitionedDatasetWriter(
            storage,
            build=BuildRequest(
                dataset=POSSESSION_DATASETS[name][0],
                parent_refs=(parent,),
                code_sha=str(identity["code_sha"]),
                config_sha=str(identity["config_sha"]),
                as_of=as_of,
                schema_version=POSSESSION_DATASETS[name][1],
                tier="gold",
            ),
            partition_keys=plan.partition_keys,
            row_partition_keys=plan.row_partition_keys,
            expected_parts=plan.expected(),
        )
        for name, plan in plans.items()
    }


def apply(
    *,
    storage: Any,
    run_id: str,
    repair: Mapping[str, Any],
    identity: Mapping[str, Any],
    preflight_result: Preflight,
) -> dict[str, Any]:
    prefix = f"{POSSESSION_OUTPUT_ROOT}/{run_id}"
    manifest_uri = f"{prefix}/measurement-manifest.json"
    if storage.exists(manifest_uri):
        existing = json.loads(storage.read_bytes(manifest_uri))
        if (existing.get("identity") or {}).get("identity_sha256") == identity[
            "identity_sha256"
        ]:
            return {
                "manifest_uri": manifest_uri,
                "manifest": existing,
                "already_applied": True,
            }
        raise PossessionRunError("possession run ID already has a different identity")
    _immutable_json(
        storage,
        f"{prefix}/publication-plan.json",
        {
            "identity": dict(identity),
            "plans": {
                name: {
                    "row_count": plan.row_count,
                    "records_sha": plan.records_sha,
                    "parts": plan.parts,
                }
                for name, plan in preflight_result.plans.items()
            },
            "certification_sha256": preflight_result.certification["manifest_sha256"],
            "production_activation_authorized": False,
        },
    )
    writers = _writers(storage, identity, repair, preflight_result.plans)
    repeated = preflight(
        storage=storage, repair=repair, identity=identity, writers=writers
    )
    if (
        repeated.certification["manifest_sha256"]
        != preflight_result.certification["manifest_sha256"]
    ):
        raise PossessionRunError("apply replay differs from same-code preflight")
    refs = {name: asdict(writer.finish()) for name, writer in writers.items()}
    manifest = {
        "schema_version": POSSESSION_MANIFEST_SCHEMA,
        "identity": dict(identity),
        "repair_manifest_uri": identity["repair_manifest_uri"],
        "repair_manifest_raw_sha256": identity["repair_manifest_raw_sha256"],
        "repair_manifest_canonical_sha256": identity[
            "repair_manifest_canonical_sha256"
        ],
        "output_refs": refs,
        "output_rows": {name: plan.row_count for name, plan in repeated.plans.items()},
        "output_records_sha256": {
            name: plan.records_sha for name, plan in repeated.plans.items()
        },
        "certification_sha256": repeated.certification["manifest_sha256"],
        "scale_diagnostics": repeated.scale_diagnostics,
        "production_activation_authorized": False,
    }
    from cks_picks_cfb.data.data_first_phase2d import signed_payload

    manifest = signed_payload(manifest)
    _immutable_json(storage, f"{prefix}/identity.json", identity)
    _immutable_json(storage, f"{prefix}/certification.json", repeated.certification)
    for name, ref in refs.items():
        _immutable_json(storage, f"{prefix}/{name}-ref.json", ref)
    _immutable_json(storage, manifest_uri, manifest)
    return {
        "manifest_uri": manifest_uri,
        "manifest": manifest,
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
    path = Path(args.config).resolve()
    if path != DEFAULT_CONFIG.resolve():
        raise PossessionRunError(
            "possession measurement runner requires sealed default config"
        )
    _load_config(path)
    if _git_sha() != args.expected_code_sha:
        raise PossessionRunError("--expected-code-sha must equal committed HEAD")
    if args.apply:
        if not _tracked_clean():
            raise PossessionRunError("apply requires a clean tracked worktree")
        _require_committed_paths()
    storage = get_storage(environment="preview")
    repair, raw_sha = _repair(storage, args.repair_manifest_uri)
    identity = possession_identity(
        run_id=args.run_id,
        as_of=_utc(args.as_of).isoformat().replace("+00:00", "Z"),
        code_sha=args.expected_code_sha,
        config_sha=sha256(path.read_bytes()),
        repair_manifest_uri=args.repair_manifest_uri,
        repair_manifest_raw_sha256=raw_sha,
        repair_manifest_canonical_sha256=repair["manifest_sha256"],
    )
    result = preflight(storage=storage, repair=repair, identity=identity)
    summary: dict[str, Any] = {
        "state": "dry_run",
        "identity": identity,
        "row_counts": {name: plan.row_count for name, plan in result.plans.items()},
        "output_records_sha256": {
            name: plan.records_sha for name, plan in result.plans.items()
        },
        "certification_sha256": result.certification["manifest_sha256"],
        "scale_diagnostics": result.scale_diagnostics,
    }
    if args.apply:
        applied = apply(
            storage=storage,
            run_id=args.run_id,
            repair=repair,
            identity=identity,
            preflight_result=result,
        )
        summary |= {
            "state": "already_applied" if applied["already_applied"] else "applied",
            "manifest_uri": applied["manifest_uri"],
        }
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
