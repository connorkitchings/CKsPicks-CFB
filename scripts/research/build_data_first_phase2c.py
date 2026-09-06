#!/usr/bin/env python3
"""Build the Preview-only Phase 2c expanded Silver corpus from sealed refs."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Mapping

import psycopg
from dotenv import load_dotenv

from cks_picks_cfb.data.catalog import (
    register_dataset_version,
    register_reconciliation_results,
    register_schema_version,
    source_capture_by_id,
)
from cks_picks_cfb.data.data_first_phase2c import (
    CHECKPOINT_SCHEMA,
    DEVELOPMENT_SEASONS,
    OUTPUT_DATASETS,
    Phase2cError,
    build_run_identity,
    canonical_bytes,
    checkpoint_payload,
    omission_reasons,
    parse_manifest,
    ref_set_payload,
    require_exact_regular_lineage,
    require_expected_dry_run,
    require_identical_identity,
    sha256_value,
)
from cks_picks_cfb.data.history_play_capture import manifest_declared_missing_game_ids
from cks_picks_cfb.data.lake import (
    BuildRequest,
    DatasetRef,
    build_dataset_version,
    read_dataset,
    read_source_capture,
)
from cks_picks_cfb.data.reconciliation import (
    reconcile_completed_games,
    require_reconciled,
)
from cks_picks_cfb.data.runtime import resolve_runtime_target
from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame
from cks_picks_cfb.data.silver import (
    SILVER_CONTRACTS,
    build_silver_version,
    normalize_fbs_involved_games,
    normalize_game_outcomes,
    normalize_plays,
    normalize_team_game_stats,
)
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.features.pipeline import build_preaggregation_pipeline

SEASONS = DEVELOPMENT_SEASONS
ROOT = "artifacts/research/data-first-football-v1/phase2/silver/runs"
PHASE1_STATE = "resolved_with_blockers"


def _git_sha() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()


def _clean_tracked_tree() -> bool:
    return all(
        subprocess.run(command, check=False).returncode == 0
        for command in (
            ["git", "diff", "--quiet"],
            ["git", "diff", "--cached", "--quiet"],
        )
    )


def _immutable_json(storage, uri: str, value: Mapping[str, Any]) -> None:
    payload = canonical_bytes(value)
    if storage.exists(uri):
        if storage.read_bytes(uri) != payload:
            raise FileExistsError(f"immutable artifact collision: {uri}")
        return
    storage.write_bytes(payload, uri)


def _ref(value: Mapping[str, Any]) -> DatasetRef:
    return DatasetRef(
        **{
            key: value[key]
            for key in ("dataset", "version_id", "schema_version", "content_sha", "uri")
        }
    )


def _capture_rows(storage, captures):
    records: list[dict[str, Any]] = []
    for capture in captures:
        rows = read_source_capture(storage, capture).to_dict("records")
        for row in rows:
            row.setdefault("__capture_id", capture.capture_id)
            row.setdefault("__captured_at", capture.captured_at.isoformat())
            row.setdefault("__capture_provider", capture.provider)
        records.extend(rows)
    return records


def _manifest(
    storage, uri: str, *, allowed_states: set[str], label: str
) -> tuple[dict[str, Any], dict[str, str]]:
    return parse_manifest(
        uri=uri,
        raw_bytes=storage.read_bytes(uri),
        allowed_states=allowed_states,
        label=label,
    )


def _run_captures(raw: Mapping[str, Any], *, entity: str) -> dict[int, str]:
    if raw.get("state") != "complete" or raw.get("failed_or_empty_count") != 0:
        raise Phase2cError("Phase 2 capture run is incomplete")
    result: dict[int, str] = {}
    for row in raw.get("results", []):
        request = row.get("parameters") or row.get("request", {}).get("parameters", {})
        # CaptureRequest is nested under the plan's requests, so resolve by SHA below.
        if row.get("state") != "captured" or not row.get("capture_id"):
            raise Phase2cError("Phase 2 run contains a non-captured request")
    by_sha = {item["request_sha"]: item for item in raw.get("requests", [])}
    for row in raw.get("results", []):
        request = by_sha.get(row["request_sha"], {})
        if request.get("entity") != entity:
            continue
        params = request.get("parameters", {})
        season = int(params.get("year", -1))
        if season not in SEASONS or params.get("season_type") != "postseason":
            raise Phase2cError("postseason capture has an invalid season/type")
        if entity in {"plays", "game_stats"} and int(params.get("week", -1)) != 1:
            raise Phase2cError("postseason detail capture must be Week 1")
        if season in result:
            raise Phase2cError(f"duplicate postseason {season}/{entity} capture")
        result[season] = str(row["capture_id"])
    if set(result) != set(SEASONS):
        raise Phase2cError(f"postseason run lacks complete {entity} coverage")
    return result


def _r1_request_evidence(
    r1: Mapping[str, Any], *, season: int, entity: str
) -> dict[str, Mapping[str, Any]]:
    matches = [
        item
        for item in r1.get("entries", [])
        if int(item.get("season", -1)) == season and item.get("entity") == entity
    ]
    if len(matches) != 1:
        raise Phase2cError(f"R1 source set lacks one {season}/{entity} entry")
    evidence = {str(row["capture_id"]): row for row in matches[0].get("requests", [])}
    if not evidence or len(evidence) != len(matches[0].get("capture_ids", [])):
        raise Phase2cError(f"R1 source set has malformed {season}/{entity} evidence")
    return evidence


def _verify_capture(
    storage,
    capture,
    *,
    season: int,
    entity: str,
    expected_request: Mapping[str, Any] | None = None,
    postseason: bool,
) -> dict[str, Any]:
    """Verify catalog metadata, the physical object, and source-request meaning."""
    if capture.state != "registered" or capture.provider != "cfbd":
        raise Phase2cError(f"unregistered or non-CFBD {season}/{entity} capture")
    request = dict(capture.request or {})
    params = dict(request.get("parameters") or {})
    expected_entity = f"data_first_{entity}" if postseason else entity
    if capture.entity != expected_entity:
        raise Phase2cError(f"unexpected catalog entity for {season}/{entity}")
    if params.get("year") != season:
        raise Phase2cError(f"capture season mismatch for {season}/{entity}")
    if entity != "teams" and params.get("season_type") != (
        "postseason" if postseason else "regular"
    ):
        raise Phase2cError(f"capture season type mismatch for {season}/{entity}")
    if entity in {"plays", "game_stats"} and postseason and params.get("week") != 1:
        raise Phase2cError(f"postseason {entity} must be Week 1")
    if params.get("classification") != "fbs" and entity != "teams":
        raise Phase2cError(f"capture classification mismatch for {season}/{entity}")
    if (
        postseason
        and capture.response_metadata.get("timing_class")
        != "historically_reconstructed"
    ):
        raise Phase2cError(f"postseason {season}/{entity} has an invalid timing class")
    if expected_request is not None:
        if capture.content_sha != expected_request.get("content_sha256"):
            raise Phase2cError(f"R1 content checksum mismatch for {season}/{entity}")
        if capture.object_sha != expected_request.get("object_sha256"):
            raise Phase2cError(f"R1 object checksum mismatch for {season}/{entity}")
        if capture.row_count != int(expected_request.get("row_count", -1)):
            raise Phase2cError(f"R1 row-count mismatch for {season}/{entity}")
        expected = dict(expected_request.get("request") or {})
        if request.get("endpoint") != expected.get("endpoint") or params != dict(
            expected.get("parameters") or {}
        ):
            raise Phase2cError(f"R1 request mismatch for {season}/{entity}")
    # The season builder below reads every selected capture through
    # ``read_source_capture`` before it can produce an output, which verifies
    # the physical object checksum and parquet readability.  Preflight only
    # performs the cheap object-existence check so it does not deserialize the
    # complete ten-season corpus twice before dry-run can report its gates.
    if not storage.exists(capture.uri):
        raise Phase2cError(f"source capture object is missing: {capture.capture_id}")
    return {
        "capture_id": capture.capture_id,
        "provider": capture.provider,
        "entity": capture.entity,
        "request": request,
        "timing_class": capture.response_metadata.get("timing_class"),
        "row_count": capture.row_count,
        "content_sha256": capture.content_sha,
        "object_sha256": capture.object_sha,
        "uri": capture.uri,
    }


def _verify_catalog_ref(conn_url: str, ref: DatasetRef) -> None:
    """Ensure the immutable ref is registered in the Preview catalog exactly."""
    with psycopg.connect(conn_url) as conn:
        row = conn.execute(
            "SELECT dataset, schema_version, content_sha, uri "
            "FROM catalog.dataset_versions WHERE version_id = %s",
            (ref.version_id,),
        ).fetchone()
    if not row or tuple(map(str, row)) != (
        ref.dataset,
        ref.schema_version,
        ref.content_sha,
        ref.uri,
    ):
        raise Phase2cError(f"Preview catalog registration mismatch: {ref.version_id}")


def _verify_checkpoint(
    storage, conn_url: str, checkpoint: Mapping[str, Any], identity
) -> dict[str, Any]:
    if (
        checkpoint.get("schema_version") != CHECKPOINT_SCHEMA
        or checkpoint.get("state") != "complete"
    ):
        raise Phase2cError("Phase 2c checkpoint is incomplete or malformed")
    if checkpoint.get("identity_sha256") != identity["identity_sha256"]:
        raise Phase2cError("Phase 2c checkpoint belongs to another run identity")
    unsigned = dict(checkpoint)
    claimed_sha = unsigned.pop("checkpoint_sha256", None)
    if claimed_sha != sha256_value(unsigned):
        raise Phase2cError("Phase 2c checkpoint checksum mismatch")
    entry = dict(checkpoint.get("entry") or {})
    if int(entry.get("season", -1)) != int(checkpoint.get("season", -1)):
        raise Phase2cError("Phase 2c checkpoint season mismatch")
    outputs = entry.get("outputs") or {}
    if set(outputs) != set(OUTPUT_DATASETS):
        raise Phase2cError("Phase 2c checkpoint lacks complete outputs")
    for raw in outputs.values():
        ref = _ref(raw)
        read_dataset(storage, ref)
        _verify_catalog_ref(conn_url, ref)
    return entry


def _dry_run_view(entries: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {key: value for key, value in entry.items() if key != "outputs"}
        for entry in entries
    ]


def _regular_capture_ids(
    phase1: Mapping[str, Any], *, entity: str
) -> dict[int, list[str]]:
    selected = {season: [] for season in SEASONS}
    for capture in phase1.get("source_captures", []):
        params = (capture.get("request") or {}).get("parameters") or {}
        season = params.get("year")
        if (
            capture.get("provider") == "cfbd"
            and capture.get("entity") == entity
            and season in selected
            and (entity == "teams" or params.get("season_type") == "regular")
        ):
            selected[season].append(str(capture["capture_id"]))
    expected = 1 if entity == "games" else None
    for season, ids in selected.items():
        if not ids or (expected and len(ids) != expected) or len(ids) != len(set(ids)):
            raise Phase2cError(
                f"Phase 1 v3 lacks exact regular {season}/{entity} captures"
            )
    return selected


def _dataset_ref(
    phase1: Mapping[str, Any],
    *,
    dataset: str,
    season: int | None = None,
    source_capture_ids: list[str] | None = None,
) -> DatasetRef:
    matches = []
    for item in phase1.get("datasets", []):
        if item.get("dataset") != dataset:
            continue
        partitions = item.get("partitions", {})
        if season is None or season in partitions.get("seasons", []):
            actual_ids = item.get("source_capture_ids", [])
            if source_capture_ids is None or set(actual_ids) == set(source_capture_ids):
                matches.append(item)
    if len(matches) != 1:
        raise Phase2cError(
            f"Phase 1 v3 must select exactly one {dataset} ref for {season}"
        )
    return _ref(matches[0])


def _build_plan(
    storage, conn_url: str, args
) -> tuple[dict[int, dict[str, Any]], dict[str, Any], list[dict[str, str]]]:
    phase1, phase1_evidence = _manifest(
        storage,
        args.phase1_manifest_uri,
        allowed_states={PHASE1_STATE},
        label="Phase 1 v3",
    )
    games_run, games_evidence = _manifest(
        storage,
        args.postseason_games_manifest_uri,
        allowed_states={"complete"},
        label="Phase 2 postseason games",
    )
    weekly_run, weekly_evidence = _manifest(
        storage,
        args.postseason_weekly_manifest_uri,
        allowed_states={"complete"},
        label="Phase 2 postseason detail",
    )
    r1, r1_manifest_evidence = _manifest(
        storage,
        args.r1_source_set_uri,
        allowed_states={"complete"},
        label="certified R1 source set",
    )
    if r1.get("contract_version") != "successor-history-source-set-v2":
        raise Phase2cError("R1 source set is not the certified source-set contract")
    post_games = _run_captures(games_run, entity="games")
    post_plays = _run_captures(weekly_run, entity="plays")
    post_stats = _run_captures(weekly_run, entity="game_stats")
    plan: dict[int, dict[str, Any]] = {}
    regular = {
        entity: _regular_capture_ids(phase1, entity=entity)
        for entity in ("games", "plays", "game_stats", "teams")
    }
    require_exact_regular_lineage(r1, regular)
    r1_root = args.r1_source_set_uri.rsplit("/", 1)[0]
    for season in SEASONS:
        ids = {
            entity: regular[entity][season] + [post]
            for entity, post in (
                ("games", post_games[season]),
                ("plays", post_plays[season]),
                ("game_stats", post_stats[season]),
            )
        }
        captures = {
            entity: [
                source_capture_by_id(conn_url, capture_id) for capture_id in values
            ]
            for entity, values in ids.items()
        }
        capture_evidence = {}
        for entity, values in captures.items():
            regular_count = len(regular[entity][season])
            expected_r1 = _r1_request_evidence(r1, season=season, entity=entity)
            evidence_rows = []
            for index, value in enumerate(values):
                is_postseason = index >= regular_count
                evidence_rows.append(
                    _verify_capture(
                        storage,
                        value,
                        season=season,
                        entity=entity,
                        expected_request=(
                            None if is_postseason else expected_r1.get(value.capture_id)
                        ),
                        postseason=is_postseason,
                    )
                )
            if any(
                row["capture_id"] not in expected_r1
                for row in evidence_rows[:regular_count]
            ):
                raise Phase2cError(f"R1 evidence is incomplete for {season}/{entity}")
            capture_evidence[entity] = evidence_rows
        plan[season] = {
            "capture_ids": ids,
            "captures": captures,
            "capture_evidence": capture_evidence,
            "teams_ref": _dataset_ref(
                phase1,
                dataset="teams",
                season=season,
                source_capture_ids=regular["teams"][season],
            ),
            "play_manifest_uri": f"{r1_root}/captures/{season}/plays.json",
        }
    meta = {
        "corrections_ref": asdict(_dataset_ref(phase1, dataset="data_corrections")),
    }
    return (
        plan,
        meta,
        [
            phase1_evidence,
            games_evidence,
            weekly_evidence,
            r1_manifest_evidence,
        ],
    )


def _season_frames(storage, item: Mapping[str, Any]):
    captures = item["captures"]
    games_records = _capture_rows(storage, captures["games"])
    games = normalize_fbs_involved_games(games_records)
    outcomes = normalize_game_outcomes(games_records, games=games)
    plays = normalize_plays(_capture_rows(storage, captures["plays"]), games=games)
    stats = normalize_team_game_stats(
        _capture_rows(storage, captures["game_stats"]), games=games
    )
    complete = set(
        games.loc[games["completed"].fillna(False).astype(bool), "game_id"].astype(int)
    )
    play_ids, stats_ids = (
        set(plays["game_id"].astype(int)),
        set(stats["game_id"].astype(int)),
    )
    missing_plays = sorted(complete - play_ids)
    declared = manifest_declared_missing_game_ids(
        storage, item["play_manifest_uri"], season=int(games.iloc[0]["season"])
    )
    detail_omissions = omission_reasons(
        missing_plays=missing_plays,
        missing_stats=sorted(complete - stats_ids),
        declared_regular_plays=declared,
        postseason_game_ids=games.loc[
            games["season_type"].eq("postseason"), "game_id"
        ].astype(int),
    )
    return (
        games,
        outcomes,
        plays,
        stats,
        {
            "missing_play_game_ids": missing_plays,
            "missing_stat_game_ids": sorted(complete - stats_ids),
            "declared_missing_play_game_ids": sorted(declared),
            "reasons": detail_omissions,
        },
    )


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("dry-run", "apply"), required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--environment", choices=("preview",), required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--phase1-manifest-uri", required=True)
    parser.add_argument("--postseason-games-manifest-uri", required=True)
    parser.add_argument("--postseason-weekly-manifest-uri", required=True)
    parser.add_argument("--r1-source-set-uri", required=True)
    args = parser.parse_args()
    if os.getenv("CFB_STORAGE_BACKEND", "").casefold() != "r2":
        raise Phase2cError("Phase 2c requires R2")
    if _git_sha() != args.expected_code_sha:
        raise Phase2cError("expected code SHA must equal HEAD")
    if args.mode == "apply" and not _clean_tracked_tree():
        raise Phase2cError("apply requires a clean tracked worktree")
    cutoff = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    target = resolve_runtime_target("preview")
    storage = get_storage(environment="preview")
    plan, input_meta, input_manifests = _build_plan(storage, target.database_url, args)
    corrections = read_dataset(storage, _ref(input_meta["corrections_ref"]))
    root = f"{ROOT}/{args.run_id}"
    identity = build_run_identity(
        run_id=args.run_id,
        environment=args.environment,
        as_of=cutoff.isoformat(),
        code_sha=args.expected_code_sha,
        configuration={
            "phase1_manifest_uri": args.phase1_manifest_uri,
            "postseason_games_manifest_uri": args.postseason_games_manifest_uri,
            "postseason_weekly_manifest_uri": args.postseason_weekly_manifest_uri,
            "r1_source_set_uri": args.r1_source_set_uri,
            "corrections_ref": input_meta["corrections_ref"],
        },
        input_manifests=input_manifests,
    )
    identity_uri = f"{root}/identity.json"
    if args.mode == "apply":
        if storage.exists(identity_uri):
            require_identical_identity(
                json.loads(storage.read_bytes(identity_uri).decode("utf-8")), identity
            )
        else:
            _immutable_json(storage, identity_uri, identity)
    entries = []
    for season, item in plan.items():
        checkpoint_uri = f"{root}/seasons/{season}.json"
        if args.mode == "apply" and storage.exists(checkpoint_uri):
            entries.append(
                _verify_checkpoint(
                    storage,
                    target.database_url,
                    json.loads(storage.read_bytes(checkpoint_uri).decode("utf-8")),
                    identity,
                )
            )
            continue
        games, outcomes, plays, stats, omissions = _season_frames(storage, item)
        teams = read_dataset(storage, item["teams_ref"])
        byplay, drives, team_game, _ = build_preaggregation_pipeline(
            plays.copy(),
            games_df=games.rename(columns={"kickoff_utc": "start_date"}),
            teams_df=teams,
            corrections_df=corrections,
        )
        reconciliation = reconcile_completed_games(
            games,
            team_game,
            stats,
            declared_incomplete_game_ids=omissions["declared_missing_play_game_ids"],
        )
        require_reconciled(reconciliation)
        for dataset, frame in (
            ("fbs_involved_games", games),
            ("game_outcomes", outcomes),
            ("plays", plays),
            ("team_game_stats", stats),
            ("byplay", byplay),
            ("drives", drives),
            ("reconciled_team_game", team_game),
            ("source_reconciliation", reconciliation),
        ):
            validate_frame(
                frame, schema_for(dataset, SILVER_CONTRACTS[dataset].schema_version)
            )
        entry = {
            "season": season,
            "source_capture_ids": item["capture_ids"],
            "capture_evidence": item["capture_evidence"],
            "teams_ref": asdict(item["teams_ref"]),
            "omissions": omissions,
            "row_counts": {
                "fbs_involved_games": len(games),
                "game_outcomes": len(outcomes),
                "plays": len(plays),
                "team_game_stats": len(stats),
                "byplay": len(byplay),
                "drives": len(drives),
                "reconciled_team_game": len(team_game),
                "source_reconciliation": len(reconciliation),
            },
            "population": games["population"].value_counts().to_dict(),
            "season_type": games["season_type"].value_counts().to_dict(),
            "reconciliation": reconciliation["classification"].value_counts().to_dict()
            | {"blocking": int(reconciliation["blocking"].fillna(True).sum())},
        }
        if args.mode == "apply":
            refs = {}
            for dataset, frame, source in (
                ("fbs_involved_games", games, item["captures"]["games"]),
                ("game_outcomes", outcomes, item["captures"]["games"]),
                ("plays", plays, item["captures"]["plays"]),
                ("team_game_stats", stats, item["captures"]["game_stats"]),
            ):
                ref, manifest = build_silver_version(
                    storage,
                    dataset=dataset,
                    records=_capture_rows(storage, source),
                    source_captures=source,
                    as_of=cutoff,
                    code_sha=args.expected_code_sha,
                    config_sha=sha256_value(
                        {"identity": identity["identity_sha256"], "dataset": dataset}
                    ),
                    context={"games": games},
                )
                register_dataset_version(target.database_url, ref, manifest)
                refs[dataset] = ref
            parents = (
                refs["plays"],
                refs["fbs_involved_games"],
                item["teams_ref"],
                refs["team_game_stats"],
                _ref(input_meta["corrections_ref"]),
            )
            for dataset, frame in (
                ("byplay", byplay),
                ("drives", drives),
                ("reconciled_team_game", team_game),
                ("source_reconciliation", reconciliation),
            ):
                schema = SILVER_CONTRACTS[dataset].schema_version
                register_schema_version(target.database_url, dataset, schema)
                ref, manifest = build_dataset_version(
                    storage,
                    build=BuildRequest(
                        dataset=dataset,
                        parent_refs=parents,
                        code_sha=args.expected_code_sha,
                        config_sha=sha256_value(
                            {
                                "identity": identity["identity_sha256"],
                                "dataset": dataset,
                            }
                        ),
                        as_of=cutoff,
                        schema_version=schema,
                        schema_sha=schema_for(dataset, schema).sha256,
                        tier="silver",
                    ),
                    records=frame.to_dict("records"),
                    partitions={"seasons": [season]},
                    validation={"nonempty": not frame.empty},
                )
                register_dataset_version(target.database_url, ref, manifest)
                refs[dataset] = ref
            register_reconciliation_results(
                target.database_url,
                reconciliation,
                source_dataset_versions=[ref.version_id for ref in parents],
            )
            entry["outputs"] = {name: asdict(ref) for name, ref in refs.items()}
            for ref in refs.values():
                read_dataset(storage, ref)
                _verify_catalog_ref(target.database_url, ref)
            _immutable_json(
                storage,
                checkpoint_uri,
                checkpoint_payload(identity=identity, entry=entry),
            )
        entries.append(entry)
    require_expected_dry_run(entries)
    payload = ref_set_payload(
        identity=identity,
        entries=entries,
        state="complete" if args.mode == "apply" else "dry_run",
    )
    ref_set_uri = f"{root}/ref-set.json"
    if args.mode == "apply":
        _immutable_json(storage, ref_set_uri, payload)
    elif storage.exists(ref_set_uri):
        existing = json.loads(storage.read_bytes(ref_set_uri).decode("utf-8"))
        require_identical_identity(existing.get("identity") or {}, identity)
        if _dry_run_view(existing.get("entries") or []) != _dry_run_view(entries):
            raise Phase2cError("repeated dry-run does not match the completed ref set")
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
