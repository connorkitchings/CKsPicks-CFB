#!/usr/bin/env python3
"""Build the isolated Phase 1 rating measurement research datasets.

Preview-only: reads immutable byplay, drives, games, outcomes, and reconciled
team-game parents and writes long-form raw observations, strictly pregame
adjusted snapshots, and the coverage/redundancy audit report under the
research prefix. Never writes predictions, V4 references, or production
artifacts, and refuses production runtime targets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from cks_picks_cfb.data.catalog import register_dataset_version
from cks_picks_cfb.data.lake import (
    BuildRequest,
    DatasetRef,
    build_dataset_version,
    read_dataset,
    require_dataset,
)
from cks_picks_cfb.data.runtime import resolve_runtime_target
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ratings.audit import build_rating_audit_report
from cks_picks_cfb.ratings.contracts import (
    OBSERVATION_DATASET,
    OBSERVATION_SCHEMA_VERSION,
    SNAPSHOT_DATASET,
    SNAPSHOT_SCHEMA_VERSION,
    TERMINAL_SNAPSHOT_DATASET,
    TERMINAL_SNAPSHOT_SCHEMA_VERSION,
    load_measurement_config,
    validate_observation_frame,
    validate_snapshot_frame,
    validate_terminal_snapshot_frame,
    verify_design_id,
)
from cks_picks_cfb.ratings.observations import build_measurement_observations
from cks_picks_cfb.ratings.snapshots import (
    build_pregame_snapshots,
    build_season_terminal_snapshots,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "conf" / "ratings" / "measurement_baseline_v1.yaml"
RELEVANT_CODE_PATHS = (
    "src/cks_picks_cfb/ratings",
    "src/cks_picks_cfb/data/schema_contracts.py",
    "scripts/pipeline/build_rating_measurements.py",
    "conf/ratings/measurement_baseline_v1.yaml",
)


def _ref(storage, uri: str) -> DatasetRef:
    return DatasetRef(**json.loads(storage.read_bytes(uri).decode()))


def _code_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _require_committed_code(expected_code_sha: str | None = None) -> str:
    """Ensure materialized artifacts name a commit containing the relevant code."""
    code_sha = expected_code_sha or _code_sha()
    if code_sha == "unknown":
        raise ValueError("Rating artifacts require a resolvable Git commit SHA")
    for path in RELEVANT_CODE_PATHS:
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", path],
            capture_output=True,
            text=True,
            check=False,
            cwd=REPO_ROOT,
        )
        if tracked.returncode:
            raise ValueError(f"Rating artifact path is not committed: {path}")
    clean = subprocess.run(
        ["git", "diff", "--quiet", code_sha, "--", *RELEVANT_CODE_PATHS],
        capture_output=True,
        check=False,
        cwd=REPO_ROOT,
    )
    if clean.returncode:
        raise ValueError("Rating artifact paths differ from the recorded commit")
    return code_sha


def _write_immutable_json(storage, uri: str, payload: bytes) -> None:
    if storage.exists(uri):
        if storage.read_bytes(uri) != payload:
            raise FileExistsError(f"Immutable artifact exists: {uri}")
        return
    storage.write_bytes(payload, uri)


def _load_grouped_frames(
    storage, uris: list[str], expected: str, flag: str
) -> tuple[DatasetRef, ...]:
    if not uris:
        raise ValueError(f"At least one {flag} is required")
    refs = []
    for uri in uris:
        ref = _ref(storage, uri)
        require_dataset(ref, expected)
        refs.append(ref)
    return tuple(refs)


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--environment", choices=["preview", "production"], required=True
    )
    parser.add_argument("--measurement-config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--expected-design-id")
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--byplay-ref-uri", action="append", required=True)
    parser.add_argument("--drives-ref-uri", action="append", required=True)
    parser.add_argument("--games-ref-uri", action="append", required=True)
    parser.add_argument("--outcomes-ref-uri", action="append", required=True)
    parser.add_argument("--team-game-ref-uri", action="append", required=True)
    parser.add_argument("--observations-ref-uri", required=True)
    parser.add_argument("--snapshots-ref-uri", required=True)
    parser.add_argument("--terminal-snapshots-ref-uri", required=True)
    parser.add_argument("--report-uri", required=True)
    parser.add_argument("--register-catalog", action="store_true")
    parser.add_argument("--expected-code-sha")
    args = parser.parse_args(argv)

    if args.environment == "production":
        raise ValueError(
            "Rating measurement research builds are permitted only in preview"
        )

    config = load_measurement_config(args.measurement_config)
    if args.expected_design_id:
        verify_design_id(config, args.expected_design_id)

    prefix = f"{config.research_prefix}/{config.design_id}"
    for uri in (
        args.observations_ref_uri,
        args.snapshots_ref_uri,
        args.terminal_snapshots_ref_uri,
        args.report_uri,
    ):
        if not uri.startswith(f"{prefix}/"):
            raise ValueError(
                f"Output URI {uri!r} must live under the research prefix {prefix!r}"
            )

    cutoff = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)

    storage = get_storage(environment=args.environment)

    byplay_refs = _load_grouped_frames(
        storage, args.byplay_ref_uri, "byplay", "--byplay-ref-uri"
    )
    drives_refs = _load_grouped_frames(
        storage, args.drives_ref_uri, "drives", "--drives-ref-uri"
    )
    games_refs = _load_grouped_frames(
        storage, args.games_ref_uri, "games", "--games-ref-uri"
    )
    outcome_refs = _load_grouped_frames(
        storage, args.outcomes_ref_uri, "game_outcomes", "--outcomes-ref-uri"
    )
    team_game_refs = _load_grouped_frames(
        storage, args.team_game_ref_uri, "reconciled_team_game", "--team-game-ref-uri"
    )

    def _concat(refs: tuple[DatasetRef, ...]) -> pd.DataFrame:
        frames = [read_dataset(storage, ref) for ref in refs]
        columns = [tuple(frame.columns) for frame in frames]
        if any(column != columns[0] for column in columns):
            raise ValueError(f"Parent frames disagree on columns: {columns}")
        nonempty = [frame for frame in frames if not frame.empty]
        if not nonempty:
            return frames[0]
        return pd.concat(nonempty, ignore_index=True)

    byplay = _concat(byplay_refs)
    drives = _concat(drives_refs)
    games = _concat(games_refs)
    outcomes = _concat(outcome_refs)
    reconciled_team_game = _concat(team_game_refs)

    parent_refs = byplay_refs + drives_refs + games_refs + outcome_refs + team_game_refs
    parent_ref_shas = ";".join(ref.content_sha for ref in parent_refs)
    code_sha = _require_committed_code(args.expected_code_sha)
    config_sha = config.design_id

    observation_build = build_measurement_observations(
        byplay=byplay,
        drives=drives,
        games=games,
        outcomes=outcomes,
        reconciled_team_game=reconciled_team_game,
        config=config,
        as_of=cutoff,
        code_sha=code_sha,
        config_sha=config_sha,
        parent_ref_shas=parent_ref_shas,
    )
    validate_observation_frame(observation_build.frame, config)
    observations_ref, observations_manifest = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset=OBSERVATION_DATASET,
            parent_refs=parent_refs,
            code_sha=code_sha,
            config_sha=config_sha,
            as_of=cutoff,
            schema_version=OBSERVATION_SCHEMA_VERSION,
            tier="gold",
        ),
        records=observation_build.frame.to_dict("records"),
        partitions={
            "seasons": sorted(
                int(season) for season in set(observation_build.frame["season"])
            )
        }
        if not observation_build.frame.empty
        else {"seasons": []},
        validation={
            "nonempty": not observation_build.frame.empty,
            "ratings_contract_valid": True,
        },
    )

    snapshot_build = build_pregame_snapshots(
        observations=observation_build.frame,
        games=games,
        config=config,
        code_sha=code_sha,
        config_sha=config_sha,
        parent_observation_version_id=observations_ref.version_id,
        parent_ref_shas=";".join(
            [observations_ref.content_sha] + [ref.content_sha for ref in games_refs]
        ),
    )
    validate_snapshot_frame(snapshot_build.frame, config)
    snapshots_ref, snapshots_manifest = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset=SNAPSHOT_DATASET,
            parent_refs=(observations_ref,) + games_refs,
            code_sha=code_sha,
            config_sha=config_sha,
            as_of=cutoff,
            schema_version=SNAPSHOT_SCHEMA_VERSION,
            tier="gold",
        ),
        records=snapshot_build.frame.to_dict("records"),
        partitions={
            "seasons": sorted(
                int(season) for season in set(snapshot_build.frame["season"])
            )
        }
        if not snapshot_build.frame.empty
        else {"seasons": []},
        validation={
            "nonempty": not snapshot_build.frame.empty,
            "ratings_contract_valid": True,
        },
    )

    terminal_build = build_season_terminal_snapshots(
        observations=observation_build.frame,
        games=games,
        config=config,
        code_sha=code_sha,
        config_sha=config_sha,
        parent_observation_version_id=observations_ref.version_id,
        parent_ref_shas=";".join(
            [observations_ref.content_sha] + [ref.content_sha for ref in games_refs]
        ),
    )
    validate_terminal_snapshot_frame(terminal_build.frame, config)
    terminal_ref, terminal_manifest = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset=TERMINAL_SNAPSHOT_DATASET,
            parent_refs=(observations_ref,) + games_refs,
            code_sha=code_sha,
            config_sha=config_sha,
            as_of=cutoff,
            schema_version=TERMINAL_SNAPSHOT_SCHEMA_VERSION,
            tier="gold",
        ),
        records=terminal_build.frame.to_dict("records"),
        partitions={"seasons": list(config.historical_development_seasons)},
        validation={
            "nonempty": not terminal_build.frame.empty,
            "ratings_contract_valid": True,
        },
    )

    report = build_rating_audit_report(
        observations=observation_build.frame,
        snapshots=snapshot_build.frame,
        terminal_snapshots=terminal_build.frame,
        games=games,
        reconciled_team_game=reconciled_team_game,
        config=config,
        observations_ref=asdict(observations_ref),
        snapshots_ref=asdict(snapshots_ref),
        terminal_snapshots_ref=asdict(terminal_ref),
        parent_refs=tuple(asdict(ref) for ref in parent_refs),
        cutoff=cutoff.isoformat(),
        code_sha=code_sha,
        build_audit=observation_build.audit,
    )
    report_payload = json.dumps(report, indent=2, sort_keys=True, default=str).encode()
    _write_immutable_json(storage, args.report_uri, report_payload)
    if not report["all_checks_passed"]:
        raise ValueError(
            "Phase 1 audit failed; successful artifact refs were not published"
        )

    _write_immutable_json(
        storage,
        args.observations_ref_uri,
        json.dumps(asdict(observations_ref), indent=2, sort_keys=True).encode(),
    )
    _write_immutable_json(
        storage,
        args.terminal_snapshots_ref_uri,
        json.dumps(asdict(terminal_ref), indent=2, sort_keys=True).encode(),
    )
    _write_immutable_json(
        storage,
        args.snapshots_ref_uri,
        json.dumps(asdict(snapshots_ref), indent=2, sort_keys=True).encode(),
    )

    if args.register_catalog:
        conn_url = resolve_runtime_target("preview").database_url
        register_dataset_version(conn_url, observations_ref, observations_manifest)
        register_dataset_version(conn_url, snapshots_ref, snapshots_manifest)
        register_dataset_version(conn_url, terminal_ref, terminal_manifest)

    print(
        json.dumps(
            {
                "observations_ref": asdict(observations_ref),
                "snapshots_ref": asdict(snapshots_ref),
                "terminal_snapshots_ref": asdict(terminal_ref),
                "report_uri": args.report_uri,
                "report_sha256": hashlib.sha256(report_payload).hexdigest(),
                "all_checks_passed": report["all_checks_passed"],
                "status": "built",
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
