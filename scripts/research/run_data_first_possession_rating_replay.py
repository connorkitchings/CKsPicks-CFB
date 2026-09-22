#!/usr/bin/env python3
"""Preflight and publish the isolated, Preview-only Contract 08 replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_phase2d import (
    sha256,
    signed_payload,
    verify_signed_payload,
)
from cks_picks_cfb.data.data_first_possession_rating_v1 import (
    RATING_DATASETS,
)
from cks_picks_cfb.data.data_first_possession_v1 import (
    POSSESSION_DATASETS,
    POSSESSION_MANIFEST_SCHEMA,
)
from cks_picks_cfb.data.lake import (
    BuildRequest,
    DatasetRef,
    PartitionedDatasetPart,
    PartitionedDatasetRef,
    PartitionedDatasetWriter,
    canonical_frame_digest,
    iter_partitioned_dataset,
    partition_key,
    partition_order_key,
    partitioned_records_sha,
)
from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ratings.possession_live_replay import (
    FROZEN_CANDIDATE,
    LiveReplayComputation,
    LiveReplayError,
    LiveReplayInputs,
    build_live_replay,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "conf/research/data_first_football_v1/possession_rating_replay_2026_v1.yaml"
OUTPUT_ROOT = "artifacts/research/data-first-football-v1/possession-v1/rating-replay/runs"
MANIFEST_NAME = "retained-rating-replay-manifest.json"
IDENTITY_SCHEMA = "data_first_possession_rating_replay_identity_v1"
MANIFEST_SCHEMA = "data_first_possession_rating_replay_manifest_v1"
OUTPUTS = ("priors", "rating_states", "team_states")
PARTITIONS = {
    "priors": ("season",),
    "rating_states": ("season", "week"),
    "team_states": ("season", "week"),
}
_PRESEASON_PREFIXES = {
    "recruiting": "raw/preseason/recruiting/snapshot_year=2026/",
    "returning_production": "raw/preseason/returning_production/snapshot_year=2026/",
    "coaches": "raw/preseason/coaches/snapshot_year=2026/",
}


class RatingReplayRunError(ValueError):
    """Raised before a Contract 08 replay can publish evidence."""


@dataclass(frozen=True)
class DatasetPlan:
    dataset: str
    schema_version: str
    partition_keys: tuple[str, ...]
    parts: tuple[dict[str, Any], ...]
    row_count: int
    records_sha: str

    def as_evidence(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "schema_version": self.schema_version,
            "partition_keys": list(self.partition_keys),
            "parts": [dict(value) for value in self.parts],
            "row_count": self.row_count,
            "records_sha": self.records_sha,
        }


def _git_sha() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def _clean_worktree() -> bool:
    return not subprocess.check_output(["git", "status", "--porcelain=v1"], cwd=ROOT, text=True).strip()


def _utc(value: str) -> datetime:
    parsed = pd.Timestamp(value)
    if parsed.tzinfo is None:
        raise RatingReplayRunError("--as-of must be timezone-aware")
    return parsed.to_pydatetime().astimezone(timezone.utc)


def _immutable_json(storage: Any, uri: str, payload: Mapping[str, Any]) -> None:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    if storage.exists(uri):
        if storage.read_bytes(uri) != encoded:
            raise RatingReplayRunError(f"immutable object collision at {uri}")
        return
    storage.write_bytes(encoded, uri)


def _dataset_ref(value: Mapping[str, Any], *, name: str) -> DatasetRef:
    fields = ("dataset", "version_id", "schema_version", "content_sha", "uri")
    if missing := [field for field in fields if not value.get(field)]:
        raise RatingReplayRunError(f"{name} reference lacks fields: {missing}")
    return DatasetRef(**{field: value[field] for field in fields})


def _partitioned_ref(value: Mapping[str, Any], *, name: str) -> PartitionedDatasetRef:
    fields = (
        "artifact_kind", "dataset", "version_id", "schema_version", "content_sha", "records_sha", "uri", "row_count", "partition_keys"
    )
    if missing := [field for field in fields if field not in value]:
        raise RatingReplayRunError(f"{name} partitioned reference lacks fields: {missing}")
    return PartitionedDatasetRef(
        artifact_kind=str(value["artifact_kind"]), dataset=str(value["dataset"]),
        version_id=str(value["version_id"]), schema_version=str(value["schema_version"]),
        content_sha=str(value["content_sha"]), records_sha=str(value["records_sha"]),
        uri=str(value["uri"]), row_count=int(value["row_count"]),
        partition_keys=tuple(value["partition_keys"]),
    )


def _read_partitioned(storage: Any, value: Mapping[str, Any], *, name: str) -> pd.DataFrame:
    ref = _partitioned_ref(value, name=name)
    frames = [frame for frame in iter_partitioned_dataset(storage, ref) if not frame.empty]
    schema = schema_for(ref.dataset, ref.schema_version)
    if not frames:
        return pd.DataFrame(columns=list(schema.required))
    unstable = {
        column
        for column in schema.required
        if len({str(frame[column].dtype) for frame in frames}) > 1
        and any(frame[column].isna().all() for frame in frames)
    }
    normalized = [
        frame.astype({column: "object" for column in unstable}) for frame in frames
    ]
    return pd.concat(normalized, ignore_index=True, sort=False).loc[
        :, list(schema.required)
    ]


def _load_config(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text())
    required = {
        "schema_version": "data_first_possession_rating_replay_config_v1",
        "environment": "preview",
        "season": 2026,
        "candidate_id": FROZEN_CANDIDATE,
        "definition": "ppp",
        "prior_family": "rho_0_60",
        "annual_carryover_rho": 0.60,
        "updater": "exposure",
        "snapshot_adjustment_iteration": 4,
        "availability_buffer_hours": 6,
        "production_activation_authorized": False,
    }
    if not isinstance(payload, dict) or any(payload.get(key) != value for key, value in required.items()):
        raise RatingReplayRunError("replay config differs from the frozen 11B design")
    return payload


def _measurement_parent(storage: Any, uri: str) -> tuple[dict[str, Any], bytes]:
    raw = storage.read_bytes(uri)
    payload = json.loads(raw)
    verify_signed_payload(payload, label="Contract 07 measurement manifest")
    identity = payload.get("identity") or {}
    if (
        payload.get("schema_version") != POSSESSION_MANIFEST_SCHEMA
        or identity.get("environment") != "preview"
        or tuple(identity.get("development_seasons") or ()) != (2026,)
        or not identity.get("run_id")
        or not payload.get("certification_sha256")
        or payload.get("production_activation_authorized") is not False
        or set(payload.get("output_refs") or {}) != set(POSSESSION_DATASETS)
    ):
        raise RatingReplayRunError("measurement parent is not the certified Contract 07 live parent")
    return payload, raw


def _historical_parent(storage: Any, uri: str) -> tuple[dict[str, Any], bytes, dict[str, Any], bytes]:
    raw = storage.read_bytes(uri)
    rating = json.loads(raw)
    verify_signed_payload(rating, label="11B retained rating manifest")
    identity = rating.get("identity") or {}
    if (
        rating.get("schema_version") != "data_first_possession_retained_rating_v1"
        or rating.get("state") != "frozen"
        or rating.get("selected_candidate") != FROZEN_CANDIDATE
        or identity.get("environment") != "preview"
        or identity.get("run_id") != "possession-v1-ratings-20260921-11d59ee-r9cert"
        or rating.get("production_activation_authorized") is not False
    ):
        raise RatingReplayRunError("historical parent is not the frozen 11B rating definition")
    historical_measurement_uri = (rating.get("parents") or {}).get("measurement_manifest_uri")
    historical_measurement_sha = (rating.get("parents") or {}).get("measurement_manifest_raw_sha256")
    if not historical_measurement_uri or not historical_measurement_sha:
        raise RatingReplayRunError("11B parent does not bind its historical measurement")
    historical_raw = storage.read_bytes(str(historical_measurement_uri))
    if hashlib.sha256(historical_raw).hexdigest() != historical_measurement_sha:
        raise RatingReplayRunError("11B historical measurement raw checksum differs")
    historical = json.loads(historical_raw)
    verify_signed_payload(historical, label="r9 measurement manifest")
    if (historical.get("identity") or {}).get("run_id") != "possession-v1-measurements-20260921-r9":
        raise RatingReplayRunError("11B historical measurement is not the certified r9 parent")
    return rating, raw, historical, historical_raw


def _preseason_refs(storage: Any, args: argparse.Namespace) -> dict[str, dict[str, str]]:
    values = {
        "recruiting": args.recruiting_manifest_uri,
        "returning_production": args.returning_production_manifest_uri,
        "coaches": args.coaches_manifest_uri,
    }
    result: dict[str, dict[str, str]] = {}
    for name, uri in values.items():
        if not str(uri).startswith(_PRESEASON_PREFIXES[name]):
            raise RatingReplayRunError(f"{name} manifest does not bind a 2026 preseason capture")
        raw = storage.read_bytes(uri)
        payload = json.loads(raw)
        if (
            payload.get("schema_version") != "cloud_v1"
            or not isinstance(payload.get("rows"), int)
            or int(payload["rows"]) <= 0
        ):
            raise RatingReplayRunError(f"{name} preseason manifest is malformed")
        result[name] = {"uri": str(uri), "raw_sha256": hashlib.sha256(raw).hexdigest()}
    return result


def _identity(args: argparse.Namespace, *, measurement_raw: bytes, historical_raw: bytes, historical_measurement_raw: bytes, preseason: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
    value = {
        "schema_version": IDENTITY_SCHEMA,
        "run_id": args.run_id,
        "environment": "preview",
        "as_of": args.as_of,
        "code_sha": args.expected_code_sha,
        "config_sha": sha256(config),
        "measurement_manifest_uri": args.measurement_manifest_uri,
        "measurement_manifest_raw_sha256": hashlib.sha256(measurement_raw).hexdigest(),
        "historical_rating_manifest_uri": args.historical_rating_manifest_uri,
        "historical_rating_manifest_raw_sha256": hashlib.sha256(historical_raw).hexdigest(),
        "historical_measurement_manifest_raw_sha256": hashlib.sha256(historical_measurement_raw).hexdigest(),
        "preseason_inputs": dict(preseason),
        "candidate_id": FROZEN_CANDIDATE,
        "production_activation_authorized": False,
    }
    value["identity_sha256"] = sha256(value)
    return value


def _plans(computation: LiveReplayComputation) -> dict[str, DatasetPlan]:
    frames = {"priors": computation.priors, "rating_states": computation.rating_states, "team_states": computation.team_states}
    plans: dict[str, DatasetPlan] = {}
    for name, frame in frames.items():
        dataset, schema_version = RATING_DATASETS[name]
        schema = schema_for(dataset, schema_version)
        validate_frame(frame, schema)
        keys = PARTITIONS[name]
        parts: list[dict[str, Any]] = []
        for partition_values, part in frame.groupby(list(keys), sort=True, dropna=False):
            values = partition_values if isinstance(partition_values, tuple) else (partition_values,)
            partition = {
                key: int(value) if key in {"season", "week"} else value
                for key, value in zip(keys, values, strict=True)
            }
            ordered = part.sort_values(list(keys) + [column for column in schema.keys if column not in keys], kind="mergesort")
            parts.append({"partition": partition, "row_count": int(len(ordered)), "records_sha": canonical_frame_digest(ordered, columns=schema.required)})
        parts.sort(key=lambda value: partition_order_key(value["partition"]))
        plans[name] = DatasetPlan(dataset, schema_version, keys, tuple(parts), int(len(frame)), partitioned_records_sha(parts, keys))
    return plans


def _load_computation(storage: Any, args: argparse.Namespace, measurement: Mapping[str, Any], historical_measurement: Mapping[str, Any]) -> LiveReplayComputation:
    outputs = measurement["output_refs"]
    historical_outputs = historical_measurement.get("output_refs") or {}
    if "terminal" not in historical_outputs:
        raise RatingReplayRunError("historical r9 parent lacks terminal measurements")
    try:
        inputs = LiveReplayInputs(
            population=_read_partitioned(storage, outputs["population"], name="live population"),
            observations=_read_partitioned(storage, outputs["observations"], name="live observations"),
            snapshots=_read_partitioned(storage, outputs["snapshots"], name="live snapshots"),
            historical_terminal=_read_partitioned(storage, historical_outputs["terminal"], name="r9 terminal"),
        )
        return build_live_replay(inputs)
    except (LiveReplayError, ValueError) as exc:
        raise RatingReplayRunError(f"live replay inputs are ineligible: {exc}") from exc


def preflight(*, storage: Any, args: argparse.Namespace) -> dict[str, Any]:
    config = _load_config(Path(args.config))
    measurement, measurement_raw = _measurement_parent(storage, args.measurement_manifest_uri)
    _, historical_raw, historical_measurement, historical_measurement_raw = _historical_parent(storage, args.historical_rating_manifest_uri)
    preseason = _preseason_refs(storage, args)
    identity = _identity(args, measurement_raw=measurement_raw, historical_raw=historical_raw, historical_measurement_raw=historical_measurement_raw, preseason=preseason, config=config)
    computation = _load_computation(storage, args, measurement, historical_measurement)
    plans = _plans(computation)
    return {
        "state": "dry_run",
        "identity": identity,
        "selected_candidate": FROZEN_CANDIDATE,
        "row_counts": {name: plan.row_count for name, plan in plans.items()},
        "output_records_sha256": {name: plan.records_sha for name, plan in plans.items()},
        "preflight_plans": {name: plan.as_evidence() for name, plan in plans.items()},
        "diagnostics": computation.diagnostics,
    }


def _evidence(path: Path, identity: Mapping[str, Any]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        raise RatingReplayRunError("preflight evidence is unreadable") from exc
    if payload.get("state") != "dry_run" or payload.get("identity") != dict(identity):
        raise RatingReplayRunError("preflight evidence identity does not match apply")
    if payload.get("selected_candidate") != FROZEN_CANDIDATE or set(payload.get("preflight_plans") or {}) != set(OUTPUTS):
        raise RatingReplayRunError("preflight evidence does not bind the replay outputs")
    return payload


def _writers(storage: Any, *, identity: Mapping[str, Any], measurement: Mapping[str, Any], historical_measurement: Mapping[str, Any], plans: Mapping[str, DatasetPlan]) -> dict[str, PartitionedDatasetWriter]:
    parent_refs = (
        _dataset_ref(measurement["output_refs"]["population"], name="live population"),
        _dataset_ref(historical_measurement["output_refs"]["terminal"], name="r9 terminal"),
    )
    return {
        name: PartitionedDatasetWriter(
            storage,
            build=BuildRequest(dataset=RATING_DATASETS[name][0], parent_refs=parent_refs, code_sha=str(identity["code_sha"]), config_sha=str(identity["config_sha"]), as_of=_utc(str(identity["as_of"])), schema_version=RATING_DATASETS[name][1], tier="gold"),
            partition_keys=PARTITIONS[name],
            expected_parts={partition_key(part["partition"]): part for part in plans[name].parts},
        )
        for name in OUTPUTS
    }


def _existing(storage: Any, uri: str, identity: Mapping[str, Any]) -> dict[str, Any] | None:
    if not storage.exists(uri):
        return None
    payload = json.loads(storage.read_bytes(uri))
    verify_signed_payload(payload, label="existing rating replay manifest")
    if (payload.get("identity") or {}).get("identity_sha256") != identity["identity_sha256"]:
        raise RatingReplayRunError("rating replay run ID already has a different identity")
    if payload.get("state") != "frozen" or set(payload.get("output_refs") or {}) != set(OUTPUTS):
        raise RatingReplayRunError("existing rating replay manifest is incomplete")
    return payload


def apply(*, storage: Any, args: argparse.Namespace, evidence: Mapping[str, Any]) -> dict[str, Any]:
    config = _load_config(Path(args.config))
    measurement, measurement_raw = _measurement_parent(storage, args.measurement_manifest_uri)
    _, historical_raw, historical_measurement, historical_measurement_raw = _historical_parent(storage, args.historical_rating_manifest_uri)
    preseason = _preseason_refs(storage, args)
    identity = _identity(args, measurement_raw=measurement_raw, historical_raw=historical_raw, historical_measurement_raw=historical_measurement_raw, preseason=preseason, config=config)
    manifest_uri = f"{OUTPUT_ROOT}/{args.run_id}/{MANIFEST_NAME}"
    if _existing(storage, manifest_uri, identity) is not None:
        return {"state": "already_applied", "manifest_uri": manifest_uri}
    prefix = manifest_uri.rsplit("/", 1)[0]
    if storage.list_files(prefix):
        raise RatingReplayRunError("rating replay prefix has a partial artifact and is permanently ineligible")
    reviewed = _evidence(Path(args.preflight_evidence), identity)
    computation = _load_computation(storage, args, measurement, historical_measurement)
    plans = _plans(computation)
    if reviewed["row_counts"] != {name: plan.row_count for name, plan in plans.items()} or reviewed["output_records_sha256"] != {name: plan.records_sha for name, plan in plans.items()}:
        raise RatingReplayRunError("apply recomputation differs from same-code preflight")
    _immutable_json(storage, f"{prefix}/publication-plan.json", {"identity": identity, "plans": {name: plan.as_evidence() for name, plan in plans.items()}, "production_activation_authorized": False})
    writers = _writers(storage, identity=identity, measurement=measurement, historical_measurement=historical_measurement, plans=plans)
    frames = {"priors": computation.priors, "rating_states": computation.rating_states, "team_states": computation.team_states}
    refs: dict[str, Any] = {}
    for name, writer in writers.items():
        frame = frames[name]
        for values, part in frame.groupby(list(PARTITIONS[name]), sort=True, dropna=False):
            key_values = values if isinstance(values, tuple) else (values,)
            partition = {
                key: int(value) if key in {"season", "week"} else value
                for key, value in zip(PARTITIONS[name], key_values, strict=True)
            }
            writer.add(PartitionedDatasetPart(partition, part.sort_values(list(PARTITIONS[name]) + [column for column in schema_for(RATING_DATASETS[name][0], RATING_DATASETS[name][1]).keys if column not in PARTITIONS[name]], kind="mergesort")))
        refs[name] = asdict(writer.finish())
    manifest = signed_payload({
        "schema_version": MANIFEST_SCHEMA,
        "state": "frozen",
        "identity": identity,
        "parents": {
            "measurement_manifest_uri": args.measurement_manifest_uri,
            "measurement_manifest_raw_sha256": hashlib.sha256(measurement_raw).hexdigest(),
            "historical_rating_manifest_uri": args.historical_rating_manifest_uri,
            "historical_rating_manifest_raw_sha256": hashlib.sha256(historical_raw).hexdigest(),
            "historical_measurement_manifest_raw_sha256": hashlib.sha256(historical_measurement_raw).hexdigest(),
            "preseason_inputs": preseason,
        },
        "selected_candidate": FROZEN_CANDIDATE,
        "output_refs": refs,
        "row_counts": {name: plan.row_count for name, plan in plans.items()},
        "output_records_sha256": {name: plan.records_sha for name, plan in plans.items()},
        "diagnostics": computation.diagnostics,
        "production_activation_authorized": False,
    })
    _immutable_json(storage, f"{prefix}/identity.json", identity)
    for name, ref in refs.items():
        _immutable_json(storage, f"{prefix}/{name}-ref.json", ref)
    _immutable_json(storage, manifest_uri, manifest)
    return {"state": "applied", "manifest_uri": manifest_uri, "selected_candidate": FROZEN_CANDIDATE}


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--environment", choices=("preview",), required=True)
    parser.add_argument("--measurement-manifest-uri", required=True)
    parser.add_argument("--historical-rating-manifest-uri", required=True)
    parser.add_argument("--recruiting-manifest-uri", required=True)
    parser.add_argument("--returning-production-manifest-uri", required=True)
    parser.add_argument("--coaches-manifest-uri", required=True)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--preflight-evidence")
    args = parser.parse_args(argv)
    if args.expected_code_sha != _git_sha():
        raise RatingReplayRunError("--expected-code-sha must match committed HEAD")
    storage = get_storage(environment="preview")
    if not args.apply:
        print(json.dumps(preflight(storage=storage, args=args), indent=2, sort_keys=True, default=str))
        return
    if not args.preflight_evidence:
        raise RatingReplayRunError("--apply requires --preflight-evidence")
    if not _clean_worktree():
        raise RatingReplayRunError("apply requires a clean committed worktree")
    print(json.dumps(apply(storage=storage, args=args, evidence={}), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
