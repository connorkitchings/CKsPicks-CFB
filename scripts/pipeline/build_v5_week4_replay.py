#!/usr/bin/env python3
"""Build, publish, and independently verify the 2026 Week 4 V5 late replay.

This is a retrospective late-publication artifact: the source cutoff precedes
every Week 4 kickoff, but the artifact itself is created after the slate began.
It is labeled replay end to end, records its actual creation time, and never
counts as prospective evidence. The first live V5 slate still follows the
stabilized Week 4 finals gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from dotenv import load_dotenv

from cks_picks_cfb.artifacts import dataframe_csv_bytes
from cks_picks_cfb.data.data_first_live_forecast_v1 import (
    BRIDGE_MANIFEST_URI,
    LIVE_FORECAST_COLUMNS,
    validate_prediction_frame,
)
from cks_picks_cfb.data.data_first_phase2d import signed_payload, verify_signed_payload
from cks_picks_cfb.data.lake import canonical_frame_digest
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.forecast.live import apply_exported_bridge
from cks_picks_cfb.forecast.live_sources import load_live_forecast_sources
from cks_picks_cfb.forecast.live_verification import (
    verify_bundle_predictions,
    verify_predictions,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "conf/research/data_first_football_v1/live_forecast_v1.yaml"
OUTPUT_ROOT = "artifacts/research/data-first-football-v1/forecasts/replay-runs"
MANIFEST_NAME = "week4-replay-manifest.json"
TARGET_WEEK = 4
PRIOR_WEEKS = (0, 1, 2, 3)


class Week4ReplayError(ValueError):
    """A late Week 4 replay cannot be safely built, published, or verified."""


def _json_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str
    ).encode()


def _write_immutable(storage: Any, uri: str, raw: bytes) -> None:
    if storage.exists(uri):
        if storage.read_bytes(uri) != raw:
            raise Week4ReplayError(f"immutable replay object collision: {uri}")
        return
    storage.write_bytes(raw, uri)


def _utc_timestamp(value: str, label: str) -> pd.Timestamp:
    parsed = pd.Timestamp(value)
    if parsed.tzinfo is None:
        raise Week4ReplayError(f"{label} must be timezone-aware")
    return parsed.tz_convert("UTC")


def _compute(args: argparse.Namespace, config: dict[str, Any], storage: Any):
    bundle_uri = str(config.get("inference_bundle_uri") or "")
    bundle_sha = str(config.get("inference_bundle_sha256") or "")
    if not bundle_uri or len(bundle_sha) != 64:
        raise Week4ReplayError("Week 4 replay requires a pinned inference bundle")
    cutoff = _utc_timestamp(args.as_of, "--as-of source cutoff")
    sources = load_live_forecast_sources(
        storage=storage,
        measurement_uri=args.measurement_manifest_uri,
        rating_uri=args.rating_manifest_uri,
        schedule_uri=args.schedule_ref_uri,
        bridge_uri=BRIDGE_MANIFEST_URI,
        as_of=args.as_of,
        target_week=TARGET_WEEK,
        include_historical_features=False,
    )
    features = sources["live_features"]
    population = sources["population"]
    schedule = sources["schedule"]
    week4_schedule = schedule[
        schedule["season"].eq(2026) & schedule["week"].eq(TARGET_WEEK)
    ]
    week4_features = features[features["season"].eq(2026)]
    if not week4_features["week"].eq(TARGET_WEEK).all() or week4_features.empty:
        raise Week4ReplayError("Week 4 replay features target another slate")
    expected_games = set(week4_schedule["game_id"].astype(int))
    observed_games = set(week4_features["game_id"].astype(int))
    if observed_games != expected_games:
        missing = sorted(expected_games - observed_games)
        raise Week4ReplayError(
            "week4_slate_incomplete: every scheduled game needs a paired "
            f"prediction; missing {len(missing)} games"
        )
    kickoffs = pd.to_datetime(week4_schedule["kickoff_utc"], utc=True)
    first_kickoff = kickoffs.min()
    last_kickoff = kickoffs.max()
    if cutoff >= first_kickoff:
        raise Week4ReplayError(
            "week4_cutoff_not_pre_kickoff: source cutoff must precede every "
            "Week 4 kickoff"
        )
    measurement_as_of = str(
        (sources["measurement"].get("identity") or {}).get("as_of", "")
    )
    measured_at = _utc_timestamp(measurement_as_of, "measurement as_of")
    if cutoff < measured_at:
        raise Week4ReplayError(
            "source cutoff predates the certified measurement parents"
        )
    prior_weeks = set(population["week"].astype(int))
    if not prior_weeks <= set(PRIOR_WEEKS):
        raise Week4ReplayError(
            "week4_input_leakage: population contains post-Week-3 evidence"
        )
    inputs = {
        "run_id": args.run_id,
        "model_ref": BRIDGE_MANIFEST_URI,
        "state_refs": sources["state_refs"],
        "source_ref": (
            f"measurement:{args.measurement_manifest_uri}"
            f"|rating:{args.rating_manifest_uri}"
            f"|schedule:{args.schedule_ref_uri}"
        ),
        "timing_class": "replay",
    }
    raw_bundle = storage.read_bytes(bundle_uri)
    if hashlib.sha256(raw_bundle).hexdigest() != bundle_sha:
        raise Week4ReplayError("pinned V5 inference bundle checksum differs")
    bundle = json.loads(raw_bundle)
    verify_signed_payload(bundle, label="V5 inference bundle")
    if (
        bundle.get("bridge_manifest_uri") != BRIDGE_MANIFEST_URI
        or bundle.get("bridge_manifest_raw_sha256")
        != sources["parents"]["bridge_raw_sha256"]
    ):
        raise Week4ReplayError("inference bundle has another accepted bridge")
    produced = apply_exported_bridge(bundle, features, **inputs).predictions
    validate_prediction_frame(produced, run_id=args.run_id, timing_class="replay")
    reconstructed = verify_bundle_predictions(bundle, features, **inputs)
    prediction_sha = canonical_frame_digest(produced, columns=LIVE_FORECAST_COLUMNS)
    verification = verify_predictions(
        manifest={
            "identity": {"run_id": args.run_id},
            "row_count": len(produced),
            "prediction_records_sha256": prediction_sha,
        },
        stored=produced,
        reconstructed=reconstructed,
        timing_class="replay",
    )
    if len(produced) != 2 * len(week4_features):
        raise Week4ReplayError("week4 replay lacks complete paired targets")
    parents = {
        **sources["parents"],
        "bundle_uri": bundle_uri,
        "bundle_sha256": bundle_sha,
    }
    timing = {
        "source_cutoff_as_of": cutoff.isoformat(),
        "first_kickoff_utc": first_kickoff.isoformat(),
        "last_kickoff_utc": last_kickoff.isoformat(),
        "measurement_as_of": measurement_as_of,
        "late_publication": True,
    }
    return (
        sources,
        week4_features,
        produced,
        parents,
        timing,
        verification,
    )


def _manifest(evidence: dict[str, Any], created_at_utc: str) -> dict[str, Any]:
    """Freeze reviewed evidence without letting its dry-run state leak through."""
    return signed_payload(
        {
            "schema_version": "v5_week4_replay_manifest_v1",
            "state": "frozen",
            "created_at_utc": created_at_utc,
            **{name: value for name, value in evidence.items() if name != "state"},
            "production_activation_authorized": False,
        }
    )


def _evidence(args: argparse.Namespace, config: dict[str, Any], storage: Any):
    sources, features, produced, parents, timing, verification = _compute(
        args, config, storage
    )
    prediction_raw = dataframe_csv_bytes(produced.loc[:, list(LIVE_FORECAST_COLUMNS)])
    identity = {
        "run_id": args.run_id,
        "season": 2026,
        "target_week": TARGET_WEEK,
        "code_sha": args.expected_code_sha,
        "config_sha256": hashlib.sha256(Path(args.config).read_bytes()).hexdigest(),
        "environment": "preview",
    }
    evidence = {
        "state": "dry_run",
        "identity": identity,
        "parents": parents,
        "timing": timing,
        "evidence_class": "replay",
        "game_count": len(features),
        "prediction_count": len(produced),
        "game_ids_sha256": hashlib.sha256(
            ",".join(map(str, sorted(features["game_id"].astype(int)))).encode()
        ).hexdigest(),
        "prediction_raw_sha256": hashlib.sha256(prediction_raw).hexdigest(),
        "prediction_records_sha256": verification["records_sha256"],
        "independent_verification": verification,
        "production_activation_authorized": False,
    }
    return evidence, prediction_raw


def verify(args: argparse.Namespace, config: dict[str, Any], storage: Any) -> dict:
    uri = args.verify_manifest_uri
    raw = storage.read_bytes(uri)
    manifest = json.loads(raw)
    verify_signed_payload(manifest, label="V5 Week 4 replay manifest")
    identity = manifest.get("identity") or {}
    if (
        manifest.get("schema_version") != "v5_week4_replay_manifest_v1"
        or manifest.get("state") != "frozen"
        or manifest.get("evidence_class") != "replay"
        or manifest.get("production_activation_authorized") is not False
        or identity.get("run_id") != args.run_id
        or identity.get("season") != 2026
        or identity.get("target_week") != TARGET_WEEK
        or manifest.get("parents", {}).get("bundle_sha256")
        != config["inference_bundle_sha256"]
        or (manifest.get("timing") or {}).get("late_publication") is not True
    ):
        raise Week4ReplayError("Week 4 replay identity or policy differs")
    created_at = _utc_timestamp(
        str(manifest.get("created_at_utc") or ""), "created_at_utc"
    )
    cutoff = _utc_timestamp(
        str(manifest.get("timing", {}).get("source_cutoff_as_of") or ""),
        "source_cutoff_as_of",
    )
    if created_at <= cutoff:
        raise Week4ReplayError(
            "late publication requires an actual creation time after the cutoff"
        )
    evidence, prediction_raw = _evidence(args, config, storage)
    for name in (
        "identity",
        "parents",
        "timing",
        "evidence_class",
        "game_count",
        "prediction_count",
        "game_ids_sha256",
        "prediction_raw_sha256",
        "prediction_records_sha256",
    ):
        if manifest.get(name) != evidence[name]:
            raise Week4ReplayError(f"Week 4 replay {name} differs from reconstruction")
    prefix = uri.rsplit("/", 1)[0]
    if storage.read_bytes(f"{prefix}/predictions.csv") != prediction_raw:
        raise Week4ReplayError("stored Week 4 replay predictions differ")
    return signed_payload(
        {
            "schema_version": "v5_week4_replay_verification_v1",
            "state": "verified",
            "replay_manifest_uri": uri,
            "replay_manifest_raw_sha256": hashlib.sha256(raw).hexdigest(),
            "prediction_records_sha256": evidence["prediction_records_sha256"],
            "game_count": evidence["game_count"],
            "prediction_count": evidence["prediction_count"],
            "late_publication": True,
            "evidence_class": "replay",
            "production_activation_authorized": False,
        }
    )


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--measurement-manifest-uri", required=True)
    parser.add_argument("--rating-manifest-uri", required=True)
    parser.add_argument("--schedule-ref-uri", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--preflight-evidence", type=Path)
    parser.add_argument("--verify-manifest-uri")
    args = parser.parse_args()
    config = yaml.safe_load(Path(args.config).read_text())
    storage = get_storage(environment="preview")
    if args.verify_manifest_uri:
        print(json.dumps(verify(args, config, storage), sort_keys=True))
        return
    evidence, prediction_raw = _evidence(args, config, storage)
    if not args.apply:
        print(json.dumps(evidence, sort_keys=True))
        return
    if not args.preflight_evidence:
        raise Week4ReplayError("replay apply requires reviewed preflight evidence")
    reviewed = json.loads(args.preflight_evidence.read_bytes())
    if reviewed != evidence:
        raise Week4ReplayError("replay apply differs from reviewed preflight")
    code_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain=v1"], text=True
    ).strip()
    if code_sha != args.expected_code_sha or dirty:
        raise Week4ReplayError(
            "replay apply requires the expected clean committed code"
        )
    prefix = f"{OUTPUT_ROOT}/{args.run_id}"
    uri = f"{prefix}/{MANIFEST_NAME}"
    if not storage.exists(uri) and storage.list_files(prefix):
        raise Week4ReplayError("replay prefix has partial immutable output")
    _write_immutable(storage, f"{prefix}/predictions.csv", prediction_raw)
    manifest = _manifest(
        evidence,
        datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )
    _write_immutable(storage, uri, _json_bytes(manifest))
    args.verify_manifest_uri = uri
    receipt = verify(args, config, storage)
    receipt_uri = f"{prefix}/verification/verifier-manifest.json"
    _write_immutable(storage, receipt_uri, _json_bytes(receipt))
    print(
        json.dumps(
            {
                "manifest_uri": uri,
                "verification_uri": receipt_uri,
                "verification_sha256": hashlib.sha256(_json_bytes(receipt)).hexdigest(),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
