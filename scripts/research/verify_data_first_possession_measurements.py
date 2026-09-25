#!/usr/bin/env python3
"""Independently reconstruct and verify a Preview V5 possession run."""

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
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_phase2 import DEVELOPMENT_SEASONS, FORBIDDEN_SEASONS
from cks_picks_cfb.data.data_first_phase2d import (
    PHASE3_DATASETS,
    REPLACEMENT_ELIGIBILITY_SCHEMA,
    verify_signed_payload,
)
from cks_picks_cfb.data.data_first_possession_v1 import (
    POSSESSION_DATASETS,
    POSSESSION_MANIFEST_SCHEMA,
    REQUIRED_REPAIR_CANONICAL_SHA256,
    REQUIRED_REPAIR_RAW_SHA256,
)
from cks_picks_cfb.data.data_first_repair_v2 import (
    LIVE_TIMING,
    RECONSTRUCTED_TIMING,
    REPAIR_MANIFEST_SCHEMA,
    REPAIR_POPULATION_DATASET,
    REPAIR_POPULATION_SCHEMA,
    REPAIRED_LIVE_STATE,
)
from cks_picks_cfb.data.lake import (
    PARTITIONED_DATASET_KIND,
    DatasetRef,
    PartitionedDatasetRef,
    canonical_frame_digest,
    iter_partitioned_dataset,
    partition_key,
    partitioned_records_sha,
    read_dataset,
)
from cks_picks_cfb.data.schema_contracts import schema_for
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ratings.possession_verification import (
    reconstruct_measurements,
    reconstruct_population,
    reconstruct_replay_partitions,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
_STATIC_OUTPUTS = {
    "population",
    "possessions",
    "scoring_events",
    "observations",
    "coverage",
}


class PossessionVerificationError(ValueError):
    """Raised when emitted evidence differs from independent reconstruction."""


class _Progress:
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

    def emit(self, event: str, /, *, force: bool = False, **fields: Any) -> None:
        now = time.monotonic()
        safe = self._safe(fields)
        with self.lock:
            self.phase = str(safe.pop("phase", event))
            self.context = safe
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
                    self._write("heartbeat", self.phase, self.context, now)
                    self.last = now

        self.thread = threading.Thread(
            target=heartbeat,
            name=f"possession-verifier-progress-{self.run_id}",
            daemon=True,
        )
        self.thread.start()

    def close(self) -> None:
        self.stop.set()
        if self.thread is not None:
            self.thread.join(timeout=min(self.interval_seconds, 1.0))


def _git_sha() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
    ).strip()


def _partitioned(value: Mapping[str, Any]) -> PartitionedDatasetRef:
    return PartitionedDatasetRef(
        artifact_kind=str(value["artifact_kind"]),
        dataset=str(value["dataset"]),
        version_id=str(value["version_id"]),
        schema_version=str(value["schema_version"]),
        content_sha=str(value["content_sha"]),
        records_sha=str(value["records_sha"]),
        uri=str(value["uri"]),
        row_count=int(value["row_count"]),
        partition_keys=tuple(value["partition_keys"]),
    )


def _ref(value: Mapping[str, Any]) -> DatasetRef:
    fields = ("dataset", "version_id", "schema_version", "content_sha", "uri")
    if missing := [field for field in fields if not value.get(field)]:
        raise PossessionVerificationError(f"dataset reference lacks fields: {missing}")
    return DatasetRef(**{field: value[field] for field in fields})


def _concat_source_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Avoid pandas' deprecated inference for cross-season all-null columns."""
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


