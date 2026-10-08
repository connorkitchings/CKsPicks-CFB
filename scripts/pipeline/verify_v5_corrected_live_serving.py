#!/usr/bin/env python3
"""Independently verify a corrected live week's serving rows (pending candidate; Preview).

Re-derives, from the pinned market objects and the schedule, the partition of the week into
games ahead of and behind the cutoff, every snapshot identity, every best-quote-v2 selection,
edge, bet label and spread confidence, and the match to the verified forecast. A display-only
run must have been built at a cutoff before which no included game kicked off and after which
every omitted game had.
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
import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from cks_picks_cfb.data.data_first_phase2d import (  # noqa: E402
    signed_payload,
    verify_signed_payload,
)
from cks_picks_cfb.data.storage import get_storage  # noqa: E402
from cks_picks_cfb.ratings_lab.artifacts import canonical_json  # noqa: E402
from cks_picks_cfb.rebuild.live_week import kicked_off_game_ids  # noqa: E402
from cks_picks_cfb.rebuild.successor_sources import lock_schedule  # noqa: E402
from scripts.pipeline.build_v5_corrected_live_serving import (  # noqa: E402
    CONFIG,
    live_week,
    receipt_uri,
    run_uris,
)
from scripts.pipeline.publish_to_db import (  # noqa: E402
    _assert_v5_artifact_matches_forecast,
)
from scripts.pipeline.verify_v5_intended_update_serving import (  # noqa: E402
    _verify_target,
    expected_snapshot_id,
    label_thresholds,
)

SCHEMA = "v5_intended_update_2026_serving_verification_v1"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _checked(storage: Any, uri: str, expected_sha: str, label: str) -> bytes:
    raw = storage.read_bytes(uri)
    if _sha(raw) != expected_sha:
        raise ValueError(f"{label} changed")
    return raw


def verify(
    storage: Any,
    lock_raw: bytes,
    *,
    release_tag: str,
    local_output: Path | None = None,
) -> dict[str, Any]:
    lock = json.loads(lock_raw)
    week = live_week(lock)
    run_id, forecast_uri, serving_uri = run_uris(week, release_tag)
    manifest_raw = (
        (local_output / "serving-manifest.json").read_bytes()
        if local_output
        else storage.read_bytes(serving_uri)
    )
    manifest = json.loads(manifest_raw)
    verify_signed_payload(manifest, label="corrected live serving")
    if (
        manifest.get("schema_version") != "v5_intended_update_2026_serving_manifest_v1"
        or manifest.get("state") != "candidate"
        or manifest.get("evidence_class") != "pending"
        or manifest.get("identity", {}).get("run_id") != run_id
        or manifest.get("identity", {}).get("week") != week
        or manifest.get("parents", {}).get("source_lock_sha256") != _sha(lock_raw)
        or manifest.get("production_activation_authorized") is not False
    ):
        raise ValueError("live serving identity differs")
    display_only = bool(manifest.get("display_only"))
    predictions_raw = (
        (local_output / "predictions.csv").read_bytes()
        if local_output
        else storage.read_bytes(manifest["prediction_ref"]["uri"])
    )
    if _sha(predictions_raw) != manifest["prediction_ref"]["raw_sha256"]:
        raise ValueError("serving prediction checksum differs")
    rows = pd.read_csv(io.BytesIO(predictions_raw))

    cutoff = pd.Timestamp(manifest["data_as_of"])
    if cutoff.tzinfo is None or cutoff > pd.Timestamp.now(tz="UTC"):
        raise ValueError("the serving cutoff is not a past, timezone-aware time")
    schedule = lock_schedule(storage, lock, canonical=False)
    schedule = schedule[
        schedule["home_classification"].eq("fbs")
        & schedule["away_classification"].eq("fbs")
    ].copy()
    week_games = schedule[schedule["week"].astype(int).eq(week)]
    kicked = kicked_off_game_ids(schedule, week, str(cutoff.isoformat()))
    if kicked and not display_only:
        raise ValueError(
            "games had kicked off at the cutoff but the run is not display-only"
        )
    if sorted(manifest.get("omitted_kicked_off_game_ids", [])) != kicked:
        raise ValueError("the omitted games are not exactly those that had kicked off")
    expected = set(week_games["game_id"].astype(int)) - set(kicked)
    if len(rows) != len(expected) or set(rows["game_id"].astype(int)) != expected:
        raise ValueError("live game population differs")
    if manifest["game_count"] != len(expected):
        raise ValueError("manifest game count differs")
    included = week_games[week_games["game_id"].astype(int).isin(expected)]
    first = min(pd.to_datetime(included["kickoff_utc"], utc=True))
    if first <= cutoff or pd.Timestamp(manifest["first_included_kickoff_utc"]) != first:
        raise ValueError("an included game kicks off at or before the cutoff")

    forecast_raw = storage.read_bytes(forecast_uri)
    forecast = json.loads(forecast_raw)
    verify_signed_payload(forecast, label="corrected live forecast")
    if (
        forecast.get("state") != "candidate"
        or forecast.get("timing_class") != "live"
        or forecast.get("evidence_class") != "pending"
        or forecast.get("identity", {}).get("run_id") != run_id
        or forecast.get("parents", {}).get("source_lock_sha256") != _sha(lock_raw)
        or manifest["parents"]["forecast_manifest_raw_sha256"] != _sha(forecast_raw)
    ):
        raise ValueError("forecast parent differs")
    if display_only:
        live = forecast.get("live") or {}
        if (
            not live.get("display_only")
            or pd.Timestamp(live["as_of"]) != cutoff
            or sorted(live.get("omitted_kicked_off_game_ids", [])) != kicked
        ):
            raise ValueError("forecast was not built for this display-only cutoff")
    model_raw = _checked(
        storage,
        forecast["prediction_ref"]["uri"],
        forecast["prediction_ref"]["raw_sha256"],
        "forecast child",
    )
    _assert_v5_artifact_matches_forecast(
        rows, pd.read_csv(io.BytesIO(model_raw)), season=2026, week=week
    )

    frames = {}
    for kind, content_key in (
        ("market_snapshots", "market_snapshot_content_sha256"),
        ("market_quotes", "market_quote_content_sha256"),
    ):
        ref_raw = _checked(
            storage,
            manifest["parents"][f"{kind}_ref_uri"],
            manifest["parents"][f"{kind}_ref_raw_sha256"],
            f"{kind} ref",
        )
        ref = json.loads(ref_raw)
        if (
            ref.get("dataset") != kind
            or ref["content_sha"] != manifest["parents"][content_key]
        ):
            raise ValueError(f"{kind} ref differs from the serving manifest")
        frames[kind] = pd.read_parquet(
            io.BytesIO(_checked(storage, ref["uri"], ref["content_sha"], kind))
        )
    snapshots = frames["market_snapshots"]
    quotes = frames["market_quotes"]
    snapshots = snapshots[snapshots["game_id"].isin(expected)].set_index("game_id")
    if pd.to_datetime(snapshots["market_captured_at"], utc=True).gt(cutoff).any():
        raise ValueError("a market snapshot was captured after the cutoff")

    config_raw = CONFIG.read_bytes()
    thresholds = label_thresholds(yaml.safe_load(config_raw))
    lined = 0
    names = week_games.set_index(week_games["game_id"].astype(int))
    for _, item in rows.iterrows():
        game_id = int(item["game_id"])
        scheduled = names.loc[game_id]
        if str(item["home_team"]) != str(scheduled["home_team"]) or str(
            item["away_team"]
        ) != str(scheduled["away_team"]):
            raise ValueError("serving team names differ from the provider schedule")
        if game_id not in snapshots.index:
            if pd.notna(item["canonical_spread_line"]) or pd.notna(
                item["spread_market_quote_id"]
            ):
                raise ValueError("a row has market data but no snapshot")
            continue
        snap = snapshots.loc[game_id]
        if (
            item["market_snapshot_id"] != expected_snapshot_id(snap, game_id)
            or str(item["source_quote_ids"]) != str(snap["source_quote_ids"])
            or abs(float(item["canonical_spread_line"]) - float(snap["spread_line"]))
            > 1e-9
            or (pd.isna(snap["total_line"]) != pd.isna(item["canonical_total_line"]))
            or (
                pd.notna(snap["total_line"])
                and abs(float(item["canonical_total_line"]) - float(snap["total_line"]))
                > 1e-9
            )
        ):
            raise ValueError("serving canonical snapshot differs")
        for target in ("spread", "total"):
            _verify_target(
                item,
                quotes,
                target=target,
                bet_threshold=thresholds[f"{target}_bet"],
                high_threshold=thresholds["spread_high"],
                cutoff=cutoff,
            )
        lined += int(
            pd.notna(item["home_team_spread_line"]) and pd.notna(item["total_line"])
        )
    unlined = sorted(
        int(g)
        for g in rows.loc[
            rows[["home_team_spread_line", "total_line"]].isna().any(axis=1), "game_id"
        ]
    )
    if unlined != sorted(manifest.get("unlined_game_ids", [])):
        raise ValueError("the unlined games differ from the manifest")
    if unlined and not display_only:
        raise ValueError("a non-display run must have a complete market")
    quote_count = int(
        rows["spread_market_quote_id"].notna().sum()
        + rows["total_market_quote_id"].notna().sum()
    )
    if quote_count != manifest["quote_count"]:
        raise ValueError("quote count differs")
    return signed_payload(
        {
            "schema_version": SCHEMA,
            "state": "verified",
            "season": 2026,
            "week": week,
            "run_id": run_id,
            "serving_manifest_raw_sha256": _sha(manifest_raw),
            "source_lock_sha256": _sha(lock_raw),
            "game_count": len(rows),
            "quote_count": quote_count,
            "lined_games": lined,
            "display_only": display_only,
            "omitted_kicked_off_games": len(kicked),
            "first_included_kickoff_utc": first.isoformat(),
            "data_as_of": cutoff.isoformat(),
            "config_sha256": _sha(config_raw),
            "verified": True,
        }
    )


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-lock", type=Path, required=True)
    parser.add_argument("--release-tag", required=True)
    parser.add_argument("--local-output", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-receipt-sha")
    parser.add_argument("--expected-code-sha")
    args = parser.parse_args()
    if (
        os.getenv("CFB_STORAGE_BACKEND") != "r2"
        or os.getenv("CFB_ARTIFACT_ENV") != "preview"
    ):
        raise SystemExit("the verifier requires Preview R2")
    if args.apply and args.local_output:
        raise SystemExit("the immutable verifier must re-read Preview R2 serving")
    storage = get_storage(environment="preview")
    lock_raw = args.source_lock.read_bytes()
    receipt = verify(
        storage, lock_raw, release_tag=args.release_tag, local_output=args.local_output
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
            raise SystemExit("verifier publication requires reviewed clean code")
        uri = receipt_uri(receipt["week"], args.release_tag)
        if storage.exists(uri):
            if storage.read_bytes(uri) != raw:
                raise FileExistsError("immutable verifier collision")
        else:
            storage.write_bytes(raw, uri)
    print(
        json.dumps(
            {
                "run_id": receipt["run_id"],
                "receipt_sha256": digest,
                "verified": True,
                "display_only": receipt["display_only"],
                "games": receipt["game_count"],
                "applied": args.apply,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
