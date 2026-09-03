#!/usr/bin/env python3
"""Publish an immutable admission report for football-only offseason context."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from dataclasses import asdict

import pyarrow as pa
import pyarrow.parquet as pq

from cks_picks_cfb.data.lake import DatasetRef, read_dataset
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ratings.offseason_context import (
    REPORT_VERSION,
    ContextAdmissionError,
    admit_offseason_context,
)


def _ref(storage, uri: str) -> DatasetRef:
    return DatasetRef(**json.loads(storage.read_bytes(uri).decode()))


def _family_refs(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        family, separator, uri = value.partition("=")
        if not separator or not family or not uri or family in result:
            raise ValueError("--family-ref must be unique FAMILY=DATASET_REF_URI")
        result[family] = uri
    return result


def _write_immutable(storage, uri: str, payload: bytes) -> None:
    if storage.exists(uri):
        if storage.read_bytes(uri) != payload:
            raise FileExistsError(f"Immutable artifact collision: {uri}")
        return
    storage.write_bytes(payload, uri)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", choices=("preview",), required=True)
    parser.add_argument("--team-universe-ref-uri", required=True)
    parser.add_argument("--family-ref", action="append", default=[])
    parser.add_argument("--context-uri", required=True)
    parser.add_argument("--context-ref-uri", required=True)
    parser.add_argument("--report-uri", required=True)
    parser.add_argument("--minimum-coverage", type=float, default=0.90)
    args = parser.parse_args()
    storage = get_storage(environment="preview")
    family_uris = _family_refs(args.family_ref)
    universe_ref = _ref(storage, args.team_universe_ref_uri)
    family_refs = {family: _ref(storage, uri) for family, uri in family_uris.items()}
    try:
        admission = admit_offseason_context(
            {family: read_dataset(storage, ref) for family, ref in family_refs.items()},
            read_dataset(storage, universe_ref),
            permitted_seasons=(
                2015,
                2016,
                2017,
                2018,
                2019,
                2021,
                2022,
                2023,
                2024,
                2025,
            ),
            source_refs={family: asdict(ref) for family, ref in family_refs.items()},
            minimum_coverage=args.minimum_coverage,
        )
    except ContextAdmissionError as exc:
        rejected = {
            "schema_version": REPORT_VERSION,
            "state": "rejected",
            "reason": str(exc),
            "team_universe_ref": asdict(universe_ref),
            "source_refs": {family: asdict(ref) for family, ref in family_refs.items()},
        }
        _write_immutable(
            storage, args.report_uri, json.dumps(rejected, indent=2, sort_keys=True).encode()
        )
        print(json.dumps({"report_uri": args.report_uri, "state": "rejected"}, sort_keys=True))
        return
    table = pa.Table.from_pandas(admission.context, preserve_index=False)
    buffer = io.BytesIO()
    pq.write_table(table, buffer)
    payload = buffer.getvalue()
    content_sha = hashlib.sha256(payload).hexdigest()
    context_ref = DatasetRef(
        dataset="offseason_context",
        version_id=content_sha[:16],
        schema_version="offseason_context_v1",
        content_sha=content_sha,
        uri=args.context_uri,
    )
    _write_immutable(storage, args.context_uri, payload)
    _write_immutable(
        storage,
        args.context_ref_uri,
        json.dumps(asdict(context_ref), sort_keys=True).encode(),
    )
    report = {**admission.report, "context_ref": asdict(context_ref), "team_universe_ref": asdict(universe_ref)}
    _write_immutable(storage, args.report_uri, json.dumps(report, indent=2, sort_keys=True).encode())
    print(json.dumps({"context_ref_uri": args.context_ref_uri, "report_uri": args.report_uri, "feature_track": report["feature_track"], "families": report["admitted_families"]}, sort_keys=True))


if __name__ == "__main__":
    main()
