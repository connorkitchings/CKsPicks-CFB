#!/usr/bin/env python3
"""Build versioned 2026 forecasts from the repaired rating and bridge parents."""

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

from cks_picks_cfb.artifacts import dataframe_csv_bytes
from cks_picks_cfb.data.data_first_live_forecast_v1 import (
    LIVE_FORECAST_COLUMNS,
    validate_prediction_frame,
)
from cks_picks_cfb.data.data_first_phase2d import signed_payload, verify_signed_payload
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.forecast.intended_update_bundle import replace_2026_ratings
from cks_picks_cfb.forecast.live import apply_exported_bridge
from cks_picks_cfb.forecast.live_sources import load_live_forecast_sources
from cks_picks_cfb.forecast.replay_sources import load_replay_sources
from cks_picks_cfb.ratings.possession_intended_update import MODEL_ID
from cks_picks_cfb.ratings_lab.artifacts import canonical_json

OUTPUT_ROOT = (
    "artifacts/research/data-first-football-v1/forecasts/intended-update/2026-runs"
)
SCHEMA_VERSION = "v5_intended_update_2026_forecast_manifest_v1"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _checked_manifest(raw: bytes, *, schema: str) -> dict[str, Any]:
    result = json.loads(raw)
    verify_signed_payload(result, label=schema)
    if result.get("schema_version") != schema or result.get("state") != "frozen":
        raise ValueError(f"unverified or unknown source manifest: {schema}")
    return result


def _checked_verifier(
    storage: Any, manifest_uri: str, digest: str, schema: str, key: str
) -> None:
    uri = f"{manifest_uri.rsplit('/', 1)[0]}/verification/verifier-manifest.json"
    value = json.loads(storage.read_bytes(uri))
    verify_signed_payload(value, label="intended-update source verifier")
    if (
        value.get("schema_version") != schema
        or value.get("state") != "verified"
        or value.get(key) != digest
    ):
        raise ValueError("intended-update source lacks matching independent verifier")


def _sources(
    lock: dict[str, Any],
    *,
    cache: Path | None,
    bridge: Path | str,
    ratings: Path | str,
) -> tuple[
    pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any], str, str
]:
    if cache is not None:
        if not isinstance(bridge, Path) or not isinstance(ratings, Path):
            raise ValueError("local cache requires local bridge and rating outputs")
        bridge_raw = (bridge / "bridge-manifest.json").read_bytes()
        bridge_manifest = _checked_manifest(
            bridge_raw, schema="v5_intended_update_bridge_manifest_v1"
        )
        bundle_raw = (bridge / "bundle.json").read_bytes()
        rating_raw = (ratings / "rating-manifest.json").read_bytes()
        rating_manifest = _checked_manifest(
            rating_raw, schema="v5_intended_update_2026_rating_manifest_v1"
        )
        state_raw = (ratings / "pregame_teams.parquet").read_bytes()
        if (
            _sha(bundle_raw)
            != bridge_manifest["output_refs"]["inference_bundle"]["raw_sha256"]
            or _sha(state_raw)
            != rating_manifest["output_refs"]["pregame_teams"]["raw_sha256"]
        ):
            raise ValueError("local intended-update source child differs from manifest")
        bundle = json.loads(bundle_raw)
        states = pd.read_parquet(io.BytesIO(state_raw))
        schedule = pd.read_parquet(cache / "schedule.parquet")
        replay_features = pd.read_parquet(cache / "replay_features.parquet")
        live_features = pd.read_parquet(cache / "live_features.parquet")
    else:
        if os.getenv("CFB_STORAGE_BACKEND") != "r2":
            raise ValueError("forecast source requires CFB_STORAGE_BACKEND=r2")
        if not isinstance(bridge, str) or not isinstance(ratings, str):
            raise ValueError("R2 source requires bridge and rating manifest URIs")
        storage = get_storage(environment="preview")
        bridge_raw = storage.read_bytes(bridge)
        bridge_manifest = _checked_manifest(
            bridge_raw, schema="v5_intended_update_bridge_manifest_v1"
        )
        rating_raw = storage.read_bytes(ratings)
        rating_manifest = _checked_manifest(
            rating_raw, schema="v5_intended_update_2026_rating_manifest_v1"
        )
        _checked_verifier(
            storage,
            bridge,
            _sha(bridge_raw),
            "v5_intended_update_bridge_verification_v1",
            "bridge_manifest_raw_sha256",
        )
        _checked_verifier(
            storage,
            ratings,
            _sha(rating_raw),
            "v5_intended_update_2026_rating_verification_v1",
            "rating_manifest_raw_sha256",
        )
        bundle_ref = bridge_manifest["output_refs"]["inference_bundle"]
        bundle_raw = storage.read_bytes(bundle_ref["uri"])
        if _sha(bundle_raw) != bundle_ref["raw_sha256"]:
            raise ValueError("successor bundle checksum differs")
        bundle = json.loads(bundle_raw)
        state_ref = rating_manifest["output_refs"]["pregame_teams"]
        state_raw = storage.read_bytes(state_ref["uri"])
        if _sha(state_raw) != state_ref["raw_sha256"]:
            raise ValueError("successor rating state checksum differs")
        states = pd.read_parquet(io.BytesIO(state_raw))
        source = lock["research_source_import"]
        parent = source["replay_parents"]
        replay, _, _ = load_replay_sources(
            storage,
            measurement_uri=parent["measurement_uri"],
            rating_uri=parent["rating_uri"],
            bundle_uri=parent["bundle_uri"],
            bundle_sha256=parent["bundle_sha256"],
        )
        replay_features = replay.features
        live_raw = storage.read_bytes(source["live_manifest_uri"])
        if _sha(live_raw) != source["live_manifest_sha256"]:
            raise ValueError("pinned live source manifest changed")
        live_manifest = json.loads(live_raw)
        live = load_live_forecast_sources(
            storage=storage,
            measurement_uri=parent["measurement_uri"],
            rating_uri=parent["rating_uri"],
            schedule_uri=parent["schedule_uri"],
            bridge_uri=parent["bridge_uri"],
            as_of=live_manifest["identity"]["as_of"],
            target_week=int(lock["active_week"]["week"]),
            include_historical_features=False,
        )
        live_features = live["live_features"]
        schedule = live["schedule"]
    return (
        schedule,
        replay_features,
        live_features,
        states,
        bundle,
        _sha(bridge_raw),
        _sha(rating_raw),
    )


