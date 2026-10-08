#!/usr/bin/env python3
"""Package a verified corrected live week as an immutable run manifest (Preview).

Counterpart of `package_v5_intended_update_live_run.py` for the corrected successor chain.
A display-only run (Contract 04, Amendment 9) is packaged with ``display_only`` in the
manifest and in ``validation`` so the site can say so; its evidence class stays ``pending``
and publication requires the operator's partial-slate override. The packaging window mirrors
the build: a prospective run must still be ahead of its first kickoff, a display-only run
must be recent.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from omegaconf import OmegaConf

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from cks_picks_cfb.artifacts import (  # noqa: E402
    prediction_run_artifact_path,
    prediction_run_manifest_path,
)
from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload  # noqa: E402
from cks_picks_cfb.data.storage import get_storage  # noqa: E402
from cks_picks_cfb.ratings_lab.artifacts import canonical_json  # noqa: E402
from scripts.pipeline.build_v5_corrected_live_serving import (  # noqa: E402
    CONFIG,
    apply_window_open,
    live_week,
    receipt_uri,
    run_uris,
)
from scripts.pipeline.package_v5_intended_update_runs import _write_once  # noqa: E402
from scripts.pipeline.publish_to_db import (  # noqa: E402
    verify_intended_update_publication_boundary,
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _signed(storage: Any, uri: str, label: str) -> tuple[dict[str, Any], bytes]:
    raw = storage.read_bytes(uri)
    value = json.loads(raw)
    verify_signed_payload(value, label=label)
    return value, raw


def package(
    storage: Any,
    lock_raw: bytes,
    *,
    release_tag: str,
    bridge_uri: str,
    rating_uri: str,
) -> tuple[dict[str, Any], bytes]:
    lock = json.loads(lock_raw)
    week = live_week(lock)
    run_id, forecast_uri, serving_uri = run_uris(week, release_tag)
    verifier_uri = receipt_uri(week, release_tag)
    serving, serving_raw = _signed(storage, serving_uri, "corrected live serving")
    receipt, receipt_raw = _signed(storage, verifier_uri, "corrected live verifier")
    forecast, forecast_raw = _signed(storage, forecast_uri, "corrected live forecast")
    bridge, bridge_raw = _signed(storage, bridge_uri, "bridge manifest")
    ratings, rating_raw = _signed(storage, rating_uri, "rating manifest")
    bridge_receipt, _ = _signed(
        storage,
        f"{bridge_uri.rsplit('/', 1)[0]}/verification/verifier-manifest.json",
        "bridge verifier",
    )
    rating_receipt, _ = _signed(
        storage,
        f"{rating_uri.rsplit('/', 1)[0]}/verification/verifier-manifest.json",
        "rating verifier",
    )
    rating_sha = _sha(rating_raw)
    display_only = bool(serving.get("display_only"))
    if (
        serving.get("evidence_class") != "pending"
        or serving.get("parents", {}).get("source_lock_sha256") != _sha(lock_raw)
        or serving.get("parents", {}).get("forecast_manifest_raw_sha256")
        != _sha(forecast_raw)
        or receipt.get("state") != "verified"
        or receipt.get("serving_manifest_raw_sha256") != _sha(serving_raw)
        or bool(receipt.get("display_only")) != display_only
        or forecast.get("state") != "candidate"
        or forecast.get("parents", {}).get("rating_manifest_raw_sha256") != rating_sha
        or forecast.get("parents", {}).get("inference_bundle_sha256")
        != bridge["output_refs"]["inference_bundle"]["raw_sha256"]
        or bridge_receipt.get("state") != "verified"
        or bridge_receipt.get("bridge_manifest_raw_sha256") != _sha(bridge_raw)
        or rating_receipt.get("state") != "verified"
        or rating_receipt.get("rating_manifest_raw_sha256") != rating_sha
        or ratings.get("state") != "frozen"
        or bridge.get("state") != "frozen"
    ):
        raise ValueError("live package source chain differs")
    raw = storage.read_bytes(serving["prediction_ref"]["uri"])
    if _sha(raw) != serving["prediction_ref"]["raw_sha256"]:
        raise ValueError("serving predictions changed")
    rows = pd.read_csv(io.BytesIO(raw))
    if len(rows) != serving["game_count"]:
        raise ValueError("live package row count differs from the serving manifest")
    lined = int(rows[["home_team_spread_line", "total_line"]].notna().all(axis=1).sum())
    if not display_only and lined != len(rows):
        raise ValueError("a non-display live package needs complete line coverage")
    refs = []
    for kind in ("market_snapshots", "market_quotes"):
        ref_raw = storage.read_bytes(serving["parents"][f"{kind}_ref_uri"])
        if _sha(ref_raw) != serving["parents"][f"{kind}_ref_raw_sha256"]:
            raise ValueError("market ref differs from the verified serving")
        refs.append(json.loads(ref_raw))
    cfg = OmegaConf.load(CONFIG)
    bundle_sha = bridge["output_refs"]["inference_bundle"]["raw_sha256"]
    validation = {
        "all_predictions_present": True,
        "line_coverage_complete": lined == len(rows),
    }
    extra: dict[str, Any] = {}
    if display_only:
        validation["display_only"] = True
        validation["omitted_kicked_off_games"] = len(
            serving["omitted_kicked_off_game_ids"]
        )
        extra = {
            "display_only": True,
            "omitted_kicked_off_game_ids": serving["omitted_kicked_off_game_ids"],
        }
    manifest = {
        "schema_version": "prediction_run_v1",
        "run_id": run_id,
        "season": 2026,
        "week": week,
        "state": "preview",
        "evidence_class": "pending",
        "model_id": cfg.model_id,
        "system_name": cfg.system_name,
        "source_config": str(CONFIG.relative_to(REPO_ROOT)),
        "config_sha": _sha(CONFIG.read_bytes()),
        "code_sha": serving["identity"]["code_sha"],
        "data_as_of": serving["data_as_of"],
        "expected_games": len(rows),
        "predicted_games": len(rows),
        "lined_games": lined,
        "row_count": len(rows),
        "artifact_uri": prediction_run_artifact_path(2026, week, run_id),
        "artifact_sha256": _sha(raw),
        "model_bundle_sha256": bundle_sha,
        "inference_bundle_sha256": bundle_sha,
        "v5_rating_replay_manifest_sha256": rating_sha,
        "v5_live_forecast_manifest_uri": forecast_uri,
        "v5_live_forecast_manifest_sha256": _sha(forecast_raw),
        "v5_intended_update_serving_manifest_uri": serving_uri,
        "v5_intended_update_serving_manifest_sha256": _sha(serving_raw),
        "v5_intended_update_verifier_uri": verifier_uri,
        "v5_intended_update_verifier_sha256": _sha(receipt_raw),
        "input_dataset_refs": refs,
        "validation": validation,
        **extra,
        "production_activation_authorized": False,
    }
    verify_intended_update_publication_boundary(
        manifest=manifest,
        model_id=cfg.model_id,
        season=2026,
        week=week,
        predictions=rows,
    )
    return manifest, raw


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-lock", type=Path, required=True)
    parser.add_argument("--release-tag", required=True)
    parser.add_argument("--bridge-uri", required=True)
    parser.add_argument("--rating-uri", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-packet-sha")
    parser.add_argument("--expected-code-sha")
    args = parser.parse_args()
    if (
        os.getenv("CFB_STORAGE_BACKEND") != "r2"
        or os.getenv("CFB_ARTIFACT_ENV") != "preview"
    ):
        raise SystemExit("corrected live packaging requires Preview R2")
    storage = get_storage(environment="preview")
    lock_raw = args.source_lock.read_bytes()
    manifest, raw = package(
        storage,
        lock_raw,
        release_tag=args.release_tag,
        bridge_uri=args.bridge_uri,
        rating_uri=args.rating_uri,
    )
    digest = _sha(canonical_json(manifest))
    if args.apply:
        serving = json.loads(
            storage.read_bytes(manifest["v5_intended_update_serving_manifest_uri"])
        )
        if not apply_window_open(
            serving,
            now=pd.Timestamp.now(tz="UTC"),
            display_only=bool(serving.get("display_only")),
        ):
            raise SystemExit("the packaging window has closed")
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
            prediction_run_manifest_path(2026, manifest["week"], manifest["run_id"]),
            canonical_json(manifest),
        )
    print(
        json.dumps(
            {
                "run_id": manifest["run_id"],
                "games": manifest["row_count"],
                "lined_games": manifest["lined_games"],
                "display_only": bool(manifest.get("display_only")),
                "packet_sha256": digest,
                "applied": args.apply,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
