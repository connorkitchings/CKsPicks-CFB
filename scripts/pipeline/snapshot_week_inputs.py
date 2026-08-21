#!/usr/bin/env python3
"""Freeze mutable compatibility partitions into explicit immutable dataset refs."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from datetime import datetime, time, timezone

from dotenv import load_dotenv

from cks_picks_cfb.data.catalog import dataset_ref_for_partition_as_of
from cks_picks_cfb.data.lake import DatasetRef, read_dataset
from cks_picks_cfb.data.storage import get_storage


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--pipeline-run-id", required=True)
    parser.add_argument("--market-ref-uri")
    parser.add_argument(
        "--prepared-gold-ref-uri",
        help="Explicit immutable Gold ref produced by prepare-week.",
    )
    args = parser.parse_args()
    cutoff = datetime.fromisoformat(args.as_of)
    if "T" not in args.as_of:
        cutoff = datetime.combine(cutoff.date(), time.max)
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    storage = get_storage()
    conn_url = os.getenv("DATABASE_URL")
    if not conn_url:
        raise SystemExit("DATABASE_URL is not set")
    cutoff_iso = cutoff.astimezone(timezone.utc).isoformat()
    inputs = (
        ("games", "games"),
        ("betting_lines", "market_snapshots"),
        ("point_in_time_matchups", "point_in_time_matchups"),
    )
    refs = []
    for entity, dataset in inputs:
        if dataset == "market_snapshots" and args.market_ref_uri:
            raw_ref = json.loads(storage.read_bytes(args.market_ref_uri).decode())
            ref = DatasetRef(**raw_ref)
        elif dataset == "point_in_time_matchups" and args.prepared_gold_ref_uri:
            raw_ref = json.loads(
                storage.read_bytes(args.prepared_gold_ref_uri).decode()
            )
            ref = DatasetRef(**raw_ref)
            if ref.dataset != "point_in_time_matchups":
                raise SystemExit(f"Prepared Gold has wrong dataset: {ref.dataset}")
        else:
            ref = dataset_ref_for_partition_as_of(
                conn_url,
                dataset,
                cutoff_iso,
                partitions={"seasons": [args.year]},
            )
        refs.append(
            {
                "entity": entity,
                "year": args.year,
                **asdict(ref),
            }
        )
    gold = next(ref for ref in refs if ref["entity"] == "point_in_time_matchups")
    gold_frame = read_dataset(
        storage,
        DatasetRef(
            **{
                field: gold[field]
                for field in (
                    "dataset",
                    "version_id",
                    "schema_version",
                    "content_sha",
                    "uri",
                )
            }
        ),
    )
    target = gold_frame[
        (gold_frame["season"].astype(int) == args.year)
        & (gold_frame["week"].astype(int) == args.week)
    ]
    if target.empty:
        raise SystemExit("Selected Gold contains no target-week rows")
    output_uri = (
        f"artifacts/{os.getenv('CFB_ARTIFACT_ENV', 'production')}/"
        f"pipeline-runs/{args.pipeline_run_id}/input_refs.json"
    )
    payload = json.dumps(refs, indent=2, sort_keys=True).encode("utf-8")
    if storage.exists(output_uri):
        if storage.read_bytes(output_uri) != payload:
            raise FileExistsError(f"Input ref set changed for {args.pipeline_run_id}")
    else:
        storage.write_bytes(payload, output_uri)
    print(output_uri)


if __name__ == "__main__":
    main()
