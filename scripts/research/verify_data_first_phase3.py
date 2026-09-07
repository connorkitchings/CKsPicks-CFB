#!/usr/bin/env python3
"""Independently verify a frozen Preview-only Phase 3 artifact set."""

from __future__ import annotations

import argparse
import hashlib
import json

import pandas as pd
from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_phase3 import (
    CORE_CANDIDATES,
    Phase3Error,
    verify_retained_core_manifest,
)
from cks_picks_cfb.data.lake import DatasetRef, read_dataset
from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame
from cks_picks_cfb.data.storage import get_storage


def _ref(value: dict) -> DatasetRef:
    return DatasetRef(
        dataset=str(value["dataset"]),
        version_id=str(value["version_id"]),
        schema_version=str(value["schema_version"]),
        content_sha=str(value["content_sha"]),
        uri=str(value["uri"]),
    )


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-uri", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument(
        "--environment", choices=["preview", "production"], required=True
    )
    args = parser.parse_args(argv)
    if args.environment != "preview":
        raise Phase3Error("Phase 3 verification is Preview-only")

    storage = get_storage(environment="preview")
    raw_manifest = storage.read_bytes(args.manifest_uri)
    manifest = verify_retained_core_manifest(json.loads(raw_manifest))
    identity = manifest["identity"]
    if identity.get("code_sha") != args.expected_code_sha:
        raise Phase3Error("frozen Phase 3 code SHA does not match expectation")
    frames: dict[str, pd.DataFrame] = {}
    for name, value in manifest["output_refs"].items():
        ref = _ref(value)
        frame = read_dataset(storage, ref)
        validate_frame(frame, schema_for(ref.dataset, ref.schema_version))
        frames[name] = frame

    observations = frames["observations"]
    adjusted = frames["adjusted_measurements"]
    predictions = frames["fold_predictions"]
    attribution = frames["attribution_coverage"]
    if any(
        frame["season"].astype(int).eq(2020).any()
        for frame in (observations, adjusted, predictions)
    ):
        raise Phase3Error("frozen Phase 3 outputs contain 2020")
    if set(adjusted["adjustment_iteration"].astype(int)) != {0, 4}:
        raise Phase3Error(
            "frozen Phase 3 outputs do not retain iterations zero and four"
        )
    if set(predictions["candidate"].astype(str)) != set(CORE_CANDIDATES):
        raise Phase3Error("frozen Phase 3 predictions have the wrong candidate set")
    if set(predictions["recency_mode"].astype(str)) != {
        "primary",
        "half_life_4_games",
    }:
        raise Phase3Error("frozen Phase 3 predictions lack the sensitivity run")
    for row in (
        predictions[["season", "training_seasons"]]
        .drop_duplicates()
        .itertuples(index=False)
    ):
        if any(
            int(season) >= int(row.season)
            for season in json.loads(row.training_seasons)
        ):
            raise Phase3Error("frozen Phase 3 fold uses future training data")
    selected_rows = attribution[attribution["selected"].astype(bool)]
    if (
        len(selected_rows) != 1
        or selected_rows.iloc[0]["candidate"] != manifest["selected_candidate"]
    ):
        raise Phase3Error("frozen Phase 3 attribution disagrees with the manifest")
    actual_prediction_sha = hashlib.sha256(
        json.dumps(
            predictions.to_dict("records"),
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode()
    ).hexdigest()
    if actual_prediction_sha != manifest["fold_predictions_sha256"]:
        raise Phase3Error("frozen Phase 3 prediction evidence checksum mismatch")

    run_prefix = args.manifest_uri.rsplit("/", 1)[0]
    certification = json.loads(
        storage.read_bytes(f"{run_prefix}/measurement-certification.json")
    )
    if not certification.get("all_checks_passed"):
        raise Phase3Error("frozen Phase 3 measurement certification did not pass")
    if (
        certification.get("report_sha256")
        != manifest["measurement_certification_sha256"]
    ):
        raise Phase3Error("frozen Phase 3 certification checksum mismatch")
    print(
        json.dumps(
            {
                "status": "verified",
                "manifest_uri": args.manifest_uri,
                "manifest_raw_sha256": hashlib.sha256(raw_manifest).hexdigest(),
                "selected_candidate": manifest["selected_candidate"],
                "output_rows": {name: len(frame) for name, frame in frames.items()},
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
