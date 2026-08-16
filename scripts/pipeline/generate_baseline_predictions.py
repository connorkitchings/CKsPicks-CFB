#!/usr/bin/env python3
"""Generate strictly temporal Ridge baseline components from structural Gold."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone

from dotenv import load_dotenv

from cks_picks_cfb.data.catalog import (
    catalog_connection_url,
    register_dataset_version,
    register_existing_dataset_ref,
)
from cks_picks_cfb.data.lake import (
    BuildRequest,
    DatasetRef,
    build_dataset_version,
    read_dataset,
)
from cks_picks_cfb.data.runtime import resolve_runtime_target
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.models.baselines import SELECTION_FOLDS, generate_baselines


def _ref(storage, uri: str) -> DatasetRef:
    return DatasetRef(**json.loads(storage.read_bytes(uri).decode()))


def _code_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-ref-uri", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--output-ref-uri", required=True)
    parser.add_argument("--include-locked-2025", action="store_true")
    parser.add_argument("--frozen-design-sha")
    parser.add_argument("--skip-catalog-registration", action="store_true")
    parser.add_argument(
        "--environment",
        choices=["production", "preview"],
        required=True,
    )
    args = parser.parse_args()
    if args.include_locked_2025 and not args.frozen_design_sha:
        raise SystemExit("--include-locked-2025 requires --frozen-design-sha")
    storage = get_storage(environment=args.environment)
    if storage.exists(args.output_ref_uri):
        register_existing_dataset_ref(
            catalog_connection_url(args.environment), storage, args.output_ref_uri
        )
        print(storage.read_bytes(args.output_ref_uri).decode())
        return
    core_ref = _ref(storage, args.core_ref_uri)
    if core_ref.dataset != "point_in_time_matchups_core":
        raise ValueError("Baselines require point_in_time_matchups_core")
    result = generate_baselines(
        read_dataset(storage, core_ref),
        include_locked_2025=args.include_locked_2025,
    )
    cutoff = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    config = {
        "folds": [list(item) for item in SELECTION_FOLDS],
        "locked_2025": args.include_locked_2025,
        "frozen_design_sha": args.frozen_design_sha,
        "model": "ridge_alpha_10",
    }
    ref, manifest = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset="baseline_predictions_oof",
            parent_refs=(core_ref,),
            code_sha=_code_sha(),
            config_sha=hashlib.sha256(
                json.dumps(config, sort_keys=True).encode()
            ).hexdigest(),
            as_of=cutoff,
            schema_version="baseline_predictions_oof_v1",
            tier="gold",
        ),
        records=result.to_dict("records"),
        partitions={"seasons": sorted(result["season"].astype(int).unique().tolist())},
        validation={
            "unique_game_keys": not result.duplicated(["season", "game_id"]).any(),
            "strictly_temporal": bool(
                (result["training_max_year"] < result["season"]).all()
            ),
            "locked_2025_guarded": 2025 not in set(result["season"].astype(int))
            or bool(args.frozen_design_sha),
        },
    )
    if manifest.state != "validated":
        raise RuntimeError(f"Baseline validation failed: {manifest.validation}")
    if not args.skip_catalog_registration:
        conn_url = resolve_runtime_target(args.environment).database_url
        register_dataset_version(conn_url, ref, manifest)
    payload = json.dumps(asdict(ref), indent=2, sort_keys=True).encode()
    if storage.exists(args.output_ref_uri):
        if storage.read_bytes(args.output_ref_uri) != payload:
            raise FileExistsError(
                f"Immutable baseline ref exists: {args.output_ref_uri}"
            )
    else:
        storage.write_bytes(payload, args.output_ref_uri)
    print(json.dumps(asdict(ref), sort_keys=True))


if __name__ == "__main__":
    main()
