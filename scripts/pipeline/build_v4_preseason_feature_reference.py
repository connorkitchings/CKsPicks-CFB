#!/usr/bin/env python3
"""Build an immutable strict or reconstructed V4 preseason team reference."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone

import pandas as pd
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
from cks_picks_cfb.models.v4_feature_variants import FAMILY_PREFIXES

FAMILY_FEATURES = {
    "returning_production": (
        "return_total_ppa",
        "return_passing_ppa",
        "return_rushing_ppa",
        "return_receiving_ppa",
        "return_percent_ppa",
        "return_passing_usage",
        "return_rushing_usage",
    ),
    "transfer_portal": (
        "transfer_in_count",
        "transfer_out_count",
        "transfer_net_rating",
        "transfer_in_qb",
        "transfer_out_qb",
    ),
    "recruiting": (
        "recruiting_4yr",
        "recruiting_current",
        "recruiting_trend",
    ),
    "coaching": ("coach_tenure", "coach_new"),
    "roster_continuity": (
        "roster_size",
        "roster_returning_share",
        "roster_returning_qb_count",
    ),
    "preseason_rankings": (
        "preseason_ap_rank",
        "preseason_coaches_rank",
        "preseason_ranked_either",
    ),
    "talent": ("talent",),
}


def _ref(storage, uri: str) -> DatasetRef:
    return DatasetRef(**json.loads(storage.read_bytes(uri).decode()))


def _code_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _canonical(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()


def _parse_family_refs(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        family, separator, uri = value.partition("=")
        if not separator or not family or not uri:
            raise ValueError("--family-ref values must be FAMILY=DATASET_REF_URI")
        if family not in FAMILY_FEATURES:
            raise ValueError(f"Unknown V4 source family: {family}")
        if family in result:
            raise ValueError(f"Duplicate V4 source family: {family}")
        result[family] = uri
    return result


def _team_universe(core: pd.DataFrame) -> pd.DataFrame:
    required = {"season", "home_team", "away_team", "start_date"}
    if missing := sorted(required - set(core.columns)):
        raise ValueError(f"Core Gold is missing V4 reference fields: {missing}")
    sides = pd.concat(
        [
            core[["season", "start_date", "home_team"]].rename(
                columns={"home_team": "team"}
            ),
            core[["season", "start_date", "away_team"]].rename(
                columns={"away_team": "team"}
            ),
        ],
        ignore_index=True,
    )
    sides["season"] = sides["season"].astype(int)
    sides["start_date"] = pd.to_datetime(sides["start_date"], utc=True, errors="raise")
    return (
        sides.groupby(["season", "team"], as_index=False)["start_date"]
        .min()
        .rename(columns={"start_date": "season_first_kickoff_utc"})
        .sort_values(["season", "team"])
        .reset_index(drop=True)
    )


def _family_frame(
    source: pd.DataFrame,
    *,
    universe: pd.DataFrame,
    family: str,
    strict: bool,
) -> tuple[pd.DataFrame | None, dict[str, object]]:
    features = list(FAMILY_FEATURES[family])
    required = {"season", "team", "effective_at", "retrieved_at", *features}
    missing = sorted(required - set(source.columns))
    if missing:
        return None, {"eligible": False, "reason": f"missing columns: {missing}"}
    frame = source[["season", "team", "effective_at", "retrieved_at", *features]].copy()
    frame["season"] = pd.to_numeric(frame["season"], errors="coerce")
    frame["effective_at"] = pd.to_datetime(frame["effective_at"], utc=True, errors="coerce")
    frame["retrieved_at"] = pd.to_datetime(frame["retrieved_at"], utc=True, errors="coerce")
    for feature in features:
        frame[feature] = pd.to_numeric(frame[feature], errors="coerce")
    if frame.duplicated(["season", "team"]).any():
        return None, {"eligible": False, "reason": "duplicate season/team rows"}
    merged = universe.merge(frame, on=["season", "team"], how="left", validate="one_to_one")
    values_complete = not merged[features].isna().any().any()
    evidence_complete = not merged[["effective_at", "retrieved_at"]].isna().any().any()
    effective_before_kickoff = bool(
        (merged["effective_at"] < merged["season_first_kickoff_utc"]).all()
    )
    eligible = values_complete and evidence_complete and (
        effective_before_kickoff if strict else True
    )
    reason = None
    if not values_complete:
        reason = "incomplete team-season feature coverage"
    elif not evidence_complete:
        reason = "missing effective_at or retrieved_at provenance"
    elif strict and not effective_before_kickoff:
        reason = "effective_at is not before season first kickoff"
    metadata = {
        "eligible": eligible,
        "reason": reason,
        "required_features": features,
        "covered_rows": int(merged[features].notna().all(axis=1).sum()),
        "required_rows": int(len(universe)),
        "effective_before_kickoff": effective_before_kickoff,
    }
    return (merged[["season", "team", *features]] if eligible else None), metadata


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-ref-uri", required=True)
    parser.add_argument("--track", choices=("strict", "reconstructed"), required=True)
    parser.add_argument("--family-ref", action="append", default=[])
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--output-ref-uri", required=True)
    parser.add_argument("--manifest-uri", required=True)
    parser.add_argument("--environment", choices=("preview", "production"), required=True)
    args = parser.parse_args()
    storage = get_storage(environment=args.environment)
    if storage.exists(args.output_ref_uri):
        register_existing_dataset_ref(
            catalog_connection_url(args.environment), storage, args.output_ref_uri
        )
        print(storage.read_bytes(args.output_ref_uri).decode())
        return
    core_ref = _ref(storage, args.core_ref_uri)
    universe = _team_universe(read_dataset(storage, core_ref))
    family_uris = _parse_family_refs(args.family_ref)
    strict = args.track == "strict"
    result = universe[["season", "team"]].copy()
    family_manifest: dict[str, dict[str, object]] = {
        "prior_core": {
            "eligible": True,
            "reason": None,
            "required_features": [],
            "covered_rows": int(len(universe)),
            "required_rows": int(len(universe)),
            "source_ref": None,
        }
    }
    parent_refs = [core_ref]
    for family in FAMILY_PREFIXES:
        if family == "prior_core":
            continue
        uri = family_uris.get(family)
        if not uri:
            family_manifest[family] = {
                "eligible": False,
                "reason": "no immutable normalized source reference supplied",
                "required_features": list(FAMILY_FEATURES[family]),
                "covered_rows": 0,
                "required_rows": int(len(universe)),
                "source_ref": None,
            }
            continue
        source_ref = _ref(storage, uri)
        parent_refs.append(source_ref)
        family_frame, metadata = _family_frame(
            read_dataset(storage, source_ref),
            universe=universe,
            family=family,
            strict=strict,
        )
        family_manifest[family] = {
            **metadata,
            "source_ref": asdict(source_ref),
            "raw_content_sha": source_ref.content_sha,
        }
        if family_frame is not None:
            result = result.merge(
                family_frame, on=["season", "team"], how="left", validate="one_to_one"
            )
    eligible_families = [
        family for family, metadata in family_manifest.items() if metadata["eligible"]
    ]
    manifest_payload = {
        "schema_version": "v4_preseason_feature_reference_v1",
        "track": args.track,
        "activation_eligible": strict,
        "core_ref": asdict(core_ref),
        "family_order": list(FAMILY_PREFIXES),
        "families": family_manifest,
        "eligible_families": eligible_families,
        "coverage": {
            "required_team_seasons": int(len(universe)),
            "seasons": sorted(universe["season"].unique().astype(int).tolist()),
        },
    }
    reference_sha = hashlib.sha256(_canonical(manifest_payload)).hexdigest()
    manifest_payload["reference_sha"] = reference_sha
    result["v4_feature_track"] = args.track
    result["v4_activation_eligible"] = strict
    result["v4_reference_sha"] = reference_sha
    cutoff = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    ref, manifest = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset="v4_preseason_team_features",
            parent_refs=tuple(parent_refs),
            code_sha=_code_sha(),
            config_sha=reference_sha,
            as_of=cutoff,
            schema_version="v4_preseason_team_features_v1",
            tier="gold",
        ),
        records=result.to_dict("records"),
        partitions={"seasons": sorted(result["season"].astype(int).unique().tolist())},
        validation={
            "unique_team_keys": not result.duplicated(["season", "team"]).any(),
            "excludes_2020": 2020 not in set(result["season"].astype(int)),
            "strict_track_activation_eligible": strict,
        },
        coverage={
            "feature_track": args.track,
            "activation_eligible": strict,
            "reference_sha": reference_sha,
            "eligible_families": eligible_families,
            "families": family_manifest,
        },
    )
    if manifest.state != "validated":
        raise RuntimeError(f"V4 preseason feature validation failed: {manifest.validation}")
    register_dataset_version(catalog_connection_url(args.environment), ref, manifest)
    encoded_manifest = json.dumps(manifest_payload, indent=2, sort_keys=True).encode()
    if storage.exists(args.manifest_uri):
        if storage.read_bytes(args.manifest_uri) != encoded_manifest:
            raise FileExistsError(f"Immutable V4 reference manifest exists: {args.manifest_uri}")
    else:
        storage.write_bytes(encoded_manifest, args.manifest_uri)
    payload = json.dumps(asdict(ref), indent=2, sort_keys=True).encode()
    storage.write_bytes(payload, args.output_ref_uri)
    print(json.dumps({"ref": asdict(ref), "reference_sha": reference_sha}, indent=2))


if __name__ == "__main__":
    main()