def build(
    *,
    release_tag: str,
    code_sha: str,
    source_lock: Path,
    output: Path,
    bridge: Path | str,
    ratings: Path | str,
    cache: Path | None = None,
) -> dict[str, Any]:
    if not re.fullmatch(r"[a-z0-9-]+", release_tag):
        raise ValueError("invalid successor release tag")
    forbidden = Path(__file__).resolve().parents[2] / "data"
    if output.resolve() == forbidden or forbidden in output.resolve().parents:
        raise ValueError("forecast output cannot use repository ./data")
    lock_raw = source_lock.read_bytes()
    lock = json.loads(lock_raw)
    schedule, replay_features, live_features, states, bundle, bridge_sha, rating_sha = (
        _sources(lock, cache=cache, bridge=bridge, ratings=ratings)
    )
    game_columns = lock["games"]["columns"]
    locked_games = [
        dict(zip(game_columns, row, strict=True)) for row in lock["games"]["rows"]
    ]
    expected = {int(row["game_id"]) for row in locked_games}
    actual = set(replay_features.game_id.astype(int)) | set(
        live_features.game_id.astype(int)
    )
    if actual != expected or set(replay_features.game_id) & set(live_features.game_id):
        raise ValueError("successor forecast game keys differ from locked population")
    if len(states) != 2 * len(expected):
        raise ValueError("successor rating states do not cover every game")
    output.mkdir(parents=True, exist_ok=True)
    manifests = {}
    for timing, base in (("replay", replay_features), ("live", live_features)):
        if base.empty:
            continue
        adjusted = replace_2026_ratings(base, schedule, states)
        for week, features in adjusted.groupby("week", sort=True):
            week = int(week)
            run_id = f"2026w{week}-v5repair-{release_tag}"
            refs = {
                int(game_id): f"rating:{rating_sha}#pregame:{int(game_id)}"
                for game_id in features.game_id
            }
            predictions = apply_exported_bridge(
                bundle,
                features,
                run_id=run_id,
                model_ref=f"bridge:{bridge_sha}",
                state_refs=refs,
                source_ref=f"ratings:{rating_sha}|measurement:{lock['research_2026_measurement_sha256']}",
                timing_class=timing,
            ).predictions
            validate_prediction_frame(predictions, run_id=run_id, timing_class=timing)
            locked_week = {
                int(row["game_id"]) for row in locked_games if int(row["week"]) == week
            }
            if set(predictions.game_id.astype(int)) != locked_week or len(
                predictions
            ) != 2 * len(locked_week):
                raise ValueError(f"successor Week {week} forecast population changed")
            if timing == "live" and week != int(lock["active_week"]["week"]):
                raise ValueError("live successor forecast targets another week")
            evidence_class = "replay" if timing == "replay" else "pending"
            week_output = output / f"week={week}"
            week_output.mkdir(parents=True, exist_ok=True)
            prediction_raw = dataframe_csv_bytes(
                predictions.loc[:, list(LIVE_FORECAST_COLUMNS)]
            )
            (week_output / "predictions.csv").write_bytes(prediction_raw)
            prefix = f"{OUTPUT_ROOT}/{release_tag}/week={week}"
            manifest = signed_payload(
                {
                    "schema_version": SCHEMA_VERSION,
                    "state": "frozen" if timing == "replay" else "candidate",
                    "evidence_class": evidence_class,
                    "identity": {
                        "run_id": run_id,
                        "season": 2026,
                        "week": week,
                        "code_sha": code_sha,
                        "environment": "preview",
                    },
                    "model_id": MODEL_ID,
                    "parents": {
                        "source_lock_sha256": _sha(lock_raw),
                        "bridge_manifest_raw_sha256": bridge_sha,
                        "rating_manifest_raw_sha256": rating_sha,
                        "inference_bundle_sha256": _sha(canonical_json(bundle)),
                        "accepted_measurement_manifest_sha256": lock[
                            "research_2026_measurement_sha256"
                        ],
                    },
                    "prediction_ref": {
                        "uri": f"{prefix}/predictions.csv",
                        "raw_sha256": _sha(prediction_raw),
                        "rows": len(predictions),
                    },
                    "game_count": len(locked_week),
                    "timing_class": timing,
                    "production_activation_authorized": False,
                }
            )
            (week_output / "forecast-manifest.json").write_bytes(
                canonical_json(manifest)
            )
            manifests[str(week)] = manifest
    if sorted(map(int, manifests)) != sorted(set(row["week"] for row in locked_games)):
        raise ValueError("successor forecast is missing a locked week")
    return manifests


