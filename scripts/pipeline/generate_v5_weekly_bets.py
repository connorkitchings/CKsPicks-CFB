"""Explicit V5 mode for the existing immutable weekly prediction-run format."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from cks_picks_cfb.artifacts import (
    dataframe_csv_bytes,
    local_prediction_path,
    prediction_run_features_path,
    prediction_run_manifest_path,
    read_json_artifact,
    write_prediction_run,
)
from cks_picks_cfb.data.lake import DatasetRef, read_dataset
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.features.point_in_time import build_point_in_time_matchups
from cks_picks_cfb.inference.v5_serving import (
    V5ServingError,
    build_v5_serving_rows,
    v5_serving_manifest_fields,
)
from scripts.research.run_v5_live_forecast import _load_stored_predictions, verify


def _ref(value: dict[str, Any]) -> DatasetRef:
    return DatasetRef(
        **{
            key: value[key]
            for key in ("dataset", "version_id", "schema_version", "content_sha", "uri")
        }
    )


def verify_v5_source(
    spec: Any, storage: Any
) -> tuple[dict[str, Any], pd.DataFrame, dict[str, Any]]:
    if spec.get("schema_version") != "v5_weekly_serving_v1":
        raise V5ServingError("unexpected V5 weekly serving schema")
    if not spec.get("forecast_manifest_uri") or not spec.get(
        "forecast_manifest_sha256"
    ):
        raise V5ServingError("V5 weekly serving requires a pinned forecast manifest")
    forecast_uri = str(spec.forecast_manifest_uri)
    raw = storage.read_bytes(forecast_uri)
    expected_sha = str(spec.forecast_manifest_sha256)
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise V5ServingError("V5 forecast manifest checksum mismatch")
    manifest = json.loads(raw)
    identity = manifest.get("identity") or {}
    parents = manifest.get("parents") or {}
    forecast_config = Path(str(spec.forecast_config))
    verification_args = argparse.Namespace(
        verify_manifest_uri=forecast_uri,
        run_id=str(identity.get("run_id")),
        expected_code_sha=str(identity.get("code_sha")),
        as_of=str(identity.get("as_of")),
        config=str(forecast_config),
        measurement_manifest_uri=str(parents.get("measurement_uri")),
        rating_manifest_uri=str(parents.get("rating_replay_uri")),
        schedule_ref_uri=str(parents.get("schedule_ref_uri")),
    )
    verification = verify(
        verification_args, yaml.safe_load(forecast_config.read_text()), storage
    )
    fields = v5_serving_manifest_fields(
        manifest_uri=forecast_uri, manifest_raw=raw, verification=verification
    )
    return manifest, _load_stored_predictions(storage, manifest), fields


def run_v5_weekly_bets(args: argparse.Namespace, cfg: Any) -> dict[str, Any]:
    """Verify V5 from its parents before creating an ordinary weekly run.

    The Preview forecast may be read in either environment because R2 content is
    immutable. Activation remains governed by the ordinary ops environment and
    the explicit configuration flag.
    """
    year = int(args.year if args.year is not None else cfg.year)
    week = int(args.week if args.week is not None else cfg.week)
    spec = cfg.v5_live_forecast
    if not args.as_of or not args.dataset_refs_uri or not args.run_id:
        raise V5ServingError(
            "V5 weekly serving requires as-of, dataset refs, and run ID"
        )
    if args.run_state != "preview":
        raise V5ServingError("V5 prediction artifact must begin in preview state")
    from_env = os.environ.get("CFB_ARTIFACT_ENV", "production")
    if (
        from_env == "production"
        and spec.get("production_activation_authorized") is not True
    ):
        raise V5ServingError(
            "V5 production publication lacks an explicit activation decision"
        )
    storage = get_storage(environment=from_env)
    manifest, forecasts, source_fields = verify_v5_source(spec, storage)
    identity = manifest["identity"]
    expected_sha = str(spec.forecast_manifest_sha256)
    if identity.get("season") != year or identity.get("environment") != "preview":
        raise V5ServingError("V5 forecast season or environment mismatch")
    forecast_cutoff = pd.Timestamp(identity.get("as_of"))
    serving_cutoff = pd.Timestamp(args.as_of)
    if (
        forecast_cutoff.tzinfo is None
        or serving_cutoff.tzinfo is None
        or forecast_cutoff > serving_cutoff
    ):
        raise V5ServingError("V5 forecast cutoff is later than serving cutoff")
    refs = json.loads(storage.read_bytes(args.dataset_refs_uri))
    by_entity = {(str(item["entity"]), int(item["year"])): item for item in refs}
    schedule_item = by_entity.get(("games", year))
    if schedule_item is None:
        raise V5ServingError("weekly dataset refs lack the 2026 serving schedule")
    schedule = read_dataset(storage, _ref(schedule_item))
    forecast_schedule_raw = storage.read_bytes(manifest["parents"]["schedule_ref_uri"])
    try:
        forecast_schedule = pd.read_parquet(io.BytesIO(forecast_schedule_raw))
    except Exception:
        forecast_schedule = pd.DataFrame(json.loads(forecast_schedule_raw))
    market_item = by_entity.get(("betting_lines", year))
    markets = read_dataset(storage, _ref(market_item)) if market_item else None
    rows = build_v5_serving_rows(
        forecasts,
        schedule,
        forecast_schedule,
        markets,
        forecast_run_id=str(identity["run_id"]),
        forecast_manifest_sha256=expected_sha,
        year=year,
        week=week,
        as_of=args.as_of,
        run_id=args.run_id,
        spread_threshold=float(cfg.spread_edge_threshold),
        spread_threshold_high=float(cfg.spread_edge_threshold_high_conf),
        total_threshold=float(cfg.total_edge_threshold),
    )
    output_path = args.output_csv or local_prediction_path(year, week)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows.to_csv(output_path, index=False)
    if not args.upload_artifact:
        return {"state": "dry_run", "row_count": len(rows), **source_fields}
    features = schedule.loc[schedule["season"].eq(year) & schedule["week"].eq(week)]
    snapshot = build_point_in_time_matchups(
        features,
        season=year,
        as_of=args.as_of,
        provenance={"v5_forecast_manifest_sha256": expected_sha},
    )
    feature_bytes = dataframe_csv_bytes(snapshot)
    feature_uri = prediction_run_features_path(year, week, args.run_id)
    if storage.exists(feature_uri):
        if storage.read_bytes(feature_uri) != feature_bytes:
            raise FileExistsError("V5 immutable serving snapshot collision")
    else:
        storage.write_bytes(feature_bytes, feature_uri)
    code_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    lined = int(rows[["home_team_spread_line", "total_line"]].notna().all(axis=1).sum())
    run_manifest = {
        "state": "preview",
        "evidence_class": "pending",
        "data_as_of": args.as_of,
        "feature_snapshot_uri": feature_uri,
        "feature_snapshot_sha256": hashlib.sha256(feature_bytes).hexdigest(),
        "expected_games": len(rows),
        "predicted_games": len(rows),
        "lined_games": lined,
        "code_sha": code_sha,
        "config_sha": hashlib.sha256(Path(args.config).read_bytes()).hexdigest(),
        "model_bundle_sha256": source_fields["inference_bundle_sha256"],
        "input_dataset_refs": refs,
        "source_config": str(args.config),
        "system_name": str(cfg.system_name),
        "model_id": str(cfg.model_id),
        "validation": {
            "all_predictions_present": True,
            "line_coverage_complete": lined == len(rows),
        },
        **source_fields,
    }
    existing_uri = prediction_run_manifest_path(year, week, args.run_id)
    if storage.exists(existing_uri):
        existing = read_json_artifact(existing_uri, storage)
        if any(existing.get(key) != value for key, value in source_fields.items()):
            raise FileExistsError("V5 run ID is bound to a different forecast identity")
    return write_prediction_run(
        rows,
        year=year,
        week=week,
        run_id=args.run_id,
        manifest=run_manifest,
        storage=storage,
    )
