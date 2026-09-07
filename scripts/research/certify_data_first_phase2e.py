#!/usr/bin/env python3
"""Normalize and certify reconstructed auxiliary evidence for Phase 3 context."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg
import yaml
from dotenv import load_dotenv

from cks_picks_cfb.data.catalog import (
    register_dataset_version,
    register_source_captures,
)
from cks_picks_cfb.data.data_first_phase2 import DEVELOPMENT_SEASONS
from cks_picks_cfb.data.data_first_phase2d import verify_phase2c_ref_set
from cks_picks_cfb.data.data_first_phase2e import (
    Phase2eError,
    auxiliary_eligibility_manifest,
    capture_set_manifest,
    family_coverage,
    normalize_coaching,
    normalize_lagged_rankings,
    normalize_market_references,
    normalize_recruiting,
    normalize_returning_production,
    normalize_roster_continuity,
    sha256,
    validate_capture_set_manifest,
)
from cks_picks_cfb.data.lake import (
    BuildRequest,
    DatasetRef,
    SourceCapture,
    build_dataset_version,
    read_dataset,
    read_source_capture,
)
from cks_picks_cfb.data.runtime import resolve_runtime_target
from cks_picks_cfb.data.storage import ReadOnlyStorage, get_storage

DEFAULT_CONFIG = "conf/research/data_first_football_v1/phase2e_auxiliary_v1.yaml"


def _git_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _tracked_worktree_clean() -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and not result.stdout.strip()


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise Phase2eError("--as-of must be an explicit UTC timestamp")
    return parsed.astimezone(timezone.utc)


def _immutable(storage, uri: str, value: dict[str, Any]) -> None:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str
    ).encode()
    if storage.exists(uri):
        if storage.read_bytes(uri) != payload:
            raise FileExistsError(f"immutable Phase 2e collision: {uri}")
        return
    storage.write_bytes(payload, uri)


def _load_yaml(path: str) -> dict[str, Any]:
    value = yaml.safe_load(Path(path).read_text())
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != "data_first_phase2e_config_v1"
    ):
        raise Phase2eError("Phase 2e requires data_first_phase2e_config_v1")
    return value


def _source_captures(
    conn_url: str, config: dict[str, Any]
) -> tuple[list[SourceCapture], list[dict[str, Any]]]:
    window = config["capture_window"]
    start, end = window["start"], window["end"]
    entities = list(config["source_entities"])
    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT capture_id,provider,entity,captured_at,effective_at,request,content_sha,object_sha,uri,row_count,provider_api_version,response_metadata,state "
            "FROM catalog.source_captures WHERE entity=ANY(%s) AND captured_at >= %s::timestamptz AND captured_at < %s::timestamptz "
            "ORDER BY entity, captured_at",
            (entities, start, end),
        )
        rows = cur.fetchall()
    captures: list[SourceCapture] = []
    inventory: list[dict[str, Any]] = []
    for row in rows:
        request = dict(row[5])
        params = dict(request.get("parameters") or {})
        if "year" not in params:
            continue
        season = int(params["year"])
        capture = SourceCapture(
            capture_id=str(row[0]),
            provider=str(row[1]),
            entity=str(row[2]),
            captured_at=row[3],
            effective_at=row[4],
            request=request,
            content_sha=str(row[6]),
            object_sha=str(row[7]),
            uri=str(row[8]),
            row_count=int(row[9]),
            provider_api_version=str(row[10]) if row[10] else None,
            response_metadata=dict(row[11]),
            state=str(row[12]),
        )
        captures.append(capture)
        inventory.append(
            {
                "capture_id": capture.capture_id,
                "provider": capture.provider,
                "entity": capture.entity,
                "season": season,
                "captured_at": capture.captured_at.isoformat(),
                "effective_at": capture.effective_at.isoformat()
                if capture.effective_at
                else None,
                "request": request,
                "content_sha": capture.content_sha,
                "object_sha": capture.object_sha,
                "uri": capture.uri,
                "row_count": capture.row_count,
                "state": capture.state,
                "timing_class": "historically_reconstructed",
            }
        )
    manifest = capture_set_manifest(inventory)
    validate_capture_set_manifest(manifest)
    return captures, inventory


def _core_universe(storage, ref_set_uri: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    payload = json.loads(storage.read_bytes(ref_set_uri))
    entries = verify_phase2c_ref_set(payload)
    games = []
    for entry in entries:
        ref = DatasetRef(**entry["outputs"]["fbs_involved_games"])
        games.append(read_dataset(storage, ref))
    schedule = pd.concat(games, ignore_index=True)
    required = {"season", "game_id", "week", "home_team", "away_team"}
    if missing := sorted(required - set(schedule)):
        raise Phase2eError(f"Phase 2c schedule is missing columns: {missing}")
    sides = pd.concat(
        [
            schedule[
                ["season", "game_id", "week", "home_team", "home_classification"]
            ].rename(
                columns={"home_team": "team", "home_classification": "classification"}
            ),
            schedule[
                ["season", "game_id", "week", "away_team", "away_classification"]
            ].rename(
                columns={"away_team": "team", "away_classification": "classification"}
            ),
        ],
        ignore_index=True,
    )
    # Auxiliary captures are provider FBS team sources.  Their coverage must be
    # measured against FBS team-seasons, not against the FCS opponent side of
    # an otherwise eligible FBS--FCS game.  Keep every game side for lagged
    # polls, and let Phase 3 apply its required fold-local fallback to any
    # source family that lacks an FCS-side value.
    universe = (
        sides.loc[
            sides["classification"].astype(str).str.casefold().eq("fbs"),
            ["season", "team"],
        ]
        .drop_duplicates()
        .reset_index(drop=True)
    )
    return universe, sides.drop(columns="classification")


def _raw_by_entity(
    source_storage, captures: list[SourceCapture]
) -> dict[str, pd.DataFrame]:
    frames: dict[str, list[pd.DataFrame]] = {}
    for capture in captures:
        observation_uri = (
            f"{capture.uri.rsplit('/data.parquet', 1)[0]}/observations/"
            f"{capture.capture_id}.json"
        )
        observation = json.loads(source_storage.read_bytes(observation_uri))
        expected_observation = {
            "capture_id": capture.capture_id,
            "content_sha": capture.content_sha,
            "object_sha": capture.object_sha,
            "row_count": capture.row_count,
            "uri": capture.uri,
        }
        if any(
            observation.get(key) != value for key, value in expected_observation.items()
        ):
            raise Phase2eError(
                f"source observation checksum mismatch: {capture.capture_id}"
            )
        frame = read_source_capture(source_storage, capture)
        if len(frame) != capture.row_count:
            raise Phase2eError(f"source row count mismatch: {capture.capture_id}")
        frame = frame.copy()
        frame["__capture_season"] = int(capture.request["parameters"]["year"])
        frame["source_capture_id"] = capture.capture_id
        frame["captured_at"] = capture.captured_at.isoformat()
        frames.setdefault(capture.entity, []).append(frame)
    return {
        entity: pd.concat(values, ignore_index=True)
        for entity, values in frames.items()
    }


def _with_capture_season(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["season"] = result["__capture_season"]
    return result


def _coverage(
    frame: pd.DataFrame, features: tuple[str, ...], *, ignore: set[int] | None = None
) -> dict[str, Any]:
    report = family_coverage(frame, features)
    structural = ignore or set()
    eligible = frame.loc[~frame["season"].isin(structural)]
    complete = eligible[list(features)].notna().all(axis=1)
    per_season = [
        value["coverage_fraction"]
        for season, value in report["coverage"].items()
        if int(season) not in structural
    ]
    # The admission threshold applies to the declared population across its
    # valid lineage, while the per-season breakdown remains visible for Phase
    # 3's chronological folds.  A single known structural lineage gap must not
    # be disguised as ordinary missing evidence.
    report["minimum_coverage"] = float(complete.mean()) if len(eligible) else 0.0
    report["seasonal_minimum_coverage"] = min(per_season) if per_season else 0.0
    report["eligible_required_rows"] = int(len(eligible))
    report["eligible_covered_rows"] = int(complete.sum())
    report["ignored_structural_seasons"] = sorted(structural)
    return report


def _write_dataset(
    storage,
    catalog_url: str,
    *,
    name: str,
    frame: pd.DataFrame,
    captures: list[SourceCapture],
    code_sha: str,
    config_sha: str,
    as_of: datetime,
) -> DatasetRef:
    ref, manifest = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset=f"phase2e_{name}",
            parent_refs=(),
            code_sha=code_sha,
            config_sha=config_sha,
            as_of=as_of,
            source_capture_ids=tuple(capture.capture_id for capture in captures),
            schema_version=f"phase2e_{name}_v1",
            tier="silver",
        ),
        records=frame.to_dict("records"),
        partitions={"seasons": list(DEVELOPMENT_SEASONS)},
        coverage={"timing_class": "historically_reconstructed"},
        validation={
            "excludes_2020": 2020 not in set(frame["season"])
            if "season" in frame
            else True,
        },
    )
    register_dataset_version(catalog_url, ref, manifest)
    return ref


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--mode", choices=("dry-run", "apply"), required=True)
    parser.add_argument("--expected-code-sha", required=True)
    args = parser.parse_args()
    if os.getenv("CFB_STORAGE_BACKEND", "").casefold() != "r2":
        raise Phase2eError("Phase 2e requires CFB_STORAGE_BACKEND=r2")
    if args.expected_code_sha != _git_sha():
        raise Phase2eError("--expected-code-sha must match HEAD")
    if args.mode == "apply" and not _tracked_worktree_clean():
        raise Phase2eError("apply requires a clean tracked worktree")
    config = _load_yaml(args.config)
    as_of = _utc(args.as_of)
    config_sha = sha256(config)
    # The historical auxiliary backfill is in the primary immutable lake.  It
    # is deliberately wrapped read-only; the separately configured import
    # source is a different legacy corpus and must not be selected by accident.
    source_storage = ReadOnlyStorage(get_storage(environment="production"))
    preview_storage = get_storage(environment="preview")
    source_url = os.getenv("DATABASE_URL")
    if not source_url:
        raise Phase2eError("DATABASE_URL is required for source catalog verification")
    preview_url = resolve_runtime_target("preview").database_url
    captures, inventory = _source_captures(source_url, config)
    raw = _raw_by_entity(source_storage, captures)
    universe, game_sides = _core_universe(
        preview_storage, config["phase2c_ref_set_uri"]
    )
    outputs = {
        "recruiting": normalize_recruiting(
            _with_capture_season(raw["recruiting"]), universe
        ),
        "returning_production": normalize_returning_production(
            _with_capture_season(raw["returning_production"]), universe
        ),
        "coaching": normalize_coaching(_with_capture_season(raw["coaches"]), universe),
        "roster_continuity": normalize_roster_continuity(
            _with_capture_season(raw["rosters"]), universe
        ),
        "lagged_rankings": normalize_lagged_rankings(
            _with_capture_season(raw["rankings"]), game_sides
        ),
    }
    market, market_exclusions = normalize_market_references(raw["betting_lines"])
    outputs["market_references"] = market
    coverage = {
        "recruiting": _coverage(
            outputs["recruiting"],
            ("recruiting_4yr", "recruiting_current", "recruiting_trend"),
            ignore={2021, 2022, 2023},
        ),
        "returning_production": _coverage(
            outputs["returning_production"],
            (
                "return_total_ppa",
                "return_passing_ppa",
                "return_rushing_ppa",
                "return_receiving_ppa",
                "return_percent_ppa",
                "return_passing_usage",
                "return_rushing_usage",
            ),
        ),
        "coaching": _coverage(outputs["coaching"], ("coach_tenure", "coach_new")),
        "roster_continuity": _coverage(
            outputs["roster_continuity"],
            ("roster_size", "roster_returning_share", "roster_returning_qb_count"),
            ignore={2015, 2021},
        ),
        "lagged_rankings": _coverage(
            outputs["lagged_rankings"].query("missing_reason.isna()"),
            ("lagged_ap_rank", "lagged_coaches_rank", "lagged_ranked_either"),
        ),
    }
    for name, report in coverage.items():
        report["denominator_population"] = (
            "fbs_involved_game_side"
            if name == "lagged_rankings"
            else "fbs_team_season"
        )
    capture_manifest = capture_set_manifest(inventory)
    prefix = f"artifacts/research/data-first-football-v1/phase2/auxiliary/{args.run_id}"
    refs: dict[str, dict[str, Any]] = {}
    if args.mode == "apply":
        register_source_captures(preview_url, captures)
        _immutable(preview_storage, f"{prefix}/capture-set.json", capture_manifest)
        for name, frame in outputs.items():
            related = [
                capture
                for capture in captures
                if capture.entity
                == (
                    {
                        "recruiting": "recruiting",
                        "returning_production": "returning_production",
                        "coaching": "coaches",
                        "roster_continuity": "rosters",
                        "lagged_rankings": "rankings",
                        "market_references": "betting_lines",
                    }[name]
                )
            ]
            refs[name] = asdict(
                _write_dataset(
                    preview_storage,
                    preview_url,
                    name=name,
                    frame=frame,
                    captures=related,
                    code_sha=args.expected_code_sha,
                    config_sha=config_sha,
                    as_of=as_of,
                )
            )
        eligibility = auxiliary_eligibility_manifest(
            capture_set=capture_manifest,
            refs=refs,
            coverage=coverage,
            exclusions={"market_references": market_exclusions.to_dict("records")},
            code_sha=args.expected_code_sha,
            as_of=as_of.isoformat().replace("+00:00", "Z"),
        )
        _immutable(preview_storage, f"{prefix}/eligibility-manifest.json", eligibility)
    print(
        json.dumps(
            {
                "state": "ready"
                if args.mode == "dry-run"
                else "eligible_reconstructed_only",
                "prefix": prefix,
                "capture_count": len(inventory),
                "output_rows": {name: len(value) for name, value in outputs.items()},
                "coverage": {
                    name: value["minimum_coverage"] for name, value in coverage.items()
                },
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
