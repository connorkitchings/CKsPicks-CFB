"""Import pinned 2026 V5 inputs into local, read-only research cache."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_live_forecast_v1 import BRIDGE_MANIFEST_URI
from cks_picks_cfb.data.lake import DatasetRef, read_dataset
from cks_picks_cfb.forecast.live import apply_exported_bridge
from cks_picks_cfb.forecast.live_sources import _read_frame, load_live_forecast_sources
from cks_picks_cfb.forecast.replay_sources import load_replay_sources
from cks_picks_cfb.ratings_lab.artifacts import (
    R2LabStore,
    ReadOnlySource,
    canonical_json,
    sha256,
)

BASE = "artifacts/research/data-first-football-v1/"
MEASUREMENT_URI = (
    BASE
    + "possession-v1/measurements/runs/possession-v1-measurements-20260927-w4/measurement-manifest.json"
)
MEASUREMENT_SHA = "c43f66206973e94b27c6cb23fcc5462aff2fc00b7c1f0eaa1a20fdeaace20a4f"
RATING_URI = (
    BASE
    + "possession-v1/rating-replay/runs/possession-v1-rating-replay-20260927-w4/retained-rating-replay-manifest.json"
)
RATING_SHA = "75e016e1b9876c940cdc98d70aebcc01472b9b1fd160ca6e8e1358d87208cae0"
BUNDLE_URI = (
    BASE
    + "forecasts/inference/f80b63ef01211bc9679b4b65769a3f16c7302c06cfa2b7806f6b8d830f19da0b/bundle.json"
)
BUNDLE_SHA = "f80b63ef01211bc9679b4b65769a3f16c7302c06cfa2b7806f6b8d830f19da0b"
LIVE_URI = (
    BASE + "forecasts/live-runs/forecast-v1-2026w5-live-r2/live-forecast-manifest.json"
)
LIVE_SHA = "799fecfcc933548bd16b914d64d0f9f314616b806979800da7d7a052cfc00a3b"


def _source() -> ReadOnlySource:
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    if os.getenv("CFB_STORAGE_BACKEND") != "r2":
        raise ValueError("2026 source import requires CFB_STORAGE_BACKEND=r2")
    names = ("BUCKET", "ACCOUNT_ID", "ACCESS_KEY", "SECRET_KEY")
    config = {name: os.getenv(f"CFB_R2_PREVIEW_{name}") for name in names}
    if not all(config.values()):
        raise ValueError("Preview read-source configuration is incomplete")
    return ReadOnlySource(
        R2LabStore(
            bucket=config["BUCKET"],
            account=config["ACCOUNT_ID"],
            access=config["ACCESS_KEY"],
            secret=config["SECRET_KEY"],
            endpoint=os.getenv("CFB_R2_PREVIEW_ENDPOINT"),
        )
    )


def _pinned_json(source: ReadOnlySource, uri: str, expected: str) -> dict:
    raw = source.read(uri)
    if sha256(raw) != expected:
        raise ValueError(f"pinned source checksum changed: {uri}")
    return json.loads(raw)


def run(output: Path) -> dict[str, object]:
    forbidden = Path(__file__).resolve().parents[2] / "data"
    if output.resolve() == forbidden or forbidden in output.resolve().parents:
        raise ValueError("source cache cannot be repository ./data")
    source = _source()
    live_manifest = _pinned_json(source, LIVE_URI, LIVE_SHA)
    measurement = _pinned_json(source, MEASUREMENT_URI, MEASUREMENT_SHA)
    rating = _pinned_json(source, RATING_URI, RATING_SHA)
    parents = live_manifest["parents"]
    if (
        parents["measurement_raw_sha256"] != MEASUREMENT_SHA
        or parents["rating_replay_raw_sha256"] != RATING_SHA
    ):
        raise ValueError("Week 5 live run has different certified parents")
    live = load_live_forecast_sources(
        storage=source,
        measurement_uri=MEASUREMENT_URI,
        rating_uri=RATING_URI,
        schedule_uri=parents["schedule_ref_uri"],
        bridge_uri=BRIDGE_MANIFEST_URI,
        as_of=live_manifest["identity"]["as_of"],
        target_week=5,
        include_historical_features=False,
    )
    replay, bundle, replay_parents = load_replay_sources(
        source,
        measurement_uri=MEASUREMENT_URI,
        rating_uri=RATING_URI,
        bundle_uri=BUNDLE_URI,
        bundle_sha256=BUNDLE_SHA,
    )
    if len(replay.gaps):
        raise ValueError("certified 2026 replay has unresolved games")
    frame = {
        "schedule": live["schedule"],
        "population": live["population"],
        "live_features": live["live_features"],
        "replay_features": replay.features,
        "live_measurement_observations": _read_frame(
            source, measurement["output_refs"]["observations"], "observations"
        ),
        "live_rating_priors": _read_frame(
            source, rating["output_refs"]["priors"], "priors"
        ),
    }
    for name, features, refs, timing in (
        ("live", live["live_features"], live["state_refs"], "live"),
        ("replay", replay.features, replay.state_refs, "replay"),
    ):
        frame[f"{name}_control_predictions"] = apply_exported_bridge(
            bundle,
            features,
            run_id="research-control",
            model_ref=BRIDGE_MANIFEST_URI,
            state_refs=refs,
            source_ref="research-control",
            timing_class=timing,
        ).predictions
    output_ref = live_manifest["output_ref"]
    partition = json.loads(source.read(output_ref["uri"]))
    parts = []
    for part in partition["parts"]:
        ref = part.get("ref")
        if ref:
            parts.append(
                read_dataset(
                    source,
                    DatasetRef(
                        **{
                            key: ref[key]
                            for key in (
                                "dataset",
                                "version_id",
                                "schema_version",
                                "content_sha",
                                "uri",
                            )
                        }
                    ),
                )
            )
    frame["live_frozen_predictions"] = pd.concat(parts, ignore_index=True)
    output.mkdir(parents=True, exist_ok=True)
    checksums = {}
    for name, values in frame.items():
        path = output / f"{name}.parquet"
        values.to_parquet(path, index=False, compression="zstd")
        checksums[name] = {"rows": len(values), "sha256": sha256(path.read_bytes())}
    result = {
        "schema_version": "v5_2026_counterfactual_source_import_v1",
        "live_manifest_uri": LIVE_URI,
        "live_manifest_sha256": LIVE_SHA,
        "measurement_manifest_sha256": MEASUREMENT_SHA,
        "rating_manifest_sha256": RATING_SHA,
        "bundle_sha256": BUNDLE_SHA,
        "replay_parents": replay_parents,
        "frames": checksums,
    }
    (output / "source_import.json").write_bytes(canonical_json(result))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.local_output)
    print(json.dumps(result["frames"], indent=2))
