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
from typing import Any, Literal, Mapping, Sequence
from uuid import uuid4

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


def parquet_bytes(records: Sequence[Mapping[str, Any]]) -> bytes:
    """Serialize records deterministically enough for content addressing."""
    df = pd.DataFrame.from_records(list(records))
    for col in df.select_dtypes(include=["object"]).columns:
        df[col] = df[col].apply(lambda v: str(v) if v is not None else None)
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
    object_sha = _sha256(payload)
    prefix = (
        f"lake/bronze/provider={provider}/entity={entity}/content_sha={content_sha}"
    )
    data_uri = f"{prefix}/data.parquet"
    _write_immutable(storage, data_uri, payload)

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
    payload = parquet_bytes(records)
    content_sha = _sha256(payload)
    identity = {
        "dataset": build.dataset,
        "tier": build.tier,
        "schema_version": build.schema_version,
        "content_sha": content_sha,
        "parents": [asdict(parent) for parent in build.parent_refs],
        "source_captures": list(build.source_capture_ids),
        "code_sha": build.code_sha,
        "config_sha": build.config_sha,
    }
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
        if existing.get("state") != "failed":
            if existing.get("content_sha") != content_sha:
                raise StorageError(f"Dataset manifest collision at {manifest_uri}")
            existing["parent_versions"] = tuple(existing.get("parent_versions", ()))
            existing["source_capture_ids"] = tuple(
                existing.get("source_capture_ids", ())
            )
            return ref, DatasetManifest(**existing)

    frame = pd.DataFrame.from_records(records)
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

    validation_results = dict(validation or {"valid": True})
    state = (
        "validated"
        if all(
            value for value in validation_results.values() if isinstance(value, bool)
        )
        else "failed"
    )
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
        state=state,
    )
    if storage.exists(manifest_uri):
        storage.write_bytes(_canonical_json(asdict(manifest)), manifest_uri)
    else:
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
        total, total_rule, total_count, total_ids = choose(group, "over_under")
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
