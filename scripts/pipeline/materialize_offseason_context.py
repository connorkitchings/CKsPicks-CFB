#!/usr/bin/env python3
"""Materialize Preview-only, provenance-bound offseason context families.

Historical CFBD responses are captured at execution time and are deliberately
classified as reconstructed.  The 2026 rows are derived only from the already
captured pre-kickoff preseason snapshots.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

import cfbd
import pandas as pd
from dotenv import load_dotenv

from cks_picks_cfb.data.catalog import (
    catalog_connection_url,
    register_dataset_version,
    register_existing_dataset_ref,
    register_source_capture,
    source_capture_by_id,
)
from cks_picks_cfb.data.lake import (
    BuildRequest,
    DatasetRef,
    build_dataset_version,
    capture_provider_records,
    read_dataset,
    read_source_capture,
)
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.preseason_features import (
    _coach_features,
    _recruiting_features,
    _returning_production,
)

HISTORICAL_SEASONS = (2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024, 2025)
FAMILIES = ("returning_production", "recruiting", "coaching")
SNAPSHOT_AS_OF = "2026-08-14"


def _ref(storage, uri: str) -> DatasetRef:
    return DatasetRef(**json.loads(storage.read_bytes(uri).decode()))


def _immutable_write(storage, uri: str, payload: bytes) -> None:
    if storage.exists(uri):
        if storage.read_bytes(uri) != payload:
            raise FileExistsError(f"Immutable artifact collision: {uri}")
        return
    storage.write_bytes(payload, uri)


def _code_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _plain(record: Any) -> dict[str, Any]:
    if isinstance(record, dict):
        return record
    if hasattr(record, "to_dict"):
        return dict(record.to_dict())
    raise TypeError(f"CFBD record cannot be serialized: {type(record)!r}")


def _fetch(client: cfbd.ApiClient, family: str, season: int) -> list[dict[str, Any]]:
    if family == "returning_production":
        rows = cfbd.PlayersApi(client).get_returning_production(year=season)
    elif family == "coaching":
        rows = cfbd.CoachesApi(client).get_coaches(year=season)
    elif family == "recruiting":
        api = cfbd.RecruitingApi(client)
        rows = []
        for recruit_year in range(season - 3, season + 1):
            rows.extend(api.get_team_recruiting_rankings(year=recruit_year))
    else:
        raise ValueError(f"Unsupported context family: {family}")
    return [_plain(row) for row in rows]


def _features(family: str, rows: list[dict[str, Any]], season: int) -> pd.DataFrame:
    raw = pd.DataFrame.from_records(rows)
    if family == "returning_production":
        result = _returning_production(raw)
    elif family == "recruiting":
        result = _recruiting_features(raw, season)
    elif family == "coaching":
        if "seasons" in raw:
            raw["seasons"] = raw["seasons"].map(
                lambda value: ast.literal_eval(value)
                if isinstance(value, str) and value.startswith("[")
                else value
            )
        result = _coach_features(raw, season)
    else:
        raise ValueError(f"Unsupported context family: {family}")
    result["season"] = season
    return result


def _snapshot_rows(storage, family: str) -> tuple[list[dict[str, Any]], datetime]:
    rows = storage.read_index(
        f"raw/preseason/{'coaches' if family == 'coaching' else family}",
        {"snapshot_year": "2026", "as_of": SNAPSHOT_AS_OF},
    )
    manifest = storage.read_index(
        f"raw/preseason_manifest/{'coaches' if family == 'coaching' else family}",
        {"snapshot_year": "2026", "as_of": SNAPSHOT_AS_OF},
    )
    if not rows or len(manifest) != 1 or int(manifest[0].get("rows", 0)) != len(rows):
        raise ValueError(f"Missing or inconsistent authentic 2026 {family} snapshot")
    captured = datetime.fromisoformat(
        str(manifest[0]["retrieved_at"]).replace("Z", "+00:00")
    )
    return rows, captured


def _capture(
    storage,
    *,
    family: str,
    season: int,
    rows: list[dict[str, Any]],
    captured_at: datetime,
    request: dict[str, Any],
    capture_id: str,
) -> tuple[object, pd.DataFrame]:
    capture = capture_provider_records(
        storage,
        provider="cfbd",
        entity=f"offseason_context_{family}",
        records=rows,
        captured_at=captured_at,
        effective_at=captured_at,
        request=request,
        response_metadata={
            "context_track": "strict" if season == 2026 else "reconstructed"
        },
        capture_id=capture_id,
    )
    return capture, _features(family, rows, season)


def _capture_id(*, family: str, season: int, as_of: str, code_sha: str) -> str:
    return hashlib.sha256(
        json.dumps(
            {"family": family, "season": season, "as_of": as_of, "code_sha": code_sha},
            sort_keys=True,
        ).encode()
    ).hexdigest()[:32]


def _team_universe(
    storage, foundation_uri: str, games_2026_uri: str
) -> tuple[pd.DataFrame, list[DatasetRef]]:
    root = foundation_uri.rsplit("/", 1)[0]
    refs: list[DatasetRef] = []
    frames: list[pd.DataFrame] = []
    for season in HISTORICAL_SEASONS:
        ref = _ref(storage, f"{root}/input-refs/{season}/games.json")
        refs.append(ref)
        frames.append(read_dataset(storage, ref))
    current = _ref(storage, games_2026_uri)
    refs.append(current)
    frames.append(read_dataset(storage, current))
    games = pd.concat(frames, ignore_index=True)
    required = {"season", "home_team", "away_team", "kickoff_utc"}
    if missing := sorted(required - set(games)):
        raise ValueError(f"Games refs lack team-universe columns: {missing}")
    games["kickoff_utc"] = pd.to_datetime(
        games["kickoff_utc"], utc=True, errors="raise"
    )
    sides = pd.concat(
        [
            games[["season", "kickoff_utc", "home_team"]].rename(
                columns={"home_team": "team"}
            ),
            games[["season", "kickoff_utc", "away_team"]].rename(
                columns={"away_team": "team"}
            ),
        ],
        ignore_index=True,
    )
    allowed = set(HISTORICAL_SEASONS) | {2026}
    sides = sides[
        pd.to_numeric(sides["season"], errors="raise").astype(int).isin(allowed)
    ]
    universe = (
        sides.assign(season=lambda frame: frame["season"].astype(int))
        .groupby(["season", "team"], as_index=False)["kickoff_utc"]
        .min()
        .rename(columns={"kickoff_utc": "first_kickoff_utc"})
        .sort_values(["season", "team"])
    )
    if universe.duplicated(["season", "team"]).any() or universe.empty:
        raise ValueError("Team universe has invalid keys")
    return universe, refs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", choices=("preview",), required=True)
    parser.add_argument("--r1-foundation-manifest-uri", required=True)
    parser.add_argument("--games-2026-ref-uri", required=True)
    parser.add_argument("--output-prefix", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    args = parser.parse_args()
    load_dotenv()
    if _code_sha() != args.expected_code_sha:
        raise ValueError("--expected-code-sha must equal current HEAD")
    if not args.output_prefix.startswith("artifacts/research/rating-successor-v2/"):
        raise ValueError("Context output must use the isolated successor-v2 prefix")
    storage = get_storage(environment="preview")
    catalog_url = catalog_connection_url("preview")
    foundation = json.loads(
        storage.read_bytes(args.r1_foundation_manifest_uri).decode()
    )
    if (
        foundation.get("contract_version") != "successor-r1-foundation-v2"
        or foundation.get("state") != "complete"
    ):
        raise ValueError("Context materialization requires a complete R1 foundation")
    cutoff = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    universe, universe_parents = _team_universe(
        storage, args.r1_foundation_manifest_uri, args.games_2026_ref_uri
    )
    universe_ref, universe_manifest = build_dataset_version(
        storage,
        build=BuildRequest(
            "offseason_context_team_universe",
            tuple(universe_parents),
            args.expected_code_sha,
            "offseason_context_universe_v1",
            cutoff,
            schema_version="offseason_context_team_universe_v1",
            tier="gold",
            identity_version="v1",
        ),
        records=universe.to_dict("records"),
        partitions={
            "seasons": sorted(universe["season"].astype(int).unique().tolist())
        },
        validation={"unique_team_keys": True, "excludes_2020": True},
    )
    register_dataset_version(catalog_url, universe_ref, universe_manifest)
    _immutable_write(
        storage,
        f"{args.output_prefix}/team-universe-ref.json",
        json.dumps(asdict(universe_ref), sort_keys=True).encode(),
    )

    client = cfbd.ApiClient(
        cfbd.Configuration(access_token=__import__("os").environ["CFBD_API_KEY"])
    )
    family_refs: dict[str, DatasetRef] = {}
    family_capture_ids: dict[str, list[str]] = {}
    for family in FAMILIES:
        print(f"materializing {family}", flush=True)
        family_ref_uri = f"{args.output_prefix}/family-refs/{family}.json"
        if storage.exists(family_ref_uri):
            ref = register_existing_dataset_ref(catalog_url, storage, family_ref_uri)
            dataset_manifest = json.loads(
                storage.read_bytes(
                    ref.uri.rsplit("/", 1)[0] + "/manifest.json"
                ).decode()
            )
            family_refs[family] = ref
            family_capture_ids[family] = list(
                dataset_manifest.get("source_capture_ids", [])
            )
            print(f"reused {family}", flush=True)
            continue
        normalized: list[pd.DataFrame] = []
        captures = []
        for season in (*HISTORICAL_SEASONS, 2026):
            if season == 2026:
                rows, captured_at = _snapshot_rows(storage, family)
                request = {
                    "operation": "reuse_authentic_preseason_snapshot",
                    "source": family,
                    "season": 2026,
                    "snapshot_as_of": SNAPSHOT_AS_OF,
                }
            else:
                captured_at = datetime.now(timezone.utc)
                rows = _fetch(client, family, season)
                request = {
                    "operation": "historical_context_backfill",
                    "source": family,
                    "season": season,
                    "provider_endpoint": "cfbd",
                }
            capture_id = _capture_id(
                family=family,
                season=season,
                as_of=args.as_of,
                code_sha=args.expected_code_sha,
            )
            try:
                capture = source_capture_by_id(catalog_url, capture_id)
                frame = _features(
                    family,
                    read_source_capture(storage, capture).to_dict("records"),
                    season,
                )
            except LookupError:
                capture, frame = _capture(
                    storage,
                    family=family,
                    season=season,
                    rows=rows,
                    captured_at=captured_at,
                    request=request,
                    capture_id=capture_id,
                )
                try:
                    register_source_capture(catalog_url, capture)
                except ValueError as exc:
                    # An interrupted prior invocation can finish catalog
                    # registration after this attempt's initial lookup.  Its
                    # capture timestamp is immutable provenance, so reuse it
                    # instead of creating a timestamp-conflicting replay.
                    if not str(exc).startswith("Immutable source capture conflict:"):
                        raise
                    capture = source_capture_by_id(catalog_url, capture_id)
                    frame = _features(
                        family,
                        read_source_capture(storage, capture).to_dict("records"),
                        season,
                    )
            captures.append(capture)
            observed_at = capture.captured_at.isoformat()
            normalized.append(
                frame.assign(effective_at=observed_at, retrieved_at=observed_at)
            )
        combined = pd.concat(normalized, ignore_index=True).sort_values(
            ["season", "team"]
        )
        ref, family_manifest = build_dataset_version(
            storage,
            build=BuildRequest(
                "offseason_context_family",
                (),
                args.expected_code_sha,
                f"offseason_context_{family}_v1",
                cutoff,
                source_capture_ids=tuple(c.capture_id for c in captures),
                schema_version="offseason_context_family_v1",
                tier="silver",
                identity_version="v1",
            ),
            records=combined.to_dict("records"),
            partitions={
                "family": family,
                "seasons": sorted(combined["season"].astype(int).unique().tolist()),
            },
            validation={
                "unique_team_keys": not combined.duplicated(["season", "team"]).any(),
                "excludes_2020": 2020 not in set(combined["season"].astype(int)),
            },
            coverage={
                "family": family,
                "track": "reconstructed",
                "source_capture_count": len(captures),
            },
        )
        register_dataset_version(catalog_url, ref, family_manifest)
        family_refs[family] = ref
        family_capture_ids[family] = [capture.capture_id for capture in captures]
        _immutable_write(
            storage, family_ref_uri, json.dumps(asdict(ref), sort_keys=True).encode()
        )
        print(f"materialized {family}", flush=True)
    manifest = {
        "schema_version": "offseason_context_source_manifest_v1",
        "state": "complete",
        "feature_track": "reconstructed",
        "team_universe_ref": asdict(universe_ref),
        "family_refs": {name: asdict(ref) for name, ref in family_refs.items()},
        "family_capture_ids": family_capture_ids,
        "rejected_families": {
            "transfer_portal": "CFBD transfer portal data is unavailable for 2015",
            "talent": "no authentic nonempty 2026 pre-kickoff capture exists",
        },
    }
    _immutable_write(
        storage,
        f"{args.output_prefix}/source-manifest.json",
        json.dumps(manifest, indent=2, sort_keys=True).encode(),
    )
    print(
        json.dumps(
            {
                "source_manifest_uri": f"{args.output_prefix}/source-manifest.json",
                "families": sorted(family_refs),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
