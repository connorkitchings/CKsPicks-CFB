#!/usr/bin/env python3
"""Build the signed authorization / selection / rollback packets from a reviewed spec.

The spec is JSON: ``environment``, ``cutover_week``, ``decision_ref``, ``runs`` (week ->
run id), and for selection ``expected_current_runs``, ``protected_runs``,
``certifications`` and ``payload_refs``; rollback also needs ``prior_runs``. The tool
only reads storage and writes the packet file; applying a packet stays with the
user-run authorizer and selection scripts.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from cks_picks_cfb.artifacts import prediction_run_manifest_path
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ops import v5_packet_builder as builder
from cks_picks_cfb.ratings_lab.artifacts import canonical_json


def _manifests(storage, runs: dict) -> dict[int, dict]:
    return {
        int(week): json.loads(
            storage.read_bytes(prediction_run_manifest_path(2026, int(week), run_id))
        )
        for week, run_id in runs.items()
    }


def _int_keys(mapping: dict) -> dict[int, str]:
    return {int(week): run for week, run in mapping.items()}


def build(kind: str, spec: dict, storage) -> dict:
    common = dict(
        environment=spec["environment"],
        cutover_week=spec["cutover_week"],
        decision_ref=spec["decision_ref"],
    )
    manifests = _manifests(storage, spec["runs"])
    if kind == "authorization":
        return builder.build_authorization_packet(manifests, **common)
    selection = builder.build_selection_packet(
        manifests,
        expected_current_runs=_int_keys(spec["expected_current_runs"]),
        protected_runs=_int_keys(spec["protected_runs"]),
        certifications=spec["certifications"],
        payload_refs=spec["payload_refs"],
        **common,
    )
    if kind == "selection":
        return selection
    rollback = spec["rollback"]
    return builder.build_rollback_packet(
        selection,
        prior_manifests=_manifests(storage, spec["expected_current_runs"]),
        certifications=rollback["certifications"],
        payload_refs=rollback["payload_refs"],
    )


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("authorization", "selection", "rollback"))
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text())
    if os.getenv("CFB_ARTIFACT_ENV") != spec["environment"]:
        raise SystemExit("CFB_ARTIFACT_ENV must match the spec environment")
    storage = get_storage(environment=spec["environment"])
    packet = build(args.kind, spec, storage)
    raw = canonical_json(packet)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("xb") as handle:
        handle.write(raw)
    import hashlib

    print(
        json.dumps(
            {
                "kind": args.kind,
                "packet_sha256": hashlib.sha256(raw).hexdigest(),
                "out": str(args.out),
            }
        )
    )


if __name__ == "__main__":
    main()
