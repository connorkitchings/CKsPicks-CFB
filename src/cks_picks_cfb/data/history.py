"""Read-only inventory and preview import of legacy historical objects."""

from __future__ import annotations

import hashlib
import io
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any, Mapping, Sequence

import pandas as pd
import psycopg

from cks_picks_cfb.data.catalog import (
    begin_ingestion_run,
    finish_ingestion_run,
    register_source_capture,
    source_capture_by_id,
)
from cks_picks_cfb.data.lake import SourceCapture, capture_provider_records
from cks_picks_cfb.data.storage import StorageBackend

ALLOWED_YEARS = frozenset({2019, 2021, 2022, 2023, 2024, 2025, 2026})
FORBIDDEN_YEARS = frozenset({2020})
DATA_SUFFIXES = frozenset({".parquet", ".csv", ".json"})
PRIOR_ONLY_2019_ENTITIES = frozenset(
    {"teams", "venues", "preseason_team_inputs", "team_season"}
)


@dataclass(frozen=True)
class HistoricalObjectRef:
    uri: str
    entity: str
    provider: str
    source_format: str
    partitions: Mapping[str, str]
    metadata: Mapping[str, Any]

    @property
    def years(self) -> frozenset[int]:
        values = {
            int(value)
            for key, value in self.partitions.items()
            if key in {"year", "season"} and str(value).isdigit()
        }
        return frozenset(values)


def _partitions(uri: str) -> dict[str, str]:
    return {
        key: value
        for key, value in re.findall(r"(?:^|/)(year|season|week|game_id)=([^/]+)", uri)
    }


def _classify(uri: str) -> tuple[str, str] | None:
    if uri.endswith("/manifest.json") or "/observations/" in uri:
        return None
    bronze = re.search(r"(?:^|/)lake/bronze/provider=([^/]+)/entity=([^/]+)/", uri)
    if bronze:
        return bronze.group(2), bronze.group(1)
    mappings = (
        ("raw/betting_lines/", "betting_lines"),
        ("raw/game_stats/", "game_stats"),
        ("raw/games/", "games"),
        ("raw/plays/", "plays"),
        ("raw/teams/", "teams"),
        ("raw/venues/", "venues"),
        ("raw/weather/", "weather_observations"),
        ("processed/team_season/", "team_season"),
        ("preseason/", "preseason_team_inputs"),
    )
    for marker, entity in mappings:
        if marker in uri:
            return entity, "legacy_cfbd_export"
    return None


def inventory_historical_source(
    source: StorageBackend, *, prefix: str = ""
) -> list[HistoricalObjectRef]:
    """Inventory recognized history without invoking a mutating source method."""
    objects: list[HistoricalObjectRef] = []
    listed = source.list_object_metadata(prefix)
    for uri in sorted(listed):
        if PurePosixPath(uri).suffix.casefold() not in DATA_SUFFIXES:
            continue
        classified = _classify(uri)
        if classified is None:
            continue
        entity, provider = classified
        objects.append(
            HistoricalObjectRef(
                uri=uri,
                entity=entity,
                provider=provider,
                source_format=PurePosixPath(uri).suffix.casefold().lstrip("."),
                partitions=_partitions(uri),
                metadata=dict(listed[uri]),
            )
        )
    return objects


def inventory_report(objects: Sequence[HistoricalObjectRef]) -> dict[str, Any]:
    by_entity: dict[str, int] = {}
    weeks: dict[str, set[int]] = {}
    years: set[int] = set()
    for item in objects:
        by_entity[item.entity] = by_entity.get(item.entity, 0) + 1
        for year in item.years:
            years.add(year)
            week = item.partitions.get("week")
            if week is not None and str(week).lstrip("-").isdigit():
                weeks.setdefault(f"{item.entity}:{year}", set()).add(int(week))
    return {
        "object_count": len(objects),
        "objects_by_entity": dict(sorted(by_entity.items())),
        "years": sorted(years),
        "weeks_by_entity_year": {
            key: sorted(value) for key, value in sorted(weeks.items())
        },
        "forbidden_2020_objects": [
            item.uri for item in objects if item.years & FORBIDDEN_YEARS
        ],
    }


def inventory_schema_report(
    source: StorageBackend, objects: Sequence[HistoricalObjectRef]
) -> dict[str, Any]:
    """Read one representative object per entity and report its record schema."""
    samples: dict[str, HistoricalObjectRef] = {}
    for item in objects:
        samples.setdefault(item.entity, item)
    schemas = {}
    for entity, item in sorted(samples.items()):
        records, source_sha = read_historical_records(source, item)
        frame = pd.DataFrame.from_records(records[:100])
        schemas[entity] = {
            "sample_uri": item.uri,
            "sample_source_sha256": source_sha,
            "row_count": len(records),
            "fields": {
                str(column): str(dtype) for column, dtype in frame.dtypes.items()
            },
        }
    return schemas


