"""Immutable, content-addressed data lake contracts and helpers.

R2 is the durable content store.  This module deliberately has no concept of
"latest": production callers must carry a :class:`DatasetRef` selected by the
catalog/control plane.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterator, Literal, Mapping, Sequence
from uuid import uuid4

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from cks_picks_cfb.data.storage import StorageBackend, StorageError

LakeTier = Literal["bronze", "silver", "gold"]


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Lake timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


def _sanitize_json(value: Any) -> Any:
    """Convert non-finite floats (NaN, Infinity) to None for deterministic JSON."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _sanitize_json(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_sanitize_json(item) for item in value]
    return value


def _canonical_json(value: Any) -> bytes:
    sanitized = _sanitize_json(value)
    return json.dumps(
        sanitized, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class DatasetRef:
    """Exact immutable dataset version selected for a pipeline operation."""

    dataset: str
    version_id: str
    schema_version: str
    content_sha: str
    uri: str


PARTITIONED_DATASET_KIND = "partitioned_dataset_v1"


@dataclass(frozen=True)
class PartitionedDatasetRef:
    """A logical immutable dataset assembled from independently immutable parts.

    ``content_sha`` protects the root manifest bytes. ``records_sha`` protects
    the canonical ordered row content, independently of Parquet serialization.
    Consumers must use :func:`iter_partitioned_dataset`, never ``read_dataset``.
    """

    artifact_kind: str
    dataset: str
    version_id: str
    schema_version: str
    content_sha: str
    records_sha: str
    uri: str
    row_count: int
    partition_keys: tuple[str, ...]


@dataclass(frozen=True)
class PartitionedDatasetPart:
    """One bounded dataframe and its exact logical partition key."""

    partition: Mapping[str, Any]
    frame: pd.DataFrame


def partition_key(partition: Mapping[str, Any]) -> str:
    return _canonical_json(dict(partition)).decode("utf-8")


def partition_order_key(
    partition: Mapping[str, Any],
) -> tuple[tuple[str, int, Any], ...]:
    """Return a natural, typed ordering for logical dataset partitions.

    ``partition_key`` is a stable canonical-JSON identity used in manifests.
    JSON's lexical ordering would put numeric week 10 before week 2, so stream
    ordering deliberately uses this separate typed key.
    """

    def typed_value(value: Any) -> tuple[int, Any]:
        if value is None:
            return (0, "")
        if isinstance(value, bool):
            return (1, int(value))
        if isinstance(value, (int, float)):
            if isinstance(value, float) and not math.isfinite(value):
                raise StorageError("partition values must be finite")
            return (2, value)
        if isinstance(value, str):
            return (3, value)
        return (4, partition_key({"value": value}))

    return tuple((str(name), *typed_value(value)) for name, value in partition.items())


def canonical_frame_digest(frame: pd.DataFrame, *, columns: Sequence[str]) -> str:
    """Hash sorted canonical rows without retaining another full dataset copy."""
    records = frame.loc[:, list(columns)].to_dict("records")
    return _sha256(_canonical_json(records))


def partitioned_records_sha(
    parts: Sequence[Mapping[str, Any]], partition_keys: Sequence[str]
) -> str:
    return _sha256(
        _canonical_json(
            {
                "artifact_kind": PARTITIONED_DATASET_KIND,
                "partition_keys": list(partition_keys),
                "parts": [
                    {
                        "partition": dict(part["partition"]),
                        "row_count": int(part["row_count"]),
                        "records_sha": str(part["records_sha"]),
                    }
                    for part in parts
                ],
            }
        )
    )


class PartitionedDatasetWriter:
    """Write immutable dataset parts while retaining only bounded metadata.

    The root manifest is deliberately delayed until :meth:`finish`. A process
    interrupted between ``add`` calls therefore leaves only unreachable,
    content-addressed children and cannot publish a consumable logical dataset.
    """

    def __init__(
        self,
        storage: StorageBackend,
        *,
        build: "BuildRequest",
        partition_keys: Sequence[str],
        row_partition_keys: Sequence[str] | None = None,
        expected_parts: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        if not partition_keys:
            raise ValueError("partitioned datasets require partition keys")
        self.storage = storage
        self.build = build
        self.partition_keys = tuple(partition_keys)
        self.row_partition_keys = tuple(row_partition_keys or partition_keys)
        if not set(self.row_partition_keys).issubset(self.partition_keys):
            raise ValueError("row partition keys must be logical partition keys")
        self.expected_parts = dict(expected_parts or {})
        self.parts: list[dict[str, Any]] = []
        self._last_key: tuple[tuple[str, int, Any], ...] | None = None

    def add(self, part: PartitionedDatasetPart) -> None:
        partition = dict(part.partition)
        if tuple(partition) != self.partition_keys:
            raise StorageError(
                f"{self.build.dataset} partition keys must be {self.partition_keys}"
            )
        key = partition_key(partition)
        order_key = partition_order_key(partition)
        if self._last_key is not None and order_key <= self._last_key:
            raise StorageError(f"{self.build.dataset} parts are not strictly ordered")
        self._last_key = order_key

        frame = part.frame
        try:
            from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame

            schema = schema_for(self.build.dataset, self.build.schema_version)
            validation = validate_frame(frame, schema)
            columns = schema.required
        except Exception as exc:
            raise StorageError(
                f"{self.build.dataset} partition schema validation failed"
            ) from exc
        for column in self.row_partition_keys:
            value = partition[column]
            if column not in frame.columns:
                raise StorageError(
                    f"{self.build.dataset} partition column is absent: {column}"
                )
            if (
                not frame.empty
                and not frame[column].map(lambda item: item == value).all()
            ):
                raise StorageError(
                    f"{self.build.dataset} rows escape partition {partition}"
                )
        records_sha = canonical_frame_digest(frame, columns=columns)
        item: dict[str, Any] = {
            "partition": partition,
            "row_count": int(len(frame)),
            "records_sha": records_sha,
            "ref": None,
        }
        expected = self.expected_parts.get(key)
        if expected is not None and (
            int(expected["row_count"]) != item["row_count"]
            or str(expected["records_sha"]) != records_sha
        ):
            raise StorageError(
                f"{self.build.dataset} partition differs from the preflight: {partition}"
            )
        if not frame.empty:
            ref, _ = build_dataset_version(
                self.storage,
                build=self.build,
                records=frame.to_dict("records"),
                partitions={
                    "partitioned_dataset": PARTITIONED_DATASET_KIND,
                    "partition": partition,
                },
                validation=validation,
            )
            item["ref"] = asdict(ref)
        self.parts.append(item)

    def finish(self) -> PartitionedDatasetRef:
        actual_keys = {partition_key(part["partition"]) for part in self.parts}
        if self.expected_parts and actual_keys != set(self.expected_parts):
            raise StorageError(
                f"{self.build.dataset} does not match the preflight plan"
            )
        records_sha = partitioned_records_sha(self.parts, self.partition_keys)
        identity = {
            "artifact_kind": PARTITIONED_DATASET_KIND,
            "dataset": self.build.dataset,
            "tier": self.build.tier,
            "schema_version": self.build.schema_version,
            "records_sha": records_sha,
            "partition_keys": list(self.partition_keys),
            "row_partition_keys": list(self.row_partition_keys),
            "parents": [asdict(parent) for parent in self.build.parent_refs],
            "source_captures": list(self.build.source_capture_ids),
            "code_sha": self.build.code_sha,
            "config_sha": self.build.config_sha,
            "as_of": _utc(self.build.as_of).isoformat(),
        }
        version_id = _sha256(_canonical_json(identity))[:24]
        prefix = (
            f"lake/{self.build.tier}/dataset={self.build.dataset}/version={version_id}"
        )
        uri = f"{prefix}/partitioned-manifest.json"
        if self.storage.exists(uri):
            payload = self.storage.read_bytes(uri)
            existing = json.loads(payload)
            if (
                existing.get("artifact_kind") != PARTITIONED_DATASET_KIND
                or existing.get("records_sha") != records_sha
                or existing.get("parts") != self.parts
            ):
                raise StorageError(f"Partitioned dataset manifest collision at {uri}")
            return PartitionedDatasetRef(
                artifact_kind=PARTITIONED_DATASET_KIND,
                dataset=self.build.dataset,
                version_id=version_id,
                schema_version=self.build.schema_version,
                content_sha=_sha256(payload),
                records_sha=records_sha,
                uri=uri,
                row_count=int(existing["row_count"]),
                partition_keys=self.partition_keys,
            )
        manifest = {
            **identity,
            "version_id": version_id,
            "uri": uri,
            "row_count": int(sum(part["row_count"] for part in self.parts)),
            "parts": self.parts,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        payload = _canonical_json(manifest)
        _write_immutable(self.storage, uri, payload)
        return PartitionedDatasetRef(
            artifact_kind=PARTITIONED_DATASET_KIND,
            dataset=self.build.dataset,
            version_id=version_id,
            schema_version=self.build.schema_version,
            content_sha=_sha256(payload),
            records_sha=records_sha,
            uri=uri,
            row_count=int(manifest["row_count"]),
            partition_keys=self.partition_keys,
        )


def iter_partitioned_dataset(
    storage: StorageBackend, ref: PartitionedDatasetRef
) -> Iterator[pd.DataFrame]:
    """Yield validated parts in manifest order without concatenating them."""
    if ref.artifact_kind != PARTITIONED_DATASET_KIND:
        raise StorageError("unsupported partitioned artifact kind")
    payload = storage.read_bytes(ref.uri)
    if _sha256(payload) != ref.content_sha:
        raise StorageError(f"Partitioned dataset checksum mismatch: {ref.uri}")
    manifest = json.loads(payload)
    if (
        manifest.get("artifact_kind") != PARTITIONED_DATASET_KIND
        or manifest.get("dataset") != ref.dataset
        or manifest.get("schema_version") != ref.schema_version
        or tuple(manifest.get("partition_keys") or ()) != ref.partition_keys
    ):
        raise StorageError("partitioned dataset manifest identity mismatch")
    parts = list(manifest.get("parts") or [])
    row_partition_keys = tuple(manifest.get("row_partition_keys") or ref.partition_keys)
    if not set(row_partition_keys).issubset(ref.partition_keys):
        raise StorageError("partitioned dataset has invalid row partition keys")
    if partitioned_records_sha(parts, ref.partition_keys) != ref.records_sha:
        raise StorageError("partitioned dataset logical digest mismatch")
    if int(sum(int(part["row_count"]) for part in parts)) != ref.row_count:
        raise StorageError("partitioned dataset row-count mismatch")
    previous: tuple[tuple[str, int, Any], ...] | None = None
    for part in parts:
        partition = dict(part["partition"])
        key = partition_order_key(partition)
        if tuple(partition) != ref.partition_keys or (
            previous is not None and key <= previous
        ):
            raise StorageError("partitioned dataset has malformed part order")
        previous = key
        child = part.get("ref")
        if child is None:
            if int(part["row_count"]) != 0:
                raise StorageError("nonempty partition lacks a child reference")
            continue
        frame = read_dataset(storage, DatasetRef(**child))
        try:
            from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame

            schema = schema_for(ref.dataset, ref.schema_version)
            validate_frame(frame, schema)
        except Exception as exc:
            raise StorageError(
                "partitioned dataset child schema validation failed"
            ) from exc
        if int(len(frame)) != int(part["row_count"]) or canonical_frame_digest(
            frame, columns=schema.required
        ) != str(part["records_sha"]):
            raise StorageError("partitioned dataset child content mismatch")
        for column in row_partition_keys:
            value = partition[column]
            if not frame[column].map(lambda item: item == value).all():
                raise StorageError("partitioned dataset child escapes its partition")
        yield frame


@dataclass(frozen=True)
class SourceCapture:
    """One observation of a provider response.

    Multiple observations may point at the same content-addressed Parquet object.
    """

    capture_id: str
    provider: str
    entity: str
    captured_at: datetime
    effective_at: datetime | None
    request: Mapping[str, Any]
    content_sha: str
    object_sha: str
    uri: str
    row_count: int
    provider_api_version: str | None = None
    response_metadata: Mapping[str, Any] = field(default_factory=dict)
    state: str = "staged"


@dataclass(frozen=True)
class BuildRequest:
    dataset: str
    parent_refs: tuple[DatasetRef, ...]
    code_sha: str
    config_sha: str
    as_of: datetime
    source_capture_ids: tuple[str, ...] = ()
    schema_version: str = "1"
    tier: Literal["silver", "gold"] = "silver"
    identity_version: str = "dataset_identity_v2"
    schema_sha: str | None = None


@dataclass(frozen=True)
class MarketQuote:
    quote_id: str
    game_id: int
    provider: str
    captured_at: datetime
    spread: float | None = None
    total: float | None = None


@dataclass(frozen=True)
class MarketSnapshot:
    game_id: int
    captured_at: datetime
    spread: float | None
    total: float | None
    source_quote_ids: tuple[str, ...]
    policy_version: str = "consensus_then_median_v1"
    spread_rule: str | None = None
    total_rule: str | None = None
    spread_provider_count: int = 0
    total_provider_count: int = 0


@dataclass(frozen=True)
class DatasetManifest:
    dataset: str
    version_id: str
    tier: LakeTier
    schema_version: str
    content_sha: str
    uri: str
    row_count: int
    partitions: Mapping[str, Any]
    created_at: str
    as_of: str
    parent_versions: tuple[str, ...] = ()
    source_capture_ids: tuple[str, ...] = ()
    code_sha: str | None = None
    config_sha: str | None = None
    provider: str | None = None
    request: Mapping[str, Any] = field(default_factory=dict)
    provider_api_version: str | None = None
    min_event_at: str | None = None
    max_event_at: str | None = None
    missingness: Mapping[str, float] = field(default_factory=dict)
    coverage: Mapping[str, Any] = field(default_factory=dict)
    validation: Mapping[str, Any] = field(default_factory=dict)
    state: str = "validated"
    identity_version: str = "v1"
    schema_sha: str | None = None


def parquet_bytes(records: Sequence[Mapping[str, Any]]) -> bytes:
    """Serialize records deterministically enough for content addressing."""
    df = pd.DataFrame.from_records(list(records))
    for col in df.select_dtypes(include=["object"]).columns:
        values = df[col].dropna()
        if (
            not values.empty
            and values.map(lambda value: isinstance(value, (bool, np.bool_))).all()
        ):
            # Nullable booleans otherwise have object dtype and used to be
            # stringified below. Preserve their semantic type in the lake.
            df[col] = pd.array(df[col], dtype="boolean")
        else:
            df[col] = df[col].apply(
                lambda value: None
                if value is None
                or value is pd.NA
                or value is pd.NaT
                or (isinstance(value, (float, np.floating)) and math.isnan(value))
                else str(value)
            )
    table = pa.Table.from_pandas(df, preserve_index=False)
    sink = io.BytesIO()
    pq.write_table(table, sink, compression="snappy")
    return sink.getvalue()


def _write_immutable(storage: StorageBackend, path: str, payload: bytes) -> None:
    if storage.exists(path):
        existing = storage.read_bytes(path)
        if existing != payload:
            raise StorageError(f"Immutable object collision at {path}")
        return
    storage.write_bytes(payload, path)


def capture_provider_records(
    storage: StorageBackend,
    *,
    provider: str,
    entity: str,
    records: Sequence[Mapping[str, Any]],
    captured_at: datetime,
    effective_at: datetime | None,
    request: Mapping[str, Any],
    provider_api_version: str | None = None,
    response_metadata: Mapping[str, Any] | None = None,
    capture_id: str | None = None,
) -> SourceCapture:
    """Persist a Bronze provider capture and a distinct observation record."""
    captured_at = _utc(captured_at)
    effective_at = _utc(effective_at) if effective_at else None
    canonical_payload = _canonical_json(list(records))
    canonical_records = json.loads(canonical_payload.decode("utf-8"))
    payload = parquet_bytes(canonical_records)
    content_sha = _sha256(canonical_payload)
    prefix = (
        f"lake/bronze/provider={provider}/entity={entity}/content_sha={content_sha}"
    )
    data_uri = f"{prefix}/data.parquet"
    object_sha = _sha256(payload)
    if storage.exists(data_uri):
        existing = storage.read_bytes(data_uri)
        object_sha = _sha256(existing)
        if existing != payload:
            # Parquet bytes are not stable across library versions, while this
            # prefix is keyed by the canonical record payload. A prior capture
            # that records the same canonical content is therefore safe to
            # reuse during a catalog-only bootstrap of a schema-only branch.
            observations = storage.list_files(f"{prefix}/observations")
            matching_observation = False
            for observation_uri in observations:
                try:
                    observation = json.loads(storage.read_bytes(observation_uri))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
                if observation.get("content_sha") == content_sha:
                    matching_observation = True
                    break
            if not matching_observation:
                raise StorageError(f"Immutable object collision at {data_uri}")
    else:
        storage.write_bytes(payload, data_uri)

    capture = SourceCapture(
        capture_id=capture_id or uuid4().hex,
        provider=provider,
        entity=entity,
        captured_at=captured_at,
        effective_at=effective_at,
        request=dict(request),
        content_sha=content_sha,
        object_sha=object_sha,
        uri=data_uri,
        row_count=len(records),
        provider_api_version=provider_api_version,
        response_metadata=dict(response_metadata or {}),
    )
    observation_uri = f"{prefix}/observations/{capture.capture_id}.json"
    observation = asdict(capture)
    observation["captured_at"] = captured_at.isoformat()
    observation["effective_at"] = effective_at.isoformat() if effective_at else None
    if storage.exists(observation_uri):
        existing_observation = json.loads(storage.read_bytes(observation_uri))
        if existing_observation.get("content_sha") != content_sha:
            raise StorageError(f"Immutable object collision at {observation_uri}")
    else:
        _write_immutable(storage, observation_uri, _canonical_json(observation))
    return capture


def build_dataset_version(
    storage: StorageBackend,
    *,
    build: BuildRequest,
    records: Sequence[Mapping[str, Any]],
    partitions: Mapping[str, Any] | None = None,
    event_time_column: str | None = None,
    coverage: Mapping[str, Any] | None = None,
    validation: Mapping[str, Any] | None = None,
) -> tuple[DatasetRef, DatasetManifest]:
    """Create an immutable Silver/Gold dataset from explicit parent versions."""
    as_of = _utc(build.as_of)
    frame = pd.DataFrame.from_records(records)
    validation_results = dict(validation or {"valid": True})
    schema_sha = build.schema_sha
    if build.identity_version == "dataset_identity_v2" and schema_sha is None:
        from cks_picks_cfb.data.schema_contracts import (
            DatasetSchemaError,
            schema_for,
            validate_frame,
        )

        try:
            schema = schema_for(build.dataset, build.schema_version)
        except DatasetSchemaError:
            schema = None
        if schema is not None:
            validation_results.update(validate_frame(frame, schema))
            schema_sha = schema.sha256
    if not all(
        value for value in validation_results.values() if isinstance(value, bool)
    ):
        raise StorageError(
            f"Dataset validation failed for {build.dataset}: {validation_results}"
        )
    payload = parquet_bytes(records)
    content_sha = _sha256(payload)
    identity: dict[str, Any] = {
        "dataset": build.dataset,
        "tier": build.tier,
        "schema_version": build.schema_version,
        "content_sha": content_sha,
        "parents": [
            {
                "dataset": parent.dataset,
                "version_id": parent.version_id,
                "schema_version": parent.schema_version,
                "content_sha": parent.content_sha,
            }
            for parent in build.parent_refs
        ],
        "source_captures": list(build.source_capture_ids),
        "code_sha": build.code_sha,
        "config_sha": build.config_sha,
    }
    if build.identity_version == "dataset_identity_v2":
        identity.update(
            {
                "identity_version": build.identity_version,
                "as_of": as_of.isoformat(),
                "partitions": dict(partitions or {}),
                "schema_sha": schema_sha,
            }
        )
    elif build.identity_version != "v1":
        raise ValueError(
            f"Unsupported dataset identity version: {build.identity_version}"
        )
    version_id = _sha256(_canonical_json(identity))[:24]
    prefix = f"lake/{build.tier}/dataset={build.dataset}/version={version_id}"
    uri = f"{prefix}/data.parquet"
    _write_immutable(storage, uri, payload)
    ref = DatasetRef(
        dataset=build.dataset,
        version_id=version_id,
        schema_version=build.schema_version,
        content_sha=content_sha,
        uri=uri,
    )
    manifest_uri = f"{prefix}/manifest.json"
    if storage.exists(manifest_uri):
        existing = json.loads(storage.read_bytes(manifest_uri).decode("utf-8"))
        if existing.get("content_sha") != content_sha:
            raise StorageError(f"Dataset manifest collision at {manifest_uri}")
        existing["parent_versions"] = tuple(existing.get("parent_versions", ()))
        existing["source_capture_ids"] = tuple(existing.get("source_capture_ids", ()))
        existing.setdefault("identity_version", "v1")
        existing.setdefault("schema_sha", None)
        manifest = DatasetManifest(**existing)
        if build.identity_version == "dataset_identity_v2" and (
            manifest.identity_version != build.identity_version
            or manifest.as_of != as_of.isoformat()
            # Dataset manifests serialize NumPy scalar partition values through
            # JSON's ``default=str``. Compare their canonical JSON forms so a
            # rerun with the same scalar (for example a pandas-derived week)
            # reuses the immutable version instead of falsely colliding.
            or _canonical_json(manifest.partitions) != _canonical_json(partitions or {})
            or manifest.schema_sha != schema_sha
        ):
            raise StorageError(f"Dataset manifest identity collision at {manifest_uri}")
        return ref, manifest

    missingness = {
        str(column): float(frame[column].isna().mean()) for column in frame.columns
    }
    min_event_at = max_event_at = None
    if event_time_column and event_time_column in frame and not frame.empty:
        event_times = pd.to_datetime(
            frame[event_time_column], utc=True, errors="coerce"
        )
        valid = event_times.dropna()
        if not valid.empty:
            min_event_at = valid.min().isoformat()
            max_event_at = valid.max().isoformat()

    manifest = DatasetManifest(
        dataset=build.dataset,
        version_id=version_id,
        tier=build.tier,
        schema_version=build.schema_version,
        content_sha=content_sha,
        uri=uri,
        row_count=len(records),
        partitions=dict(partitions or {}),
        created_at=datetime.now(timezone.utc).isoformat(),
        as_of=as_of.isoformat(),
        parent_versions=tuple(parent.version_id for parent in build.parent_refs),
        source_capture_ids=tuple(build.source_capture_ids),
        code_sha=build.code_sha,
        config_sha=build.config_sha,
        min_event_at=min_event_at,
        max_event_at=max_event_at,
        missingness=missingness,
        coverage=dict(coverage or {}),
        validation=validation_results,
        state="validated",
        identity_version=build.identity_version,
        schema_sha=schema_sha,
    )
    _write_immutable(storage, manifest_uri, _canonical_json(asdict(manifest)))
    return ref, manifest


def read_dataset(storage: StorageBackend, ref: DatasetRef) -> pd.DataFrame:
    """Read an exact dataset and verify the content hash before decoding."""
    payload = storage.read_bytes(ref.uri)
    actual = _sha256(payload)
    if actual != ref.content_sha:
        raise StorageError(
            f"Dataset checksum mismatch for {ref.dataset}/{ref.version_id}: "
            f"{actual} != {ref.content_sha}"
        )
    try:
        return pd.read_parquet(io.BytesIO(payload))
    except Exception as exc:
        raise StorageError(f"Unreadable dataset object: {ref.uri}") from exc


def read_source_capture(
    storage: StorageBackend, capture: SourceCapture
) -> pd.DataFrame:
    """Read a Bronze capture and verify its physical object checksum."""
    payload = storage.read_bytes(capture.uri)
    actual = _sha256(payload)
    if actual != capture.object_sha:
        raise StorageError(
            f"Source capture checksum mismatch for {capture.capture_id}: "
            f"{actual} != {capture.object_sha}"
        )
    try:
        return pd.read_parquet(io.BytesIO(payload))
    except Exception as exc:
        raise StorageError(f"Unreadable source capture: {capture.uri}") from exc


def select_capture_as_of(
    captures: Sequence[SourceCapture], as_of: datetime
) -> SourceCapture:
    """Select the newest capture available at the point-in-time cutoff."""
    cutoff = _utc(as_of)
    eligible = [capture for capture in captures if _utc(capture.captured_at) <= cutoff]
    if not eligible:
        raise LookupError(f"No source capture exists at or before {cutoff.isoformat()}")
    return max(eligible, key=lambda capture: _utc(capture.captured_at))


def require_dataset(ref: DatasetRef, expected: str) -> None:
    """Fail closed if an immutable dataset reference is the wrong dataset."""
    if ref.dataset != expected:
        raise ValueError(
            f"Expected dataset {expected!r} but reference resolves to "
            f"{ref.dataset!r}; refusing to consume an incompatible dataset"
        )


def select_market_snapshot(
    quotes: Sequence[MarketQuote], *, game_id: int, as_of: datetime
) -> MarketSnapshot:
    """Select Consensus independently per target, else median valid providers."""
    cutoff = _utc(as_of)
    eligible = [
        quote
        for quote in quotes
        if quote.game_id == game_id and _utc(quote.captured_at) <= cutoff
    ]

    def select(target: str) -> tuple[float | None, str | None, list[str], int]:
        valid = [q for q in eligible if getattr(q, target) is not None]
        consensus = [q for q in valid if q.provider.casefold() == "consensus"]
        if consensus:
            chosen = max(consensus, key=lambda q: _utc(q.captured_at))
            return (
                float(getattr(chosen, target)),
                "cfbd_consensus",
                [chosen.quote_id],
                1,
            )
        if not valid:
            return None, None, [], 0
        latest_by_provider: dict[str, MarketQuote] = {}
        for quote in valid:
            key = quote.provider.casefold()
            if key not in latest_by_provider or _utc(quote.captured_at) > _utc(
                latest_by_provider[key].captured_at
            ):
                latest_by_provider[key] = quote
        selected = sorted(latest_by_provider.values(), key=lambda q: q.quote_id)
        values = [float(getattr(q, target)) for q in selected]
        return (
            float(pd.Series(values).median()),
            "provider_median",
            [q.quote_id for q in selected],
            len(selected),
        )

    spread, spread_rule, spread_ids, spread_count = select("spread")
    total, total_rule, total_ids, total_count = select("total")
    return MarketSnapshot(
        game_id=game_id,
        captured_at=cutoff,
        spread=spread,
        total=total,
        source_quote_ids=tuple(dict.fromkeys(spread_ids + total_ids)),
        spread_rule=spread_rule,
        total_rule=total_rule,
        spread_provider_count=spread_count,
        total_provider_count=total_count,
    )


def canonicalize_market_quotes_frame(quotes: pd.DataFrame) -> pd.DataFrame:
    """Apply the canonical Consensus-then-median policy to ingested quote rows."""
    required = {"game_id", "provider"}
    if not required.issubset(quotes.columns):
        raise ValueError(
            f"Market quotes missing columns: {required - set(quotes.columns)}"
        )

    def choose(
        group: pd.DataFrame, column: str
    ) -> tuple[float | None, str | None, int, list[str]]:
        valid = group.dropna(subset=[column])
        if valid.empty:
            return None, None, 0, []
        if "captured_at" in valid:
            valid = valid.sort_values("captured_at")
        consensus = valid[valid["provider"].astype(str).str.casefold() == "consensus"]
        if not consensus.empty:
            chosen = consensus.iloc[-1]
            quote_id = str(chosen.get("quote_id", ""))
            return (
                float(chosen[column]),
                "cfbd_consensus",
                1,
                [quote_id] if quote_id else [],
            )
        providers = valid.drop_duplicates(subset=["provider"], keep="last")
        quote_ids = [str(value) for value in providers.get("quote_id", []) if value]
        return (
            float(providers[column].median()),
            "provider_median",
            len(providers),
            quote_ids,
        )

    rows = []
    for game_id, group in quotes.sort_index().groupby("game_id", sort=True):
        spread, spread_rule, spread_count, spread_ids = choose(group, "spread")
        total_column = "over_under" if "over_under" in group else "total"
        total, total_rule, total_count, total_ids = choose(group, total_column)
        quote_ids = list(dict.fromkeys(spread_ids + total_ids))
        snapshot_payload = {
            "game_id": int(game_id),
            "spread": spread,
            "total": total,
            "quote_ids": quote_ids,
            "policy": "consensus_then_median_v1",
        }
        captured_at = None
        if "captured_at" in group:
            captured = pd.to_datetime(group["captured_at"], utc=True, errors="coerce")
            if captured.notna().any():
                captured_at = captured.max().isoformat()
        rows.append(
            {
                "game_id": game_id,
                "spread_line": spread,
                "total_line": total,
                "market_policy_version": "consensus_then_median_v1",
                "spread_selection_rule": spread_rule,
                "total_selection_rule": total_rule,
                "spread_provider_count": spread_count,
                "total_provider_count": total_count,
                "source_quote_ids": json.dumps(quote_ids),
                "market_snapshot_id": _sha256(_canonical_json(snapshot_payload))[:32],
                "market_captured_at": captured_at,
            }
        )
    return pd.DataFrame.from_records(rows)
