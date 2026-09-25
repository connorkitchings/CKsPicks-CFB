#!/usr/bin/env python3
"""Read-only validation for an exact V5 production release packet."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from dotenv import load_dotenv

from cks_picks_cfb.artifacts import prediction_run_manifest_path, read_json_artifact
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ops.v5_release import (
    validate_release_record,
    validate_replay_release_record,
)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record-json", type=Path, required=True)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument(
        "--kind",
        choices=("live", "replay"),
        default="live",
        help="Release lane: live 09/05 authorization or replay authorization. "
        "Replay packets bind an already-prepared production candidate artifact.",
    )
    args = parser.parse_args()
    storage = get_storage(environment="production")
    manifest = read_json_artifact(
        prediction_run_manifest_path(args.season, args.week, args.run_id), storage
    )
    if args.kind == "replay" and manifest.get("evidence_class") != "replay":
        parser.error("replay packet requires a replay serving manifest")
    record = json.loads(args.record_json.read_text())
    if hashlib.sha256(args.config.read_bytes()).hexdigest() != record.get(
        "serving_config_sha256"
    ):
        parser.error("release config checksum does not match the reviewed packet")
    if args.kind == "replay":
        validate_replay_release_record(
            record,
            manifest=manifest,
            storage=storage,
            environment="production",
            season=args.season,
            week=args.week,
        )
    else:
        validate_release_record(
            record,
            manifest=manifest,
            storage=storage,
            environment="production",
            season=args.season,
            week=args.week,
        )
    print(json.dumps({"valid": True, "authorization_id": record["authorization_id"]}))


if __name__ == "__main__":
    main()
