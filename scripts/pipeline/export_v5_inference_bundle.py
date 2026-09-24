#!/usr/bin/env python3
"""Export the accepted through-2025 V5 bridge as immutable coefficients."""

from __future__ import annotations

import argparse
import hashlib
import json

import numpy as np
import pandas as pd
from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_live_forecast_v1 import BRIDGE_MANIFEST_URI
from cks_picks_cfb.data.data_first_phase2d import signed_payload, verify_signed_payload
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.forecast.live import (
    FEATURES,
    apply_exported_bridge,
    apply_frozen_bridge,
    export_frozen_bridge,
)
from cks_picks_cfb.forecast.live_sources import _historical_features
from cks_picks_cfb.ratings.possession_live_replay import (
    _AVAILABILITY_HOURS,
    _K,
    FROZEN_CANDIDATE,
    FROZEN_DEFINITION,
)


def prepare_bundle(storage) -> dict:
    raw = storage.read_bytes(BRIDGE_MANIFEST_URI)
    bridge = json.loads(raw)
    verify_signed_payload(bridge, label="accepted 11C bridge")
    recipes = bridge.get("head_recipes") or {}
    by_target = (bridge.get("calibration_summary") or {}).get("by_target") or {}
    variances = {}
    for target in ("margin", "total"):
        values = by_target.get(target) or {}
        value = values.get("2025", values.get(2025))
        if value is None or not pd.notna(float(value)) or float(value) <= 0:
            raise ValueError(f"accepted 11C {target} calibration is missing")
        variances[target] = float(value)
    historical = _historical_features(storage, bridge)
    fitted = export_frozen_bridge(
        historical,
        recipes=recipes,
        calibration_variances=variances,
    )
    sample = (
        historical.replace([np.inf, -np.inf], np.nan)
        .dropna(subset=[*FEATURES, "offset_margin", "offset_total"])
        .copy()
    )
    if len(sample) < 16:
        raise ValueError("accepted 11C fit lacks enough equivalence rows")
    sample["season"] = 2026
    sample["week"] = 0
    sample["game_id"] = range(1, len(sample) + 1)
    refs = {int(value): f"equivalence/{value}" for value in sample["game_id"]}
    inputs = {
        "run_id": "v5-bundle-equivalence",
        "model_ref": "accepted-11c",
        "state_refs": refs,
        "source_ref": BRIDGE_MANIFEST_URI,
    }
    reconstructed = apply_frozen_bridge(
        historical,
        sample,
        recipes=recipes,
        calibration_variances=variances,
        **inputs,
    ).predictions
    exported = apply_exported_bridge(fitted, sample, **inputs).predictions
    columns = ("mean", "variance", "interval_lower_95", "interval_upper_95")
    if len(reconstructed) != len(exported) or len(reconstructed) != 2 * len(sample):
        raise ValueError("exported bridge comparison has incomplete target coverage")
    if not all(
        np.isfinite(reconstructed[column].to_numpy(float)).all()
        and np.isfinite(exported[column].to_numpy(float)).all()
        for column in columns
    ):
        raise ValueError("exported bridge comparison contains nonfinite predictions")
    maximum_difference = max(
        float(np.max(np.abs(reconstructed[column] - exported[column])))
        for column in columns
    )
    if not np.isfinite(maximum_difference) or maximum_difference > 1e-9:
        raise ValueError(
            "exported bridge differs from accepted historical reconstruction"
        )
    return signed_payload(
        {
            **fitted,
            "equivalence": {
                "sample_rows": len(sample),
                "excluded_incomplete_rows": len(historical) - len(sample),
                "maximum_absolute_difference": maximum_difference,
                "columns": list(columns),
            },
            "rating_constants": {
                "candidate_id": FROZEN_CANDIDATE,
                "definition": FROZEN_DEFINITION,
                "exposure_information_divisor": _K,
                "later_week_availability_hours": _AVAILABILITY_HOURS,
            },
            "prior_references": dict(bridge.get("parents") or {}),
            "offset_prerequisites": {
                "development_seasons": list(fitted["development_seasons"]),
                "equivalent_games": 4,
                "requires_regulation_scoring_events": True,
            },
            "bridge_manifest_uri": BRIDGE_MANIFEST_URI,
            "bridge_manifest_raw_sha256": hashlib.sha256(raw).hexdigest(),
            "production_activation_authorized": False,
        }
    )


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    storage = get_storage(environment="preview")
    bundle = prepare_bundle(storage)
    raw = json.dumps(
        bundle, sort_keys=True, separators=(",", ":"), default=str
    ).encode()
    digest = hashlib.sha256(raw).hexdigest()
    uri = f"artifacts/research/data-first-football-v1/forecasts/inference/{digest}/bundle.json"
    if args.apply:
        if storage.exists(uri):
            if storage.read_bytes(uri) != raw:
                raise FileExistsError(
                    "immutable inference bundle identity already exists"
                )
        else:
            storage.write_bytes(raw, uri)
    print(
        json.dumps(
            {
                "bundle_uri": uri,
                "bundle_sha256": digest,
                "applied": args.apply,
                "equivalence": bundle["equivalence"],
                "training_rows": {
                    target: bundle["targets"][target]["training_rows"]
                    for target in ("margin", "total")
                },
            }
        )
    )


if __name__ == "__main__":
    main()
