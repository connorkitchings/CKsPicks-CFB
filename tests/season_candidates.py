"""Sealed season release candidates that pass the REAL verification.

A candidate is the byte triple ``runner.prepare`` hands to staging (run manifest,
``season_verification_v2`` report, serving-projection payload), chained by
checksums exactly as the runner writes them. The payload is
``test_season_verification.synthetic_payload`` for the candidate's own run id, so
``verification.derive_checks`` / ``validate_report`` pass on it unmodified.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable

from cks_picks_cfb.season import verification as v
from cks_picks_cfb.season.manifest import canonical, sha
from tests.test_season_verification import (
    IDENTITY,
    OUTPUT_REFS,
    PASSING_PREPARE,
    synthetic_payload,
)

#: The owner policy every candidate identity satisfies.
POLICY = {
    "model_manifest_sha256": IDENTITY["model_manifest_sha256"],
    "workflow_version": IDENTITY["workflow_version"],
    "grading_policy_sha256": IDENTITY["grading_policy_sha256"],
}


def identity_for(label: str) -> dict:
    """A run identity per label: same model/policy, distinct config (and run id)."""
    return {**IDENTITY, "config_sha": sha(label.encode())}


def run_id(label: str) -> str:
    return v.run_id_for(identity_for(label))


def payload_for(label: str) -> dict[str, list[dict]]:
    """The consistent synthetic payload of ``label``'s run."""
    identity = identity_for(label)
    lineage = v.lineage_identities(identity, OUTPUT_REFS)
    return synthetic_payload(run_id(label), lineage["rating"], lineage["measurement"])


def rename_venue(payload: dict) -> None:
    """A content change every check still accepts (same identity, other bytes)."""
    for row in payload["game_venues"]:
        row["city"] = "Elsewhere"


def seal(
    label: str,
    payload: dict,
    *,
    reported_payload: dict | None = None,
    edit_report: Callable[[dict], None] | None = None,
) -> dict[str, bytes]:
    """Manifest/report/payload bytes for ``payload`` under ``label``'s identity.

    The report is computed by ``verification.assemble_report`` from
    ``reported_payload`` (default: ``payload`` itself), then ``edit_report`` may
    forge it; the manifest binds the exact payload bytes and report bytes.
    """
    identity = identity_for(label)
    release_id = v.run_id_for(identity)
    projection_raw = canonical(payload)
    refs = {
        **OUTPUT_REFS,
        "serving_projections": {
            "uri": f"/prepared/{release_id}/serving-projections.json",
            "logical_uri": f"season-run:{release_id}/serving-projections.json",
            "sha256": sha(projection_raw),
            "rows": sum(map(len, payload.values())),
        },
    }
    context = {"identity": identity, "output_refs": refs}
    report = v.assemble_report(
        copy.deepcopy(reported_payload or payload),
        context,
        copy.deepcopy(PASSING_PREPARE),
    )
    if edit_report:
        edit_report(report)
    verification_raw = canonical(report)
    manifest = {
        "schema_version": "season_run_v1",
        "release_id": release_id,
        **identity,
        "identity": identity,
        "identities": v.lineage_identities(identity, refs),
        "state": "prepared",
        "verification_uri": f"/prepared/{release_id}/verification.json",
        "verification_logical_uri": f"season-run:{release_id}/verification.json",
        "verification_sha256": sha(verification_raw),
        "run_manifest_logical_uri": f"season-run:{release_id}/run-manifest.json",
        "output_refs": refs,
    }
    return {
        "manifest_raw": canonical(manifest),
        "verification_raw": verification_raw,
        "projection_raw": projection_raw,
    }


def candidate(
    label: str = "r1",
    *,
    edit_payload: Callable[[dict], None] | None = None,
    **kwargs,
) -> dict[str, bytes]:
    """A sealed candidate of ``label``; ``edit_payload`` changes it before sealing."""
    payload = payload_for(label)
    if edit_payload:
        edit_payload(payload)
    return seal(label, payload, **kwargs)


def manifest_uri(sealed: dict[str, bytes]) -> str:
    """The logical run-manifest URI staging must record for ``sealed``."""
    return json.loads(sealed["manifest_raw"])["run_manifest_logical_uri"]
