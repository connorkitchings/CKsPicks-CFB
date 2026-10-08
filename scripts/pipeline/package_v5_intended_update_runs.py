#!/usr/bin/env python3
"""Package verified successor replay serving artifacts as immutable run artifacts.

Preflight prints exact hashes without writes. Apply is Preview-only and requires
the reviewed packet hash plus a clean committed checkout. Production promotion
remains a separate exact release decision.
"""

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
from dotenv import load_dotenv
from omegaconf import OmegaConf

from cks_picks_cfb.artifacts import (
    prediction_run_artifact_path,
    prediction_run_manifest_path,
    scored_run_artifact_path,
    scored_run_manifest_path,
)
from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ratings_lab.artifacts import canonical_json
from scripts.pipeline.build_v5_intended_update_forecasts import (
    OUTPUT_ROOT as FORECAST_ROOT,
)
from scripts.pipeline.build_v5_intended_update_serving import (
    OUTPUT_ROOT as SERVING_ROOT,
)
from scripts.pipeline.publish_to_db import verify_intended_update_publication_boundary

BRIDGE_URI = (
    "artifacts/research/data-first-football-v1/forecasts/intended-update/"
    "runs/v5-intended-update-2026-v1/bridge-manifest.json"
)
RATING_URI = (
    "artifacts/research/data-first-football-v1/possession-v1/"
    "intended-update-2026/runs/v5-intended-update-2026-ratings-v1/rating-manifest.json"
)
CONFIG = Path("conf/weekly_bets/v5_intended_update_2026.yaml")
DEFAULT_RELEASE_TAG = "20260929-p1"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _signed(storage: Any, uri: str) -> tuple[dict[str, Any], str]:
    raw = storage.read_bytes(uri)
    value = json.loads(raw)
    verify_signed_payload(value, label=uri)
    return value, _sha(raw)


def _write_once(storage: Any, uri: str, raw: bytes) -> None:
    if storage.exists(uri):
        if storage.read_bytes(uri) != raw:
            raise FileExistsError(f"immutable run artifact collision: {uri}")
        return
    storage.write_bytes(raw, uri)


