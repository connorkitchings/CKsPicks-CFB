#!/usr/bin/env python3
"""Append independently verified intended-update ratings to Neon serving."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from typing import Any

import pandas as pd
import psycopg
from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ops.lease import assert_active_pipeline_lease
from cks_picks_cfb.ops.v5_release import assert_v5_database_environment
from cks_picks_cfb.ratings.possession_intended_update import CANDIDATE_ID

INSERT_COLUMNS = (
    "snapshot_id",
    "source_run_id",
    "source_manifest_sha256",
    "team",
    "season",
    "week",
    "game_id",
    "snapshot_class",
    "cutoff_utc",
    "offense_rating",
    "offense_variance",
    "defense_rating",
    "defense_variance",
    "overall_rating",
    "overall_variance",
    "fallback_reason",
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _load_child(storage: Any, ref: dict[str, Any]) -> pd.DataFrame:
    raw = storage.read_bytes(ref["uri"])
    if _sha(raw) != ref["raw_sha256"]:
        raise ValueError("intended-update rating child checksum changed")
    frame = pd.read_parquet(io.BytesIO(raw))
    if len(frame) != int(ref["rows"]):
        raise ValueError("intended-update rating child count changed")
    return frame


def load_verified_snapshots(storage: Any, uri: str) -> tuple[list[dict[str, Any]], str]:
    raw = storage.read_bytes(uri)
    manifest = json.loads(raw)
    verify_signed_payload(manifest, label="intended-update rating manifest")
    digest = _sha(raw)
    if (
        manifest.get("schema_version") != "v5_intended_update_2026_rating_manifest_v1"
        or manifest.get("state") != "frozen"
        or manifest.get("candidate_id") != CANDIDATE_ID
        or manifest.get("production_activation_authorized") is not False
    ):
        raise ValueError("rating manifest is not the reviewed successor")
    verifier_uri = f"{uri.rsplit('/', 1)[0]}/verification/verifier-manifest.json"
    verifier = json.loads(storage.read_bytes(verifier_uri))
    verify_signed_payload(verifier, label="intended-update rating verification")
    if (
        verifier.get("schema_version")
        != "v5_intended_update_2026_rating_verification_v1"
        or verifier.get("state") != "verified"
        or verifier.get("rating_manifest_raw_sha256") != digest
    ):
        raise ValueError("rating manifest lacks a matching independent verifier")
    refs = manifest["output_refs"]
    priors = _load_child(storage, refs["priors"])
    pregame = _load_child(storage, refs["pregame_teams"])
    current = _load_child(storage, refs["current_teams"])
    if len(priors) != 276 or priors.duplicated(["team", "unit_role"]).any():
        raise ValueError("certified prior coverage changed")
    p_off = priors[priors.unit_role.eq("offense")].set_index("team")
    p_def = priors[priors.unit_role.eq("defense")].set_index("team")
    teams = sorted(set(p_off.index) & set(p_def.index))
    if len(teams) != 138:
        raise ValueError("preseason rating projection lacks 138 teams")
    run_id = manifest["identity"]["run_id"]
    records: list[dict[str, Any]] = []
    for team in teams:
        off, defense = p_off.loc[team], p_def.loc[team]
        off_mean, off_var = float(off.prior_mean), float(off.prior_variance)
        def_mean, def_var = float(defense.prior_mean), float(defense.prior_variance)
        fallbacks = sorted(
            {
                str(value)
                for value in (
                    off.get("fallback_reason"),
                    defense.get("fallback_reason"),
                )
                if pd.notna(value) and str(value)
            }
        )
        records.append(
            {
                "snapshot_id": f"{run_id}:pregame:{team}:preseason",
                "source_run_id": run_id,
                "source_manifest_sha256": digest,
                "team": team,
                "season": 2026,
                "week": 0,
                "game_id": None,
                "snapshot_class": "pregame",
                "cutoff_utc": pd.Timestamp("2026-08-20T00:00:00Z").to_pydatetime(),
                "offense_rating": off_mean,
                "offense_variance": off_var,
                "defense_rating": def_mean,
                "defense_variance": def_var,
                "overall_rating": (off_mean + def_mean) / 2,
                "overall_variance": (off_var + def_var) / 4,
                "fallback_reason": ";".join(fallbacks) or None,
            }
        )
    for classification, frame in (("pregame", pregame), ("current", current)):
        if frame.duplicated(["week", "game_id", "team"]).any():
            raise ValueError("rating projection duplicates a generation team")
        for row in frame.itertuples(index=False):
            post_week = int(row.week) - 1
            game_id = int(row.game_id) if classification == "pregame" else None
            records.append(
                {
                    "snapshot_id": f"{run_id}:pregame:{row.team}:{game_id}"
                    if classification == "pregame"
                    else f"{run_id}:current:post-week-{post_week}:{row.team}",
                    "source_run_id": run_id,
                    "source_manifest_sha256": digest,
                    "team": str(row.team),
                    "season": 2026,
                    "week": int(row.week) if classification == "pregame" else post_week,
                    "game_id": game_id,
                    "snapshot_class": classification,
                    "cutoff_utc": pd.Timestamp(row.cutoff_utc).to_pydatetime(),
                    "offense_rating": float(row.offense_rating),
                    "offense_variance": float(row.offense_variance),
                    "defense_rating": float(row.defense_rating),
                    "defense_variance": float(row.defense_variance),
                    "overall_rating": float(row.overall_rating),
                    "overall_variance": float(row.overall_variance),
                    "fallback_reason": None,
                }
            )
    if len(records) != 138 + len(pregame) + len(current):
        raise ValueError("rating projection row count changed")
    return records, digest


def _project(cur: Any, records: list[dict[str, Any]]) -> tuple[int, int]:
    inserted = 0
    skipped = 0
    placeholders = ", ".join(f"%({name})s" for name in INSERT_COLUMNS)
    insert = (
        f"INSERT INTO v5_rating_snapshots ({', '.join(INSERT_COLUMNS)}) "
        f"VALUES ({placeholders}) ON CONFLICT (snapshot_id) DO NOTHING"
    )
    select = f"SELECT {', '.join(INSERT_COLUMNS)} FROM v5_rating_snapshots WHERE snapshot_id = %s"
    for record in records:
        cur.execute(insert, record)
        if cur.rowcount:
            inserted += 1
            continue
        cur.execute(select, (record["snapshot_id"],))
        existing = cur.fetchone()
        if existing is None:
            raise ValueError("rating projection conflict row disappeared")
        for name, actual in zip(INSERT_COLUMNS, existing, strict=True):
            expected = record[name]
            if name == "cutoff_utc":
                actual = pd.Timestamp(actual).tz_convert("UTC")
                expected = pd.Timestamp(expected).tz_convert("UTC")
            if actual != expected:
                raise ValueError(
                    f"rating projection conflicts with existing {record['snapshot_id']}: {name}"
                )
        skipped += 1
    return inserted, skipped


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rating-manifest-uri", required=True)
    parser.add_argument(
        "--environment", choices=("preview", "production"), required=True
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    storage = get_storage(environment="preview")
    records, digest = load_verified_snapshots(storage, args.rating_manifest_uri)
    if not args.apply:
        print(json.dumps({"rows": len(records), "rating_manifest_sha256": digest}))
        return
    key = "PREVIEW_DATABASE_URL" if args.environment == "preview" else "DATABASE_URL"
    url = os.getenv(key)
    if not url:
        raise ValueError(f"{key} is required")
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            assert_v5_database_environment(cur, args.environment)
            assert_active_pipeline_lease(cur)
            inserted, skipped = _project(cur, records)
    print(
        json.dumps(
            {
                "inserted": inserted,
                "unchanged": skipped,
                "rating_manifest_sha256": digest,
            }
        )
    )


if __name__ == "__main__":
    main()
