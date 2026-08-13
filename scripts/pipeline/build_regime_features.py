#!/usr/bin/env python3
"""Build one immutable Gold matchup dataset from explicit Silver parents."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone

from dotenv import load_dotenv

from cks_picks_cfb.data.catalog import register_dataset_version
from cks_picks_cfb.data.lake import (
    BuildRequest,
    DatasetRef,
    build_dataset_version,
    read_dataset,
)
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.features.point_in_time import (
    attach_baseline_predictions,
    build_team_side_gold,
    team_side_to_wide,
)


def _ref(storage, uri: str) -> DatasetRef:
    raw = json.loads(storage.read_bytes(uri).decode("utf-8"))
    return DatasetRef(
        dataset=str(raw["dataset"]),
        version_id=str(raw["version_id"]),
        schema_version=str(raw["schema_version"]),
        content_sha=str(raw["content_sha"]),
        uri=str(raw["uri"]),
    )


def _code_sha() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return completed.stdout.strip() if completed.returncode == 0 else "unknown"


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matchups-ref-uri", required=True)
    parser.add_argument("--schedule-ref-uri", required=True)
    parser.add_argument("--baselines-ref-uri")
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--output-ref-uri", required=True)
    parser.add_argument(
        "--environment",
        choices=["production", "preview"],
        default=os.getenv("CFB_ARTIFACT_ENV", "production"),
    )
    args = parser.parse_args()
    cutoff = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    storage = get_storage(environment=args.environment)
    if storage.exists(args.output_ref_uri):
        print(storage.read_bytes(args.output_ref_uri).decode())
        return
    matchup_ref = _ref(storage, args.matchups_ref_uri)
    schedule_ref = _ref(storage, args.schedule_ref_uri)
    baselines_ref = (
        _ref(storage, args.baselines_ref_uri) if args.baselines_ref_uri else None
    )
    matchups = read_dataset(storage, matchup_ref)
    schedule = read_dataset(storage, schedule_ref)
    if "kickoff_utc" in schedule.columns and "start_date" not in schedule.columns:
        schedule = schedule.rename(columns={"kickoff_utc": "start_date"})
    team_side = build_team_side_gold(
        matchups,
        schedule,
        as_of=cutoff.isoformat(),
        provenance={
            "matchups": matchup_ref.version_id,
            "schedule": schedule_ref.version_id,
        },
    )
    if team_side.empty:
        raise RuntimeError("Gold point-in-time matchup build produced no rows")
    config_sha = hashlib.sha256(
        json.dumps(
            {
                "prior_source_overrides": {"2021": 2019},
                "excluded_years": [2020],
                "routing": "min_completed_games_v1",
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    team_ref, team_manifest = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset="point_in_time_team_features",
            parent_refs=(matchup_ref, schedule_ref),
            code_sha=_code_sha(),
            config_sha=config_sha,
            as_of=cutoff,
            schema_version="point_in_time_team_features_v1",
            tier="gold",
        ),
        records=team_side.to_dict("records"),
        partitions={
            "seasons": sorted(team_side["season"].astype(int).unique().tolist())
        },
        event_time_column="kickoff_utc",
        coverage={
            "rows_by_season": {
                str(year): int(count)
                for year, count in team_side.groupby("season").size().items()
            },
            "rows_by_regime": {
                str(regime): int(count)
                for regime, count in team_side.groupby("prediction_regime")
                .size()
                .items()
            },
        },
        validation={
            "unique_team_keys": not team_side.duplicated(
                ["season", "game_id", "team"]
            ).any(),
            "excludes_2020": 2020 not in set(team_side["season"].astype(int))
            and 2020 not in set(team_side["prior_source_season"].astype(int)),
        },
    )
    if not all(team_manifest.validation.values()):
        raise RuntimeError(
            f"Gold team-side validation failed: {team_manifest.validation}"
        )
    result = team_side_to_wide(team_side)
    if baselines_ref is not None:
        required_baseline_seasons = set(result["season"].astype(int)) - {2021}
        result = attach_baseline_predictions(
            result,
            read_dataset(storage, baselines_ref),
            required_seasons=required_baseline_seasons,
        )
    output_dataset = (
        "point_in_time_matchups" if baselines_ref else "point_in_time_matchups_core"
    )
    ref, manifest = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset=output_dataset,
            parent_refs=(team_ref, *((baselines_ref,) if baselines_ref else ())),
            code_sha=_code_sha(),
            config_sha=config_sha,
            as_of=cutoff,
            schema_version=(
                "point_in_time_matchups_v3"
                if baselines_ref
                else "point_in_time_matchups_core_v1"
            ),
            tier="gold",
        ),
        records=result.to_dict("records"),
        partitions={"seasons": sorted(result["season"].astype(int).unique().tolist())},
        event_time_column="start_date",
        coverage={
            "rows_by_season": {
                str(year): int(count)
                for year, count in result.groupby("season").size().items()
            },
            "rows_by_regime": {
                str(regime): int(count)
                for regime, count in result.groupby("prediction_regime").size().items()
            },
        },
        validation={
            "unique_game_keys": not result.duplicated(["season", "game_id"]).any(),
            **(
                {
                    "baseline_complete": not result[
                        result["season"].astype(int) != 2021
                    ][["baseline_spread_prediction", "baseline_total_prediction"]]
                    .isna()
                    .any()
                    .any()
                }
                if baselines_ref
                else {}
            ),
            "excludes_2020": 2020 not in set(result["season"].astype(int))
            and 2020 not in set(result["prior_source_season"].astype(int)),
        },
    )
    if not all(manifest.validation.values()):
        raise RuntimeError(f"Gold dataset validation failed: {manifest.validation}")
    if args.environment == "preview":
        conn_url = os.getenv("PREVIEW_DATABASE_URL") or os.getenv("DATABASE_URL")
    else:
        conn_url = os.getenv("DATABASE_URL")
    if not conn_url:
        raise SystemExit("DATABASE_URL is required for catalog registration")
    register_dataset_version(conn_url, team_ref, team_manifest)
    register_dataset_version(conn_url, ref, manifest)
    payload = json.dumps(asdict(ref), indent=2, sort_keys=True).encode("utf-8")
    if storage.exists(args.output_ref_uri):
        if storage.read_bytes(args.output_ref_uri) != payload:
            raise FileExistsError(f"Immutable ref exists: {args.output_ref_uri}")
    else:
        storage.write_bytes(payload, args.output_ref_uri)
    print(json.dumps(asdict(ref), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
