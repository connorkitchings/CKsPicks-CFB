#!/usr/bin/env python3
"""Independently verify a frozen Preview-only Phase 4B artifact set."""

from __future__ import annotations

import argparse
import hashlib
import json

import numpy as np
import pandas as pd
from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_phase2 import FORBIDDEN_SEASONS
from cks_picks_cfb.data.data_first_phase4b import (
    ALL_CONTEXT_CANDIDATES,
    TARGETS,
    Phase4BError,
    verify_retained_baseline_manifest,
)
from cks_picks_cfb.data.lake import DatasetRef, read_dataset
from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ratings.phase4b import validate_tournament_evidence


def _ref(value: dict[str, object]) -> DatasetRef:
    return DatasetRef(
        dataset=str(value["dataset"]),
        version_id=str(value["version_id"]),
        schema_version=str(value["schema_version"]),
        content_sha=str(value["content_sha"]),
        uri=str(value["uri"]),
    )


def _validate_numeric_artifact_evidence(
    predictions: pd.DataFrame, attribution: pd.DataFrame
) -> None:
    """Validate retained tournament evidence independently of the runner."""
    validate_tournament_evidence(predictions, attribution)
    for row in predictions.itertuples(index=False):
        try:
            coefficients = np.asarray(
                json.loads(row.ridge_coefficients), dtype=np.float64
            )
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise Phase4BError(
                "frozen Phase 4B Ridge coefficients are malformed"
            ) from exc
        if not np.isfinite(coefficients).all():
            raise Phase4BError("frozen Phase 4B Ridge coefficients are non-finite")


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
        raise Phase4BError("Phase 4B verification is Preview-only")
    storage = get_storage(environment="preview")
    raw = storage.read_bytes(args.manifest_uri)
    manifest = verify_retained_baseline_manifest(json.loads(raw))
    if manifest["identity"].get("code_sha") != args.expected_code_sha:
        raise Phase4BError("frozen Phase 4B code SHA does not match expectation")
    if manifest.get("production_activation_authorized") is not False:
        raise Phase4BError("frozen Phase 4B result authorizes production")
    frames: dict[str, pd.DataFrame] = {}
    expected = {
        "context_predictions",
        "context_attribution",
        "context_coverage",
    }
    if set(manifest.get("output_refs") or ()) != expected:
        raise Phase4BError("frozen Phase 4B manifest has the wrong output set")
    for name, value in manifest["output_refs"].items():
        ref = _ref(value)
        frame = read_dataset(storage, ref)
        validate_frame(frame, schema_for(ref.dataset, ref.schema_version))
        frames[name] = frame
    predictions, attribution, _coverage = (
        frames["context_predictions"],
        frames["context_attribution"],
        frames["context_coverage"],
    )
    if any(
        frame["season"].astype(int).isin(FORBIDDEN_SEASONS).any()
        for frame in (predictions,)
    ):
        raise Phase4BError("frozen Phase 4B outputs contain 2020")
    if set(predictions["family"].astype(str)) != set(ALL_CONTEXT_CANDIDATES):
        raise Phase4BError(
            "frozen Phase 4B artifacts lack the complete context family set"
        )
    if set(attribution["family"].astype(str)) != set(ALL_CONTEXT_CANDIDATES):
        raise Phase4BError(
            "frozen Phase 4B attribution lacks the complete context family set"
        )
    if set(attribution["target"].astype(str)) != set(TARGETS):
        raise Phase4BError("frozen Phase 4B attribution lacks both targets")
    _validate_numeric_artifact_evidence(predictions, attribution)
    for target in TARGETS:
        target_attribution = attribution[attribution["target"] == target]
        selected = target_attribution[target_attribution["selected"].astype(bool)]
        if len(selected) != 1:
            raise Phase4BError(f"frozen Phase 4B {target} selection is ambiguous")
        selected_family = str(selected.iloc[0]["family"])
        manifest_key = f"{target}_context_selected"
        if selected_family != manifest[manifest_key]:
            raise Phase4BError(
                f"frozen Phase 4B {target} selection disagrees with attribution"
            )
    for row in (
        predictions[["season", "training_seasons"]]
        .drop_duplicates()
        .itertuples(index=False)
    ):
        if any(
            int(value) >= int(row.season) for value in json.loads(row.training_seasons)
        ):
            raise Phase4BError("frozen Phase 4B fold uses future training data")
    print(
        json.dumps(
            {
                "status": "verified",
                "manifest_uri": args.manifest_uri,
                "manifest_raw_sha256": hashlib.sha256(raw).hexdigest(),
                "margin_context_selected": manifest["margin_context_selected"],
                "total_context_selected": manifest["total_context_selected"],
                "output_rows": {name: len(frame) for name, frame in frames.items()},
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