def _verify_repair_2026(raw: bytes) -> dict[str, Any]:
    """Verify a Repair-2026 parent by manifest chain, not historical pins."""
    payload = json.loads(raw)
    if payload.get("schema_version") != REPAIR_MANIFEST_SCHEMA:
        raise PossessionVerificationError("Repair-2026 source is not a repair manifest")
    verify_signed_payload(payload, label="Repair-2026 manifest")
    if (
        payload.get("state") != REPAIRED_LIVE_STATE
        or payload.get("timing_class") != LIVE_TIMING
        or payload.get("production_activation_authorized") is not False
        or (payload.get("identity") or {}).get("environment") != "preview"
    ):
        raise PossessionVerificationError(
            "Repair-2026 source is not eligible Preview live evidence"
        )
    summary = payload.get("population") or {}
    if (
        int(summary.get("scheduled_games", -1)) <= 0
        or int(summary.get("forecast_eligible_games", -1)) <= 0
    ):
        raise PossessionVerificationError("Repair-2026 population summary is missing")
    population_ref = (payload.get("output_refs") or {}).get("population") or {}
    if (
        population_ref.get("dataset") != REPAIR_POPULATION_DATASET
        or population_ref.get("schema_version") != REPAIR_POPULATION_SCHEMA
    ):
        raise PossessionVerificationError(
            "Repair-2026 source lacks its declared population"
        )
    return payload


def _verify_repair(raw: bytes, *, scope: str = "historical") -> dict[str, Any]:
    if scope == "season_2026":
        return _verify_repair_2026(raw)
    if hashlib.sha256(raw).hexdigest() != REQUIRED_REPAIR_RAW_SHA256:
        raise PossessionVerificationError("Repair raw checksum mismatch")
    payload = json.loads(raw)
    if payload.get("schema_version") != REPAIR_MANIFEST_SCHEMA:
        raise PossessionVerificationError("Repair source is not the sealed v2 manifest")
    verify_signed_payload(payload, label="Repair v2 manifest")
    if payload.get("manifest_sha256") != REQUIRED_REPAIR_CANONICAL_SHA256:
        raise PossessionVerificationError("Repair canonical checksum mismatch")
    if (
        payload.get("state") != "repaired_reconstructed_only"
        or payload.get("timing_class") != RECONSTRUCTED_TIMING
        or payload.get("production_activation_authorized") is not False
        or (payload.get("identity") or {}).get("environment") != "preview"
    ):
        raise PossessionVerificationError(
            "Repair source is not eligible Preview evidence"
        )
    expected_counts = {
        "scheduled_games": 8936,
        "forecast_eligible_games": 8935,
        "measurement_usable_games": 8903,
        "measurement_missing_games": 33,
    }
    counts = payload.get("population") or {}
    if any(counts.get(key) != value for key, value in expected_counts.items()):
        raise PossessionVerificationError(
            "Repair population summary differs from sealed counts"
        )
    population_ref = (payload.get("output_refs") or {}).get("population") or {}
    if (
        population_ref.get("dataset") != REPAIR_POPULATION_DATASET
        or population_ref.get("schema_version") != REPAIR_POPULATION_SCHEMA
    ):
        raise PossessionVerificationError("Repair source lacks its declared population")
    return payload


