"""Convert an independently verified V5 replay into weekly serving artifacts."""

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

from cks_picks_cfb.artifacts import (
    dataframe_csv_bytes,
    prediction_run_features_path,
    write_prediction_run,
)
from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.inference.v5_serving import V5ServingError, build_v5_serving_rows
from scripts.pipeline.build_v5_replay import verify as verify_replay
from scripts.pipeline.build_v5_week4_replay import verify as verify_week4_replay


def verify_v5_replay_source(spec: Any, storage: Any):
    if spec.get("schema_version") != "v5_replay_serving_v1":
        raise V5ServingError("unexpected V5 replay serving schema")
    uri = str(spec.get("replay_manifest_uri") or "")
    expected_sha = str(spec.get("replay_manifest_sha256") or "")
    if not uri or len(expected_sha) != 64:
        raise V5ServingError("V5 replay serving requires an exact pinned manifest")
    raw = storage.read_bytes(uri)
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise V5ServingError("V5 replay manifest checksum differs")
    manifest = json.loads(raw)
    verify_signed_payload(manifest, label="V5 replay manifest")
    identity = manifest.get("identity") or {}
    parents = manifest.get("parents") or {}
    config_path = Path(str(spec.get("forecast_config") or ""))
    if not config_path.is_file():
        raise V5ServingError("V5 replay forecast config is absent")
    import yaml

    schema = manifest.get("schema_version")
    if schema == "v5_replay_manifest_v1":
        args = argparse.Namespace(
            run_id=str(identity.get("run_id")),
            expected_code_sha=str(identity.get("code_sha")),
            measurement_manifest_uri=str(parents.get("measurement_uri")),
            rating_manifest_uri=str(parents.get("rating_uri")),
            config=str(config_path),
            verify_manifest_uri=uri,
        )
        receipt = verify_replay(args, yaml.safe_load(config_path.read_text()), storage)
    elif schema == "v5_week4_replay_manifest_v1":
        timing = manifest.get("timing") or {}
        args = argparse.Namespace(
            run_id=str(identity.get("run_id")),
            expected_code_sha=str(identity.get("code_sha")),
            measurement_manifest_uri=str(parents.get("measurement_uri")),
            rating_manifest_uri=str(parents.get("rating_replay_uri")),
            schedule_ref_uri=str(
                parents.get("schedule_ref_uri") or parents.get("schedule_uri")
            ),
            as_of=str(timing.get("source_cutoff_as_of")),
            config=str(config_path),
            verify_manifest_uri=uri,
        )
        receipt = verify_week4_replay(
            args, yaml.safe_load(config_path.read_text()), storage
        )
    else:
        raise V5ServingError("unexpected V5 replay manifest schema")
    receipt_uri = f"{uri.rsplit('/', 1)[0]}/verification/verifier-manifest.json"
    receipt_raw = storage.read_bytes(receipt_uri)
    if (
        receipt_raw
        != json.dumps(
            receipt, sort_keys=True, separators=(",", ":"), default=str
        ).encode()
    ):
        raise V5ServingError("stored replay verifier receipt differs")
    predictions_raw = storage.read_bytes(f"{uri.rsplit('/', 1)[0]}/predictions.csv")
    if hashlib.sha256(predictions_raw).hexdigest() != manifest.get(
        "prediction_raw_sha256"
    ):
        raise V5ServingError("V5 replay prediction artifact checksum differs")
    forecasts = pd.read_csv(io.BytesIO(predictions_raw))
    schedule_uri = parents.get("schedule_uri") or parents.get("schedule_ref_uri")
    rating_raw_sha256 = parents.get("rating_replay_raw_sha256") or parents.get(
        "rating_raw_sha256"
    )
    if not schedule_uri or not rating_raw_sha256:
        raise V5ServingError("V5 replay manifest lacks schedule or rating lineage")
    fields = {
        "v5_replay_manifest_uri": uri,
        "v5_replay_manifest_sha256": expected_sha,
        "replay_verification_sha256": hashlib.sha256(receipt_raw).hexdigest(),
        "v5_rating_replay_manifest_sha256": rating_raw_sha256,
        "inference_bundle_sha256": parents["bundle_sha256"],
    }
    return manifest, forecasts, fields, str(schedule_uri)


def run_v5_replay_weekly_bets(args: argparse.Namespace, cfg: Any) -> dict[str, Any]:
    year = int(args.year if args.year is not None else cfg.year)
    week = int(args.week if args.week is not None else cfg.week)
    if year != 2026 or not args.run_id or not args.as_of or args.run_state != "preview":
        raise V5ServingError(
            "V5 replay requires a 2026 week, timestamp, and preview run"
        )
    storage = get_storage(environment=os.getenv("CFB_ARTIFACT_ENV", "preview"))
    manifest, forecasts, fields, schedule_uri = verify_v5_replay_source(
        cfg.v5_replay, storage
    )
    schedule_raw = storage.read_bytes(schedule_uri)
    schedule = pd.read_parquet(io.BytesIO(schedule_raw))
    if {"home_classification", "away_classification"} <= set(schedule):
        schedule = schedule[
            schedule["home_classification"].eq("fbs")
            & schedule["away_classification"].eq("fbs")
        ].copy()
    schedule["start_date"] = schedule["kickoff_utc"]
    rows = build_v5_serving_rows(
        forecasts,
        schedule,
        schedule,
        None,
        forecast_run_id=manifest["identity"]["run_id"],
        forecast_manifest_sha256=fields["v5_replay_manifest_sha256"],
        year=year,
        week=week,
        as_of=args.as_of,
        run_id=args.run_id,
        spread_threshold=float(cfg.spread_edge_threshold),
        spread_threshold_high=float(cfg.spread_edge_threshold_high_conf),
        total_threshold=float(cfg.total_edge_threshold),
        timing_class="replay",
    )
    if args.output_csv:
        args.output_csv.parent.mkdir(parents=True, exist_ok=True)
        rows.to_csv(args.output_csv, index=False)
    if not args.upload_artifact:
        return {"state": "dry_run", "row_count": len(rows), **fields}
    feature_bytes = dataframe_csv_bytes(
        schedule.loc[schedule["season"].eq(year) & schedule["week"].eq(week)]
    )
    feature_uri = prediction_run_features_path(year, week, args.run_id)
    if storage.exists(feature_uri):
        if storage.read_bytes(feature_uri) != feature_bytes:
            raise FileExistsError("V5 replay serving schedule collision")
    else:
        storage.write_bytes(feature_bytes, feature_uri)
    code_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    run_manifest = {
        "state": "preview",
        "evidence_class": "replay",
        "data_as_of": args.as_of,
        "feature_snapshot_uri": feature_uri,
        "feature_snapshot_sha256": hashlib.sha256(feature_bytes).hexdigest(),
        "expected_games": len(rows),
        "predicted_games": len(rows),
        "lined_games": 0,
        "code_sha": code_sha,
        "config_sha": hashlib.sha256(Path(args.config).read_bytes()).hexdigest(),
        "model_bundle_sha256": fields["inference_bundle_sha256"],
        "input_dataset_refs": [],
        "source_config": str(args.config),
        "system_name": str(cfg.system_name),
        "model_id": str(cfg.model_id),
        "validation": {
            "all_predictions_present": True,
            "line_coverage_complete": False,
        },
        **fields,
    }
    return write_prediction_run(
        rows,
        year=year,
        week=week,
        run_id=args.run_id,
        manifest=run_manifest,
        storage=storage,
    )
