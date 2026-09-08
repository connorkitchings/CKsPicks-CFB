#!/usr/bin/env python3
"""Independently verify a frozen Preview-only Phase 4A artifact set."""

from __future__ import annotations

import argparse
import hashlib
import json

import numpy as np
import pandas as pd
from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_phase2 import FORBIDDEN_SEASONS
from cks_picks_cfb.data.data_first_phase4a import (
    RATING_CANDIDATES,
    Phase4AError,
    verify_retained_rating_manifest,
)
from cks_picks_cfb.data.lake import DatasetRef, read_dataset
from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame
from cks_picks_cfb.data.storage import get_storage


def _ref(value: dict[str, object]) -> DatasetRef:
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
        raise Phase4AError("Phase 4A verification is Preview-only")
    storage = get_storage(environment="preview")
    raw = storage.read_bytes(args.manifest_uri)
    manifest = verify_retained_rating_manifest(json.loads(raw))
    if manifest["identity"].get("code_sha") != args.expected_code_sha:
        raise Phase4AError("frozen Phase 4A code SHA does not match expectation")
    if manifest.get("production_activation_authorized") is not False:
        raise Phase4AError("frozen Phase 4A result authorizes production")
    frames: dict[str, pd.DataFrame] = {}
    expected = {
        "rating_states",
        "team_states",
        "fold_predictions",
        "attribution_coverage",
    }
    if set(manifest.get("output_refs") or ()) != expected:
        raise Phase4AError("frozen Phase 4A manifest has the wrong output set")
    for name, value in manifest["output_refs"].items():
        ref = _ref(value)
        frame = read_dataset(storage, ref)
        validate_frame(frame, schema_for(ref.dataset, ref.schema_version))
        frames[name] = frame
    states, teams, predictions, attribution = (
        frames["rating_states"],
        frames["team_states"],
        frames["fold_predictions"],
        frames["attribution_coverage"],
    )
    if any(
        frame["season"].astype(int).isin(FORBIDDEN_SEASONS).any()
        for frame in (states, teams, predictions)
    ):
        raise Phase4AError("frozen Phase 4A outputs contain 2020")
    if set(states["candidate"].astype(str)) != set(RATING_CANDIDATES) or set(
        predictions["candidate"].astype(str)
    ) != set(RATING_CANDIDATES):
        raise Phase4AError("frozen Phase 4A artifacts lack the complete candidate grid")
    if (
        not np.isfinite(
            states[["posterior_variance", "posterior_sd"]].to_numpy(dtype=float)
        ).all()
        or (states["posterior_variance"] <= 0).any()
    ):
        raise Phase4AError("frozen Phase 4A uncertainty is invalid")
    if not np.allclose(
        teams["overall_rating"], (teams["offense_rating"] + teams["defense_rating"]) / 2
    ):
        raise Phase4AError("frozen Phase 4A overall rating is not role-composed")
    selected = attribution[attribution["selected"].astype(bool)]
    if (
        len(selected) != 1
        or selected.iloc[0]["candidate"] != manifest["selected_candidate"]
    ):
        raise Phase4AError("frozen Phase 4A selection disagrees with attribution")
    for row in (
        predictions[["season", "training_seasons"]]
        .drop_duplicates()
        .itertuples(index=False)
    ):
        if any(
            int(value) >= int(row.season) for value in json.loads(row.training_seasons)
        ):
            raise Phase4AError("frozen Phase 4A fold uses future training data")
    print(
        json.dumps(
            {
                "status": "verified",
                "manifest_uri": args.manifest_uri,
                "manifest_raw_sha256": hashlib.sha256(raw).hexdigest(),
                "selected_candidate": manifest["selected_candidate"],
                "output_rows": {name: len(frame) for name, frame in frames.items()},
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