def _write_once(storage: Any, uri: str, raw: bytes) -> None:
    if storage.exists(uri):
        if storage.read_bytes(uri) != raw:
            raise ValueError(f"immutable successor forecast collision: {uri}")
        return
    storage.write_bytes(raw, uri)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-tag", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--source-lock", type=Path, required=True)
    parser.add_argument("--local-output", type=Path, required=True)
    parser.add_argument("--local-cache", type=Path)
    parser.add_argument("--bridge-source", required=True)
    parser.add_argument("--rating-source", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--preflight-evidence", type=Path)
    args = parser.parse_args()
    if args.apply and args.local_cache:
        raise ValueError("forecast publication must re-read certified R2 parents")
    bridge = Path(args.bridge_source) if args.local_cache else args.bridge_source
    ratings = Path(args.rating_source) if args.local_cache else args.rating_source
    manifests = build(
        release_tag=args.release_tag,
        code_sha=args.expected_code_sha,
        source_lock=args.source_lock,
        output=args.local_output,
        bridge=bridge,
        ratings=ratings,
        cache=args.local_cache,
    )
    if not args.apply:
        print(json.dumps(manifests, sort_keys=True))
        return
    if (
        not args.preflight_evidence
        or json.loads(args.preflight_evidence.read_bytes()) != manifests
    ):
        raise ValueError("forecast apply differs from reviewed preflight")
    actual_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True
    ).strip()
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain=v1"], text=True
    ).strip()
    if dirty or actual_sha != args.expected_code_sha:
        raise ValueError("forecast publication requires expected clean committed code")
    storage = get_storage(environment="preview")
    for week, manifest in manifests.items():
        directory = args.local_output / f"week={week}"
        _write_once(
            storage,
            manifest["prediction_ref"]["uri"],
            (directory / "predictions.csv").read_bytes(),
        )
        uri = f"{OUTPUT_ROOT}/{args.release_tag}/week={week}/forecast-manifest.json"
        _write_once(storage, uri, (directory / "forecast-manifest.json").read_bytes())
    print(json.dumps({"published_weeks": sorted(manifests)}))


if __name__ == "__main__":
    main()
