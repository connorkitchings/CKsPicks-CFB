#!/usr/bin/env python3
"""Independently validate the sealed V5-03 rating parent and retained manifest."""

from __future__ import annotations

import argparse
import hashlib
import json

from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload
from cks_picks_cfb.data.data_first_possession_rating_v1 import (
    POSSESSION_RATING_MANIFEST_SCHEMA,
    candidate_registry,
)
from cks_picks_cfb.data.storage import get_storage


class PossessionRatingVerificationError(ValueError):
    """Raised when a retained V5-03 artifact cannot be independently trusted."""


def verify_manifest(
    payload: dict[str, object], *, expected_code_sha: str
) -> dict[str, object]:
    if payload.get("schema_version") != POSSESSION_RATING_MANIFEST_SCHEMA:
        raise PossessionRatingVerificationError("unexpected retained rating schema")
    verify_signed_payload(payload, label="retained possession rating manifest")
    if (
        payload.get("state") != "frozen"
        or payload.get("production_activation_authorized") is not False
    ):
        raise PossessionRatingVerificationError(
            "retained rating violates research boundary"
        )
    identity = payload.get("identity") or {}
    if (
        identity.get("code_sha") != expected_code_sha
        or identity.get("environment") != "preview"
    ):
        raise PossessionRatingVerificationError(
            "retained rating code or environment mismatch"
        )
    if payload.get("selected_candidate") not in {
        item["candidate_id"] for item in candidate_registry()
    }:
        raise PossessionRatingVerificationError("unsealed selected candidate")
    required = {
        "rating_registry",
        "priors",
        "noise_fits",
        "rating_states",
        "team_states",
        "bridge_predictions",
        "attribution",
    }
    if set((payload.get("output_refs") or {})) != required:
        raise PossessionRatingVerificationError(
            "retained rating lacks complete output evidence"
        )
    return payload


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-uri", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--environment", choices=("preview",), required=True)
    args = parser.parse_args(argv)
    storage = get_storage(environment="preview")
    raw = storage.read_bytes(args.manifest_uri)
    verified = verify_manifest(
        json.loads(raw), expected_code_sha=args.expected_code_sha
    )
    print(
        json.dumps(
            {
                "status": "verified",
                "manifest_uri": args.manifest_uri,
                "manifest_raw_sha256": hashlib.sha256(raw).hexdigest(),
                "selected_candidate": verified["selected_candidate"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
