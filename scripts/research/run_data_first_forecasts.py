#!/usr/bin/env python3
"""V5-04B forecast preflight, apply, and verification runner.

Dry run produces deterministic evidence including calibration.  Apply path
owns immutable child writes, candidate manifests, and idempotency.
"""

from __future__ import annotations

import argparse
import atexit
import hashlib
import json
import subprocess
import sys
import threading
import time
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_forecast_v1 import (
    FORECAST_CALIBRATION_COLUMNS,
    FORECAST_DATASETS,
    FORECAST_MANIFEST_NAME,
    FORECAST_MANIFEST_SCHEMA,
    FORECAST_MODEL_COLUMNS,
    FORECAST_OUTPUT_ROOT,
    FORECAST_PREDICTION_COLUMNS,
    FORECAST_REGISTRY_COLUMNS,
    FORECAST_SELECTION_COLUMNS,
    WINDOW_COMPARISON_COLUMNS,
    forecast_identity,
    forecast_manifest,
    validate_config,
    verify_rating_parent,
)
from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload
from cks_picks_cfb.data.data_first_possession_rating_v1 import TEAM_STATE_COLUMNS
from cks_picks_cfb.data.lake import (
    BuildRequest,
    PartitionedDatasetPart,
    PartitionedDatasetWriter,
    build_dataset_version,
    canonical_frame_digest,
    partition_key,
    partition_order_key,
    partitioned_records_sha,
)
from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.forecast.calibration import calibrate_uncertainty
from cks_picks_cfb.forecast.heads import FINAL_FIT_SEASON, evaluate_heads, fit_final
from cks_picks_cfb.forecast.historical_features import _feature_frame
from cks_picks_cfb.forecast.horizons import select_horizon
from cks_picks_cfb.forecast.offsets import build_offsets
from cks_picks_cfb.ratings.possession_rating_materializer import (
    _concat_frames,
    _manifest_parts,
    _partitioned_ref,
    _read_child,
    _stream_output,
    load_rating_inputs,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "conf/research/data_first_football_v1/forecast_v1.yaml"


class ForecastRunError(ValueError):
    """Raised before a V5-04A preflight could produce reviewable evidence."""


class _Progress:
    """Bounded, secret-safe stderr progress heartbeat for long phases.

    Mirrors the proven ratings-runner pattern: a daemon heartbeat thread, an
    interval cap on routine events, forced emission for phase boundaries, and
    a blocked-keyword filter so credentials can never reach stderr.  Stdout
    stays pure JSON evidence.
    """

    _FORCED_EVENTS = frozenset(
        {
            "preflight_started",
            "parents_loaded",
            "offsets_built",
            "horizon_started",
            "horizon_complete",
            "horizon_selected",
            "calibration_started",
            "calibration_complete",
            "evidence_constructed",
            "dry_run_complete",
        }
    )
    _BLOCKED_MARKERS = ("credential", "password", "secret", "token", "access_key")

    def __init__(self, run_id: str, interval_seconds: float = 30.0) -> None:
        self.run_id = run_id
        self.interval_seconds = interval_seconds
        self.started = time.monotonic()
        self.last = float("-inf")
        self.phase = "initializing"
        self.fields: dict[str, Any] = {}
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.thread: threading.Thread | None = None

    @classmethod
    def _safe(cls, fields: Mapping[str, Any]) -> dict[str, Any]:
        return {
            str(key): value
            for key, value in fields.items()
            if not any(marker in str(key).casefold() for marker in cls._BLOCKED_MARKERS)
        }

    def emit(self, event: str, /, **fields: Any) -> None:
        now = time.monotonic()
        force = bool(fields.pop("force", False)) or event in self._FORCED_EVENTS
        safe = self._safe(fields)
        with self.lock:
            self.phase = str(safe.pop("phase", event))
            self.fields = safe
            if not force and now - self.last < self.interval_seconds:
                return
            self.last = now
            self._write(event, self.phase, safe, now)

    def _write(
        self, event: str, phase: str, fields: Mapping[str, Any], now: float
    ) -> None:
        print(
            json.dumps(
                {
                    "event": event,
                    "phase": phase,
                    "run_id": self.run_id,
                    "elapsed_seconds": round(now - self.started, 3),
                    **fields,
                },
                sort_keys=True,
                default=str,
            ),
            file=sys.stderr,
            flush=True,
        )

    def start(self) -> None:
        def heartbeat() -> None:
            while not self.stop.wait(self.interval_seconds):
                with self.lock:
                    now = time.monotonic()
                    self._write("heartbeat", self.phase, self.fields, now)
                    self.last = now

        self.thread = threading.Thread(
            target=heartbeat,
            name=f"forecast-progress-{self.run_id}",
            daemon=True,
        )
        self.thread.start()

    def close(self) -> None:
        self.stop.set()
        if self.thread is not None:
            self.thread.join(timeout=1.0)


def _git_sha() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def _clean_worktree() -> bool:
    return not subprocess.check_output(
        ["git", "status", "--porcelain=v1"], cwd=ROOT, text=True
    ).strip()


def _utc(value: str) -> datetime:
    parsed = pd.Timestamp(value)
    if parsed.tzinfo is None:
        raise ForecastRunError("--as-of must be timezone-aware")
    return parsed.to_pydatetime().astimezone(timezone.utc)


def _immutable_json(storage: object, uri: str, payload: Mapping[str, Any]) -> None:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=str
    ).encode()
    if storage.exists(uri):
        if storage.read_bytes(uri) != encoded:
            raise ForecastRunError(f"immutable object collision at {uri}")
        return
    storage.write_bytes(encoded, uri)


