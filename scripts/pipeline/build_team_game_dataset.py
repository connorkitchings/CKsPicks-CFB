#!/usr/bin/env python3
"""Build immutable by-play, drive, and reconciled team-game datasets."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone

from dotenv import load_dotenv

from cks_picks_cfb.data.catalog import (
    register_dataset_version,
    register_existing_dataset_ref,
    register_reconciliation_results,
)
from cks_picks_cfb.data.lake import (
    BuildRequest,
    DatasetRef,
    build_dataset_version,
    read_dataset,
)
from cks_picks_cfb.data.reconciliation import (
    reconcile_completed_games,
    require_reconciled,
)
from cks_picks_cfb.data.runtime import resolve_runtime_target
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.features.pipeline import build_preaggregation_pipeline


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
    parser.add_argument("--plays-ref-uri", required=True)
    parser.add_argument("--games-ref-uri", required=True)
    parser.add_argument("--teams-ref-uri")
    parser.add_argument("--venues-ref-uri")
    parser.add_argument("--weather-ref-uri")
    parser.add_argument("--game-stats-ref-uri")
    parser.add_argument("--corrections-ref-uri", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--output-ref-uri", required=True)
    parser.add_argument(
        "--environment",
        choices=["production", "preview"],
        required=True,
    )
    args = parser.parse_args()
    conn_url = resolve_runtime_target(args.environment).database_url
    storage = get_storage(environment=args.environment)
    if storage.exists(args.output_ref_uri):
        register_existing_dataset_ref(conn_url, storage, args.output_ref_uri)
        print(storage.read_bytes(args.output_ref_uri).decode())
        return
    refs = [_ref(storage, args.plays_ref_uri), _ref(storage, args.games_ref_uri)]
    optional = {}
    for name in ("teams", "venues", "weather", "game_stats", "corrections"):
        uri = getattr(args, f"{name}_ref_uri", None)
        if uri and storage.exists(uri):
            optional[name] = _ref(storage, uri)
            refs.append(optional[name])
    frames = {ref.dataset: read_dataset(storage, ref) for ref in refs}
    plays = read_dataset(storage, refs[0])
    games = read_dataset(storage, refs[1]).rename(columns={"kickoff_utc": "start_date"})
    byplay, drives, team_game, _ = build_preaggregation_pipeline(
        plays,
        games_df=games,
        teams_df=frames.get("teams"),
        venues_df=frames.get("venues"),
        weather_df=frames.get("weather_observations"),
        corrections_df=frames.get("data_corrections"),
    )
    reconciliation = reconcile_completed_games(
        games,
        team_game,
        frames.get("team_game_stats"),
    )
    cutoff = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    code_sha = _code_sha()
    config_sha = hashlib.sha256(b"team_game_pipeline_v1").hexdigest()
    outputs = []
    parent_refs = tuple(refs)
    seasons = sorted(
        {int(value) for value in games.get("season", []).tolist() if value is not None}
    )
    for dataset, frame, schema in (
        ("byplay", byplay, "byplay_v1"),
        ("drives", drives, "drives_v1"),
        ("reconciled_team_game", team_game, "team_game_v1"),
        ("source_reconciliation", reconciliation, "reconciliation_v1"),
    ):
        ref, manifest = build_dataset_version(
            storage,
            build=BuildRequest(
                dataset=dataset,
                parent_refs=parent_refs,
                code_sha=code_sha,
                config_sha=config_sha,
                as_of=cutoff,
                schema_version=schema,
                tier="silver",
            ),
            records=frame.to_dict("records"),
            partitions={"seasons": seasons},
            validation={
                "nonempty": not frame.empty,
                "no_blocking_conflicts": not (
                    dataset == "source_reconciliation"
                    and frame["blocking"].fillna(True).any()
                ),
            },
        )
        register_dataset_version(conn_url, ref, manifest)
        outputs.append(ref)
    final_ref = next(ref for ref in outputs if ref.dataset == "reconciled_team_game")
    register_reconciliation_results(
        conn_url,
        reconciliation,
        source_dataset_versions=[ref.version_id for ref in refs],
    )
    require_reconciled(reconciliation)
    payload = json.dumps(asdict(final_ref), indent=2, sort_keys=True).encode()
    if storage.exists(args.output_ref_uri):
        if storage.read_bytes(args.output_ref_uri) != payload:
            raise FileExistsError(f"Immutable ref exists: {args.output_ref_uri}")
    else:
        storage.write_bytes(payload, args.output_ref_uri)
    print(json.dumps([asdict(ref) for ref in outputs], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
