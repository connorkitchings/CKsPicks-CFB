#!/usr/bin/env python3
"""Materialize the run-scoped successor-v2 R1 measurement/state foundation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from cks_picks_cfb.data.lake import DatasetRef
from cks_picks_cfb.data.season_lineage import load_season_lineage_policy
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ratings.contracts import load_measurement_config
from cks_picks_cfb.ratings.state_contracts import load_team_state_config
from cks_picks_cfb.ratings.successor_history import (
    DERIVED_REF_SET_VERSION,
    R1_REQUIRED_DATASETS,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _immutable_write(storage, uri: str, payload: bytes) -> None:
    if storage.exists(uri):
        if storage.read_bytes(uri) != payload:
            raise FileExistsError(f"Immutable successor-v2 artifact collision: {uri}")
        return
    storage.write_bytes(payload, uri)


def _ref(value: dict) -> DatasetRef:
    return DatasetRef(**value)


def _pointer(storage, uri: str, ref: DatasetRef) -> None:
    _immutable_write(storage, uri, json.dumps(asdict(ref), sort_keys=True).encode())


def _run(argv: list[str]) -> None:
    result = subprocess.run(
        argv,
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": ".:src"},
        check=False,
    )
    if result.returncode:
        raise subprocess.CalledProcessError(result.returncode, argv)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", choices=("preview", "production"), required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--derived-ref-set-uri", required=True)
    parser.add_argument("--output-manifest-uri", required=True)
    parser.add_argument(
        "--measurement-config",
        default="conf/ratings/measurement_successor_v2.yaml",
    )
    parser.add_argument(
        "--state-config", default="conf/ratings/team_state_successor_v2.yaml"
    )
    args = parser.parse_args(argv)
    if args.environment != "preview":
        raise ValueError("Successor-v2 R1 foundation is Preview-only")
    policy = load_season_lineage_policy("conf/ratings/successor_v2_season_lineage.yaml")
    if not args.output_manifest_uri.startswith(f"{policy.research_prefix}/"):
        raise ValueError("R1 foundation output must use the isolated research prefix")
    storage = get_storage(environment="preview")
    derived_bytes = storage.read_bytes(args.derived_ref_set_uri)
    derived = json.loads(derived_bytes.decode())
    if (
        derived.get("contract_version") != DERIVED_REF_SET_VERSION
        or derived.get("state") != "complete"
        or derived.get("season_lineage_policy_version") != policy.version
    ):
        raise ValueError("R1 foundation requires a complete exact derived-ref set")
    identity = derived.get("identity")
    if not isinstance(identity, dict) or not identity.get("code_sha"):
        raise ValueError("R1 derived-ref set is missing its committed code identity")
    current = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True
    ).stdout.strip()
    if current != identity["code_sha"]:
        raise ValueError("R1 foundation code SHA differs from the capture identity")
    refs = {
        (int(entry["season"]), str(entry["dataset"])): _ref(entry)
        for entry in derived.get("entries", [])
    }
    expected = {
        (season, dataset)
        for season in policy.historical_development_seasons
        for dataset in R1_REQUIRED_DATASETS
    }
    if set(refs) != expected:
        raise ValueError("R1 foundation derived refs are incomplete or out of scope")
    root = args.derived_ref_set_uri.rsplit("/", 1)[0]
    input_root = f"{root}/foundation/input-refs"
    pointers: dict[tuple[int, str], str] = {}
    for key, ref in refs.items():
        season, dataset = key
        uri = f"{input_root}/{season}/{dataset}.json"
        _pointer(storage, uri, ref)
        pointers[key] = uri
    measurement = load_measurement_config(args.measurement_config)
    states = load_team_state_config(args.state_config)
    measurement_prefix = f"{root}/foundation/measurements/{measurement.design_id}"
    state_prefix = f"{root}/foundation/states/{states.design_id}"
    measurement_refs = {
        "observations": f"{measurement_prefix}/observations-ref.json",
        "snapshots": f"{measurement_prefix}/snapshots-ref.json",
        "terminal": f"{measurement_prefix}/terminal-snapshots-ref.json",
        "report": f"{measurement_prefix}/report.json",
    }
    measurement_argv = [
        sys.executable,
        "scripts/pipeline/build_rating_measurements.py",
        "--environment",
        "preview",
        "--measurement-config",
        args.measurement_config,
        "--output-prefix",
        measurement_prefix,
        "--as-of",
        args.as_of,
        "--expected-code-sha",
        str(identity["code_sha"]),
        "--observations-ref-uri",
        measurement_refs["observations"],
        "--snapshots-ref-uri",
        measurement_refs["snapshots"],
        "--terminal-snapshots-ref-uri",
        measurement_refs["terminal"],
        "--report-uri",
        measurement_refs["report"],
    ]
    for season in policy.historical_development_seasons:
        for option, dataset in (
            ("--byplay-ref-uri", "byplay"),
            ("--drives-ref-uri", "drives"),
            ("--games-ref-uri", "games"),
            ("--outcomes-ref-uri", "game_outcomes"),
            ("--team-game-ref-uri", "reconciled_team_game"),
        ):
            measurement_argv.extend([option, pointers[(season, dataset)]])
    _run(measurement_argv)
    state_refs = {
        "measurement": f"{state_prefix}/measurement-states-ref.json",
        "team": f"{state_prefix}/team-states-ref.json",
        "report": f"{state_prefix}/report.json",
    }
    _run(
        [
            sys.executable,
            "scripts/pipeline/build_rating_team_states.py",
            "--environment",
            "preview",
            "--state-config",
            args.state_config,
            "--output-prefix",
            state_prefix,
            "--as-of",
            args.as_of,
            "--expected-code-sha",
            str(identity["code_sha"]),
            "--observations-ref-uri",
            measurement_refs["observations"],
            "--snapshots-ref-uri",
            measurement_refs["snapshots"],
            "--terminal-snapshots-ref-uri",
            measurement_refs["terminal"],
            "--phase1-report-uri",
            measurement_refs["report"],
            "--measurement-states-ref-uri",
            state_refs["measurement"],
            "--team-states-ref-uri",
            state_refs["team"],
            "--report-uri",
            state_refs["report"],
        ]
    )
    manifest = {
        "contract_version": "successor-r1-foundation-v2",
        "state": "complete",
        "derived_ref_set_uri": args.derived_ref_set_uri,
        "derived_ref_set_sha256": _sha256(derived_bytes),
        "identity": identity,
        "measurement": {"design_id": measurement.design_id, **measurement_refs},
        "states": {"design_id": states.design_id, **state_refs},
    }
    manifest["manifest_sha256"] = _sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    )
    _immutable_write(
        storage,
        args.output_manifest_uri,
        json.dumps(manifest, indent=2, sort_keys=True).encode(),
    )
    print(json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
