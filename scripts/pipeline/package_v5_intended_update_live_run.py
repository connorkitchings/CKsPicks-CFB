#!/usr/bin/env python3
"""Package the independently verified Week 5 candidate for Preview publication."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from omegaconf import OmegaConf

from cks_picks_cfb.artifacts import (
    prediction_run_artifact_path,
    prediction_run_manifest_path,
)
from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ratings_lab.artifacts import canonical_json
from scripts.pipeline.build_v5_intended_update_live_serving import (
    OLD_RUN_URI,
    run_uris,
)
from scripts.pipeline.package_v5_intended_update_runs import (
    BRIDGE_URI,
    CONFIG,
    RATING_URI,
    _write_once,
)
from scripts.pipeline.publish_to_db import verify_intended_update_publication_boundary
from scripts.pipeline.verify_v5_intended_update_live_serving import receipt_uri


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def package(
    storage, lock_raw: bytes, *, release_tag: str = "20260929-p1"
) -> tuple[dict, bytes]:
    run_id, forecast_uri, serving_uri = run_uris(release_tag)
    verifier_uri = receipt_uri(release_tag)
    source = json.loads(storage.read_bytes(serving_uri))
    receipt_raw = storage.read_bytes(verifier_uri)
    receipt = json.loads(receipt_raw)
    verify_signed_payload(source, label="Week 5 serving")
    verify_signed_payload(receipt, label="Week 5 serving verifier")
    forecast_raw = storage.read_bytes(forecast_uri)
    forecast = json.loads(forecast_raw)
    verify_signed_payload(forecast, label="Week 5 forecast")
    bridge_raw = storage.read_bytes(BRIDGE_URI)
    rating_raw = storage.read_bytes(RATING_URI)
    bridge = json.loads(bridge_raw)
    ratings = json.loads(rating_raw)
    verify_signed_payload(bridge, label="intended-update bridge")
    verify_signed_payload(ratings, label="intended-update ratings")
    bridge_receipt = json.loads(
        storage.read_bytes(
            f"{BRIDGE_URI.rsplit('/', 1)[0]}/verification/verifier-manifest.json"
        )
    )
    rating_receipt = json.loads(
        storage.read_bytes(
            f"{RATING_URI.rsplit('/', 1)[0]}/verification/verifier-manifest.json"
        )
    )
    verify_signed_payload(bridge_receipt, label="intended-update bridge verifier")
    verify_signed_payload(rating_receipt, label="intended-update rating verifier")
    rating_sha = _sha(rating_raw)
    if (
        source.get("evidence_class") != "pending"
        or source.get("parents", {}).get("source_lock_sha256") != _sha(lock_raw)
        or source.get("parents", {}).get("forecast_manifest_raw_sha256")
        != _sha(forecast_raw)
        or receipt.get("state") != "verified"
        or receipt.get("serving_manifest_raw_sha256")
        != _sha(storage.read_bytes(serving_uri))
        or forecast.get("state") != "candidate"
        or forecast.get("parents", {}).get("rating_manifest_raw_sha256") != rating_sha
        or forecast.get("parents", {}).get("inference_bundle_sha256")
        != bridge["output_refs"]["inference_bundle"]["raw_sha256"]
        or bridge_receipt.get("state") != "verified"
        or bridge_receipt.get("bridge_manifest_raw_sha256") != _sha(bridge_raw)
        or rating_receipt.get("state") != "verified"
        or rating_receipt.get("rating_manifest_raw_sha256") != rating_sha
    ):
        raise ValueError("Week 5 live package source chain differs")
    raw = storage.read_bytes(source["prediction_ref"]["uri"])
    if _sha(raw) != source["prediction_ref"]["raw_sha256"]:
        raise ValueError("Week 5 serving predictions changed")
    rows = pd.read_csv(io.BytesIO(raw))
    if (
        len(rows) != 56
        or rows[["home_team_spread_line", "total_line"]].isna().any().any()
    ):
        raise ValueError("Week 5 live package lacks complete game/line coverage")
    old = json.loads(storage.read_bytes(OLD_RUN_URI))
    if old.get("run_id") != source["parents"]["original_selected_run_id"]:
        raise ValueError("Week 5 market parent differs")
    refs = {ref["dataset"]: ref for ref in old["input_dataset_refs"]}
    for kind in ("market_snapshots", "market_quotes"):
        ref_uri = source["parents"].get(f"{kind}_ref_uri")
        if ref_uri:
            ref_raw = storage.read_bytes(ref_uri)
            if _sha(ref_raw) != source["parents"][f"{kind}_ref_raw_sha256"]:
                raise ValueError("Week 5 market ref differs from verified serving")
            ref = json.loads(ref_raw)
            if ref.get("dataset") != kind:
                raise ValueError("Week 5 market ref has another dataset")
            refs[kind] = ref
    cfg = OmegaConf.load(CONFIG)
    bundle_sha = bridge["output_refs"]["inference_bundle"]["raw_sha256"]
    manifest = {
        "schema_version": "prediction_run_v1",
        "run_id": run_id,
        "season": 2026,
        "week": 5,
        "state": "preview",
        "evidence_class": "pending",
        "model_id": cfg.model_id,
        "system_name": cfg.system_name,
        "source_config": str(CONFIG),
        "config_sha": _sha(CONFIG.read_bytes()),
        "code_sha": source["identity"]["code_sha"],
        "data_as_of": source["data_as_of"],
        "expected_games": 56,
        "predicted_games": 56,
        "lined_games": 56,
        "row_count": 56,
        "artifact_uri": prediction_run_artifact_path(2026, 5, run_id),
        "artifact_sha256": _sha(raw),
        "model_bundle_sha256": bundle_sha,
        "inference_bundle_sha256": bundle_sha,
        "v5_rating_replay_manifest_sha256": rating_sha,
        "v5_live_forecast_manifest_uri": forecast_uri,
        "v5_live_forecast_manifest_sha256": _sha(forecast_raw),
        "v5_intended_update_serving_manifest_uri": serving_uri,
        "v5_intended_update_serving_manifest_sha256": _sha(
            storage.read_bytes(serving_uri)
        ),
        "v5_intended_update_verifier_uri": verifier_uri,
        "v5_intended_update_verifier_sha256": _sha(receipt_raw),
        "input_dataset_refs": list(refs.values()),
        "validation": {"all_predictions_present": True, "line_coverage_complete": True},
        "production_activation_authorized": False,
    }
    verify_intended_update_publication_boundary(
        manifest=manifest, model_id=cfg.model_id, season=2026, week=5, predictions=rows
    )
    return manifest, raw


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-lock", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-packet-sha")
    parser.add_argument("--expected-code-sha")
    parser.add_argument("--release-tag", default="20260929-p1")
    args = parser.parse_args()
    if (
        os.getenv("CFB_STORAGE_BACKEND") != "r2"
        or os.getenv("CFB_ARTIFACT_ENV") != "preview"
    ):
        raise SystemExit("Week 5 packaging requires Preview R2")
    storage = get_storage(environment="preview")
    manifest, raw = package(
        storage, args.source_lock.read_bytes(), release_tag=args.release_tag
    )
    digest = _sha(canonical_json(manifest))
    if args.apply:
        receipt = json.loads(storage.read_bytes(receipt_uri(args.release_tag)))
        if pd.Timestamp.now(tz="UTC") >= pd.Timestamp(receipt["first_kickoff_utc"]):
            raise SystemExit("Week 5 prospective packaging window has closed")
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain=v1"], text=True
        ).strip()
        if (
            dirty
            or head != args.expected_code_sha
            or digest != args.expected_packet_sha
        ):
            raise SystemExit("live packaging requires reviewed clean committed code")
        _write_once(storage, manifest["artifact_uri"], raw)
        _write_once(
            storage,
            prediction_run_manifest_path(2026, 5, run_uris(args.release_tag)[0]),
            canonical_json(manifest),
        )
    print(
        json.dumps(
            {
                "run_id": run_uris(args.release_tag)[0],
                "games": 56,
                "packet_sha256": digest,
                "applied": args.apply,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