def read_historical_records(
    source: StorageBackend, item: HistoricalObjectRef
) -> tuple[list[dict[str, Any]], str]:
    payload = source.read_bytes(item.uri)
    source_sha = hashlib.sha256(payload).hexdigest()
    if item.source_format == "parquet":
        frame = pd.read_parquet(io.BytesIO(payload))
        records = frame.to_dict("records")
    elif item.source_format == "csv":
        records = pd.read_csv(io.BytesIO(payload)).to_dict("records")
    else:
        decoded = json.loads(payload)
        if isinstance(decoded, list):
            records = decoded
        elif isinstance(decoded, dict) and isinstance(decoded.get("records"), list):
            records = decoded["records"]
        elif isinstance(decoded, dict):
            records = [decoded]
        else:
            raise ValueError(f"Unsupported JSON record shape: {item.uri}")
    if not all(isinstance(record, dict) for record in records):
        raise ValueError(f"Historical object contains non-record rows: {item.uri}")
    return records, source_sha


def _record_years(records: Sequence[Mapping[str, Any]]) -> set[int]:
    years: set[int] = set()
    for record in records:
        value = record.get("season", record.get("year"))
        if value is not None and str(value).isdigit():
            years.add(int(value))
    return years


def validate_historical_scope(
    item: HistoricalObjectRef, records: Sequence[Mapping[str, Any]]
) -> set[int]:
    years = set(item.years) | _record_years(records)
    if years & FORBIDDEN_YEARS:
        raise ValueError(f"2020 data is forbidden: {item.uri}")
    unknown = years - ALLOWED_YEARS
    if unknown:
        raise ValueError(f"Historical object has unsupported years {sorted(unknown)}")
    if 2019 in years and item.entity not in PRIOR_ONLY_2019_ENTITIES:
        raise ValueError(
            f"2019 is prior-only; entity {item.entity!r} is not eligible: {item.uri}"
        )
    return years


def _source_time(item: HistoricalObjectRef) -> datetime:
    value = item.metadata.get("last_modified")
    if value:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def import_historical_object(
    *,
    source: StorageBackend,
    destination: StorageBackend,
    conn_url: str,
    item: HistoricalObjectRef,
) -> SourceCapture:
    """Import one source object idempotently into preview Bronze and Neon."""
    records, source_sha = read_historical_records(source, item)
    years = validate_historical_scope(item, records)
    identity = json.dumps(
        {
            "source_uri": item.uri,
            "source_sha256": source_sha,
            "last_modified": item.metadata.get("last_modified"),
        },
        sort_keys=True,
    )
    capture_id = hashlib.sha256(identity.encode()).hexdigest()[:32]
    try:
        capture = source_capture_by_id(conn_url, capture_id)
        return capture
    except LookupError:
        pass
    except psycopg.OperationalError:
        # If the catalog is unreachable for the idempotency probe, fall through
        # to the normal ingestion path so transient DB issues don't block import.
        pass

    ingestion_run_id = f"history-{capture_id}"
    request = {
        "operation": "historical_r2_import",
        "source_uri": item.uri,
        "source_partitions": dict(item.partitions),
        "years": sorted(years),
    }
    begin_ingestion_run(
        conn_url,
        ingestion_run_id=ingestion_run_id,
        provider=item.provider,
        entity=item.entity,
        request=request,
    )
    try:
        capture = capture_provider_records(
            destination,
            provider=item.provider,
            entity=item.entity,
            records=records,
            captured_at=_source_time(item),
            effective_at=_source_time(item),
            request=request,
            response_metadata={
                "import_classification": item.provider,
                "source_sha256": source_sha,
                "source_metadata": dict(item.metadata),
                "source_format": item.source_format,
            },
            capture_id=capture_id,
        )
        register_source_capture(conn_url, capture, ingestion_run_id=ingestion_run_id)
        finish_ingestion_run(conn_url, ingestion_run_id, succeeded=True)
        return capture
    except Exception as exc:
        finish_ingestion_run(
            conn_url,
            ingestion_run_id,
            succeeded=False,
            error_category=type(exc).__name__,
            error_detail=str(exc),
        )
        raise


def object_json(item: HistoricalObjectRef) -> dict[str, Any]:
    return asdict(item)