PARTITIONED_DATASETS = ("forecast_model", "forecast_prediction")
COMPACT_DATASETS = (
    "forecast_registry",
    "forecast_calibration",
    "window_comparison",
    "forecast_selection",
)
DATASET_PARTITION_KEYS = {
    "forecast_model": ("horizon", "outer_season"),
    "forecast_prediction": ("season", "week"),
}


class DatasetPlan:
    def __init__(
        self,
        dataset: str,
        schema_version: str,
        partition_keys: tuple[str, ...],
        parts: tuple[dict[str, Any], ...],
        row_count: int,
        records_sha: str,
    ) -> None:
        self.dataset = dataset
        self.schema_version = schema_version
        self.partition_keys = partition_keys
        self.parts = parts
        self.row_count = row_count
        self.records_sha = records_sha


class ForecastPreflightEvidence:
    def __init__(
        self,
        plans: dict[str, DatasetPlan],
        selected_horizon: str,
        horizon_sha256: str,
        head_metrics: dict[str, Any],
    ) -> None:
        self.plans = plans
        self.selected_horizon = selected_horizon
        self.horizon_sha256 = horizon_sha256
        self.head_metrics = head_metrics


def _load_forecast_preflight_evidence(
    path: Path, *, identity: Mapping[str, Any]
) -> ForecastPreflightEvidence:
    """Load an exact reviewed dry-run plan without trusting it blindly."""
    try:
        payload = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        raise ForecastRunError("preflight evidence is unreadable") from exc
    if payload.get("state") != "dry_run" or payload.get("identity") != dict(identity):
        raise ForecastRunError("preflight evidence identity does not match apply")
    raw_plans = payload.get("preflight_plans")
    if not isinstance(raw_plans, dict) or set(raw_plans) != set(FORECAST_DATASETS) - {
        "candidate_manifest"
    }:
        raise ForecastRunError("preflight evidence lacks the complete part plan")
    plans: dict[str, DatasetPlan] = {}
    for name, (dataset, schema_version) in FORECAST_DATASETS.items():
        if name == "candidate_manifest":
            continue
        raw = raw_plans.get(name)
        expected_keys = list(DATASET_PARTITION_KEYS.get(name, ()))
        if not isinstance(raw, dict) or (
            raw.get("name") != name
            or raw.get("partition_keys") != expected_keys
            or not isinstance(raw.get("parts"), list)
        ):
            raise ForecastRunError(f"preflight evidence has invalid {name} plan")
        parts: tuple[dict[str, Any], ...] = tuple()
        for part in raw["parts"]:
            if not isinstance(part, dict):
                raise ForecastRunError(f"preflight evidence has malformed {name} part")
            partition = part.get("partition")
            row_count = part.get("row_count")
            records_sha = part.get("records_sha")
            if (
                not isinstance(partition, dict)
                or tuple(partition) != tuple(expected_keys)
                or not isinstance(row_count, int)
                or row_count <= 0
                or not isinstance(records_sha, str)
                or len(records_sha) != 64
            ):
                raise ForecastRunError(f"preflight evidence has invalid {name} part")
            if parts and partition_order_key(partition) <= partition_order_key(
                parts[-1]["partition"]
            ):
                raise ForecastRunError(
                    f"preflight evidence has unordered {name} partitions"
                )
            parts = (
                *parts,
                {
                    "partition": partition,
                    "row_count": row_count,
                    "records_sha": records_sha,
                },
            )
        plans[name] = DatasetPlan(
            dataset=dataset,
            schema_version=schema_version,
            partition_keys=tuple(expected_keys),
            parts=parts,
            row_count=int(raw.get("row_count") or 0),
            records_sha=str(raw.get("records_sha") or ""),
        )
    row_counts = payload.get("row_counts")
    output_digests = payload.get("output_records_sha256")
    if row_counts != {
        name: plan.row_count for name, plan in plans.items()
    } or output_digests != {name: plan.records_sha for name, plan in plans.items()}:
        raise ForecastRunError(
            "preflight evidence summary does not match its part plan"
        )
    selected_horizon = payload.get("selected_horizon")
    if selected_horizon not in ("expanding", "latest_five"):
        raise ForecastRunError("preflight evidence has an unknown selected horizon")
    horizon_sha256 = payload.get("horizon_sha256")
    if not isinstance(horizon_sha256, str) or len(horizon_sha256) != 64:
        raise ForecastRunError("preflight evidence lacks its horizon checksum")
    head_metrics = payload.get("head_metrics")
    if not isinstance(head_metrics, dict):
        raise ForecastRunError("preflight evidence lacks head metrics")
    return ForecastPreflightEvidence(
        plans=plans,
        selected_horizon=str(selected_horizon),
        horizon_sha256=horizon_sha256,
        head_metrics=head_metrics,
    )


def _existing_forecast_manifest(
    storage: Any, *, manifest_uri: str, identity: Mapping[str, Any]
) -> dict[str, Any] | None:
    """Validate an existing terminal manifest without replaying its producer."""
    if not storage.exists(manifest_uri):
        return None
    existing = json.loads(storage.read_bytes(manifest_uri))
    try:
        verify_signed_payload(existing, label="existing forecast manifest")
    except ValueError as exc:
        raise ForecastRunError(str(exc)) from exc
    if (existing.get("identity") or {}).get("identity_sha256") != identity[
        "identity_sha256"
    ]:
        raise ForecastRunError("forecast run ID already has a different identity")
    outputs = existing.get("output_refs") or {}
    expected_outputs = set(FORECAST_DATASETS) - {"candidate_manifest"}
    if (
        existing.get("state") != "frozen"
        or existing.get("schema_version") != FORECAST_MANIFEST_SCHEMA
        or existing.get("production_activation_authorized") is not False
        or set(outputs) != expected_outputs
    ):
        raise ForecastRunError("existing forecast manifest is incomplete")
    required_ref_fields = {
        "artifact_kind",
        "dataset",
        "version_id",
        "schema_version",
        "content_sha",
        "records_sha",
        "uri",
        "row_count",
    }
    for name, value in outputs.items():
        dataset, schema_version = FORECAST_DATASETS[name]
        if required_ref_fields - set(value) or (
            value.get("dataset") != dataset
            or value.get("schema_version") != schema_version
        ):
            raise ForecastRunError(f"existing {name} output reference is invalid")
    return existing


