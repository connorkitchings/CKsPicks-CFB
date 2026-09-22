#!/usr/bin/env python3
"""Materialize certified Preview-only V5 possession measurements."""

from __future__ import annotations

import argparse
import atexit
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

from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload
from cks_picks_cfb.data.data_first_phase3 import verify_core_eligibility
from cks_picks_cfb.data.data_first_phase3_v2 import verify_repair_manifest
from cks_picks_cfb.data.data_first_possession_v1 import (
    EXTENSION_2026_SEASONS_LIST,
    LIVE_TIMING,
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
from cks_picks_cfb.data.data_first_repair_v2 import REPAIRED_LIVE_STATE
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
from cks_picks_cfb.data.research_progress import ResearchProgress
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
CONFIG_2026 = (
    REPO_ROOT
    / "conf/research/data_first_football_v1/possession_measurement_2026_v1.yaml"
)
SEALED_CONFIGS = (DEFAULT_CONFIG.resolve(), CONFIG_2026.resolve())
RELEVANT_PATHS = (
    "conf/research/data_first_football_v1/possession_measurement_v1.yaml",
    "conf/research/data_first_football_v1/possession_measurement_2026_v1.yaml",
    "src/cks_picks_cfb/data/data_first_possession_v1.py",
    "src/cks_picks_cfb/ratings/possession_measurements.py",
    "src/cks_picks_cfb/ratings/possession_verification.py",
    "src/cks_picks_cfb/data/research_progress.py",
    "src/cks_picks_cfb/data/schema_contracts.py",
    "scripts/research/run_data_first_possession_measurements.py",
    "scripts/research/verify_data_first_possession_measurements.py",
)


class PossessionRunError(ValueError):
    pass


@dataclass(frozen=True)
class PreflightEvidence:
    """Reviewed dry-run plan used to avoid repeating an expensive apply preflight."""

    plans: dict[str, "DatasetPlan"]
    certification_sha256: str


def _git_sha() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
    ).strip()