def package_week(
    storage: Any,
    lock: dict[str, Any],
    lock_sha: str,
    week: int,
    *,
    release_tag: str = DEFAULT_RELEASE_TAG,
    bridge_uri: str = BRIDGE_URI,
    rating_uri: str = RATING_URI,
) -> tuple[dict, dict, bytes, bytes]:
    """Build a standard run and scored manifest from the signed research chain."""
    if os.getenv("CFB_ARTIFACT_ENV") != "preview":
        raise ValueError("replay packaging requires the Preview artifact namespace")
    if not 0 <= week < int(lock["active_week"]["week"]):
        raise ValueError("only weeks before the lock's active week have replay serving")
    cfg = OmegaConf.load(CONFIG)
    if cfg.model_id != "v5-intended-update-2026-v1":
        raise ValueError("successor serving config has another model")
    bridge, bridge_sha = _signed(storage, bridge_uri)
    ratings, rating_sha = _signed(storage, rating_uri)
    bridge_verifier, _ = _signed(
        storage, f"{bridge_uri.rsplit('/', 1)[0]}/verification/verifier-manifest.json"
    )
    rating_verifier, _ = _signed(
        storage, f"{rating_uri.rsplit('/', 1)[0]}/verification/verifier-manifest.json"
    )
    run_id = f"2026w{week}-v5repair-{release_tag}"
    forecast_uri = f"{FORECAST_ROOT}/{release_tag}/week={week}/forecast-manifest.json"
    serving_uri = f"{SERVING_ROOT}/{run_id}/serving-manifest.json"
    verifier_uri = f"{SERVING_ROOT}/{run_id}/verification/verifier-manifest.json"
    forecast, forecast_sha = _signed(storage, forecast_uri)
    serving, serving_sha = _signed(storage, serving_uri)
    verifier, verifier_sha = _signed(storage, verifier_uri)
    if (
        bridge.get("state") != "frozen"
        or ratings.get("state") != "frozen"
        or bridge_verifier.get("state") != "verified"
        or bridge_verifier.get("bridge_manifest_raw_sha256") != bridge_sha
        or rating_verifier.get("state") != "verified"
        or rating_verifier.get("rating_manifest_raw_sha256") != rating_sha
        or forecast.get("state") != "frozen"
        or serving.get("state") != "candidate"
        or verifier.get("state") != "verified"
        or serving.get("identity", {}).get("run_id") != run_id
        or serving.get("identity", {}).get("week") != week
        or serving.get("parents", {}).get("source_lock_sha256") != lock_sha
        or serving.get("parents", {}).get("forecast_manifest_raw_sha256")
        != forecast_sha
        or forecast.get("parents", {}).get("rating_manifest_raw_sha256") != rating_sha
        or forecast.get("parents", {}).get("inference_bundle_sha256")
        != bridge["output_refs"]["inference_bundle"]["raw_sha256"]
        or verifier.get("serving_manifest_raw_sha256") != serving_sha
    ):
        raise ValueError(f"Week {week} signed source chain differs")
    predictions_raw = storage.read_bytes(serving["prediction_ref"]["uri"])
    scored_raw = storage.read_bytes(serving["scored_ref"]["uri"])
    if (
        _sha(predictions_raw) != serving["prediction_ref"]["raw_sha256"]
        or _sha(scored_raw) != serving["scored_ref"]["raw_sha256"]
    ):
        raise ValueError(f"Week {week} serving child checksum differs")
    predictions = pd.read_csv(io.BytesIO(predictions_raw))
    scored = pd.read_csv(io.BytesIO(scored_raw))
    if (
        len(predictions) != serving["game_count"]
        or len(scored) != serving["game_count"]
        or set(predictions.game_id) != set(scored.game_id)
    ):
        raise ValueError(f"Week {week} serving row coverage differs")
    market = lock["market_sources"][str(week)]
    if (
        serving["parents"]["market_snapshot_content_sha256"]
        != market["market_snapshots"]["content_sha"]
        or serving["parents"]["market_quote_content_sha256"]
        != market["market_quotes"]["content_sha"]
    ):
        raise ValueError(f"Week {week} market sources differ from the lock")
    quote_ref = {"dataset": "market_quotes", **market["market_quotes"]}
    snapshot_ref = {"dataset": "market_snapshots", **market["market_snapshots"]}
    bundle_sha = bridge["output_refs"]["inference_bundle"]["raw_sha256"]
    artifact_uri = prediction_run_artifact_path(2026, week, run_id)
    scored_uri = scored_run_artifact_path(2026, week, run_id)
    manifest = {
        "schema_version": "prediction_run_v1",
        "run_id": run_id,
        "season": 2026,
        "week": week,
        "state": "preview",
        "evidence_class": "replay",
        "model_id": cfg.model_id,
        "system_name": cfg.system_name,
        "source_config": str(CONFIG),
        "config_sha": _sha(CONFIG.read_bytes()),
        "code_sha": serving["identity"]["code_sha"],
        "data_as_of": serving["data_as_of"],
        "expected_games": len(predictions),
        "predicted_games": len(predictions),
        "lined_games": int(
            predictions[["home_team_spread_line", "total_line"]]
            .notna()
            .all(axis=1)
            .sum()
        ),
        "row_count": len(predictions),
        "artifact_uri": artifact_uri,
        "artifact_sha256": _sha(predictions_raw),
        "model_bundle_sha256": bundle_sha,
        "inference_bundle_sha256": bundle_sha,
        "v5_rating_replay_manifest_sha256": rating_sha,
        "v5_live_forecast_manifest_uri": forecast_uri,
        "v5_live_forecast_manifest_sha256": forecast_sha,
        "v5_intended_update_serving_manifest_uri": serving_uri,
        "v5_intended_update_serving_manifest_sha256": serving_sha,
        "v5_intended_update_verifier_uri": verifier_uri,
        "v5_intended_update_verifier_sha256": verifier_sha,
        "input_dataset_refs": [snapshot_ref, quote_ref],
        "validation": {
            "all_predictions_present": True,
            "line_coverage_complete": bool(
                predictions[["home_team_spread_line", "total_line"]]
                .notna()
                .all(axis=1)
                .all()
            ),
        },
        "production_activation_authorized": False,
    }
    verify_intended_update_publication_boundary(
        manifest=manifest,
        model_id=cfg.model_id,
        season=2026,
        week=week,
        predictions=predictions,
    )
    scored_manifest = {
        "schema_version": "scored_run_v1",
        "run_id": run_id,
        "season": 2026,
        "week": week,
        "artifact_uri": scored_uri,
        "artifact_sha256": _sha(scored_raw),
        "row_count": len(scored),
        "prediction_artifact_sha256": _sha(predictions_raw),
    }
    return manifest, scored_manifest, predictions_raw, scored_raw


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-lock", type=Path, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--release-tag", default=DEFAULT_RELEASE_TAG)
    parser.add_argument("--bridge-uri", default=BRIDGE_URI)
    parser.add_argument("--rating-uri", default=RATING_URI)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-packet-sha")
    parser.add_argument("--expected-code-sha")
    args = parser.parse_args()
    if os.getenv("CFB_STORAGE_BACKEND") != "r2":
        raise SystemExit("packaging requires CFB_STORAGE_BACKEND=r2")
    if os.getenv("CFB_ARTIFACT_ENV") != "preview":
        raise SystemExit("packaging is Preview-only")
    storage = get_storage(environment="preview")
    lock_raw = args.source_lock.read_bytes()
    manifest, scored_manifest, predictions_raw, scored_raw = package_week(
        storage,
        json.loads(lock_raw),
        _sha(lock_raw),
        args.week,
        release_tag=args.release_tag,
        bridge_uri=args.bridge_uri,
        rating_uri=args.rating_uri,
    )
    packet = {"prediction": manifest, "scored": scored_manifest}
    packet_sha = _sha(canonical_json(packet))
    if args.apply:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain=v1"], text=True
        ).strip()
        if dirty or not args.expected_packet_sha or head != args.expected_code_sha:
            raise SystemExit(
                "apply requires a clean committed checkout and reviewed packet SHA"
            )
        if packet_sha != args.expected_packet_sha:
            raise SystemExit("packaging differs from reviewed packet")
        _write_once(storage, manifest["artifact_uri"], predictions_raw)
        _write_once(
            storage,
            prediction_run_manifest_path(2026, args.week, manifest["run_id"]),
            canonical_json(manifest),
        )
        _write_once(storage, scored_manifest["artifact_uri"], scored_raw)
        _write_once(
            storage,
            scored_run_manifest_path(2026, args.week, manifest["run_id"]),
            canonical_json(scored_manifest),
        )
    print(
        json.dumps(
            {
                "run_id": manifest["run_id"],
                "games": manifest["row_count"],
                "packet_sha256": packet_sha,
                "applied": args.apply,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