def _parent_ref(value: Mapping[str, Any], *, name: str):
    from cks_picks_cfb.data.lake import DatasetRef

    fields = ("dataset", "version_id", "schema_version", "content_sha", "uri")
    if missing := [item for item in fields if not value.get(item)]:
        raise ForecastRunError(
            f"parent output reference is malformed: {name} {missing}"
        )
    return DatasetRef(**{item: value[item] for item in fields})


def _writers(
    storage: Any,
    identity: Mapping[str, Any],
    measurement: Mapping[str, Any],
    repair: Mapping[str, Any],
    evidence: ForecastPreflightEvidence,
) -> dict[str, PartitionedDatasetWriter]:
    parents = (
        _parent_ref(measurement["output_refs"]["population"], name="R6 population"),
        _parent_ref(repair["output_refs"]["population"], name="Repair population"),
    )
    as_of = _utc(str(identity["as_of"]))
    return {
        name: PartitionedDatasetWriter(
            storage,
            build=BuildRequest(
                dataset=FORECAST_DATASETS[name][0],
                parent_refs=parents,
                code_sha=str(identity["code_sha"]),
                config_sha=str(identity["config_sha"]),
                as_of=as_of,
                schema_version=FORECAST_DATASETS[name][1],
                tier="gold",
            ),
            partition_keys=evidence.plans[name].partition_keys,
            expected_parts={
                partition_key(part["partition"]): dict(part)
                for part in evidence.plans[name].parts
            },
            max_workers=8,
        )
        for name in PARTITIONED_DATASETS
    }


class _CompactWrite:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []
        self.row_count: int = 0
        self.records_sha: str = ""


