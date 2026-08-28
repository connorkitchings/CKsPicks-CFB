"""Exact archive contracts for legacy comparison-only evidence."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from cks_picks_cfb.data.history import HistoricalObjectRef, read_historical_records
from cks_picks_cfb.data.storage import StorageBackend

LEGACY_COMPARISON_2019_CONTRACT = "legacy-comparison-2019-source-set-v1"
LEGACY_COMPARISON_2019_SEASON = 2019
SUCCESSOR_RESEARCH_PREFIX = "artifacts/research/rating-successor-v2/"


@dataclass(frozen=True)
class LegacyArchiveSpec:
    entity: str
    uri: str
    sha256: str


@dataclass(frozen=True)
class LegacyComparisonRestoreConfig:
    version: str
    season: int
    output_prefix: str
    archives: tuple[LegacyArchiveSpec, ...]
    sha256: str


def load_legacy_comparison_restore_config(
    path: str | Path = "conf/ratings/legacy_comparison_2019_restore.yaml",
) -> LegacyComparisonRestoreConfig:
    """Load the fixed, checksummed source allowlist for the 2019 restoration."""

    config_path = Path(path)
    raw = config_path.read_bytes()
    payload = yaml.safe_load(raw)
    if not isinstance(payload, Mapping):
        raise ValueError("Legacy comparison restore configuration must be a mapping")
    archives_raw = payload.get("archives")
    if not isinstance(archives_raw, list):
        raise ValueError("Legacy comparison restore configuration requires archives")
    archives = tuple(
        LegacyArchiveSpec(
            entity=str(item["entity"]),
            uri=str(item["uri"]),
            sha256=str(item["sha256"]),
        )
        for item in archives_raw
        if isinstance(item, Mapping)
    )
    config = LegacyComparisonRestoreConfig(
        version=str(payload.get("version")),
        season=int(payload.get("season")),
        output_prefix=str(payload.get("output_prefix")),
        archives=archives,
        sha256=hashlib.sha256(raw).hexdigest(),
    )
    if config.version != "legacy_comparison_2019_restore_v1":
        raise ValueError("Unsupported legacy comparison restore configuration version")
    if config.season != LEGACY_COMPARISON_2019_SEASON:
        raise ValueError("Legacy comparison restoration is fixed to season 2019")
    if config.output_prefix != "artifacts/preview/legacy-comparison/2019":
        raise ValueError("Legacy comparison restoration output prefix is fixed")
    if config.output_prefix.startswith(SUCCESSOR_RESEARCH_PREFIX):
        raise ValueError("Legacy comparison evidence may not use a successor prefix")
    expected_entities = {"games", "teams"}
    if {archive.entity for archive in config.archives} != expected_entities:
        raise ValueError("Legacy comparison restoration requires exactly games and teams")
    if len(config.archives) != len(expected_entities):
        raise ValueError("Legacy comparison restoration archive entities must be unique")
    for archive in config.archives:
        if len(archive.sha256) != 64 or any(
            char not in "0123456789abcdef" for char in archive.sha256
        ):
            raise ValueError(f"Invalid SHA-256 for legacy archive {archive.entity}")
        if not archive.uri.startswith("raw/") or "/year=2019/" not in archive.uri:
            raise ValueError(f"Legacy archive URI is outside fixed 2019 scope: {archive.uri}")
    return config


def find_and_verify_legacy_archives(
    source: StorageBackend,
    config: LegacyComparisonRestoreConfig,
    inventory: Sequence[HistoricalObjectRef],
) -> list[tuple[LegacyArchiveSpec, HistoricalObjectRef, list[dict[str, Any]]]]:
    """Return only allowlisted source records after exact checksum verification."""

    by_uri = {item.uri: item for item in inventory}
    verified: list[tuple[LegacyArchiveSpec, HistoricalObjectRef, list[dict[str, Any]]]] = []
    for archive in config.archives:
        item = by_uri.get(archive.uri)
        if item is None:
            raise LookupError(f"Required legacy archive is unavailable: {archive.uri}")
        if item.entity != archive.entity or item.years != {config.season}:
            raise ValueError(f"Legacy archive scope mismatch: {archive.uri}")
        records, source_sha = read_historical_records(source, item)
        if source_sha != archive.sha256:
            raise ValueError(f"Legacy archive checksum changed: {archive.uri}")
        if not records:
            raise ValueError(f"Legacy archive is empty: {archive.uri}")
        verified.append((archive, item, records))
    return verified
