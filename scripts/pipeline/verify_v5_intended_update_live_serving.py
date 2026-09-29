#!/usr/bin/env python3
"""Independently verify the prospective successor serving quote and forecast chain."""

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

from cks_picks_cfb.data.data_first_phase2d import signed_payload, verify_signed_payload
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ratings_lab.artifacts import canonical_json
from scripts.pipeline.build_v5_intended_update_live_serving import (
    OLD_RUN_URI,
    run_uris,
)
from scripts.pipeline.publish_to_db import _assert_v5_artifact_matches_forecast
from scripts.pipeline.verify_v5_intended_update_serving import _verify_target


def receipt_uri(release_tag: str) -> str:
    return f"{run_uris(release_tag)[2].rsplit('/', 1)[0]}/verification/verifier-manifest.json"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def verify(
    storage,
    lock_raw: bytes,
    local_output: Path | None = None,
    *,
    release_tag: str = "20260929-p1",
) -> dict:
    run_id, forecast_uri, serving_uri = run_uris(release_tag)
    manifest_raw = (
        (local_output / "serving-manifest.json").read_bytes()
        if local_output
        else storage.read_bytes(serving_uri)
    )
    manifest = json.loads(manifest_raw)
    verify_signed_payload(manifest, label="Week 5 serving")
    if (
        manifest.get("state") != "candidate"
        or manifest.get("evidence_class") != "pending"
        or manifest.get("identity", {}).get("run_id") != run_id
        or manifest.get("parents", {}).get("source_lock_sha256") != _sha(lock_raw)
        or manifest.get("production_activation_authorized") is not False
    ):
        raise ValueError("Week 5 live serving identity differs")
    predictions_raw = (
        (local_output / "predictions.csv").read_bytes()
        if local_output
        else storage.read_bytes(manifest["prediction_ref"]["uri"])
    )
    if _sha(predictions_raw) != manifest["prediction_ref"]["raw_sha256"]:
        raise ValueError("Week 5 serving prediction checksum differs")
    rows = pd.read_csv(io.BytesIO(predictions_raw))
    lock = json.loads(lock_raw)
    cols = lock["games"]["columns"]
    week_games = [
        dict(zip(cols, item, strict=True))
        for item in lock["games"]["rows"]
        if int(dict(zip(cols, item, strict=True))["week"]) == 5
    ]
    expected = {int(item["game_id"]) for item in week_games}
    if len(rows) != 56 or set(rows.game_id.astype(int)) != expected:
        raise ValueError("Week 5 live game population differs")
    first_kickoff = min(
        pd.to_datetime(item["start_date"], utc=True) for item in week_games
    )
    cutoff = pd.Timestamp(manifest["data_as_of"])
    if cutoff.tzinfo is None or cutoff >= first_kickoff:
        raise ValueError("Week 5 source was not frozen before first kickoff")
    old = json.loads(storage.read_bytes(OLD_RUN_URI))
    if manifest["parents"]["original_selected_run_id"] != old["run_id"]:
        raise ValueError("Week 5 market parent differs")
    refs = {ref["dataset"]: ref for ref in old["input_dataset_refs"]}
    for kind in ("market_snapshots", "market_quotes"):
        ref_uri = manifest["parents"].get(f"{kind}_ref_uri")
        if ref_uri:
            ref_raw = storage.read_bytes(ref_uri)
            if _sha(ref_raw) != manifest["parents"][f"{kind}_ref_raw_sha256"]:
                raise ValueError("Week 5 fresh market ref changed")
            ref = json.loads(ref_raw)
            if ref.get("dataset") != kind:
                raise ValueError("Week 5 fresh market ref has another dataset")
            refs[kind] = ref
    if bool(manifest["parents"].get("market_snapshots_ref_uri")) != bool(
        manifest["parents"].get("market_quotes_ref_uri")
    ):
        raise ValueError("Week 5 market refs are incomplete")
    for kind, parent_key in (
        ("market_snapshots", "market_snapshot_content_sha256"),
        ("market_quotes", "market_quote_content_sha256"),
    ):
        if manifest["parents"][parent_key] != refs[kind]["content_sha"]:
            raise ValueError("Week 5 market source checksum differs")
    market_raw = storage.read_bytes(refs["market_snapshots"]["uri"])
    quote_raw = storage.read_bytes(refs["market_quotes"]["uri"])
    if (
        _sha(market_raw) != refs["market_snapshots"]["content_sha"]
        or _sha(quote_raw) != refs["market_quotes"]["content_sha"]
    ):
        raise ValueError("Week 5 market child checksum differs")
    snapshots = pd.read_parquet(io.BytesIO(market_raw)).set_index("game_id")
    quotes = pd.read_parquet(io.BytesIO(quote_raw))
    for captures in (
        pd.to_datetime(snapshots["market_captured_at"], utc=True, errors="coerce"),
        pd.to_datetime(quotes["captured_at"], utc=True, errors="coerce"),
    ):
        if captures.isna().any() or captures.gt(cutoff).any():
            raise ValueError("Week 5 market observation exceeds serving cutoff")
    for _, row in rows.iterrows():
        snapshot = snapshots.loc[int(row.game_id)]
        if (
            row.market_snapshot_id != snapshot.market_snapshot_id
            or abs(float(row.canonical_spread_line) - float(snapshot.spread_line))
            > 1e-9
            or abs(float(row.canonical_total_line) - float(snapshot.total_line)) > 1e-9
        ):
            raise ValueError("Week 5 canonical market snapshot differs")
        for target in ("spread", "total"):
            _verify_target(row, quotes, target=target)
    forecast_raw = storage.read_bytes(forecast_uri)
    forecast = json.loads(forecast_raw)
    verify_signed_payload(forecast, label="Week 5 forecast")
    if (
        forecast.get("state") != "candidate"
        or forecast.get("timing_class") != "live"
        or manifest["parents"]["forecast_manifest_raw_sha256"] != _sha(forecast_raw)
        or forecast.get("identity", {}).get("run_id") != run_id
    ):
        raise ValueError("Week 5 forecast parent differs")
    model_raw = storage.read_bytes(forecast["prediction_ref"]["uri"])
    if _sha(model_raw) != forecast["prediction_ref"]["raw_sha256"]:
        raise ValueError("Week 5 model child differs")
    _assert_v5_artifact_matches_forecast(
        rows, pd.read_csv(io.BytesIO(model_raw)), season=2026, week=5
    )
    if manifest["quote_count"] != 112:
        raise ValueError("Week 5 source lacks full quote coverage")
    return signed_payload(
        {
            "schema_version": "v5_intended_update_2026_serving_verification_v1",
            "state": "verified",
            "season": 2026,
            "week": 5,
            "run_id": run_id,
            "serving_manifest_raw_sha256": _sha(manifest_raw),
            "source_lock_sha256": _sha(lock_raw),
            "game_count": 56,
            "quote_count": 112,
            "first_kickoff_utc": first_kickoff.isoformat(),
            "data_as_of": manifest["data_as_of"],
            "verified": True,
        }
    )


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-lock", type=Path, required=True)
    parser.add_argument("--local-output", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-receipt-sha")
    parser.add_argument("--expected-code-sha")
    parser.add_argument("--release-tag", default="20260929-p1")
    args = parser.parse_args()
    if (
        os.getenv("CFB_STORAGE_BACKEND") != "r2"
        or os.getenv("CFB_ARTIFACT_ENV") != "preview"
    ):
        raise SystemExit("Week 5 verifier requires Preview R2")
    if args.apply and args.local_output:
        raise SystemExit("immutable verifier must re-read Preview R2 serving")
    storage = get_storage(environment="preview")
    receipt = verify(
        storage,
        args.source_lock.read_bytes(),
        args.local_output,
        release_tag=args.release_tag,
    )
    raw = canonical_json(receipt)
    digest = _sha(raw)
    if args.apply:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain=v1"], text=True
        ).strip()
        if (
            dirty
            or head != args.expected_code_sha
            or digest != args.expected_receipt_sha
        ):
            raise SystemExit("live verifier publication requires reviewed clean code")
        uri = receipt_uri(args.release_tag)
        if storage.exists(uri):
            if storage.read_bytes(uri) != raw:
                raise FileExistsError("immutable Week 5 verifier collision")
        else:
            storage.write_bytes(raw, uri)
    print(
        json.dumps(
            {
                "run_id": run_uris(args.release_tag)[0],
                "receipt_sha256": digest,
                "verified": True,
                "applied": args.apply,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
