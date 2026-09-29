#!/usr/bin/env python3
"""Build a prospective Week 5 successor serving candidate from pinned sources."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from omegaconf import OmegaConf

from cks_picks_cfb.artifacts import dataframe_csv_bytes
from cks_picks_cfb.data.data_first_phase2d import signed_payload, verify_signed_payload
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.inference.v5_serving import build_v5_serving_rows
from cks_picks_cfb.inference.weekly import resolve_label_thresholds
from cks_picks_cfb.ratings_lab.artifacts import canonical_json
from scripts.pipeline.build_v5_intended_update_forecasts import (
    OUTPUT_ROOT as FORECAST_ROOT,
)
from scripts.pipeline.build_v5_intended_update_serving import (
    OUTPUT_ROOT as SERVING_ROOT,
)
from scripts.pipeline.package_v5_intended_update_runs import CONFIG

RUN_ID = "2026w5-v5repair-20260929-p1"
OLD_RUN_URI = "artifacts/production/predictions/year=2026/week=5/run_id=2026w5-5d436e58c072/manifest.json"
FORECAST_URI = f"{FORECAST_ROOT}/20260929-p1/week=5/forecast-manifest.json"
SERVING_URI = f"{SERVING_ROOT}/{RUN_ID}/serving-manifest.json"


def run_uris(release_tag: str) -> tuple[str, str, str]:
    if not re.fullmatch(r"[a-z0-9-]+", release_tag):
        raise ValueError("invalid live release tag")
    run_id = f"2026w5-v5repair-{release_tag}"
    return (
        run_id,
        f"{FORECAST_ROOT}/{release_tag}/week=5/forecast-manifest.json",
        f"{SERVING_ROOT}/{run_id}/serving-manifest.json",
    )


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _frame(storage: Any, ref: dict) -> pd.DataFrame:
    raw = storage.read_bytes(ref["uri"])
    if _sha(raw) != ref["content_sha"]:
        raise ValueError("Week 5 market or schedule parent changed")
    return pd.read_parquet(io.BytesIO(raw))


def build(
    storage: Any,
    lock_raw: bytes,
    *,
    release_tag: str = "20260929-p1",
    market_ref_uri: str | None = None,
    as_of: str | None = None,
) -> tuple[dict, bytes]:
    run_id, forecast_uri, serving_uri = run_uris(release_tag)
    if release_tag != "20260929-p1" and (not market_ref_uri or not as_of):
        raise ValueError("refreshed live run requires fresh market refs and cutoff")
    lock = json.loads(lock_raw)
    if lock["active_week"] != {
        "active_run_id": "2026w5-5d436e58c072",
        "season": 2026,
        "week": 5,
    }:
        raise ValueError("Week 5 live source lock differs")
    forecast_raw = storage.read_bytes(forecast_uri)
    forecast = json.loads(forecast_raw)
    verify_signed_payload(forecast, label="Week 5 intended-update forecast")
    if (
        forecast.get("state") != "candidate"
        or forecast.get("timing_class") != "live"
        or forecast.get("identity", {}).get("run_id") != run_id
    ):
        raise ValueError("Week 5 forecast is not the pinned live candidate")
    forecast_csv = storage.read_bytes(forecast["prediction_ref"]["uri"])
    if _sha(forecast_csv) != forecast["prediction_ref"]["raw_sha256"]:
        raise ValueError("Week 5 forecast child changed")
    old = json.loads(storage.read_bytes(OLD_RUN_URI))
    if old.get("run_id") != lock["active_week"]["active_run_id"]:
        raise ValueError("Week 5 old selected run differs")
    refs = {ref["dataset"]: ref for ref in old["input_dataset_refs"]}
    market_parent = {}
    if market_ref_uri:
        if not as_of:
            raise ValueError("fresh market serving requires an explicit cutoff")
        quote_ref_uri = f"{market_ref_uri.rsplit('/', 1)[0]}/market_quotes_ref.json"
        for dataset, uri in (
            ("market_snapshots", market_ref_uri),
            ("market_quotes", quote_ref_uri),
        ):
            ref_raw = storage.read_bytes(uri)
            ref = json.loads(ref_raw)
            if ref.get("dataset") != dataset:
                raise ValueError("fresh market ref has another dataset")
            refs[dataset] = ref
            market_parent[f"{dataset}_ref_uri"] = uri
            market_parent[f"{dataset}_ref_raw_sha256"] = _sha(ref_raw)
    elif as_of and as_of != old["data_as_of"]:
        raise ValueError("old market cutoff cannot be relabeled")
    cutoff = as_of or old["data_as_of"]
    schedule = _frame(storage, refs["games"])
    markets = _frame(storage, refs["market_snapshots"])
    quotes = _frame(storage, refs["market_quotes"])
    schedule = schedule[
        schedule.home_classification.eq("fbs") & schedule.away_classification.eq("fbs")
    ].copy()
    schedule["start_date"] = schedule["kickoff_utc"]
    cfg = OmegaConf.load(CONFIG)
    thresholds = resolve_label_thresholds(cfg)
    rows = (
        build_v5_serving_rows(
            pd.read_csv(io.BytesIO(forecast_csv)),
            schedule,
            schedule,
            markets,
            forecast_run_id=run_id,
            forecast_manifest_sha256=_sha(forecast_raw),
            year=2026,
            week=5,
            as_of=cutoff,
            run_id=run_id,
            spread_threshold=thresholds[0],
            spread_threshold_high=thresholds[1],
            total_threshold=thresholds[2],
            timing_class="live",
            market_quotes=quotes,
        )
        .sort_values("game_id", kind="mergesort")
        .reset_index(drop=True)
    )
    columns = lock["games"]["columns"]
    expected = {
        int(dict(zip(columns, row, strict=True))["game_id"])
        for row in lock["games"]["rows"]
        if int(dict(zip(columns, row, strict=True))["week"]) == 5
    }
    if len(rows) != 56 or set(rows.game_id.astype(int)) != expected:
        raise ValueError("Week 5 live serving game population differs")
    if rows[["home_team_spread_line", "total_line"]].isna().any().any():
        raise ValueError("Week 5 live serving lacks a complete market")
    raw = dataframe_csv_bytes(rows)
    serving = signed_payload(
        {
            "schema_version": "v5_intended_update_2026_serving_manifest_v1",
            "state": "candidate",
            "evidence_class": "pending",
            "identity": {
                "run_id": run_id,
                "season": 2026,
                "week": 5,
                "code_sha": forecast["identity"]["code_sha"],
            },
            "parents": {
                "source_lock_sha256": _sha(lock_raw),
                "forecast_manifest_raw_sha256": _sha(forecast_raw),
                **market_parent,
                "market_snapshot_content_sha256": refs["market_snapshots"][
                    "content_sha"
                ],
                "market_quote_content_sha256": refs["market_quotes"]["content_sha"],
                "original_selected_run_id": old["run_id"],
            },
            "prediction_ref": {
                "uri": f"{SERVING_ROOT}/{run_id}/predictions.csv",
                "raw_sha256": _sha(raw),
                "rows": len(rows),
            },
            "quote_count": int(
                rows.spread_market_quote_id.notna().sum()
                + rows.total_market_quote_id.notna().sum()
            ),
            "game_count": len(rows),
            "data_as_of": cutoff,
            "production_activation_authorized": False,
        }
    )
    return serving, raw


def _write_once(storage: Any, uri: str, raw: bytes) -> None:
    if storage.exists(uri):
        if storage.read_bytes(uri) != raw:
            raise FileExistsError(f"immutable live serving collision: {uri}")
    else:
        storage.write_bytes(raw, uri)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-lock", type=Path, required=True)
    parser.add_argument("--local-output", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-manifest-sha")
    parser.add_argument("--expected-code-sha")
    parser.add_argument("--release-tag", default="20260929-p1")
    parser.add_argument("--market-ref-uri")
    parser.add_argument("--as-of")
    args = parser.parse_args()
    if (
        os.getenv("CFB_STORAGE_BACKEND") != "r2"
        or os.getenv("CFB_ARTIFACT_ENV") != "preview"
    ):
        raise SystemExit("Week 5 live serving requires Preview R2")
    if args.local_output.resolve().is_relative_to(
        Path(__file__).resolve().parents[2] / "data"
    ):
        raise SystemExit("output cannot be repository ./data")
    lock_raw = args.source_lock.read_bytes()
    storage = get_storage(environment="preview")
    manifest, predictions_raw = build(
        storage,
        lock_raw,
        release_tag=args.release_tag,
        market_ref_uri=args.market_ref_uri,
        as_of=args.as_of,
    )
    manifest_raw = canonical_json(manifest)
    args.local_output.mkdir(parents=True, exist_ok=True)
    (args.local_output / "serving-manifest.json").write_bytes(manifest_raw)
    (args.local_output / "predictions.csv").write_bytes(predictions_raw)
    digest = _sha(manifest_raw)
    if args.apply:
        lock = json.loads(lock_raw)
        columns = lock["games"]["columns"]
        first_kickoff = min(
            pd.to_datetime(dict(zip(columns, row, strict=True))["start_date"], utc=True)
            for row in lock["games"]["rows"]
            if int(dict(zip(columns, row, strict=True))["week"]) == 5
        )
        if pd.Timestamp.now(tz="UTC") >= first_kickoff:
            raise SystemExit("Week 5 prospective serving window has closed")
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain=v1"], text=True
        ).strip()
        if (
            dirty
            or head != args.expected_code_sha
            or digest != args.expected_manifest_sha
        ):
            raise SystemExit(
                "live publication requires reviewed output and clean committed code"
            )
        _write_once(storage, manifest["prediction_ref"]["uri"], predictions_raw)
        _write_once(storage, run_uris(args.release_tag)[2], manifest_raw)
    print(
        json.dumps(
            {
                "run_id": run_uris(args.release_tag)[0],
                "games": manifest["game_count"],
                "manifest_sha256": digest,
                "applied": args.apply,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