def apply(
    *,
    storage: Any,
    args: argparse.Namespace,
    identity: Mapping[str, Any],
    evidence: ForecastPreflightEvidence,
) -> dict[str, Any]:
    """Recompute the forecast and publish it exactly as the evidence plans."""
    prefix = f"{FORECAST_OUTPUT_ROOT}/{args.run_id}"
    manifest_uri = f"{prefix}/{FORECAST_MANIFEST_NAME}"
    if (
        _existing_forecast_manifest(
            storage, manifest_uri=manifest_uri, identity=identity
        )
        is not None
    ):
        return {"state": "already_applied", "manifest_uri": manifest_uri}
    preexisting = sorted(storage.list_files(prefix))
    if preexisting:
        raise ForecastRunError(
            "forecast run prefix has a partial artifact and is permanently ineligible"
        )

    rating_raw = storage.read_bytes(args.rating_manifest_uri)
    measurement_raw = storage.read_bytes(args.measurement_manifest_uri)
    repair_raw = storage.read_bytes(args.repair_manifest_uri)
    rating, measurement, repair = (
        json.loads(rating_raw),
        json.loads(measurement_raw),
        json.loads(repair_raw),
    )
    verify_rating_parent(
        rating,
        rating_manifest_uri=args.rating_manifest_uri,
        rating_raw_sha256=hashlib.sha256(rating_raw).hexdigest(),
        measurement=measurement,
        measurement_manifest_uri=args.measurement_manifest_uri,
        measurement_raw_sha256=hashlib.sha256(measurement_raw).hexdigest(),
        repair=repair,
        repair_manifest_uri=args.repair_manifest_uri,
        repair_raw_sha256=hashlib.sha256(repair_raw).hexdigest(),
    )

    progress = _Progress(args.run_id)
    progress.start()
    atexit.register(progress.close)
    progress.emit("apply_started", force=True)

    config = yaml.safe_load(Path(args.config).read_text())
    validate_config(config)
    selection = config["selection"]
    bridge = config["bridge"]

    _immutable_json(
        storage,
        f"{prefix}/publication-plan.json",
        {
            "identity": dict(identity),
            "selected_horizon": evidence.selected_horizon,
            "horizon_sha256": evidence.horizon_sha256,
            "plans": {
                name: {
                    "row_count": plan.row_count,
                    "records_sha": plan.records_sha,
                    "parts": [dict(part) for part in plan.parts],
                }
                for name, plan in evidence.plans.items()
            },
            "production_activation_authorized": False,
        },
    )

    writers = _writers(storage, identity, measurement, repair, evidence)
    compact: dict[str, _CompactWrite] = {
        name: _CompactWrite() for name in COMPACT_DATASETS
    }
    dataset_of = {name: FORECAST_DATASETS[name][0] for name in FORECAST_DATASETS}

    def sink(name: str, partition: Mapping[str, Any], frame: pd.DataFrame) -> None:
        if name in compact:
            plan = evidence.plans[name]
            schema = schema_for(FORECAST_DATASETS[name][0], FORECAST_DATASETS[name][1])
            records_sha = canonical_frame_digest(frame, columns=schema.required)
            if len(frame) != plan.row_count or records_sha != plan.records_sha:
                raise ForecastRunError(
                    f"apply recomputation differs from preflight: {name}"
                )
            compact[name].records = frame.loc[:, list(schema.required)].to_dict(
                "records"
            )
            compact[name].row_count = int(len(frame))
            compact[name].records_sha = records_sha
        else:
            progress.emit(
                "apply_partition",
                dataset=dataset_of[name],
                partition=dict(partition),
                rows=int(len(frame)),
            )
            writers[name].add(PartitionedDatasetPart(dict(partition), frame))

    rating_inputs = load_rating_inputs(
        storage=storage,
        measurement=measurement,
        repair=repair,
        progress=progress.emit,
    )
    scoring_events = _stream_output(
        storage,
        name="scoring_events",
        value=measurement["output_refs"]["scoring_events"],
        progress=progress.emit,
    )
    team_states = _stream_partitioned(
        storage,
        value=rating["output_refs"]["team_states"],
        dataset="possession_team_state",
        schema="data_first_possession_team_state_v1",
        columns=list(TEAM_STATE_COLUMNS),
    )
    offsets = build_offsets(
        rating_inputs.population,
        scoring_events,
        development_seasons=tuple(config["development_seasons"]),
        equivalent_games=int(config["offsets"]["equivalent_games"]),
    )
    features = _feature_frame(
        population=rating_inputs.population,
        outcomes=rating_inputs.outcomes,
        team_states=team_states,
        offsets=offsets.offsets,
    )
    computations: dict[str, Any] = {}
    for horizon in config["horizons"]:
        computations[horizon] = evaluate_heads(
            features,
            horizon=horizon,
            development_seasons=tuple(config["development_seasons"]),
            outer_seasons=tuple(selection["outer_seasons"]),
            reporting_seasons=tuple(selection["reporting_seasons"]),
            alpha_grid=tuple(bridge["alpha_grid"]),
            floor=float(bridge["scaling_floor"]),
            bootstrap_seed=int(selection["bootstrap_seed"]),
            bootstrap_samples=int(selection["bootstrap_replicates"]),
        )
    retained = {
        horizon: computation.predictions.merge(
            pd.DataFrame(
                [
                    {"target": target, "head": head}
                    for target, head in computation.retained.items()
                ]
            ),
            on=["target", "head"],
            how="inner",
            validate="many_to_one",
        )
        for horizon, computation in computations.items()
    }
    selected_horizon, comparison = select_horizon(
        retained["expanding"],
        retained["latest_five"],
        seed=int(selection["bootstrap_seed"]),
        samples=int(selection["bootstrap_replicates"]),
    )
    if selected_horizon != evidence.selected_horizon:
        raise ForecastRunError(
            "apply replay selected a different horizon than preflight"
        )
    calibration = calibrate_uncertainty(
        features,
        horizon=selected_horizon,
        development_seasons=tuple(config["development_seasons"]),
        outer_seasons=tuple(selection["outer_seasons"]),
        alpha_grid=tuple(bridge["alpha_grid"]),
        floor=float(bridge["scaling_floor"]),
        residual_floor=float(config["calibration"]["residual_floor"]),
    )
    predictions = retained[selected_horizon].copy()
    models = computations[selected_horizon].models.copy()
    final_models, final_calibration = _final_fit_outputs(
        features,
        calibration.records,
        horizon=selected_horizon,
        retained=computations[selected_horizon].retained,
        development_seasons=tuple(config["development_seasons"]),
        alpha_grid=tuple(bridge["alpha_grid"]),
        floor=float(bridge["scaling_floor"]),
    )
    progress.emit(
        "final_fit_complete",
        rows=int(len(final_models) + len(final_calibration)),
    )
    models = pd.concat([models, final_models], ignore_index=True)
    calibration_records = pd.concat(
        [calibration.records, final_calibration], ignore_index=True
    )
    registry = pd.DataFrame.from_records(
        [
            {
                "horizon": horizon,
                "target": target,
                "reference_alpha": 10.0,
                "alpha_grid": ",".join(map(str, bridge["alpha_grid"])),
            }
            for horizon in config["horizons"]
            for target in ("margin", "total")
        ]
    )
    selection_frame = pd.DataFrame.from_records(
        [
            {
                "selected_horizon": selected_horizon,
                "target": target,
                "selected_head": computations[selected_horizon].retained[target],
                "selection_reason": "latest_five_gates_passed"
                if selected_horizon == "latest_five"
                else "retain_expanding",
                "horizon_sha256": evidence.horizon_sha256,
            }
            for target in ("margin", "total")
        ]
    )
    outputs = {
        "forecast_registry": (registry, FORECAST_REGISTRY_COLUMNS, ()),
        "forecast_model": (
            models,
            FORECAST_MODEL_COLUMNS,
            ("horizon", "outer_season"),
        ),
        "forecast_prediction": (
            predictions,
            FORECAST_PREDICTION_COLUMNS,
            ("season", "week"),
        ),
        "forecast_calibration": (
            calibration_records,
            FORECAST_CALIBRATION_COLUMNS,
            (),
        ),
        "window_comparison": (comparison, WINDOW_COMPARISON_COLUMNS, ()),
        "forecast_selection": (selection_frame, FORECAST_SELECTION_COLUMNS, ()),
    }
    for name, (frame, _columns, keys) in outputs.items():
        dataset, schema = FORECAST_DATASETS[name]
        validate_frame(frame, schema_for(dataset, schema))
        if name in PARTITIONED_DATASETS and keys:
            for partition_values, group in frame.groupby(
                list(keys), sort=True, dropna=False
            ):
                partition_values = (
                    partition_values
                    if isinstance(partition_values, tuple)
                    else (partition_values,)
                )
                partition = {
                    key: value.item() if hasattr(value, "item") else value
                    for key, value in zip(keys, partition_values, strict=True)
                }
                sink(name, partition, group)
        else:
            sink(name, {}, frame)

    refs: dict[str, dict[str, Any]] = {}
    for name, writer in writers.items():
        ref = writer.finish()
        plan = evidence.plans[name]
        if ref.records_sha != plan.records_sha or ref.row_count != plan.row_count:
            raise ForecastRunError(
                f"apply replay differs from same-code preflight: {name}"
            )
        refs[name] = {
            "artifact_kind": ref.artifact_kind,
            "dataset": ref.dataset,
            "version_id": ref.version_id,
            "schema_version": ref.schema_version,
            "content_sha": ref.content_sha,
            "records_sha": ref.records_sha,
            "uri": ref.uri,
            "row_count": ref.row_count,
        }
    as_of = _utc(str(identity["as_of"]))
    parents_ref = (
        _parent_ref(measurement["output_refs"]["population"], name="R6 population"),
        _parent_ref(repair["output_refs"]["population"], name="Repair population"),
    )
    for name, write in compact.items():
        dataset, schema_version = FORECAST_DATASETS[name]
        ref, _ = build_dataset_version(
            storage,
            build=BuildRequest(
                dataset=dataset,
                parent_refs=parents_ref,
                code_sha=str(identity["code_sha"]),
                config_sha=str(identity["config_sha"]),
                as_of=as_of,
                schema_version=schema_version,
                tier="gold",
            ),
            records=write.records,
        )
        refs[name] = {
            "artifact_kind": "dataset_v1",
            "dataset": ref.dataset,
            "version_id": ref.version_id,
            "schema_version": ref.schema_version,
            "content_sha": ref.content_sha,
            "records_sha": write.records_sha,
            "uri": ref.uri,
            "row_count": write.row_count,
        }

    validation_models = models[models["outer_season"] != FINAL_FIT_SEASON]
    final_rows = models[models["outer_season"] == FINAL_FIT_SEASON]
    head_recipes = {}
    for target in ("margin", "total"):
        retained_head = computations[selected_horizon].retained[target]
        challenger_rows = validation_models[
            (validation_models["target"] == target)
            & (validation_models["head"] == "challenger")
            & validation_models["retained"].astype(bool)
        ]
        final_row = final_rows[final_rows["target"] == target]
        if final_row.empty:
            raise ForecastRunError(f"final fit is missing for {target!r}")
        head_recipes[target] = {
            "head": retained_head,
            "alpha": 10.0
            if retained_head == "reference"
            else float(challenger_rows["alpha"].iloc[0])
            if not challenger_rows.empty
            else 10.0,
            "final_alpha": float(final_row["alpha"].iloc[0]),
            "final_training_seasons": str(final_row["training_seasons"].iloc[0]),
        }
    calibration_summary = {
        "records_sha": canonical_frame_digest(
            calibration_records, columns=tuple(calibration_records.columns)
        ),
        "row_count": len(calibration_records),
        "by_target": {
            target: {int(season): variance for season, variance in seasons.items()}
            for target, seasons in calibration.variances.items()
        },
    }
    preflight_sha = hashlib.sha256(
        json.dumps(
            {name: plan.records_sha for name, plan in evidence.plans.items()},
            sort_keys=True,
        ).encode()
    ).hexdigest()
    manifest = forecast_manifest(
        identity=identity,
        parents={
            "rating_manifest_uri": args.rating_manifest_uri,
            "rating_manifest_raw_sha256": hashlib.sha256(rating_raw).hexdigest(),
            "measurement_manifest_uri": args.measurement_manifest_uri,
            "measurement_manifest_raw_sha256": hashlib.sha256(
                measurement_raw
            ).hexdigest(),
            "repair_manifest_uri": args.repair_manifest_uri,
            "repair_manifest_raw_sha256": hashlib.sha256(repair_raw).hexdigest(),
        },
        output_refs=refs,
        selected_horizon=selected_horizon,
        head_recipes=head_recipes,
        calibration_summary=calibration_summary,
        preflight_sha=preflight_sha,
        horizon_sha=evidence.horizon_sha256,
    )
    _immutable_json(storage, f"{prefix}/identity.json", dict(identity))
    for name, ref in refs.items():
        _immutable_json(storage, f"{prefix}/{name}-ref.json", ref)
    _immutable_json(storage, manifest_uri, manifest)
    progress.emit("apply_complete", force=True, manifest_uri=manifest_uri)
    progress.close()
    return {
        "state": "applied",
        "manifest_uri": manifest_uri,
        "selected_horizon": selected_horizon,
        "already_applied": False,
    }


