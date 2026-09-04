#!/usr/bin/env python3
"""Join explicit temporal baseline artifacts onto structural Gold."""

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
    require_dataset,
)
from cks_picks_cfb.data.runtime import resolve_runtime_target
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.features.point_in_time import attach_baseline_predictions
from cks_picks_cfb.preseason_features import canonical_team


def _ref(storage, uri: str) -> DatasetRef:
    return DatasetRef(**json.loads(storage.read_bytes(uri).decode()))


def _code_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _attach_preseason_features(
    result: pd.DataFrame, preseason: pd.DataFrame, feature_columns: list[str]
) -> pd.DataFrame:
    """Join canonical preseason evidence without altering game-facing labels."""
    attached = result.copy()
    for side in ("home", "away"):
        join_key = f"_{side}_preseason_team"
        attached[join_key] = attached[f"{side}_team"].map(canonical_team)
        if attached[join_key].isna().any():
            raise ValueError(f"V4 core has an invalid {side} team identity")
        renamed = preseason[["season", "team", *feature_columns]].rename(
            columns={
                "team": join_key,
                **{column: f"{side}_{column}" for column in feature_columns},
            }
        )
        attached = attached.merge(
            renamed,
            on=["season", join_key],
            how="left",
            validate="many_to_one",
        ).drop(columns=[join_key])
    return attached


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-ref-uri", required=True)
    parser.add_argument("--baselines-ref-uri", required=True)
    parser.add_argument("--markets-ref-uri")
    parser.add_argument("--preseason-features-ref-uri")
    parser.add_argument("--feature-track", choices=("strict", "reconstructed"))
    parser.add_argument("--skip-catalog-registration", action="store_true")
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--output-ref-uri", required=True)
    parser.add_argument(
        "--environment",
        choices=["production", "preview"],
        required=True,
    )
    args = parser.parse_args()
    storage = get_storage(environment=args.environment)
    if storage.exists(args.output_ref_uri):
        register_existing_dataset_ref(
            catalog_connection_url(args.environment), storage, args.output_ref_uri
        )
        print(storage.read_bytes(args.output_ref_uri).decode())
        return
    core_ref = _ref(storage, args.core_ref_uri)
    baselines_ref = _ref(storage, args.baselines_ref_uri)
    core = read_dataset(storage, core_ref)
    baselines = read_dataset(storage, baselines_ref)
    required_seasons = set(baselines["season"].astype(int))
    result = attach_baseline_predictions(
        core, baselines, required_seasons=required_seasons
    )
    preseason_ref: DatasetRef | None = None
    feature_track: str | None = None
    activation_eligible = True
    if args.preseason_features_ref_uri:
        if not args.feature_track:
            raise ValueError("--feature-track is required with V4 preseason features")
        preseason_ref = _ref(storage, args.preseason_features_ref_uri)
        if preseason_ref.dataset != "v4_preseason_team_features":
            raise ValueError("V4 model-ready Gold requires v4_preseason_team_features")
        preseason = read_dataset(storage, preseason_ref)
        required_preseason = {
            "season",
            "team",
            "v4_feature_track",
            "v4_activation_eligible",
            "v4_reference_sha",
        }
        if missing := sorted(required_preseason - set(preseason.columns)):
            raise ValueError(f"V4 preseason reference is missing columns: {missing}")
        if preseason.duplicated(["season", "team"]).any():
            raise ValueError("V4 preseason reference has duplicate season/team keys")
        tracks = set(preseason["v4_feature_track"].dropna().astype(str))
        if tracks != {args.feature_track}:
            raise ValueError(
                f"V4 preseason track mismatch: expected {args.feature_track}, found {sorted(tracks)}"
            )
        feature_track = args.feature_track
        activation_eligible = bool(preseason["v4_activation_eligible"].all())
        if feature_track == "strict" and not activation_eligible:
            raise ValueError("Strict V4 feature reference is not activation eligible")
        feature_columns = [
            column
            for column in preseason.columns
            if column
            not in {
                "season",
                "team",
                "v4_feature_track",
                "v4_activation_eligible",
                "v4_reference_sha",
            }
        ]
        result = _attach_preseason_features(result, preseason, feature_columns)
        if (
            feature_columns
            and result[[f"home_{column}" for column in feature_columns]]
            .isna()
            .all(axis=1)
            .any()
        ):
            raise ValueError("V4 preseason reference does not cover every home team")
        result["v4_feature_track"] = feature_track
        result["v4_activation_eligible"] = activation_eligible
        result["v4_reference_sha"] = preseason["v4_reference_sha"].iloc[0]
    # Historical all-null boolean-like prior fields arrive from Parquet as
    # object dtype.  Keep them as usable numeric missingness features rather
    # than letting the Gold schema treat them as undeclared string metadata.
    for column in result.columns:
        if (
            column.endswith(("_missing", "_neutral_site"))
            and result[column].dtype == object
        ):
            result[column] = pd.to_numeric(result[column], errors="coerce")
    markets_ref: DatasetRef | None = None
    markets_joined = False
    if args.markets_ref_uri:
        markets_ref = _ref(storage, args.markets_ref_uri)
        require_dataset(markets_ref, "market_snapshots")
        markets = read_dataset(storage, markets_ref).rename(
            columns={"spread_line": "home_team_spread_line"}
        )
        market_columns = [
            column
            for column in (
                "season",
                "game_id",
                "market_snapshot_id",
                "market_captured_at",
                "home_team_spread_line",
                "total_line",
                "source_quote_ids",
            )
            if column in markets
        ]
        result = result.merge(
            markets[market_columns].drop_duplicates(["season", "game_id"], keep="last"),
            on=["season", "game_id"],
            how="left",
            validate="one_to_one",
        )
        markets_joined = True
    cutoff = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    parent_refs = tuple(
        r for r in (core_ref, baselines_ref, preseason_ref, markets_ref) if r
    )
    if markets_joined:
        timestamp_check = (
            "market_captured_at" in result
            and not result.loc[
                result["home_team_spread_line"].notna() | result["total_line"].notna(),
                "market_captured_at",
            ]
            .isna()
            .any()
        )
    else:
        timestamp_check = True
    ref, manifest = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset=(
                "point_in_time_matchups_v5"
                if preseason_ref
                else "point_in_time_matchups"
            ),
            parent_refs=parent_refs,
            code_sha=_code_sha(),
            config_sha=hashlib.sha256(
                json.dumps(
                    {
                        "model_ready_gold": "v5" if preseason_ref else "v4",
                        "feature_track": feature_track,
                        "activation_eligible": activation_eligible,
                    },
                    sort_keys=True,
                ).encode()
            ).hexdigest(),
            as_of=cutoff,
            schema_version=(
                "point_in_time_matchups_v5"
                if preseason_ref
                else "point_in_time_matchups_v4"
            ),
            tier="gold",
        ),
        records=result.to_dict("records"),
        partitions={"seasons": sorted(result["season"].astype(int).unique().tolist())},
        event_time_column="start_date",
        validation={
            "unique_game_keys": not result.duplicated(["season", "game_id"]).any(),
            # Resultless labeled-season games (canceled or unreported) carry no
            # baseline and no target; they are unlabeled like future games.
            "baseline_complete_for_oof_seasons": not result[
                result["season"].astype(int).isin(required_seasons)
                & result["spread_target"].notna()
                & result["total_target"].notna()
            ][["baseline_spread_prediction", "baseline_total_prediction"]]
            .isna()
            .any()
            .any(),
            "excludes_2020": 2020 not in set(result["season"].astype(int)),
            "markets_joined": markets_joined if args.markets_ref_uri else True,
            "market_timestamps_authentic": timestamp_check,
            "strict_track_activation_eligible": (
                activation_eligible if feature_track == "strict" else True
            ),
        },
        coverage={
            "feature_track": feature_track,
            "activation_eligible": activation_eligible,
            "preseason_feature_ref": asdict(preseason_ref) if preseason_ref else None,
        },
    )
    if manifest.state != "validated":
        raise RuntimeError(f"Model-ready Gold validation failed: {manifest.validation}")
    if not args.skip_catalog_registration:
        conn_url = resolve_runtime_target(args.environment).database_url
        register_dataset_version(conn_url, ref, manifest)
    payload = json.dumps(asdict(ref), indent=2, sort_keys=True).encode()
    if storage.exists(args.output_ref_uri):
        if storage.read_bytes(args.output_ref_uri) != payload:
            raise FileExistsError(
                f"Immutable model-ready ref exists: {args.output_ref_uri}"
            )
    else:
        storage.write_bytes(payload, args.output_ref_uri)
    print(json.dumps(asdict(ref), sort_keys=True))


if __name__ == "__main__":
    main()
