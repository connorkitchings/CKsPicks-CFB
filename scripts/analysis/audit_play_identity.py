#!/usr/bin/env python3
"""Read pinned play parents and measure by-play identity collisions without writes."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path

import pandas as pd
import psycopg
from dotenv import load_dotenv

from cks_picks_cfb.data.lake import (
    DatasetRef,
    SourceCapture,
    read_dataset,
    read_source_capture,
)
from cks_picks_cfb.data.storage import get_storage


def _plays_ref(block: dict) -> dict:
    matches = [parent for parent in block["parents"] if parent["dataset"] == "plays"]
    if len(matches) != 1:
        raise ValueError("One pinned plays parent is required per season")
    return matches[0]


def census(frame: pd.DataFrame, *, season: int, ref: dict, tier: str) -> dict:
    key = ["game_id", "drive_number", "play_number"]
    if set(key) - set(frame):
        raise ValueError(f"Pinned {season} plays lack sequence keys")
    id_column = next((name for name in ("play_id", "id") if name in frame), None)
    if id_column is None:
        raise ValueError(f"Pinned {season} plays lack provider play IDs")
    complete_sequence = frame[key].notna().all(axis=1)
    duplicates = frame.loc[complete_sequence & frame.duplicated(key, keep=False)]
    groups = duplicates.groupby(key, dropna=False, sort=False)
    missing_ids = frame[id_column].isna() | frame[id_column].astype(str).str.strip().eq(
        ""
    )
    identified = frame.loc[~missing_ids]
    id_conflicts = identified.loc[
        identified.duplicated(["game_id", id_column], keep=False)
    ]
    collisions = []
    for values, group in groups:
        identities = sorted(int(value) for value in group[id_column] if pd.notna(value))
        collisions.append(
            {
                **{
                    name: int(value) if pd.notna(value) else None
                    for name, value in zip(key, values)
                },
                "provider_play_ids": identities,
            }
        )
    drop_candidates = []
    if tier == "silver":
        current_drop = frame.loc[
            complete_sequence & frame.duplicated(key, keep="first")
        ]
        for row in current_drop.to_dict("records"):
            ppa = row.get("ppa")
            drop_candidates.append(
                {
                    "game_id": int(row["game_id"]),
                    "drive_number": int(row["drive_number"]),
                    "play_number": int(row["play_number"]),
                    "provider_play_id": str(row[id_column]),
                    "play_type": str(row.get("play_type", "")),
                    "offense": str(row.get("offense", "")),
                    "ppa": float(ppa) if pd.notna(ppa) else None,
                    "scoring": bool(row.get("scoring", False)),
                    "capture_id": str(row.get("__capture_id", "")),
                }
            )
        drop_candidates.sort(
            key=lambda row: (row["game_id"], row["drive_number"], row["play_number"])
        )
    return {
        "season": season,
        "ref_uri": ref["uri"],
        "ref_sha256": ref["content_sha"],
        "rows": len(frame),
        "provider_id_column": id_column,
        "source_tier": tier,
        "missing_provider_ids": int(missing_ids.sum()),
        "missing_sequence_rows": int((~complete_sequence).sum()),
        "duplicate_sequence_rows": len(duplicates),
        "duplicate_sequence_groups": len(groups),
        "distinct_id_sequence_groups": int(
            sum(
                group[id_column].notna().all()
                and group[id_column].nunique() == len(group)
                for _, group in groups
            )
        ),
        "same_id_rows": len(id_conflicts),
        "sequence_collisions": collisions,
        "current_sequence_dedup_drop_candidates": drop_candidates,
    }


def bronze_sources(storage, refs: dict[int, dict], conn_url: str):
    manifests = {}
    all_ids = set()
    for year, ref in refs.items():
        uri = ref["uri"].replace("/data.parquet", "/manifest.json")
        raw = storage.read_bytes(uri)
        ids = list(json.loads(raw).get("source_capture_ids", []))
        if not ids or len(ids) != len(set(ids)):
            raise ValueError(f"Pinned {year} plays lack unique Bronze captures")
        manifests[year] = (
            {"uri": uri, "content_sha": hashlib.sha256(raw).hexdigest()},
            ids,
        )
        all_ids.update(ids)
    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT capture_id, provider, entity, captured_at, effective_at, request, "
            "content_sha, object_sha, uri, row_count, provider_api_version, "
            "response_metadata, state FROM catalog.source_captures WHERE capture_id = ANY(%s)",
            (sorted(all_ids),),
        )
        rows = cur.fetchall()
    captures = {
        str(row[0]): SourceCapture(
            capture_id=str(row[0]),
            provider=str(row[1]),
            entity=str(row[2]),
            captured_at=row[3],
            effective_at=row[4],
            request=dict(row[5]),
            content_sha=str(row[6]),
            object_sha=str(row[7]),
            uri=str(row[8]),
            row_count=int(row[9]),
            provider_api_version=str(row[10]) if row[10] else None,
            response_metadata=dict(row[11] or {}),
            state=str(row[12]),
        )
        for row in rows
    }
    if set(captures) != all_ids:
        raise ValueError(f"Missing Bronze captures: {sorted(all_ids - set(captures))}")
    return {
        year: (ref, [captures[capture_id] for capture_id in ids])
        for year, (ref, ids) in manifests.items()
    }


def normalize_bronze(frame: pd.DataFrame) -> pd.DataFrame:
    if "provider_record" not in frame:
        return frame
    values = frame["provider_record"].map(
        lambda value: ast.literal_eval(value) if isinstance(value, str) else value
    )
    if not values.map(lambda value: isinstance(value, dict)).all():
        raise ValueError("Wrapped Bronze play record is not a mapping")
    nested = pd.DataFrame.from_records(values.tolist())
    return nested.rename(
        columns={
            "gameId": "game_id",
            "driveNumber": "drive_number",
            "playNumber": "play_number",
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historical-parents", type=Path, required=True)
    parser.add_argument("--season-2026-parents", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--include-bronze", action="store_true")
    args = parser.parse_args()
    load_dotenv(".env")
    if os.getenv("CFB_STORAGE_BACKEND") != "r2":
        raise SystemExit("Identity census requires explicit R2 storage")
    historical = json.loads(args.historical_parents.read_text())["seasons"]
    current = json.loads(args.season_2026_parents.read_text())
    blocks = {int(year): block for year, block in historical.items()}
    blocks[2026] = current
    storage = get_storage(environment="preview")
    reports = []
    refs = {year: _plays_ref(block) for year, block in blocks.items()}
    bronze = None
    if args.include_bronze:
        conn_url = os.getenv("PREVIEW_DATABASE_URL")
        if not conn_url:
            raise SystemExit("Bronze census requires PREVIEW_DATABASE_URL")
        bronze = bronze_sources(storage, refs, conn_url)
    for year, block in sorted(blocks.items()):
        ref = refs[year]
        pinned = DatasetRef(
            **{
                name: ref[name]
                for name in (
                    "dataset",
                    "version_id",
                    "schema_version",
                    "content_sha",
                    "uri",
                )
            }
        )
        report = census(
            read_dataset(storage, pinned), season=year, ref=ref, tier="silver"
        )
        if bronze is not None:
            bronze_ref, captures = bronze[year]
            frames = [read_source_capture(storage, capture) for capture in captures]
            for frame, capture in zip(frames, captures):
                if len(frame) != capture.row_count:
                    raise ValueError(
                        f"Bronze row count differs for {capture.capture_id}"
                    )
            source_report = census(
                pd.concat(
                    [normalize_bronze(frame) for frame in frames], ignore_index=True
                ),
                season=year,
                ref=bronze_ref,
                tier="bronze",
            )
            source_report["source_capture_count"] = len(captures)
            report["bronze"] = source_report
            report["collision_identities_match_bronze"] = {
                json.dumps(item, sort_keys=True)
                for item in report["sequence_collisions"]
            } == {
                json.dumps(item, sort_keys=True)
                for item in source_report["sequence_collisions"]
            }
        reports.append(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            {"schema_version": "play_identity_census_v1", "seasons": reports},
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    print(
        json.dumps(
            {
                "seasons": len(reports),
                "duplicate_sequence_rows": sum(
                    r["duplicate_sequence_rows"] for r in reports
                ),
                "missing_provider_ids": sum(r["missing_provider_ids"] for r in reports),
            }
        )
    )


if __name__ == "__main__":
    main()