def _source_refs(
    storage: Any, repair: Mapping[str, Any], *, scope: str = "historical"
) -> dict[int, dict[str, DatasetRef]]:
    if scope == "season_2026":
        return _source_refs_2026(storage, repair)
    uri = ((repair.get("parents") or {}).get("core_eligibility") or {}).get("uri")
    if not uri:
        raise PossessionVerificationError(
            "Repair source lacks core eligibility lineage"
        )
    payload = json.loads(storage.read_bytes(str(uri)))
    if payload.get("schema_version") != REPLACEMENT_ELIGIBILITY_SCHEMA:
        raise PossessionVerificationError("core eligibility schema mismatch")
    verify_signed_payload(payload, label="core eligibility")
    if (
        payload.get("state") != "eligible"
        or payload.get("production_activation_authorized") is not False
        or tuple(payload.get("development_seasons") or ()) != DEVELOPMENT_SEASONS
        or tuple(payload.get("forbidden_seasons") or ()) != FORBIDDEN_SEASONS
    ):
        raise PossessionVerificationError(
            "core eligibility is not sealed Preview evidence"
        )
    refs = [dict(value) for value in payload.get("phase3_input_refs") or []]
    expected = {
        (season, dataset)
        for season in DEVELOPMENT_SEASONS
        for dataset in PHASE3_DATASETS
    }
    seen: set[tuple[int, str]] = set()
    immutable: set[tuple[str, str, str, str, str]] = set()
    result: dict[int, dict[str, DatasetRef]] = {}
    for value in refs:
        key = (int(value.get("season", -1)), str(value.get("dataset")))
        identity = tuple(
            str(value.get(field) or "")
            for field in (
                "dataset",
                "version_id",
                "schema_version",
                "content_sha",
                "uri",
            )
        )
        if key in seen or identity in immutable or not all(identity):
            raise PossessionVerificationError(
                "core eligibility contains duplicate or malformed refs"
            )
        if value.get("eligible") is not True or list(
            value.get("permitted_uses") or []
        ) != ["phase3_measurement_validation"]:
            raise PossessionVerificationError(f"core eligibility rejects source {key}")
        seen.add(key)
        immutable.add(identity)
        result.setdefault(key[0], {})[key[1]] = _ref(value)
    if seen != expected or len(refs) != len(expected):
        raise PossessionVerificationError(
            "core eligibility must contain the exact 70-ref source set"
        )
    if any({"byplay", "game_outcomes"} - set(values) for values in result.values()):
        raise PossessionVerificationError(
            "Repair core sources lack byplay or outcome evidence"
        )
    return result


def _source_refs_2026(
    storage: Any, repair: Mapping[str, Any]
) -> dict[int, dict[str, DatasetRef]]:
    """Resolve 2026 byplay/outcome sources through the Repair-2026 input bundle."""
    bundle_uri = ((repair.get("parents") or {}).get("season_2026_inputs") or {}).get(
        "uri"
    )
    if not bundle_uri:
        raise PossessionVerificationError(
            "Repair-2026 manifest does not bind 2026 inputs"
        )
    bundle = json.loads(storage.read_bytes(str(bundle_uri)))
    if (
        bundle.get("schema_version") != "data_first_2026_silver_inputs_v1"
        or int(bundle.get("season", -1)) != 2026
    ):
        raise PossessionVerificationError("2026 input bundle identity mismatch")
    refs = dict(bundle.get("refs") or {})
    if set(refs) != {"byplay", "game_outcomes"}:
        raise PossessionVerificationError("2026 input bundle refs are incomplete")
    result: dict[str, DatasetRef] = {}
    for name, value in refs.items():
        ref = _ref(dict(value))
        parquet_bytes = storage.read_bytes(ref.uri)
        if hashlib.sha256(parquet_bytes).hexdigest() != ref.content_sha:
            raise PossessionVerificationError(f"2026 {name} content SHA mismatch")
        result[name] = ref
    return {2026: result}


