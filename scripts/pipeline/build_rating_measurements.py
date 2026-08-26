#!/usr/bin/env python3
"""Build the isolated Phase 1 rating measurement research datasets.

Preview-only: reads immutable byplay, drives, games, outcomes, and reconciled
team-game parents and writes long-form raw observations, strictly pregame
adjusted snapshots, terminal adjusted snapshots, and the coverage/redundancy
audit report under the research prefix. Raw byplay/drives evidence is
materialized one historical season at a time, so at most one season of raw
plays and drives is resident while only compact observation outputs persist
across seasons. Never writes predictions, V4 references, or production
artifacts, and refuses production runtime targets, unverified code, and
failing audits.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

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
    OBSERVATION_COLUMNS,
    OBSERVATION_DATASET,
    SNAPSHOT_DATASET,
    TERMINAL_SNAPSHOT_DATASET,
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
)

_OBSERVATION_SORT_KEYS = (
    "season",
    "kickoff_utc",
    "game_id",
    "team",
    "measurement_id",
    "unit_role",
)


def _ref(storage, uri: str) -> DatasetRef:
    return DatasetRef(**json.loads(storage.read_bytes(uri).decode()))


def _code_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _require_committed_code(
    expected_code_sha: str | None = None, *, config_path: Path = DEFAULT_CONFIG
) -> str:
    """Ensure materialized artifacts name a commit containing the relevant code."""
    code_sha = expected_code_sha or _code_sha()
    if code_sha == "unknown":
        raise ValueError("Rating artifacts require a resolvable Git commit SHA")
    paths = RELEVANT_CODE_PATHS + (str(config_path.relative_to(REPO_ROOT)),)
    for path in paths:
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
        ["git", "diff", "--quiet", code_sha, "--", *paths],
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


def _manifest_seasons(storage, ref: DatasetRef) -> tuple[int, ...]:
    """Read the manifest season partition of an immutable raw parent."""
    manifest_uri = ref.uri.rsplit("/", 1)[0] + "/manifest.json"
    manifest = json.loads(storage.read_bytes(manifest_uri))
    seasons = (manifest.get("partitions") or {}).get("seasons") or []
    return tuple(int(season) for season in seasons)


def _season_parent_maps(
    storage,
    byplay_refs: tuple[DatasetRef, ...],
    drives_refs: tuple[DatasetRef, ...],
    config,
) -> tuple[dict[int, DatasetRef], dict[int, DatasetRef]]:
    """Map raw parents to seasons and fail closed before any raw data read.

    Every historical development season must have exactly one byplay and one
    drives parent, each partitioned to exactly that season. Protected or
    out-of-scope raw seasons are rejected because bounded materialization
    only covers historical development evidence.
    """
    maps: dict[str, dict[int, DatasetRef]] = {}
    for label, refs in (("byplay", byplay_refs), ("drives", drives_refs)):
        by_season: dict[int, DatasetRef] = {}
        for ref in refs:
            seasons = _manifest_seasons(storage, ref)
            if len(seasons) != 1:
                raise ValueError(
                    f"{label} parent {ref.version_id} must be partitioned to "
                    f"exactly one season, got {list(seasons)}"
                )
            season = seasons[0]
            if season in by_season:
                raise ValueError(
                    f"Duplicate {label} parent for season {season}: "
                    f"{by_season[season].version_id} and {ref.version_id}"
                )
            by_season[season] = ref
        maps[label] = by_season
    required = tuple(config.historical_development_seasons)
    missing = [
        f"{label}:{season}"
        for label in ("byplay", "drives")
        for season in required
        if season not in maps[label]
    ]
    if missing:
        raise ValueError(
            "Missing raw parent refs for historical development seasons "
            f"(exactly one byplay and one drives parent each): {missing}"
        )
    extra = sorted((set(maps["byplay"]) | set(maps["drives"])) - set(required))
    if extra:
        raise ValueError(
            f"Raw parent refs cover non-historical seasons {extra}; bounded "
            "materialization covers historical development seasons only"
        )
    return maps["byplay"], maps["drives"]


def _concat_frames(storage, refs: tuple[DatasetRef, ...]) -> pd.DataFrame:
    frames = [read_dataset(storage, ref) for ref in refs]
    columns = [tuple(frame.columns) for frame in frames]
    if any(column != columns[0] for column in columns):
        raise ValueError(f"Parent frames disagree on columns: {columns}")
    nonempty = [frame for frame in frames if not frame.empty]
    if not nonempty:
        return frames[0]
    return pd.concat(nonempty, ignore_index=True)


def _build_observations_season_scoped(
    *,
    storage,
    config,
    byplay_by_season: Mapping[int, DatasetRef],
    drives_by_season: Mapping[int, DatasetRef],
    games: pd.DataFrame,
    outcomes: pd.DataFrame,
    reconciled_team_game: pd.DataFrame,
    as_of: datetime,
    code_sha: str,
    config_sha: str,
    parent_ref_shas: str,
    progress: Callable[[str], None] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any], dict[str, Any]]:
    """Build observations one historical season at a time.

    Loads, verifies, and aggregates a single season's byplay/drives parents,
    retains only that season's compact observation output, releases the raw
    frames, and finally concatenates and globally re-sorts the per-season
    outputs into the canonical all-history observation ordering.
    """
    merged_audit: dict[str, Any] = {
        "excluded_games": [],
        "season_counts": {},
        "out_of_scope_season_games": {},
        "quality_flag_counts": {},
        "score_reconciliation": {},
    }
    raw_input_rows: dict[str, dict[int, int]] = {"byplay": {}, "drives": {}}
    observation_rows_by_season: dict[int, int] = {}
    timings_ms: dict[str, float] = {"raw_read": 0.0, "build": 0.0, "assemble": 0.0}

    compact = {}
    for name, frame in (
        ("games", games),
        ("outcomes", outcomes),
        ("reconciled", reconciled_team_game),
    ):
        season_frame = frame.copy()
        season_frame["season"] = pd.to_numeric(season_frame["season"], errors="coerce")
        compact[name] = season_frame

    frames: list[pd.DataFrame] = []
    for season in sorted(config.historical_development_seasons):
        if progress is not None:
            progress(f"read:byplay:{season}")
        started = time.perf_counter()
        byplay = read_dataset(storage, byplay_by_season[season])
        if progress is not None:
            progress(f"read:drives:{season}")
        drives = read_dataset(storage, drives_by_season[season])
        timings_ms["raw_read"] += time.perf_counter() - started
        for label, frame in (("byplay", byplay), ("drives", drives)):
            frame_seasons = set(
                pd.to_numeric(frame["season"], errors="coerce").dropna().astype(int)
            )
            if frame_seasons != {season}:
                raise ValueError(
                    f"{label} parent for season {season} contains rows from "
                    f"seasons {sorted(frame_seasons)}; manifest partition and "
                    "rows disagree"
                )
            raw_input_rows[label][int(season)] = int(len(frame))

        if progress is not None:
            progress(f"build:{season}")
        started = time.perf_counter()
        build = build_measurement_observations(
            byplay=byplay,
            drives=drives,
            games=compact["games"][compact["games"]["season"] == season],
            outcomes=compact["outcomes"][compact["outcomes"]["season"] == season],
            reconciled_team_game=compact["reconciled"][
                compact["reconciled"]["season"] == season
            ],
            config=config,
            as_of=as_of,
            code_sha=code_sha,
            config_sha=config_sha,
            parent_ref_shas=parent_ref_shas,
        )
        timings_ms["build"] += time.perf_counter() - started
        frames.append(build.frame)
        observation_rows_by_season[int(season)] = int(len(build.frame))
        audit = build.audit
        merged_audit["excluded_games"].extend(audit.get("excluded_games", []))
        for flag, count in audit.get("quality_flag_counts", {}).items():
            merged_audit["quality_flag_counts"][flag] = (
                merged_audit["quality_flag_counts"].get(flag, 0) + count
            )
        for season_key, counts in audit.get("season_counts", {}).items():
            merged_audit["season_counts"][season_key] = counts
        for season_key, reconciliation in audit.get("score_reconciliation", {}).items():
            merged_audit["score_reconciliation"][season_key] = reconciliation
        for other_season, count in audit.get("out_of_scope_season_games", {}).items():
            merged_audit["out_of_scope_season_games"][other_season] = (
                merged_audit["out_of_scope_season_games"].get(other_season, 0) + count
            )
        del byplay, drives, build

    started = time.perf_counter()
    if frames:
        combined = pd.concat(frames, ignore_index=True)
        combined = combined.sort_values(
            list(_OBSERVATION_SORT_KEYS), kind="mergesort"
        ).reset_index(drop=True)
    else:
        combined = pd.DataFrame(columns=OBSERVATION_COLUMNS)
    if config.uses_true_ppso:
        missing = [
            season
            for season in config.historical_development_seasons
            if season not in merged_audit["score_reconciliation"]
        ]
        failed = [
            season
            for season, values in merged_audit["score_reconciliation"].items()
            if float(values["exact_rate"]) < 0.94
        ]
        if missing or failed:
            raise ValueError(
                "PPSO score reconciliation failed; missing seasons "
                f"{missing}, below-94% seasons {sorted(failed)}"
            )
    timings_ms["assemble"] = time.perf_counter() - started

    execution = {
        "raw_seasons_processed": [
            int(season) for season in sorted(config.historical_development_seasons)
        ],
        "raw_input_rows": raw_input_rows,
        "observation_rows_by_season": observation_rows_by_season,
        "timings_ms": timings_ms,
    }
    return combined, merged_audit, execution


def _serialize_report(report: Mapping[str, Any]) -> bytes:
    return json.dumps(report, indent=2, sort_keys=True, default=str).encode()


def _report_identity(report: Mapping[str, Any]) -> dict[str, Any]:
    """Return report content excluding wall-clock timing diagnostics."""
    identity = json.loads(json.dumps(report, default=str))
    execution = identity.get("execution")
    if isinstance(execution, dict):
        execution.pop("timing_by_stage_ms", None)
    return identity


def _write_report(storage, uri: str, report: Mapping[str, Any]) -> bytes:
    """Write the audit report immutably, ignoring wall-clock timing drift.

    A rerun whose report differs only in ``execution.timing_by_stage_ms`` is
    byte-stable for every deterministic field; the first execution's timings
    are retained. Any other difference is an immutable collision.
    """
    identity_payload = _serialize_report(_report_identity(report))
    if storage.exists(uri):
        try:
            existing = json.loads(storage.read_bytes(uri))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FileExistsError(f"Immutable artifact exists: {uri}") from exc
        if _serialize_report(_report_identity(existing)) != identity_payload:
            raise FileExistsError(f"Immutable artifact exists: {uri}")
        return identity_payload
    storage.write_bytes(_serialize_report(report), uri)
    return identity_payload


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

    # Validate the raw season map from manifests before materializing any raw
    # data so missing, duplicate, or out-of-scope parents fail before reads.
    byplay_by_season, drives_by_season = _season_parent_maps(
        storage, byplay_refs, drives_refs, config
    )

    parent_refs = byplay_refs + drives_refs + games_refs + outcome_refs + team_game_refs
    parent_ref_shas = ";".join(ref.content_sha for ref in parent_refs)
    code_sha = _require_committed_code(
        args.expected_code_sha, config_path=Path(args.measurement_config).resolve()
    )
    config_sha = config.design_id

    read_started = time.perf_counter()
    games = _concat_frames(storage, games_refs)
    outcomes = _concat_frames(storage, outcome_refs)
    reconciled_team_game = _concat_frames(storage, team_game_refs)
    compact_read_s = time.perf_counter() - read_started

    observations, merged_observation_audit, season_execution = (
        _build_observations_season_scoped(
            storage=storage,
            config=config,
            byplay_by_season=byplay_by_season,
            drives_by_season=drives_by_season,
            games=games,
            outcomes=outcomes,
            reconciled_team_game=reconciled_team_game,
            as_of=cutoff,
            code_sha=code_sha,
            config_sha=config_sha,
            parent_ref_shas=parent_ref_shas,
        )
    )
    observation_build_s = (
        season_execution["timings_ms"]["build"]
        + season_execution["timings_ms"]["assemble"]
    )
    read_s = compact_read_s + season_execution["timings_ms"]["raw_read"]

    observation_build_started = time.perf_counter()
    validate_observation_frame(observations, config)
    observation_build_s += time.perf_counter() - observation_build_started
    terminal_materialization_s = 0.0

    dataset_started = time.perf_counter()
    observations_ref, observations_manifest = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset=OBSERVATION_DATASET,
            parent_refs=parent_refs,
            code_sha=code_sha,
            config_sha=config_sha,
            as_of=cutoff,
            schema_version=config.observation_schema_version,
            tier="gold",
        ),
        records=observations.to_dict("records"),
        partitions={
            "seasons": sorted(int(season) for season in set(observations["season"]))
        }
        if not observations.empty
        else {"seasons": []},
        validation={
            "nonempty": not observations.empty,
            "ratings_contract_valid": True,
        },
    )
    terminal_materialization_s += time.perf_counter() - dataset_started

    snapshot_computation_started = time.perf_counter()
    snapshot_build = build_pregame_snapshots(
        observations=observations,
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
    snapshot_computation_s = time.perf_counter() - snapshot_computation_started

    dataset_started = time.perf_counter()
    snapshots_ref, snapshots_manifest = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset=SNAPSHOT_DATASET,
            parent_refs=(observations_ref,) + games_refs,
            code_sha=code_sha,
            config_sha=config_sha,
            as_of=cutoff,
            schema_version=config.snapshot_schema_version,
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
    terminal_materialization_s += time.perf_counter() - dataset_started

    terminal_computation_started = time.perf_counter()
    terminal_build = build_season_terminal_snapshots(
        observations=observations,
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
    terminal_computation_s = time.perf_counter() - terminal_computation_started
    snapshot_build_s = snapshot_computation_s + terminal_computation_s

    dataset_started = time.perf_counter()
    terminal_ref, terminal_manifest = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset=TERMINAL_SNAPSHOT_DATASET,
            parent_refs=(observations_ref,) + games_refs,
            code_sha=code_sha,
            config_sha=config_sha,
            as_of=cutoff,
            schema_version=config.terminal_snapshot_schema_version,
            tier="gold",
        ),
        records=terminal_build.frame.to_dict("records"),
        partitions={"seasons": list(config.historical_development_seasons)},
        validation={
            "nonempty": not terminal_build.frame.empty,
            "ratings_contract_valid": True,
        },
    )
    terminal_build_s = terminal_materialization_s + (
        time.perf_counter() - dataset_started
    )

    audit_started = time.perf_counter()
    report = build_rating_audit_report(
        observations=observations,
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
        build_audit=merged_observation_audit,
    )
    report["execution"] = {
        "materialization": "season_scoped_v1",
        "raw_seasons_processed": season_execution["raw_seasons_processed"],
        "raw_input_rows": season_execution["raw_input_rows"],
        "observation_rows_by_season": season_execution["observation_rows_by_season"],
        "snapshot_rows": int(len(snapshot_build.frame)),
        "terminal_snapshot_rows": int(len(terminal_build.frame)),
        "timing_by_stage_ms": {
            "read": int(read_s * 1000),
            "observation_build": int(observation_build_s * 1000),
            "snapshot_build": int(snapshot_build_s * 1000),
            "terminal_build": int(terminal_build_s * 1000),
            "audit": int((time.perf_counter() - audit_started) * 1000),
        },
        "timing_identity_note": (
            "timing_by_stage_ms is execution diagnostics only and is excluded "
            "from report_sha256 identity"
        ),
    }
    identity_payload = _write_report(storage, args.report_uri, report)
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
                "report_sha256": hashlib.sha256(identity_payload).hexdigest(),
                "all_checks_passed": report["all_checks_passed"],
                "status": "built",
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