def _worktree_clean() -> bool:
    return not subprocess.check_output(
        ["git", "status", "--porcelain"],
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


def _existing_apply_manifest(
    storage: Any, *, manifest_uri: str, identity: Mapping[str, Any]
) -> dict[str, Any] | None:
    """Validate an existing terminal identity without replaying its producer."""
    if not storage.exists(manifest_uri):
        return None
    from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload

    existing = json.loads(storage.read_bytes(manifest_uri))
    verify_signed_payload(existing, label="existing possession measurement manifest")
    if (existing.get("identity") or {}).get("identity_sha256") != identity[
        "identity_sha256"
    ]:
        raise PossessionRunError("possession run ID already has a different identity")
    outputs = existing.get("output_refs") or {}
    if (
        existing.get("production_activation_authorized") is not False
        or set(outputs) != set(POSSESSION_DATASETS)
        or not existing.get("certification_sha256")
    ):
        raise PossessionRunError("existing possession manifest is incomplete")
    required_ref_fields = {
        "artifact_kind",
        "dataset",
        "version_id",
        "schema_version",
        "content_sha",
        "records_sha",
        "uri",
        "row_count",
        "partition_keys",
    }
    for name, value in outputs.items():
        dataset, schema_version = POSSESSION_DATASETS[name]
        if (
            required_ref_fields - set(value)
            or value.get("artifact_kind") != "partitioned_dataset_v1"
            or value.get("dataset") != dataset
            or value.get("schema_version") != schema_version
        ):
            raise PossessionRunError(f"existing {name} output reference is invalid")
    certification_uri = manifest_uri.rsplit("/", 1)[0] + "/certification.json"
    certification_payload = json.loads(storage.read_bytes(certification_uri))
    verify_signed_payload(
        certification_payload, label="existing possession certification"
    )
    if (
        certification_payload.get("manifest_sha256") != existing["certification_sha256"]
        or not certification_payload.get("all_checks_passed")
        or certification_payload.get("production_activation_authorized") is not False
    ):
        raise PossessionRunError("existing possession certification is invalid")
    return existing


def _load_config(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text())
    if not isinstance(payload, dict):
        raise PossessionRunError("possession config must be a mapping")
    validate_config(payload)
    return payload


def _concat_source_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Concatenate source seasons with explicit all-null dtype handling."""
    if not frames:
        return pd.DataFrame()
    columns = list(dict.fromkeys(column for frame in frames for column in frame))
    unstable = {
        column
        for column in columns
        if len({str(frame[column].dtype) for frame in frames if column in frame}) > 1
        and any(column in frame and frame[column].isna().all() for frame in frames)
    }
    normalized = [
        frame.astype({column: "object" for column in unstable if column in frame})
        for frame in frames
    ]
    return pd.concat(normalized, ignore_index=True)


def _repair(
    storage: Any, uri: str, *, scope: str = "historical", config: Mapping | None = None
) -> tuple[dict[str, Any], str]:
    raw = storage.read_bytes(uri)
    raw_sha = hashlib.sha256(raw).hexdigest()
    if scope == "season_2026":
        return _repair_2026(storage, raw, raw_sha, config=config)
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


def _repair_2026(
    storage: Any, raw: bytes, raw_sha: str, *, config: Mapping | None = None
) -> tuple[dict[str, Any], str]:
    """Bind the certified Repair-2026 parent by manifest chain, not module pins."""
    from cks_picks_cfb.data.data_first_repair_v2 import REPAIR_MANIFEST_SCHEMA

    payload = json.loads(raw)
    verify_signed_payload(payload, label="Repair-2026 manifest")
    if payload.get("schema_version") != REPAIR_MANIFEST_SCHEMA:
        raise PossessionRunError("Repair-2026 source is not a repair manifest")
    if (
        payload.get("state") != REPAIRED_LIVE_STATE
        or payload.get("timing_class") != LIVE_TIMING
        or payload.get("production_activation_authorized") is not False
        or (payload.get("identity") or {}).get("environment") != "preview"
    ):
        raise PossessionRunError(
            "Repair-2026 source is not eligible Preview live evidence"
        )
    expected = (config or {}).get("expected_population") or {}
    summary = payload.get("population") or {}
    if (
        summary.get("scheduled_games") != int(expected.get("rows", -1))
        or summary.get("forecast_eligible_games")
        != int(expected.get("forecast_eligible", -1))
    ):
        raise PossessionRunError(
            "Repair-2026 population summary differs from the 2026 config declaration"
        )
    return payload, raw_sha


def _sources(
    storage: Any, repair: Mapping[str, Any], *, scope: str = "historical"
) -> dict[int, dict[str, DatasetRef]]:
    if scope == "season_2026":
        return _sources_2026(storage, repair)
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


def _sources_2026(
    storage: Any, repair: Mapping[str, Any]
) -> dict[int, dict[str, DatasetRef]]:
    """Resolve 2026 byplay/outcome sources through the Repair-2026 input bundle."""
    bundle_uri = ((repair.get("parents") or {}).get("season_2026_inputs") or {}).get(
        "uri"
    )
    if not bundle_uri:
        raise PossessionRunError("Repair-2026 manifest does not bind 2026 inputs")
    bundle = json.loads(storage.read_bytes(str(bundle_uri)))
    if bundle.get("schema_version") != "data_first_2026_silver_inputs_v1":
        raise PossessionRunError("2026 input bundle schema mismatch")
    refs = dict(bundle.get("refs") or {})
    if set(refs) != {"byplay", "game_outcomes"}:
        raise PossessionRunError("2026 input bundle must bind byplay and game_outcomes")
    result: dict[str, DatasetRef] = {}
    for name, value in refs.items():
        ref = _ref(value)
        parquet_bytes = storage.read_bytes(ref.uri)
        if hashlib.sha256(parquet_bytes).hexdigest() != ref.content_sha:
            raise PossessionRunError(f"2026 {name} content SHA mismatch")
        result[name] = ref
    return {2026: result}


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


def _plan_payload(plans: Mapping[str, DatasetPlan]) -> dict[str, Any]:
    """Serialize the complete logical part plan for a later write-only apply."""
    return {
        name: {
            "partition_keys": list(plan.partition_keys),
            "row_partition_keys": list(plan.row_partition_keys),
            "parts": plan.parts,
        }
        for name, plan in plans.items()
    }


def _load_preflight_evidence(
    path: Path, *, identity: Mapping[str, Any]
) -> PreflightEvidence:
    """Load an exact reviewed dry-run plan without trusting it blindly."""
    try:
        payload = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        raise PossessionRunError("preflight evidence is unreadable") from exc
    if payload.get("state") != "dry_run" or payload.get("identity") != dict(identity):
        raise PossessionRunError("preflight evidence identity does not match apply")
    raw_plans = payload.get("preflight_plans")
    if not isinstance(raw_plans, dict) or set(raw_plans) != set(POSSESSION_DATASETS):
        raise PossessionRunError("preflight evidence lacks the complete part plan")

    plans: dict[str, DatasetPlan] = {}
    for name, (partition_keys, row_partition_keys) in _PARTITIONS.items():
        raw = raw_plans.get(name)
        if not isinstance(raw, dict) or (
            raw.get("partition_keys") != list(partition_keys)
            or raw.get("row_partition_keys") != list(row_partition_keys)
            or not isinstance(raw.get("parts"), list)
        ):
            raise PossessionRunError(f"preflight evidence has invalid {name} plan")
        plan = DatasetPlan(name, partition_keys, row_partition_keys)
        for part in raw["parts"]:
            if not isinstance(part, dict):
                raise PossessionRunError(
                    f"preflight evidence has malformed {name} part"
                )
            partition = part.get("partition")
            row_count = part.get("row_count")
            records_sha = part.get("records_sha")
            if (
                not isinstance(partition, dict)
                or tuple(partition) != partition_keys
                or not isinstance(row_count, int)
                or row_count < 0
                or not isinstance(records_sha, str)
                or len(records_sha) != 64
            ):
                raise PossessionRunError(f"preflight evidence has invalid {name} part")
            if plan.parts and partition_order_key(partition) <= partition_order_key(
                plan.parts[-1]["partition"]
            ):
                raise PossessionRunError(
                    f"preflight evidence has unordered {name} partitions"
                )
            plan.parts.append(
                {
                    "partition": partition,
                    "row_count": row_count,
                    "records_sha": records_sha,
                }
            )
        plans[name] = plan

    row_counts = payload.get("row_counts")
    output_digests = payload.get("output_records_sha256")
    if row_counts != {
        name: plan.row_count for name, plan in plans.items()
    } or output_digests != {name: plan.records_sha for name, plan in plans.items()}:
        raise PossessionRunError(
            "preflight evidence summary does not match its part plan"
        )
    certification_sha256 = payload.get("certification_sha256")
    if not isinstance(certification_sha256, str) or len(certification_sha256) != 64:
        raise PossessionRunError("preflight evidence lacks its certification checksum")
    return PreflightEvidence(plans=plans, certification_sha256=certification_sha256)


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
    scope: str = "historical",
    expected_rows: int | None = None,
    expected_eligible: int | None = None,
    writers: Mapping[str, PartitionedDatasetWriter] | None = None,
    progress: ResearchProgress | None = None,
) -> Preflight:
    if progress is not None:
        progress.emit("preflight_started", force=True)
    population_ref = _ref(repair["output_refs"]["population"])
    repair_population = read_dataset(storage, population_ref)
    population = build_population(
        repair_population,
        scope=scope,
        expected_rows=expected_rows,
        expected_eligible=expected_eligible,
    )
    refs = _sources(storage, repair, scope=scope)
    byplay, outcomes = [], []
    for season in sorted(refs):
        if progress is not None:
            progress.emit(
                "source_loading",
                force=True,
                season=season,
                dataset="byplay_and_game_outcomes",
                completed=len(byplay),
                total=len(refs),
                rows=0,
            )
        byplay_frame = read_dataset(storage, refs[season]["byplay"])
        outcomes_frame = read_dataset(storage, refs[season]["game_outcomes"])
        byplay.append(byplay_frame)
        outcomes.append(outcomes_frame)
        if progress is not None:
            progress.emit(
                "source_loaded",
                force=True,
                season=season,
                dataset="byplay_and_game_outcomes",
                completed=len(byplay),
                total=len(refs),
                rows=len(byplay_frame) + len(outcomes_frame),
            )
    combined_byplay = _concat_source_frames(byplay)
    combined_outcomes = _concat_source_frames(outcomes)
    if progress is not None:
        progress.emit(
            "measurement_build_started",
            force=True,
            dataset="possession_measurements",
            completed=0,
            total=len(combined_byplay),
            rows=0,
        )
    measurements = build_measurements(
        byplay=combined_byplay,
        outcomes=combined_outcomes,
        population=population,
        progress=(progress.emit if progress is not None else None),
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
    if progress is not None:
        progress.emit(
            "replay_started",
            force=True,
            dataset="possession_replay",
            completed=0,
            total=int(population["forecast_eligible"].sum()),
            rows=0,
        )
    replay_evidence = replay_partitions(
        population=population,
        observations=measurements.observations,
        emit=lambda name, partition, frame: _add(
            plans, name, partition, frame, writers
        ),
        progress=(progress.emit if progress is not None else None),
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
        scope=scope,
        expected_rows=expected_rows,
        expected_eligible=expected_eligible,
    )
    if not signed["all_checks_passed"]:
        raise PossessionRunError("possession measurement certification failed")
    if progress is not None:
        progress.emit("preflight_complete", force=True, output_rows=output_rows)
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
            # The writer starts immutable, content-addressed part uploads as
            # replay emits them. This overlaps bounded R2 I/O with the CPU
            # replay and preserves the same ordered logical manifest.
            max_workers=8,
        )
        for name, plan in plans.items()
    }


def apply(
    *,
    storage: Any,
    run_id: str,
    repair: Mapping[str, Any],
    identity: Mapping[str, Any],
    expected: PreflightEvidence,
    progress: ResearchProgress | None = None,
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
                for name, plan in expected.plans.items()
            },
            "certification_sha256": expected.certification_sha256,
            "production_activation_authorized": False,
        },
    )
    writers = _writers(storage, identity, repair, expected.plans)
    if progress is not None:
        progress.emit("apply_replay_started", force=True)
    repeated = preflight(
        storage=storage,
        repair=repair,
        identity=identity,
        writers=writers,
        progress=progress,
    )
    if (
        repeated.certification["manifest_sha256"] != expected.certification_sha256
        or {name: plan.row_count for name, plan in repeated.plans.items()}
        != {name: plan.row_count for name, plan in expected.plans.items()}
        or {name: plan.records_sha for name, plan in repeated.plans.items()}
        != {name: plan.records_sha for name, plan in expected.plans.items()}
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
    if progress is not None:
        progress.emit("apply_complete", force=True, manifest_uri=manifest_uri)
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
    parser.add_argument(
        "--preflight-evidence",
        help="reviewed dry-run JSON used for a write-only apply",
    )
    args = parser.parse_args(argv)
    path = Path(args.config).resolve()
    if path not in SEALED_CONFIGS:
        raise PossessionRunError(
            "possession measurement runner requires a sealed versioned config "
            "(historical default or 2026 extension)"
        )
    _load_config(path)
    config = _load_config(path)
    scope = (
        "season_2026"
        if list(config.get("development_seasons") or []) == EXTENSION_2026_SEASONS_LIST
        else "historical"
    )
    expected_population = config.get("expected_population") or {}
    expected_rows = (
        int(expected_population["rows"]) if scope == "season_2026" else None
    )
    expected_eligible = (
        int(expected_population["forecast_eligible"]) if scope == "season_2026" else None
    )
    if _git_sha() != args.expected_code_sha:
        raise PossessionRunError("--expected-code-sha must equal committed HEAD")
    if args.preflight_evidence and not args.apply:
        raise PossessionRunError("--preflight-evidence requires --apply")
    if args.apply:
        if not _worktree_clean():
            raise PossessionRunError("apply requires a clean committed worktree")
        _require_committed_paths()
    storage = get_storage(environment="preview")
    repair, raw_sha = _repair(storage, args.repair_manifest_uri, scope=scope, config=config)
    identity = possession_identity(
        run_id=args.run_id,
        as_of=_utc(args.as_of).isoformat().replace("+00:00", "Z"),
        code_sha=args.expected_code_sha,
        config_sha=sha256(path.read_bytes()),
        repair_manifest_uri=args.repair_manifest_uri,
        repair_manifest_raw_sha256=raw_sha,
        repair_manifest_canonical_sha256=repair["manifest_sha256"],
        development_seasons=tuple(config.get("development_seasons") or ()),
    )
    manifest_uri = f"{POSSESSION_OUTPUT_ROOT}/{args.run_id}/measurement-manifest.json"
    existing = (
        _existing_apply_manifest(storage, manifest_uri=manifest_uri, identity=identity)
        if args.apply
        else None
    )
    if existing is not None:
        print(
            json.dumps(
                {"state": "already_applied", "manifest_uri": manifest_uri},
                sort_keys=True,
            )
        )
        return
    progress = ResearchProgress(run_id=args.run_id)
    progress.start()
    atexit.register(progress.close)
    expected = (
        _load_preflight_evidence(Path(args.preflight_evidence), identity=identity)
        if args.preflight_evidence
        else None
    )
    result = (
        None
        if expected is not None
        else preflight(
            storage=storage,
            repair=repair,
            identity=identity,
            scope=scope,
            expected_rows=expected_rows,
            expected_eligible=expected_eligible,
            progress=progress,
        )
    )
    plans = expected.plans if expected is not None else result.plans
    certification_sha256 = (
        expected.certification_sha256
        if expected is not None
        else result.certification["manifest_sha256"]
    )
    summary: dict[str, Any] = {
        "state": "write_only_apply" if expected is not None else "dry_run",
        "identity": identity,
        "row_counts": {name: plan.row_count for name, plan in plans.items()},
        "output_records_sha256": {
            name: plan.records_sha for name, plan in plans.items()
        },
        "certification_sha256": certification_sha256,
        "preflight_plans": _plan_payload(plans),
    }
    if result is not None:
        summary["scale_diagnostics"] = result.scale_diagnostics
    if args.apply:
        applied = apply(
            storage=storage,
            run_id=args.run_id,
            repair=repair,
            identity=identity,
            expected=expected
            or PreflightEvidence(
                plans=result.plans,
                certification_sha256=result.certification["manifest_sha256"],
            ),
            progress=progress,
        )
        summary |= {
            "state": "already_applied" if applied["already_applied"] else "applied",
            "manifest_uri": applied["manifest_uri"],
        }
    progress.close()
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