def _read_output(
    storage: Any,
    *,
    name: str,
    value: Mapping[str, Any],
    collect: bool,
    progress: _Progress,
) -> tuple[PartitionedDatasetRef, dict[str, dict[str, Any]], pd.DataFrame | None]:
    expected_dataset, expected_schema = POSSESSION_DATASETS[name]
    ref = _partitioned(value)
    if (
        ref.artifact_kind != PARTITIONED_DATASET_KIND
        or ref.dataset != expected_dataset
        or ref.schema_version != expected_schema
    ):
        raise PossessionVerificationError(f"output identity mismatch: {name}")
    raw_manifest = storage.read_bytes(ref.uri)
    if hashlib.sha256(raw_manifest).hexdigest() != ref.content_sha:
        raise PossessionVerificationError(
            f"partition manifest checksum mismatch: {name}"
        )
    partition_manifest = json.loads(raw_manifest)
    if (
        partition_manifest.get("artifact_kind") != PARTITIONED_DATASET_KIND
        or partition_manifest.get("dataset") != ref.dataset
        or partition_manifest.get("schema_version") != ref.schema_version
        or tuple(partition_manifest.get("partition_keys") or ()) != ref.partition_keys
    ):
        raise PossessionVerificationError(f"partition identity mismatch: {name}")
    parts = list(partition_manifest.get("parts") or [])
    if partitioned_records_sha(parts, ref.partition_keys) != ref.records_sha:
        raise PossessionVerificationError(f"partition digest mismatch: {name}")
    if sum(int(part["row_count"]) for part in parts) != ref.row_count:
        raise PossessionVerificationError(f"partition count mismatch: {name}")
    by_partition = {partition_key(part["partition"]): part for part in parts}
    if len(by_partition) != len(parts):
        raise PossessionVerificationError(f"duplicate output partition: {name}")
    records: list[dict[str, Any]] | None = [] if collect else None
    nonempty = [part for part in parts if int(part["row_count"]) > 0]
    progress.emit(
        "stored_output_started",
        force=True,
        dataset=name,
        completed=0,
        total=len(nonempty),
        rows=0,
    )
    completed = 0
    for part, frame in zip(
        nonempty, iter_partitioned_dataset(storage, ref), strict=True
    ):
        completed += 1
        if collect:
            assert records is not None
            records.extend(frame.to_dict("records"))
        progress.emit(
            "stored_output_read",
            dataset=name,
            completed=completed,
            total=len(nonempty),
            rows=int(part["row_count"]),
            partition=part["partition"],
        )
    progress.emit(
        "stored_output_complete",
        force=True,
        dataset=name,
        completed=len(nonempty),
        total=len(nonempty),
        rows=ref.row_count,
    )
    frame = (
        pd.DataFrame.from_records(
            records,
            columns=schema_for(expected_dataset, expected_schema).required,
        )
        if collect
        else None
    )
    return ref, by_partition, frame