def _read_json(storage: Any, uri: str) -> tuple[dict[str, Any], bytes]:
    raw = storage.read_bytes(uri)
    try:
        return json.loads(raw), raw
    except json.JSONDecodeError as exc:
        raise ForecastRunError(f"unreadable manifest: {uri}") from exc


def _stream_partitioned(
    storage: Any,
    *,
    value: Mapping[str, Any],
    dataset: str,
    schema: str,
    columns: list[str],
) -> pd.DataFrame:
    ref = _partitioned_ref(value, name=dataset)
    if ref.dataset != dataset or ref.schema_version != schema:
        raise ForecastRunError(f"retained rating output identity mismatch: {dataset}")
    _, parts = _manifest_parts(storage, ref)
    frames = [
        _read_child(storage, dataset=dataset, schema_version=schema, part=part)
        for part in parts
    ]
    return _concat_frames(frames, columns=columns) if frames else pd.DataFrame()


def _plan(
    name: str,
    frame: pd.DataFrame,
    columns: tuple[str, ...],
    partition_keys: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Record deterministic compact or bounded partition membership without writes."""
    if not partition_keys:
        return {
            "name": name,
            "partition_keys": [],
            "parts": [],
            "row_count": len(frame),
            "records_sha": canonical_frame_digest(frame, columns=columns),
        }
    parts: list[dict[str, Any]] = []
    for values, group in frame.groupby(list(partition_keys), sort=True, dropna=False):
        values = values if isinstance(values, tuple) else (values,)
        partition = {
            key: value.item() if hasattr(value, "item") else value
            for key, value in zip(partition_keys, values, strict=True)
        }
        parts.append(
            {
                "partition": partition,
                "row_count": len(group),
                "records_sha": canonical_frame_digest(group, columns=columns),
            }
        )
    parts.sort(key=lambda item: partition_order_key(item["partition"]))
    return {
        "name": name,
        "partition_keys": list(partition_keys),
        "parts": parts,
        "row_count": len(frame),
        "records_sha": partitioned_records_sha(parts, partition_keys),
    }


def _retained_rows(frame: pd.DataFrame, *, target: str, head: str) -> pd.DataFrame:
    if frame.empty:
        return frame
    return frame[frame["target"].eq(target) & frame["head"].eq(head)]


def _slice_metrics(frame: pd.DataFrame, key: str) -> dict[str, dict[str, float]]:
    slices: dict[str, dict[str, float]] = {}
    if frame.empty:
        return slices
    for value, group in frame.groupby(key, sort=True):
        slices[str(int(value))] = {
            "mae": float(group["absolute_error"].mean()),
            "gaussian_crps": float(group["gaussian_crps"].mean()),
            "n": int(len(group)),
        }
    return slices


def _head_metrics_block(computations: Mapping[str, Any]) -> dict[str, Any]:
    """Build the expanded, deterministic per-horizon/per-target metric block."""
    block: dict[str, Any] = {}
    for horizon, computation in computations.items():
        block[horizon] = {}
        for target, head in computation.retained.items():
            selection = _retained_rows(
                computation.predictions, target=target, head=head
            )
            reporting = _retained_rows(
                computation.reporting_predictions, target=target, head=head
            )
            block[horizon][target] = {
                "head": head,
                "selection": {
                    "pooled": {
                        "mae": float(selection["absolute_error"].mean()),
                        "gaussian_crps": float(selection["gaussian_crps"].mean()),
                        "n": int(len(selection)),
                    },
                    "by_season": _slice_metrics(selection, "season"),
                    "by_completed_game_stage": _slice_metrics(
                        selection, "completed_game_stage"
                    ),
                },
                "reporting": {
                    "by_season": _slice_metrics(reporting, "season"),
                },
            }
    return block


def _horizon_populations(computations: Mapping[str, Any]) -> dict[str, Any]:
    """Per-horizon retained-head selection row counts for population equality."""
    return {
        horizon: {
            target: int(
                len(_retained_rows(computation.predictions, target=target, head=head))
            )
            for target, head in computation.retained.items()
        }
        for horizon, computation in computations.items()
    }


def _final_fit_outputs(
    features: pd.DataFrame,
    calibration_records: pd.DataFrame,
    *,
    horizon: str,
    retained: Mapping[str, str],
    development_seasons: tuple[int, ...],
    alpha_grid: tuple[float, ...],
    floor: float,
    calibration_source_season: int = 2025,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build through-window final-fit model and calibration rows (Contract 11C).

    One ``forecast_model`` row per target with ``outer_season == 0``
    (``FINAL_FIT_SEASON``: no validation season exists for a final fit) trained
    on every development season, plus one ``forecast_calibration`` row per
    target carrying the design's latest rolling-origin variance.  No
    predictions are emitted.  Fail closed when the carried calibration entry
    is a fallback or missing.
    """
    model_rows: list[dict[str, object]] = []
    calibration_rows: list[dict[str, object]] = []
    for target in ("margin", "total"):
        recipe = fit_final(
            features,
            target=target,
            head=retained[target],
            development_seasons=tuple(development_seasons),
            alpha_grid=tuple(alpha_grid),
            floor=float(floor),
        )
        model_rows.append(
            {
                "horizon": horizon,
                "target": target,
                "outer_season": FINAL_FIT_SEASON,
                "head": recipe["head"],
                "alpha": recipe["alpha"],
                "training_seasons": ",".join(map(str, recipe["training_seasons"])),
                "inner_fallback": recipe["inner_fallback"],
                "retained": True,
                "fallback_reason": "insufficient_inner_fold"
                if recipe["inner_fallback"]
                else None,
            }
        )
        source = calibration_records[
            (calibration_records["target"] == target)
            & (calibration_records["season"] == calibration_source_season)
        ]
        if source.empty:
            raise ForecastRunError(
                f"final fit has no {calibration_source_season} calibration entry "
                f"for {target!r}"
            )
        entry = source.iloc[0]
        if (
            str(entry["fallback_reason"] or "") != ""
            or int(entry["residual_count"]) <= 0
        ):
            raise ForecastRunError(
                f"final fit cannot carry a fallback calibration entry for {target!r}"
            )
        calibration_rows.append(
            {
                "target": target,
                "season": FINAL_FIT_SEASON,
                "residual_count": int(entry["residual_count"]),
                "variance": float(entry["variance"]),
                "fallback_reason": "",
            }
        )
    return (
        pd.DataFrame.from_records(model_rows),
        pd.DataFrame.from_records(calibration_rows),
    )


def preflight(
    *, storage: Any, args: argparse.Namespace, progress: _Progress
) -> dict[str, Any]:
    progress.emit("preflight_started", run_id=args.run_id, as_of=args.as_of)
    config = yaml.safe_load(Path(args.config).read_text())
    validate_config(config)
    selection = config["selection"]
    rating, rating_raw = _read_json(storage, args.rating_manifest_uri)
    measurement, measurement_raw = _read_json(storage, args.measurement_manifest_uri)
    repair, repair_raw = _read_json(storage, args.repair_manifest_uri)
    parents = verify_rating_parent(
        rating,
        rating_manifest_uri=args.rating_manifest_uri,
        rating_raw_sha256=hashlib.sha256(rating_raw).hexdigest(),
        measurement=measurement,
        measurement_manifest_uri=args.measurement_manifest_uri,
        measurement_raw_sha256=hashlib.sha256(measurement_raw).hexdigest(),
        repair=repair,
        repair_manifest_uri=args.repair_manifest_uri,
        repair_raw_sha256=hashlib.sha256(repair_raw).hexdigest(),
    )
    identity = forecast_identity(
        run_id=args.run_id,
        as_of=args.as_of,
        code_sha=args.expected_code_sha,
        config_sha=hashlib.sha256(Path(args.config).read_bytes()).hexdigest(),
        parents={
            "rating_manifest_uri": parents["rating_manifest_uri"],
            "rating_raw_sha256": parents["rating_raw_sha256"],
            "measurement_manifest_uri": parents["measurement_manifest_uri"],
            "measurement_raw_sha256": parents["measurement_raw_sha256"],
            "repair_manifest_uri": parents["repair_manifest_uri"],
            "repair_raw_sha256": parents["repair_raw_sha256"],
        },
    )
    progress.emit(
        "parents_loaded",
        rating_parent=rating["identity"]["run_id"],
        measurement_parent=measurement["identity"]["run_id"],
        repair_parent=repair["identity"]["run_id"],
    )
    # Reuse 03's audited source loading.  It validates bounded parent parts and
    # chronology before any forecast feature is formed.
    rating_inputs = load_rating_inputs(
        storage=storage,
        measurement=measurement,
        repair=repair,
        progress=progress.emit,
    )
    progress.emit("source_streamed", source="rating_inputs")
    scoring_events = _stream_output(
        storage,
        name="scoring_events",
        value=measurement["output_refs"]["scoring_events"],
        progress=progress.emit,
    )
    progress.emit("source_streamed", source="scoring_events", rows=len(scoring_events))
    team_states = _stream_partitioned(
        storage,
        value=rating["output_refs"]["team_states"],
        dataset="possession_team_state",
        schema="data_first_possession_team_state_v1",
        columns=list(TEAM_STATE_COLUMNS),
    )
    progress.emit("source_streamed", source="team_states", rows=len(team_states))
    offsets = build_offsets(
        rating_inputs.population,
        scoring_events,
        development_seasons=tuple(config["development_seasons"]),
        equivalent_games=int(config["offsets"]["equivalent_games"]),
    )
    progress.emit("offsets_built", rows=len(offsets.offsets))
    features = _feature_frame(
        population=rating_inputs.population,
        outcomes=rating_inputs.outcomes,
        team_states=team_states,
        offsets=offsets.offsets,
    )
    bridge = config["bridge"]
    computations: dict[str, Any] = {}
    for horizon in config["horizons"]:
        progress.emit("horizon_started", horizon=horizon)
        computations[horizon] = evaluate_heads(
            features,
            horizon=horizon,
            development_seasons=tuple(config["development_seasons"]),
            outer_seasons=tuple(selection["outer_seasons"]),
            reporting_seasons=tuple(selection["reporting_seasons"]),
            alpha_grid=tuple(bridge["alpha_grid"]),
            floor=float(bridge["scaling_floor"]),
            bootstrap_seed=int(selection["bootstrap_seed"]),
            bootstrap_samples=int(selection["bootstrap_replicates"]),
        )
        progress.emit("horizon_complete", horizon=horizon)
    retained = {
        horizon: computation.predictions.merge(
            pd.DataFrame(
                [
                    {"target": target, "head": head}
                    for target, head in computation.retained.items()
                ]
            ),
            on=["target", "head"],
            how="inner",
            validate="many_to_one",
        )
        for horizon, computation in computations.items()
    }
    selected_horizon, comparison = select_horizon(
        retained["expanding"],
        retained["latest_five"],
        seed=int(selection["bootstrap_seed"]),
        samples=int(selection["bootstrap_replicates"]),
    )
    progress.emit("horizon_selected", selected_horizon=selected_horizon)
    progress.emit("calibration_started")
    calibration = calibrate_uncertainty(
        features,
        horizon=selected_horizon,
        development_seasons=tuple(config["development_seasons"]),
        outer_seasons=tuple(selection["outer_seasons"]),
        alpha_grid=tuple(bridge["alpha_grid"]),
        floor=float(bridge["scaling_floor"]),
        residual_floor=float(config["calibration"]["residual_floor"]),
    )
    progress.emit("calibration_complete", rows=len(calibration.records))
    predictions = retained[selected_horizon].copy()
    models = computations[selected_horizon].models.copy()
    final_models, final_calibration = _final_fit_outputs(
        features,
        calibration.records,
        horizon=selected_horizon,
        retained=computations[selected_horizon].retained,
        development_seasons=tuple(config["development_seasons"]),
        alpha_grid=tuple(bridge["alpha_grid"]),
        floor=float(bridge["scaling_floor"]),
    )
    progress.emit(
        "final_fit_complete",
        rows=int(len(final_models) + len(final_calibration)),
    )
    models = pd.concat([models, final_models], ignore_index=True)
    calibration_records = pd.concat(
        [calibration.records, final_calibration], ignore_index=True
    )
    registry = pd.DataFrame.from_records(
        [
            {
                "horizon": horizon,
                "target": target,
                "reference_alpha": 10.0,
                "alpha_grid": ",".join(map(str, bridge["alpha_grid"])),
            }
            for horizon in config["horizons"]
            for target in ("margin", "total")
        ]
    )
    horizon_sha = hashlib.sha256(
        comparison.to_json(
            orient="records", date_format="iso", double_precision=15
        ).encode()
    ).hexdigest()
    selection_frame = pd.DataFrame.from_records(
        [
            {
                "selected_horizon": selected_horizon,
                "target": target,
                "selected_head": computations[selected_horizon].retained[target],
                "selection_reason": "latest_five_gates_passed"
                if selected_horizon == "latest_five"
                else "retain_expanding",
                "horizon_sha256": horizon_sha,
            }
            for target in ("margin", "total")
        ]
    )
    outputs = {
        "forecast_registry": (registry, FORECAST_REGISTRY_COLUMNS, ()),
        "forecast_model": (
            models,
            FORECAST_MODEL_COLUMNS,
            ("horizon", "outer_season"),
        ),
        "forecast_prediction": (
            predictions,
            FORECAST_PREDICTION_COLUMNS,
            ("season", "week"),
        ),
        "forecast_calibration": (
            calibration_records,
            FORECAST_CALIBRATION_COLUMNS,
            (),
        ),
        "window_comparison": (comparison, WINDOW_COMPARISON_COLUMNS, ()),
        "forecast_selection": (selection_frame, FORECAST_SELECTION_COLUMNS, ()),
    }
    for name, (frame, _columns, _keys) in outputs.items():
        dataset, schema = FORECAST_DATASETS[name]
        validate_frame(frame, schema_for(dataset, schema))
    plans = {
        name: _plan(name, frame, columns, keys)
        for name, (frame, columns, keys) in outputs.items()
    }
    evidence = {
        "state": "dry_run",
        "identity": identity,
        "parent_uris": {
            "rating_manifest_uri": parents["rating_manifest_uri"],
            "measurement_manifest_uri": parents["measurement_manifest_uri"],
            "repair_manifest_uri": parents["repair_manifest_uri"],
        },
        "rating_parent": rating["identity"]["run_id"],
        "measurement_parent": measurement["identity"]["run_id"],
        "repair_parent": repair["identity"]["run_id"],
        "selection_seasons": list(selection["outer_seasons"]),
        "reporting_seasons": list(selection["reporting_seasons"]),
        "offsets_sha256": canonical_frame_digest(
            offsets.offsets, columns=tuple(offsets.offsets.columns)
        ),
        "head_metrics": _head_metrics_block(computations),
        "horizon_populations": _horizon_populations(computations),
        "selected_horizon": selected_horizon,
        "horizon_sha256": horizon_sha,
        "preflight_plans": plans,
        "row_counts": {name: value["row_count"] for name, value in plans.items()},
        "output_records_sha256": {
            name: value["records_sha"] for name, value in plans.items()
        },
        "calibration": {
            "records_sha": canonical_frame_digest(
                calibration_records, columns=tuple(calibration_records.columns)
            ),
            "row_count": len(calibration_records),
            "by_target": {
                target: {int(season): variance for season, variance in seasons.items()}
                for target, seasons in calibration.variances.items()
            },
        },
        "production_activation_authorized": False,
    }
    progress.emit("evidence_constructed")
    return evidence


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--environment", required=True, choices=("preview",))
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--rating-manifest-uri", required=True)
    parser.add_argument("--measurement-manifest-uri", required=True)
    parser.add_argument("--repair-manifest-uri", required=True)
    parser.add_argument("--v4-benchmark-manifest-uri")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--preflight-evidence",
        help="reviewed dry-run JSON used for a write-only apply",
    )
    args = parser.parse_args(argv)
    if _git_sha() != args.expected_code_sha:
        raise ForecastRunError("expected code SHA does not match committed HEAD")
    if bool(args.preflight_evidence) != bool(args.apply):
        raise ForecastRunError("--apply and --preflight-evidence must be used together")
    storage = get_storage(environment="preview")
    if args.apply:
        if not _clean_worktree():
            raise ForecastRunError(
                "apply requires a completely clean committed worktree"
            )
        validate_config(yaml.safe_load(Path(args.config).read_text()))
        identity = forecast_identity(
            run_id=args.run_id,
            as_of=args.as_of,
            code_sha=args.expected_code_sha,
            config_sha=hashlib.sha256(Path(args.config).read_bytes()).hexdigest(),
            parents={
                "rating_manifest_uri": args.rating_manifest_uri,
                "rating_raw_sha256": hashlib.sha256(
                    storage.read_bytes(args.rating_manifest_uri)
                ).hexdigest(),
                "measurement_manifest_uri": args.measurement_manifest_uri,
                "measurement_raw_sha256": hashlib.sha256(
                    storage.read_bytes(args.measurement_manifest_uri)
                ).hexdigest(),
                "repair_manifest_uri": args.repair_manifest_uri,
                "repair_raw_sha256": hashlib.sha256(
                    storage.read_bytes(args.repair_manifest_uri)
                ).hexdigest(),
            },
        )
        evidence = _load_forecast_preflight_evidence(
            Path(args.preflight_evidence), identity=identity
        )
        result = apply(
            storage=storage,
            args=args,
            identity=identity,
            evidence=evidence,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    progress = _Progress(args.run_id)
    progress.start()
    try:
        evidence = preflight(storage=storage, args=args, progress=progress)
        print(
            json.dumps(
                evidence,
                indent=2,
                sort_keys=True,
                default=str,
            )
        )
        progress.emit(
            "dry_run_complete", identity=evidence["identity"]["identity_sha256"]
        )
    finally:
        progress.close()


if __name__ == "__main__":
    main()
