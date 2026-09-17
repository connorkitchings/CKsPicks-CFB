#!/usr/bin/env python3
"""Preflight and evidence-bound apply for the sealed V5-03 rating tournament.

The dry run loads the exact R6/Repair v2 parents read-only, constructs every
chronological prior and pregame state for the sealed 60-candidate registry,
runs the common bridge and selection tournament, and prints complete
deterministic preflight evidence (part plans, row counts, record digests, and
the selected identity).

The apply path is exclusively evidence-bound: it requires the reviewed JSON of
a dry run with the exact same identity, recomputes the tournament, compares
every canonical partition to that evidence before enqueueing its immutable
write, and publishes the terminal retained-rating manifest last.  A partial or
failed prefix can never be repaired into eligibility.
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
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload
from cks_picks_cfb.data.data_first_possession_rating_v1 import (
    POSSESSION_RATING_OUTPUT_ROOT,
    RATING_DATASETS,
    candidate_registry,
    rating_identity,
    retained_manifest,
    validate_config,
    verify_parents,
)
from cks_picks_cfb.data.lake import (
    BuildRequest,
    DatasetRef,
    PartitionedDatasetPart,
    PartitionedDatasetWriter,
    build_dataset_version,
    canonical_frame_digest,
    partition_key,
    partition_order_key,
)
from cks_picks_cfb.data.schema_contracts import schema_for
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ratings.possession_rating_materializer import (
    DatasetPlan,
    compute_tournament,
    load_rating_inputs,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "conf/research/data_first_football_v1/possession_rating_v1.yaml"

RATING_MANIFEST_NAME = "retained-rating-manifest.json"
COMPACT_DATASETS = ("rating_registry", "attribution")
PARTITIONED_DATASETS = (
    "priors",
    "noise_fits",
    "rating_states",
    "team_states",
    "bridge_predictions",
)
DATASET_PARTITION_KEYS = {
    "priors": ("season",),
    "noise_fits": ("season",),
    "rating_states": ("season", "week"),
    "team_states": ("season", "week"),
    "bridge_predictions": ("season", "week"),
}


class PossessionRatingRunError(ValueError):
    """Raised before a V5-03 run can produce immutable output."""


class _Progress:
    """Bounded, secret-safe stderr progress heartbeat for long phases."""

    def __init__(self, run_id: str, interval_seconds: float = 30.0) -> None:
        self.run_id = run_id
        self.interval_seconds = interval_seconds
        self.started = time.monotonic()
        self.last = float("-inf")
        self.phase = "initializing"
        self.context: dict[str, Any] = {}
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.thread: threading.Thread | None = None

    @staticmethod
    def _safe(fields: Mapping[str, Any]) -> dict[str, Any]:
        blocked = ("credential", "password", "secret", "token", "access_key")
        return {
            str(key): value
            for key, value in fields.items()
            if not any(marker in str(key).casefold() for marker in blocked)
        }

    def emit(self, event: str, /, **fields: Any) -> None:
        now = time.monotonic()
        safe = self._safe(fields)
        with self.lock:
            self.phase = str(safe.pop("phase", event))
            self.context = safe
            if now - self.last < self.interval_seconds and event != "heartbeat":
                if event not in {
                    "tournament_started",
                    "r6_stream_started",
                    "history_audit_started",
                    "apply_started",
                }:
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
                    self._write("heartbeat", self.phase, self.context, now)
                    self.last = now

        self.thread = threading.Thread(
            target=heartbeat,
            name=f"possession-rating-progress-{self.run_id}",
            daemon=True,
        )
        self.thread.start()

    def close(self) -> None:
        self.stop.set()
        if self.thread is not None:
            self.thread.join(timeout=min(self.interval_seconds, 1.0))


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
        raise PossessionRatingRunError("--as-of must be timezone-aware")
    return parsed.to_pydatetime().astimezone(timezone.utc)


def _immutable_json(storage: object, uri: str, payload: Mapping[str, Any]) -> None:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=str
    ).encode()
    if storage.exists(uri):
        if storage.read_bytes(uri) != encoded:
            raise PossessionRatingRunError(f"immutable object collision at {uri}")
        return
    storage.write_bytes(encoded, uri)


@dataclass
class RatingPreflightEvidence:
    """Reviewed dry-run evidence an evidence-bound apply must reproduce."""

    plans: dict[str, DatasetPlan]
    selected_candidate: str
    selection_sha256: str
    candidate_status: dict[str, str]


def _load_rating_preflight_evidence(
    path: Path, *, identity: Mapping[str, Any]
) -> RatingPreflightEvidence:
    """Load an exact reviewed dry-run plan without trusting it blindly."""
    try:
        payload = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        raise PossessionRatingRunError("preflight evidence is unreadable") from exc
    if payload.get("state") != "dry_run" or payload.get("identity") != dict(identity):
        raise PossessionRatingRunError(
            "preflight evidence identity does not match apply"
        )
    raw_plans = payload.get("preflight_plans")
    if not isinstance(raw_plans, dict) or set(raw_plans) != set(RATING_DATASETS):
        raise PossessionRatingRunError(
            "preflight evidence lacks the complete part plan"
        )

    plans: dict[str, DatasetPlan] = {}
    for name, (dataset, schema_version) in RATING_DATASETS.items():
        raw = raw_plans.get(name)
        expected_keys = list(DATASET_PARTITION_KEYS.get(name, ()))
        if not isinstance(raw, dict) or (
            raw.get("dataset") != dataset
            or raw.get("schema_version") != schema_version
            or raw.get("partition_keys") != expected_keys
            or not isinstance(raw.get("parts"), list)
        ):
            raise PossessionRatingRunError(
                f"preflight evidence has invalid {name} plan"
            )
        parts: tuple[dict[str, Any], ...] = tuple()
        for part in raw["parts"]:
            if not isinstance(part, dict):
                raise PossessionRatingRunError(
                    f"preflight evidence has malformed {name} part"
                )
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
                raise PossessionRatingRunError(
                    f"preflight evidence has invalid {name} part"
                )
            if parts and partition_order_key(partition) <= partition_order_key(
                parts[-1]["partition"]
            ):
                raise PossessionRatingRunError(
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
        raise PossessionRatingRunError(
            "preflight evidence summary does not match its part plan"
        )
    selected = payload.get("selected_candidate")
    if selected not in {entry["candidate_id"] for entry in candidate_registry()}:
        raise PossessionRatingRunError("preflight evidence has an unsealed candidate")
    selection_sha256 = payload.get("selection_sha256")
    if not isinstance(selection_sha256, str) or len(selection_sha256) != 64:
        raise PossessionRatingRunError(
            "preflight evidence lacks its selection checksum"
        )
    status = payload.get("candidate_status")
    if not isinstance(status, dict) or set(status) != {
        entry["candidate_id"] for entry in candidate_registry()
    }:
        raise PossessionRatingRunError("preflight evidence lacks candidate status")
    return RatingPreflightEvidence(
        plans=plans,
        selected_candidate=str(selected),
        selection_sha256=selection_sha256,
        candidate_status={str(k): str(v) for k, v in status.items()},
    )


def _existing_rating_manifest(
    storage: Any, *, manifest_uri: str, identity: Mapping[str, Any]
) -> dict[str, Any] | None:
    """Validate an existing terminal manifest without replaying its producer."""
    if not storage.exists(manifest_uri):
        return None
    existing = json.loads(storage.read_bytes(manifest_uri))
    try:
        verify_signed_payload(existing, label="existing retained rating manifest")
    except ValueError as exc:
        raise PossessionRatingRunError(str(exc)) from exc
    if (existing.get("identity") or {}).get("identity_sha256") != identity[
        "identity_sha256"
    ]:
        raise PossessionRatingRunError("rating run ID already has a different identity")
    outputs = existing.get("output_refs") or {}
    if (
        existing.get("state") != "frozen"
        or existing.get("production_activation_authorized") is not False
        or set(outputs) != set(RATING_DATASETS)
    ):
        raise PossessionRatingRunError(
            "existing retained rating manifest is incomplete"
        )
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
        dataset, schema_version = RATING_DATASETS[name]
        if required_ref_fields - set(value) or (
            value.get("dataset") != dataset
            or value.get("schema_version") != schema_version
        ):
            raise PossessionRatingRunError(
                f"existing {name} output reference is invalid"
            )
    if existing.get("selected_candidate") not in {
        entry["candidate_id"] for entry in candidate_registry()
    }:
        raise PossessionRatingRunError(
            "existing retained rating has an unsealed candidate"
        )
    return existing


def _parent_ref(value: Mapping[str, Any], *, name: str) -> DatasetRef:
    fields = ("dataset", "version_id", "schema_version", "content_sha", "uri")
    if missing := [item for item in fields if not value.get(item)]:
        raise PossessionRatingRunError(
            f"parent output reference is malformed: {name} {missing}"
        )
    return DatasetRef(**{item: value[item] for item in fields})


def _writers(
    storage: Any,
    identity: Mapping[str, Any],
    measurement: Mapping[str, Any],
    repair: Mapping[str, Any],
    evidence: RatingPreflightEvidence,
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
                dataset=RATING_DATASETS[name][0],
                parent_refs=parents,
                code_sha=str(identity["code_sha"]),
                config_sha=str(identity["config_sha"]),
                as_of=as_of,
                schema_version=RATING_DATASETS[name][1],
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


@dataclass
class _CompactWrite:
    records: list[dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    records_sha: str = ""


def apply(
    *,
    storage: Any,
    args: argparse.Namespace,
    identity: Mapping[str, Any],
    evidence: RatingPreflightEvidence,
) -> dict[str, Any]:
    """Recompute the tournament and publish it exactly as the evidence plans."""
    prefix = f"{POSSESSION_RATING_OUTPUT_ROOT}/{args.run_id}"
    manifest_uri = f"{prefix}/{RATING_MANIFEST_NAME}"
    if (
        _existing_rating_manifest(storage, manifest_uri=manifest_uri, identity=identity)
        is not None
    ):
        return {"state": "already_applied", "manifest_uri": manifest_uri}
    preexisting = sorted(storage.list_files(prefix))
    if preexisting:
        raise PossessionRatingRunError(
            "rating run prefix has a partial artifact and is permanently ineligible"
        )

    measurement_raw = storage.read_bytes(args.measurement_manifest_uri)
    repair_raw = storage.read_bytes(args.repair_manifest_uri)
    measurement, repair = verify_parents(
        json.loads(measurement_raw), json.loads(repair_raw)
    )

    progress = _Progress(args.run_id)
    progress.start()
    atexit.register(progress.close)
    progress.emit("apply_started", force=True)

    _immutable_json(
        storage,
        f"{prefix}/publication-plan.json",
        {
            "identity": dict(identity),
            "selected_candidate": evidence.selected_candidate,
            "selection_sha256": evidence.selection_sha256,
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
    dataset_of = {name: RATING_DATASETS[name][0] for name in RATING_DATASETS}

    def sink(name: str, partition: Mapping[str, Any], frame: pd.DataFrame) -> None:
        if name in compact:
            plan = evidence.plans[name]
            schema = schema_for(RATING_DATASETS[name][0], RATING_DATASETS[name][1])
            records_sha = canonical_frame_digest(frame, columns=schema.required)
            if len(frame) != plan.row_count or records_sha != plan.records_sha:
                raise PossessionRatingRunError(
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

    inputs = load_rating_inputs(
        storage=storage,
        measurement=measurement,
        repair=repair,
        progress=progress.emit,
    )
    computation = compute_tournament(inputs=inputs, progress=progress.emit, sink=sink)

    if (
        computation.selected_candidate != evidence.selected_candidate
        or computation.preflight_evidence()["selection_sha256"]
        != evidence.selection_sha256
        or computation.candidate_status != evidence.candidate_status
    ):
        raise PossessionRatingRunError(
            "apply replay differs from same-code preflight selection"
        )

    refs: dict[str, dict[str, Any]] = {}
    for name, writer in writers.items():
        ref = writer.finish()
        plan = evidence.plans[name]
        if ref.records_sha != plan.records_sha or ref.row_count != plan.row_count:
            raise PossessionRatingRunError(
                f"apply replay differs from same-code preflight: {name}"
            )
        refs[name] = asdict(ref)
    as_of = _utc(str(identity["as_of"]))
    parents = (
        _parent_ref(measurement["output_refs"]["population"], name="R6 population"),
        _parent_ref(repair["output_refs"]["population"], name="Repair population"),
    )
    for name, write in compact.items():
        dataset, schema_version = RATING_DATASETS[name]
        ref, _ = build_dataset_version(
            storage,
            build=BuildRequest(
                dataset=dataset,
                parent_refs=parents,
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

    manifest = retained_manifest(
        identity=identity,
        parents={
            "measurement_manifest_uri": args.measurement_manifest_uri,
            "measurement_manifest_raw_sha256": hashlib.sha256(
                measurement_raw
            ).hexdigest(),
            "repair_manifest_uri": args.repair_manifest_uri,
            "repair_manifest_raw_sha256": hashlib.sha256(repair_raw).hexdigest(),
        },
        output_refs=refs,
        selected_candidate=computation.selected_candidate,
        selection={
            "selection_sha256": evidence.selection_sha256,
            "candidate_status": dict(sorted(computation.candidate_status.items())),
            "row_counts": {
                name: plan.row_count for name, plan in evidence.plans.items()
            },
            "output_records_sha256": {
                name: plan.records_sha for name, plan in evidence.plans.items()
            },
        },
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
        "selected_candidate": computation.selected_candidate,
        "already_applied": False,
    }


def preflight(*, storage: object, args: argparse.Namespace) -> dict[str, object]:
    config_path = Path(args.config)
    config = yaml.safe_load(config_path.read_text())
    validate_config(config)
    measurement_raw = storage.read_bytes(args.measurement_manifest_uri)
    repair_raw = storage.read_bytes(args.repair_manifest_uri)
    measurement, repair = verify_parents(
        json.loads(measurement_raw), json.loads(repair_raw)
    )
    identity = _identity(storage, args)
    progress = _Progress(args.run_id)
    progress.start()
    atexit.register(progress.close)
    progress.emit("dry_run_started", force=True)
    inputs = load_rating_inputs(
        storage=storage,
        measurement=measurement,
        repair=repair,
        progress=progress.emit,
    )
    computation = compute_tournament(inputs=inputs, progress=progress.emit)
    progress.emit("dry_run_complete", force=True)
    progress.close()
    return {
        "state": "dry_run",
        "identity": identity,
        "candidate_count": len(candidate_registry()),
        "candidates": [item["candidate_id"] for item in candidate_registry()],
        "measurement_parent": measurement["identity"]["run_id"],
        "repair_parent": repair["identity"]["run_id"],
        "output_prefix": f"{POSSESSION_RATING_OUTPUT_ROOT}/{args.run_id}",
        "source_refs": inputs.source_refs,
        "population_sha256": inputs.population_sha256,
        **computation.preflight_evidence(),
        "production_activation_authorized": False,
    }


def _identity(storage: object, args: argparse.Namespace) -> dict[str, Any]:
    measurement_raw = storage.read_bytes(args.measurement_manifest_uri)
    repair_raw = storage.read_bytes(args.repair_manifest_uri)
    config_sha = hashlib.sha256(Path(args.config).read_bytes()).hexdigest()
    return rating_identity(
        run_id=args.run_id,
        as_of=args.as_of,
        code_sha=args.expected_code_sha,
        config_sha=config_sha,
        measurement_manifest_uri=args.measurement_manifest_uri,
        measurement_manifest_raw_sha256=hashlib.sha256(measurement_raw).hexdigest(),
        repair_manifest_uri=args.repair_manifest_uri,
        repair_manifest_raw_sha256=hashlib.sha256(repair_raw).hexdigest(),
    )


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--environment", required=True, choices=("preview",))
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--measurement-manifest-uri", required=True)
    parser.add_argument("--repair-manifest-uri", required=True)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--preflight-evidence",
        help="reviewed dry-run JSON used for a write-only apply",
    )
    args = parser.parse_args(argv)
    if _git_sha() != args.expected_code_sha:
        raise PossessionRatingRunError(
            "expected code SHA does not match committed HEAD"
        )
    if bool(args.preflight_evidence) != bool(args.apply):
        raise PossessionRatingRunError(
            "--apply and --preflight-evidence must be used together"
        )
    storage = get_storage(environment="preview")
    if args.apply:
        if not _clean_worktree():
            raise PossessionRatingRunError(
                "apply requires a completely clean committed worktree"
            )
        validate_config(yaml.safe_load(Path(args.config).read_text()))
        identity = _identity(storage, args)
        evidence = _load_rating_preflight_evidence(
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
    evidence = preflight(storage=storage, args=args)
    print(json.dumps(evidence, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
