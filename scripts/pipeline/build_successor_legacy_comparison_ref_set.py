#!/usr/bin/env python3
"""Freeze comparison-only legacy refs for successor-v2 R1 cross-lineage checks."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from typing import Any

from cks_picks_cfb.data.catalog import legacy_dataset_ref_for_season
from cks_picks_cfb.data.lake import DatasetRef
from cks_picks_cfb.data.runtime import resolve_runtime_target
from cks_picks_cfb.data.storage import get_storage

COMPARISON_SEASONS = (2019, 2021, 2022, 2023, 2024, 2025)
HARD_DATASETS = ("games", "game_outcomes", "teams")
OPTIONAL_DATASETS = ("plays", "team_game_stats")
SUCCESSOR_PREFIX = "artifacts/research/rating-successor-v2/"
CONTRACT_VERSION = "successor-legacy-comparison-ref-set-v1"

# Pinned restoration manifest for season 2019.
# The 2019 legacy artifacts were restored from the Feb 2026 export before the
# catalog ingestion integration existed; they were never registered in
# catalog.dataset_versions. This manifest is the sole authoritative source for
# the 2019 legacy comparison refs. Its SHA-256 is pinned here so any mutation
# of the supposedly-immutable R2 object is caught at preflight time.
LEGACY_COMPARISON_2019_MANIFEST_URI = (
    "artifacts/preview/legacy-comparison/2019/"
    "legacy-comparison-2019-55f6968/manifest.json"
)
LEGACY_COMPARISON_2019_MANIFEST_SHA256 = (
    "a2b9398fc9773ce37b1d126714c035b896c3ba43359834be6026b664651d316a"
)
LEGACY_COMPARISON_2019_CONTRACT_VERSION = "legacy-comparison-2019-restoration-v1"


def _sha256(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _immutable_write(storage, uri: str, payload: bytes) -> None:
    if storage.exists(uri):
        if storage.read_bytes(uri) != payload:
            raise FileExistsError(
                f"Immutable legacy comparison ref-set collision: {uri}"
            )
        return
    storage.write_bytes(payload, uri)


def _failure_uri(output_uri: str) -> str:
    """Keep a failed preflight immutable without occupying its success URI."""

    suffix = ".json"
    if output_uri.endswith(suffix):
        return f"{output_uri[: -len(suffix)]}.failure{suffix}"
    return f"{output_uri}.failure.json"


def _write_failure_diagnostic(
    storage,
    *,
    output_uri: str,
    selection_mode: str,
    selection_as_of: str,
    error: Exception,
) -> str:
    """Persist the terminal, comparison-only failure required before capture."""

    diagnostic_uri = _failure_uri(output_uri)
    payload: dict[str, Any] = {
        "contract_version": CONTRACT_VERSION,
        "state": "failed",
        "selection_mode": selection_mode,
        "selection_as_of": selection_as_of,
        "failure": {
            "error_type": type(error).__name__,
            "message": str(error),
        },
    }
    payload["manifest_sha256"] = _sha256(payload)
    _immutable_write(
        storage,
        diagnostic_uri,
        json.dumps(payload, indent=2, sort_keys=True).encode(),
    )
    return diagnostic_uri


def _entries(raw: dict[str, Any]) -> list[dict[str, Any]]:
    entries = raw.get("entries")
    if not isinstance(entries, list):
        raise ValueError("comparison ref set must contain entries")
    required = {
        (season, dataset) for season in COMPARISON_SEASONS for dataset in HARD_DATASETS
    }
    output = []
    observed = set()
    for entry in entries:
        season = int(entry["season"])
        dataset = str(entry["dataset"])
        ref = DatasetRef(
            dataset=dataset,
            version_id=str(entry["version_id"]),
            schema_version=str(entry["schema_version"]),
            content_sha=str(entry["content_sha"]),
            uri=str(entry["uri"]),
        )
        if season not in COMPARISON_SEASONS or ref.uri.startswith(SUCCESSOR_PREFIX):
            raise ValueError(
                "comparison evidence may not include successor or out-of-scope refs"
            )
        key = (season, dataset)
        if key in observed:
            raise ValueError(f"comparison ref set duplicates {key}")
        observed.add(key)
        output.append({"season": season, **asdict(ref)})
    if not required.issubset(observed):
        raise ValueError("comparison ref set lacks required legacy evidence")
    return sorted(output, key=lambda item: (item["season"], item["dataset"]))


def _manifest_2019_entry(storage) -> list[dict[str, Any]]:
    """Read the pinned 2019 restoration manifest from R2 and return its refs.

    The 2019 legacy artifacts were never registered in catalog.dataset_versions
    (the restoration predated catalog integration). This function reads the
    immutable restoration manifest, verifies its integrity and contract
    constraints, and returns the three hard-dataset refs in the same shape
    that _catalog_entries() produces for 2021-2025.

    Integrity checks (mirrors the restore script's own _ref() validation):
    1. contract_version == LEGACY_COMPARISON_2019_CONTRACT_VERSION
    2. state == "complete"
    3. season == 2019
    4. SHA-256 of raw manifest bytes == LEGACY_COMPARISON_2019_MANIFEST_SHA256
    5. Ref dataset names exactly {"games", "game_outcomes", "teams"}
    6. Each ref URI starts with "lake/silver/" (non-successor)
    7. Each ref contains the required DatasetRef fields
    """
    try:
        raw_bytes = storage.read_bytes(LEGACY_COMPARISON_2019_MANIFEST_URI)
    except (KeyError, FileNotFoundError) as exc:
        raise LookupError(
            f"2019 restoration manifest not found in R2: {LEGACY_COMPARISON_2019_MANIFEST_URI}"
        ) from exc

    # Check 4: SHA-256 integrity before parsing
    actual_sha = hashlib.sha256(raw_bytes).hexdigest()
    if actual_sha != LEGACY_COMPARISON_2019_MANIFEST_SHA256:
        raise ValueError(
            f"2019 restoration manifest SHA-256 mismatch: "
            f"expected {LEGACY_COMPARISON_2019_MANIFEST_SHA256}, got {actual_sha}"
        )

    manifest = json.loads(raw_bytes)

    # Check 1: contract version
    cv = manifest.get("contract_version")
    if cv != LEGACY_COMPARISON_2019_CONTRACT_VERSION:
        raise ValueError(
            f"2019 restoration manifest contract_version mismatch: "
            f"expected {LEGACY_COMPARISON_2019_CONTRACT_VERSION!r}, got {cv!r}"
        )

    # Check 2: state
    state = manifest.get("state")
    if state != "complete":
        raise ValueError(f"2019 restoration manifest state is not complete: {state!r}")

    # Check 3: season
    season = manifest.get("season")
    if season != 2019:
        raise ValueError(
            f"2019 restoration manifest season mismatch: expected 2019, got {season!r}"
        )

    refs = manifest.get("refs")
    if not isinstance(refs, list) or not refs:
        raise ValueError("2019 restoration manifest has no refs list")

    # Check 5: dataset names exactly {"games", "game_outcomes", "teams"}
    actual_datasets = {str(r.get("dataset", "")) for r in refs}
    expected_datasets = set(HARD_DATASETS)
    if actual_datasets != expected_datasets:
        raise ValueError(
            f"2019 restoration manifest ref datasets mismatch: "
            f"expected {sorted(expected_datasets)}, got {sorted(actual_datasets)}"
        )

    output = []
    for ref_obj in refs:
        dataset = str(ref_obj.get("dataset", ""))
        uri = str(ref_obj.get("uri", ""))

        # Check 6: non-successor lake/silver/ URIs
        if not uri.startswith("lake/silver/"):
            raise ValueError(
                f"2019 restoration manifest ref {dataset!r} URI does not start "
                f"with 'lake/silver/': {uri!r}"
            )
        if uri.startswith(SUCCESSOR_PREFIX):
            raise ValueError(
                f"2019 restoration manifest ref {dataset!r} URI must not be a "
                f"successor URI: {uri!r}"
            )

        # Check 7: required DatasetRef fields present
        for field in ("version_id", "schema_version", "content_sha"):
            if not ref_obj.get(field):
                raise ValueError(
                    f"2019 restoration manifest ref {dataset!r} missing field {field!r}"
                )

        ref = DatasetRef(
            dataset=dataset,
            version_id=str(ref_obj["version_id"]),
            schema_version=str(ref_obj["schema_version"]),
            content_sha=str(ref_obj["content_sha"]),
            uri=uri,
        )
        output.append({"season": 2019, **asdict(ref)})

    return sorted(output, key=lambda item: item["dataset"])


def _catalog_entries(conn_url: str, selection_as_of: str) -> list[dict[str, Any]]:
    """Resolve 2021-2025 legacy comparison refs from catalog.dataset_versions."""
    catalog_seasons = tuple(s for s in COMPARISON_SEASONS if s != 2019)
    output = []
    for season in catalog_seasons:
        for dataset in HARD_DATASETS:
            ref = legacy_dataset_ref_for_season(
                conn_url, dataset, selection_as_of, season=season
            )
            output.append({"season": season, **asdict(ref)})
        for dataset in OPTIONAL_DATASETS:
            try:
                ref = legacy_dataset_ref_for_season(
                    conn_url, dataset, selection_as_of, season=season
                )
            except LookupError:
                continue
            output.append({"season": season, **asdict(ref)})
    return sorted(output, key=lambda item: (item["season"], item["dataset"]))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--environment", choices=("preview", "production"), required=True
    )
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--output-uri", required=True)
    parser.add_argument(
        "--comparison-ref-set-uri",
        help="Expert override: immutable legacy evidence to validate and re-freeze.",
    )
    args = parser.parse_args(argv)
    if args.environment != "preview":
        raise ValueError("Legacy comparison evidence may be resolved only in Preview")
    if not args.output_uri.startswith(SUCCESSOR_PREFIX):
        raise ValueError("Comparison ref set must use the isolated successor-v2 prefix")
    storage = get_storage(environment="preview")
    mode = "explicit_override" if args.comparison_ref_set_uri else "catalog_preflight"
    try:
        if args.comparison_ref_set_uri:
            source_bytes = storage.read_bytes(args.comparison_ref_set_uri)
            entries = _entries(json.loads(source_bytes.decode()))
            source_uri = args.comparison_ref_set_uri
            source_sha256 = hashlib.sha256(source_bytes).hexdigest()
        else:
            # 2019: read from pinned restoration manifest in R2 (never in catalog)
            entries_2019 = _manifest_2019_entry(storage)
            # 2021-2025: read from catalog.dataset_versions (v1 pin)
            conn_url = resolve_runtime_target("preview").database_url
            entries_catalog = _catalog_entries(conn_url, args.as_of)
            entries = sorted(
                entries_2019 + entries_catalog,
                key=lambda item: (item["season"], item["dataset"]),
            )
            source_uri = None
            source_sha256 = None
    except (KeyError, LookupError, TypeError, ValueError) as exc:
        diagnostic_uri = _write_failure_diagnostic(
            storage,
            output_uri=args.output_uri,
            selection_mode=mode,
            selection_as_of=args.as_of,
            error=exc,
        )
        raise SystemExit(
            f"Legacy comparison evidence preflight failed; diagnostic: {diagnostic_uri}; {exc}"
        ) from exc
    payload: dict[str, Any] = {
        "contract_version": CONTRACT_VERSION,
        "state": "complete",
        "selection_mode": mode,
        "selection_as_of": args.as_of,
        "source_ref_set_uri": source_uri,
        "source_ref_set_sha256": source_sha256,
        "entries": entries,
    }
    payload["manifest_sha256"] = _sha256(payload)
    _immutable_write(
        storage, args.output_uri, json.dumps(payload, indent=2, sort_keys=True).encode()
    )
    print(
        json.dumps(
            {
                "output_uri": args.output_uri,
                "manifest_sha256": payload["manifest_sha256"],
                "selection_mode": mode,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
