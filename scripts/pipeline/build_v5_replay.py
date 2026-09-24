#!/usr/bin/env python3
"""Preflight, publish, and independently verify 2026 V5 retrospective replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

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
from cks_picks_cfb.forecast.live_verification import (
    verify_bundle_predictions,
    verify_predictions,
)
from cks_picks_cfb.forecast.replay_sources import load_replay_sources

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "conf/research/data_first_football_v1/live_forecast_v1.yaml"
OUTPUT_ROOT = "artifacts/research/data-first-football-v1/forecasts/replay-runs"


class ReplayRunError(ValueError):
    """A retrospective forecast cannot be safely published or verified."""


def _json_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str
    ).encode()


def _write_immutable(storage: Any, uri: str, raw: bytes) -> None:
    if storage.exists(uri):
        if storage.read_bytes(uri) != raw:
            raise ReplayRunError(f"immutable replay object collision: {uri}")
        return
    storage.write_bytes(raw, uri)


def _compute(args: argparse.Namespace, config: dict[str, Any], storage: Any):
    replay, bundle, parents = load_replay_sources(
        storage,
        measurement_uri=args.measurement_manifest_uri,
        rating_uri=args.rating_manifest_uri,
        bundle_uri=config["inference_bundle_uri"],
        bundle_sha256=config["inference_bundle_sha256"],
    )
    inputs = {
        "run_id": args.run_id,
        "model_ref": BRIDGE_MANIFEST_URI,
        "state_refs": replay.state_refs,
        "source_ref": (
            f"measurement:{args.measurement_manifest_uri}"
            f"|rating:{args.rating_manifest_uri}"
        ),
        "timing_class": "replay",
    }
    produced = apply_exported_bridge(bundle, replay.features, **inputs).predictions
    validate_prediction_frame(produced, run_id=args.run_id, timing_class="replay")
    reconstructed = verify_bundle_predictions(bundle, replay.features, **inputs)
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
    if len(produced) != 2 * len(replay.features):
        raise ReplayRunError("replay lacks complete paired targets")
    if len(replay.features) + len(replay.gaps) == 0:
        raise ReplayRunError("replay has no certified games")
    return replay, produced, parents, verification


def _evidence(args: argparse.Namespace, config: dict[str, Any], storage: Any):
    replay, produced, parents, verification = _compute(args, config, storage)
    prediction_raw = dataframe_csv_bytes(produced.loc[:, list(LIVE_FORECAST_COLUMNS)])
    gap_raw = dataframe_csv_bytes(replay.gaps)
    identity = {
        "run_id": args.run_id,
        "season": 2026,
        "code_sha": args.expected_code_sha,
        "config_sha256": hashlib.sha256(Path(args.config).read_bytes()).hexdigest(),
        "environment": "preview",
    }
    evidence = {
        "state": "dry_run",
        "identity": identity,
        "parents": parents,
        "prediction_count": len(produced),
        "game_count": len(replay.features),
        "gap_count": len(replay.gaps),
        "weeks": {
            str(week): int(count)
            for week, count in replay.features.groupby("week").size().items()
        },
        "prediction_raw_sha256": hashlib.sha256(prediction_raw).hexdigest(),
        "prediction_records_sha256": verification["records_sha256"],
        "gap_raw_sha256": hashlib.sha256(gap_raw).hexdigest(),
        "independent_verification": verification,
        "production_activation_authorized": False,
    }
    return evidence, prediction_raw, gap_raw


def verify(args: argparse.Namespace, config: dict[str, Any], storage: Any) -> dict:
    uri = args.verify_manifest_uri
    raw = storage.read_bytes(uri)
    manifest = json.loads(raw)
    verify_signed_payload(manifest, label="V5 replay manifest")
    identity = manifest.get("identity") or {}
    if (
        manifest.get("schema_version") != "v5_replay_manifest_v1"
        or manifest.get("state") != "frozen"
        or manifest.get("evidence_class") != "replay"
        or manifest.get("production_activation_authorized") is not False
        or identity.get("run_id") != args.run_id
        or identity.get("season") != 2026
        or manifest.get("parents", {}).get("bundle_sha256")
        != config["inference_bundle_sha256"]
    ):
        raise ReplayRunError("replay manifest identity or policy differs")
    evidence, prediction_raw, gap_raw = _evidence(args, config, storage)
    for name in (
        "identity",
        "parents",
        "prediction_count",
        "game_count",
        "gap_count",
        "weeks",
        "prediction_raw_sha256",
        "prediction_records_sha256",
        "gap_raw_sha256",
    ):
        if manifest.get(name) != evidence[name]:
            raise ReplayRunError(f"replay {name} differs from reconstruction")
    prefix = uri.rsplit("/", 1)[0]
    if storage.read_bytes(f"{prefix}/predictions.csv") != prediction_raw:
        raise ReplayRunError("stored replay predictions differ")
    if storage.read_bytes(f"{prefix}/gaps.csv") != gap_raw:
        raise ReplayRunError("stored replay gaps differ")
    return signed_payload(
        {
            "schema_version": "v5_replay_verification_v1",
            "state": "verified",
            "replay_manifest_uri": uri,
            "replay_manifest_raw_sha256": hashlib.sha256(raw).hexdigest(),
            "prediction_records_sha256": evidence["prediction_records_sha256"],
            "game_count": evidence["game_count"],
            "gap_count": evidence["gap_count"],
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
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--preflight-evidence", type=Path)
    parser.add_argument("--verify-manifest-uri")
    args = parser.parse_args()
    config = yaml.safe_load(Path(args.config).read_text())
    if not config.get("inference_bundle_uri") or not config.get(
        "inference_bundle_sha256"
    ):
        raise ReplayRunError("V5 replay requires a pinned inference bundle")
    storage = get_storage(environment="preview")
    if args.verify_manifest_uri:
        print(json.dumps(verify(args, config, storage), sort_keys=True))
        return
    evidence, prediction_raw, gap_raw = _evidence(args, config, storage)
    if not args.apply:
        print(json.dumps(evidence, sort_keys=True))
        return
    if not args.preflight_evidence:
        raise ReplayRunError("replay apply requires reviewed preflight evidence")
    reviewed = json.loads(args.preflight_evidence.read_bytes())
    if reviewed != evidence:
        raise ReplayRunError("replay apply differs from reviewed preflight")
    code_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain=v1"], text=True
    ).strip()
    if code_sha != args.expected_code_sha or dirty:
        raise ReplayRunError("replay apply requires the expected clean committed code")
    prefix = f"{OUTPUT_ROOT}/{args.run_id}"
    uri = f"{prefix}/replay-manifest.json"
    if not storage.exists(uri) and storage.list_files(prefix):
        raise ReplayRunError("replay prefix has partial immutable output")
    _write_immutable(storage, f"{prefix}/predictions.csv", prediction_raw)
    _write_immutable(storage, f"{prefix}/gaps.csv", gap_raw)
    manifest = signed_payload(
        {
            "schema_version": "v5_replay_manifest_v1",
            "state": "frozen",
            "evidence_class": "replay",
            **{name: value for name, value in evidence.items() if name != "state"},
            "production_activation_authorized": False,
        }
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