def _compare_partitioned_frame(
    name: str,
    frame: pd.DataFrame,
    parts: Mapping[str, Mapping[str, Any]],
) -> None:
    dataset, schema_version = POSSESSION_DATASETS[name]
    schema = schema_for(dataset, schema_version)
    keys = tuple(next(iter(parts.values()))["partition"]) if parts else ()
    seen: set[str] = set()
    groups = frame.groupby(list(keys), sort=True, dropna=False) if keys else []
    for values, partition_frame in groups:
        values = values if isinstance(values, tuple) else (values,)
        partition = dict(zip(keys, values))
        key = partition_key(partition)
        stored = parts.get(key)
        if stored is None:
            raise PossessionVerificationError(
                f"independent reconstruction added {name} {partition}"
            )
        digest = canonical_frame_digest(
            partition_frame.reset_index(drop=True), columns=schema.required
        )
        if (
            int(stored["row_count"]) != len(partition_frame)
            or stored["records_sha"] != digest
        ):
            raise PossessionVerificationError(
                f"independent reconstruction mismatch: {name} {partition}"
            )
        seen.add(key)
    expected = {key for key, value in parts.items() if int(value["row_count"]) > 0}
    if seen != expected:
        raise PossessionVerificationError(
            f"independent reconstruction omitted a {name} partition"
        )


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-uri", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--environment", choices=["preview"], required=True)
    args = parser.parse_args(argv)
    verifier_sha = _git_sha()
    if verifier_sha != args.expected_code_sha:
        raise PossessionVerificationError(
            "verifier must run from the expected committed code"
        )
    storage = get_storage(environment="preview")
    raw = storage.read_bytes(args.manifest_uri)
    manifest = json.loads(raw)
    if manifest.get("schema_version") != POSSESSION_MANIFEST_SCHEMA:
        raise PossessionVerificationError("unexpected possession manifest schema")
    verify_signed_payload(manifest, label="possession measurement manifest")
    identity = manifest.get("identity") or {}
    if (
        identity.get("environment") != "preview"
        or identity.get("code_sha") != args.expected_code_sha
    ):
        raise PossessionVerificationError(
            "manifest is not the expected committed Preview code"
        )
    if manifest.get("production_activation_authorized") is not False:
        raise PossessionVerificationError("manifest authorizes production")
    progress = _Progress(str(identity.get("run_id") or "unknown"))
    progress.start()
    atexit.register(progress.close)
    progress.emit("verification_started", force=True, manifest_uri=args.manifest_uri)

    scope = (
        "season_2026"
        if list(identity.get("development_seasons") or []) == [2026]
        else "historical"
    )
    repair = _verify_repair(
        storage.read_bytes(str(manifest.get("repair_manifest_uri") or "")),
        scope=scope,
    )
    if scope == "season_2026":
        repair_summary = repair.get("population") or {}
        expected_rows = int(repair_summary.get("scheduled_games", -1))
        expected_eligible = int(repair_summary.get("forecast_eligible_games", -1))
    else:
        expected_rows, expected_eligible = None, None
    refs = _source_refs(storage, repair, scope=scope)
    output_values = manifest.get("output_refs") or {}
    if set(output_values) != set(POSSESSION_DATASETS):
        raise PossessionVerificationError(
            "manifest output membership differs from Contract 02"
        )
    stored_parts: dict[str, dict[str, dict[str, Any]]] = {}
    stored_frames: dict[str, pd.DataFrame] = {}
    row_counts: dict[str, int] = {}
    digests: dict[str, str] = {}
    for name in POSSESSION_DATASETS:
        output_ref, parts, frame = _read_output(
            storage,
            name=name,
            value=output_values[name],
            collect=name in _STATIC_OUTPUTS,
            progress=progress,
        )
        stored_parts[name] = parts
        row_counts[name] = output_ref.row_count
        digests[name] = output_ref.records_sha
        if frame is not None:
            stored_frames[name] = frame
    if row_counts != manifest.get("output_rows") or digests != manifest.get(
        "output_records_sha256"
    ):
        raise PossessionVerificationError("stored output summary differs from manifest")

    population_ref = _ref((repair.get("output_refs") or {})["population"])
    population = reconstruct_population(
        read_dataset(storage, population_ref),
        scope=scope,
        expected_rows=expected_rows,
        expected_eligible=expected_eligible,
    )
    byplay_parts: list[pd.DataFrame] = []
    outcome_parts: list[pd.DataFrame] = []
    for completed, season in enumerate(sorted(refs), start=1):
        progress.emit(
            "source_read_started",
            force=True,
            season=season,
            dataset="byplay_and_game_outcomes",
            completed=completed - 1,
            total=len(refs),
            rows=0,
        )
        byplay_parts.append(read_dataset(storage, refs[season]["byplay"]))
        outcome_parts.append(read_dataset(storage, refs[season]["game_outcomes"]))
        progress.emit(
            "source_read",
            force=True,
            season=season,
            dataset="byplay_and_game_outcomes",
            completed=completed,
            total=len(refs),
            rows=len(byplay_parts[-1]) + len(outcome_parts[-1]),
        )
    byplay = _concat_source_frames(byplay_parts)
    outcomes = _concat_source_frames(outcome_parts)
    progress.emit(
        "measurement_reconstruction_started",
        force=True,
        dataset="possession_measurements",
        completed=0,
        total=len(population),
        rows=0,
    )
    rebuilt = reconstruct_measurements(
        byplay=byplay,
        outcomes=outcomes,
        population=population,
        progress=progress.emit,
        scope=scope,
    )
    expected_static = {
        "population": population,
        "possessions": rebuilt.possessions,
        "scoring_events": rebuilt.scoring_events,
        "observations": rebuilt.observations,
        "coverage": rebuilt.coverage,
    }
    for name, frame in expected_static.items():
        _compare_partitioned_frame(name, frame, stored_parts[name])
        dataset, schema_version = POSSESSION_DATASETS[name]
        columns = schema_for(dataset, schema_version).required
        if canonical_frame_digest(frame, columns=columns) != canonical_frame_digest(
            stored_frames[name], columns=columns
        ):
            raise PossessionVerificationError(
                f"stored row order/content differs: {name}"
            )
        progress.emit(
            "independent_output_verified",
            force=True,
            dataset=name,
            rows=len(frame),
        )

    replay_seen: dict[str, set[str]] = {
        "snapshots": set(),
        "adjusted_history": set(),
        "terminal": set(),
    }

    def compare_replay(
        name: str, partition: dict[str, int], frame: pd.DataFrame
    ) -> None:
        key = partition_key(partition)
        if key in replay_seen[name]:
            raise PossessionVerificationError(
                f"duplicate reconstructed {name} partition"
            )
        stored = stored_parts[name].get(key)
        if stored is None:
            raise PossessionVerificationError(
                f"reconstructed {name} has undeclared partition {partition}"
            )
        dataset, schema_version = POSSESSION_DATASETS[name]
        digest = canonical_frame_digest(
            frame, columns=schema_for(dataset, schema_version).required
        )
        if int(stored["row_count"]) != len(frame) or stored["records_sha"] != digest:
            raise PossessionVerificationError(
                f"independent replay mismatch: {name} {partition}"
            )
        replay_seen[name].add(key)
        progress.emit(
            "replay_partition_verified",
            force=True,
            dataset=name,
            partition=partition,
            rows=len(frame),
            completed=len(replay_seen[name]),
            total=len(stored_parts[name]),
        )

    progress.emit(
        "replay_reconstruction_started",
        force=True,
        dataset="replay_outputs",
        completed=0,
        total=sum(
            len(values) for name, values in stored_parts.items() if name in replay_seen
        ),
        rows=0,
    )
    replay_evidence = reconstruct_replay_partitions(
        population=population,
        observations=rebuilt.observations,
        emit=compare_replay,
        progress=progress.emit,
        scope=scope,
    )
    for name, seen in replay_seen.items():
        expected = {
            key
            for key, value in stored_parts[name].items()
            if int(value["row_count"]) > 0
        }
        if seen != expected:
            raise PossessionVerificationError(
                f"independent replay omitted {name} partitions"
            )
    if replay_evidence != (manifest.get("scale_diagnostics") or {}).get("replay"):
        raise PossessionVerificationError(
            "independent replay diagnostics differ from manifest"
        )

    certification_uri = args.manifest_uri.rsplit("/", 1)[0] + "/certification.json"
    certification = json.loads(storage.read_bytes(certification_uri))
    verify_signed_payload(certification, label="possession certification")
    if (
        certification.get("manifest_sha256") != manifest.get("certification_sha256")
        or not certification.get("all_checks_passed")
        or certification.get("row_counts") != row_counts
        or certification.get("output_records_sha256") != digests
        or certification.get("production_activation_authorized") is not False
    ):
        raise PossessionVerificationError(
            "certification is missing, failed, or inconsistent"
        )
    progress.emit("verification_complete", force=True, output_rows=row_counts)
    progress.close()
    print(
        json.dumps(
            {
                "status": "verified",
                "manifest_uri": args.manifest_uri,
                "manifest_raw_sha256": hashlib.sha256(raw).hexdigest(),
                "manifest_canonical_sha256": manifest["manifest_sha256"],
                "certification_sha256": certification["manifest_sha256"],
                "verifier_code_sha": verifier_sha,
                "output_rows": row_counts,
                "output_records_sha256": digests,
                "reconciliation": rebuilt.final_reconciliation,
                "production_activation_authorized": False,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
