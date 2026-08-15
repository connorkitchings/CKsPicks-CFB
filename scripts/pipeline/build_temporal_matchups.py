#!/usr/bin/env python3
"""Build point-in-time matchup inputs from reconciled team-game history."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone

from dotenv import load_dotenv

from cks_picks_cfb.data.catalog import (
    catalog_connection_url,
    register_dataset_version,
    register_existing_dataset_ref,
)
from cks_picks_cfb.data.lake import (
    BuildRequest,
    DatasetRef,
    build_dataset_version,
    read_dataset,
)
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.features.point_in_time import build_temporal_matchup_inputs


def _ref(storage, uri: str) -> DatasetRef:
    return DatasetRef(**json.loads(storage.read_bytes(uri).decode()))


def _code_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team-game-ref-uri", required=True)
    parser.add_argument("--schedule-ref-uri", required=True)
    parser.add_argument("--prior-2019-ref-uri", required=True)
    parser.add_argument("--outcomes-ref-uri")
    parser.add_argument(
        "--inference-season",
        action="append",
        type=int,
        default=[],
        help="Season retained without completed historical outcomes (repeatable).",
    )
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--output-ref-uri", required=True)
    parser.add_argument(
        "--environment",
        choices=["production", "preview"],
        default=os.getenv("CFB_ARTIFACT_ENV", "production"),
    )
    args = parser.parse_args()
    storage = get_storage(environment=args.environment)
    if storage.exists(args.output_ref_uri):
        register_existing_dataset_ref(
            catalog_connection_url(args.environment), storage, args.output_ref_uri
        )
        print(storage.read_bytes(args.output_ref_uri).decode())
        return
    team_game_ref = _ref(storage, args.team_game_ref_uri)
    schedule_ref = _ref(storage, args.schedule_ref_uri)
    prior_ref = _ref(storage, args.prior_2019_ref_uri)
    outcomes_ref = (
        _ref(storage, args.outcomes_ref_uri) if args.outcomes_ref_uri else None
    )
    result = build_temporal_matchup_inputs(
        read_dataset(storage, schedule_ref),
        read_dataset(storage, team_game_ref),
        prior_2019=read_dataset(storage, prior_ref),
        outcomes=(read_dataset(storage, outcomes_ref) if outcomes_ref else None),
        inference_seasons=frozenset(args.inference_season),
    )
    cutoff = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    ref, manifest = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset="temporal_matchup_inputs",
            parent_refs=(
                team_game_ref,
                schedule_ref,
                prior_ref,
                *((outcomes_ref,) if outcomes_ref else ()),
            ),
            code_sha=_code_sha(),
            config_sha=hashlib.sha256(
                b"temporal_matchup_inputs_alpha_0.5_v1"
            ).hexdigest(),
            as_of=cutoff,
            schema_version="temporal_matchup_inputs_v1",
            tier="gold",
        ),
        records=result.to_dict("records"),
        partitions={"seasons": sorted(result["season"].astype(int).unique().tolist())},
        event_time_column="start_date",
        validation={
            "unique_game_keys": not result.duplicated(["season", "game_id"]).any(),
            "excludes_2020": 2020 not in set(result["season"].astype(int)),
            "contains_2026": 2026 in set(result["season"].astype(int)),
            "separate_prior_current": any(
                column.startswith("home_prior_") for column in result
            )
            and any(column.startswith("home_current_") for column in result),
        },
    )
    if manifest.state != "validated":
        raise RuntimeError(f"Temporal matchup validation failed: {manifest.validation}")
    if args.environment == "preview":
        conn_url = os.getenv("PREVIEW_DATABASE_URL") or os.getenv("DATABASE_URL")
    else:
        conn_url = os.getenv("DATABASE_URL")
    if not conn_url:
        raise SystemExit("DATABASE_URL is required")
    register_dataset_version(conn_url, ref, manifest)
    payload = json.dumps(asdict(ref), indent=2, sort_keys=True).encode()
    if storage.exists(args.output_ref_uri):
        if storage.read_bytes(args.output_ref_uri) != payload:
            raise FileExistsError(
                f"Immutable matchup ref exists: {args.output_ref_uri}"
            )
    else:
        storage.write_bytes(payload, args.output_ref_uri)
    print(json.dumps(asdict(ref), sort_keys=True))


if __name__ == "__main__":
    main()
